#!/usr/bin/env python3
"""Relé de informes de tvlite -> Telegram, version para TU PROPIO servidor (sin Cloudflare). Solo libreria estandar.

Por que hace falta un relé: el token del bot NO puede ir dentro del programa que se reparte a los usuarios (cualquiera
lo extraeria y controlaria el bot). El programa envia el informe anonimo a este relé y solo el relé conoce el token,
que vive en un archivo .env que solo existe en tu servidor y que NO se sube al repositorio.

    cp .env.example .env      # y rellena TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID
    python server.py          # escucha en HOST:PORT (por defecto 0.0.0.0:8787)

Ponlo detras de HTTPS (Caddy, nginx o un tunel) y pon esa URL en DEFAULT_REPORT_URL de installer/tvlite/telemetry.py.
Hace lo mismo que worker.js (que debe dar el mismo texto: hay una prueba de paridad):
- solo POST, user agent tvlite/*, JSON <= 12 KB con el esquema validado;
- construye el mensaje él mismo (el cliente no puede mandar texto libre al bot) y lo envia como texto plano;
- limita el ritmo por IP (guardada solo como hash y en memoria)."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MAX_BYTES = 12000
DISCARD_MAX_BYTES = 1 << 20  # tope de lo que se lee y descarta al rechazar; mas grande: se corta la conexion
MAX_TEXT = 3900  # Telegram admite 4096
RATE_LIMIT_PER_HOUR = 30
KINDS = {"success", "partial", "failure"}


def load_env(path: Path) -> None:
    """Lee KEY=VALUE de un .env sin pisar variables ya definidas en el entorno."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _str(value, limit: int = 120) -> str:
    return value[:limit] if isinstance(value, str) else ""


def _num(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _show(value) -> str:
    """Numeros como los imprime JavaScript: 3, no 3.0; y 'null' si no hay valor."""
    if value is None:
        return "null"
    return str(int(value)) if float(value).is_integer() else str(value)


def _or_q(value) -> str:
    return "?" if value is None else _show(value)


def valid(ev) -> bool:
    return (
        isinstance(ev, dict) and ev.get("schema") == 1 and ev.get("kind") in KINDS
        and isinstance(ev.get("tvlite"), str) and isinstance(ev.get("tv"), dict) and isinstance(ev.get("pc"), dict)
    )


def format_message(ev: dict) -> str:
    """Mismo texto que format() de worker.js."""
    icon = {"success": "✅", "partial": "⚠️", "failure": "❌"}[ev["kind"]]
    label = {"success": "OK", "partial": "PARCIAL", "failure": "FALLO"}[ev["kind"]]
    tv, pc = ev.get("tv") or {}, ev.get("pc") or {}
    name = " ".join(p for p in (_str(tv.get("manufacturer") or tv.get("brand")), _str(tv.get("model"))) if p) or "tele desconocida"
    abis = ",".join(_str(a, 20) for a in tv["abis"]) if isinstance(tv.get("abis"), list) else ""
    lines = [
        f"{icon} tvlite {label} - {name}{' (SIMULADA)' if tv.get('simulated') else ''}",
        f"Android {_str(tv.get('android'), 20)} (API {_or_q(_num(tv.get('sdk')))}) | SoC {_str(tv.get('soc'), 40) or '?'} | ABI {abis or '?'}",
        f"RAM {_or_q(_num(tv.get('ram_mb')))} MB ({_str(tv.get('profile'), 20)}) | libre {_or_q(_num(tv.get('storage_free_mb')))} MB | "
        f"{_str(tv.get('resolution'), 20)} | Play Store: {'NO' if tv.get('play_store') is False else 'si'}",
        f"PC: {_str(pc.get('os'), 20)} {_str(pc.get('release'), 20)} {_str(pc.get('arch'), 20)}"
        f"{' (ejecutable)' if pc.get('frozen') else ''} | tvlite {_str(ev.get('tvlite'), 20)}",
    ]
    r = ev.get("result")
    if isinstance(r, dict):
        apps = ""
        if isinstance(r.get("apps"), dict):
            apps = " ".join(f"{_str(k, 30)}:{'ok' if v == 'ok' else 'FALLO'}" for k, v in list(r["apps"].items())[:30])
        failed = r.get("failed") if isinstance(r.get("failed"), list) else []
        lines.append(
            f"Quitados {_show(_num(r.get('removed_count')) or 0)}{' (simulacion)' if r.get('dry_run') else ''} | fallos {len(failed)}"
            f" | revertidos {_show(_num(r.get('rolled_back')) or 0)}{' | ABORTADO' if r.get('aborted') else ''}"
        )
        lines.append(f"Launcher: {_str(r.get('launcher'), 160)}{' | Apps: ' + apps if apps else ''}")
        if failed:
            lines.append("No se pudo quitar: " + "; ".join(
                f"{_str(f.get('pkg') if isinstance(f, dict) else None, 80)} ({_str(f.get('why') if isinstance(f, dict) else None, 60)})"
                for f in failed[:8]
            ))
    m = ev.get("metrics")
    if isinstance(m, dict) and m.get("before") and m.get("after"):
        b, a = m["before"], m["after"]
        lines.append(
            f"RAM disponible {_show(_num(b.get('ram_available_mb')))} -> {_show(_num(a.get('ram_available_mb')))} MB | "
            f"paquetes {_show(_num(b.get('packages')))} -> {_show(_num(a.get('packages')))}"
        )
    error = _str(ev.get("error"), 1600)
    if error:
        lines += ["", "Error:", error]
    return "\n".join(lines)[:MAX_TEXT]


class RateLimiter:
    """Cuenta envios por hora y por IP. La IP solo se guarda como hash y en memoria."""

    def __init__(self, limit: int = RATE_LIMIT_PER_HOUR, clock=time.time) -> None:
        self.limit, self._clock, self._counts, self._lock = limit, clock, {}, threading.Lock()

    def hit(self, ip: str) -> bool:
        """True si este envio esta permitido."""
        hour = int(self._clock() // 3600)
        key = hashlib.sha256(ip.encode()).hexdigest()[:24]
        with self._lock:
            self._counts = {k: v for k, v in self._counts.items() if v[0] == hour}
            _, count = self._counts.get(key, (hour, 0))
            if count >= self.limit:
                return False
            self._counts[key] = (hour, count + 1)
            return True


def send_telegram(text: str, token: str, chat_id: str, timeout: float = 15.0) -> bool:
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=json.dumps({"chat_id": chat_id, "text": text, "disable_web_page_preview": True}).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (API fija de Telegram)
            return 200 <= response.status < 300
    except Exception:  # noqa: BLE001 - no se devuelve el motivo al cliente
        return False


def make_handler(token: str, chat_id: str, limiter: RateLimiter, sender=send_telegram, trust_proxy: bool = False):
    class Handler(BaseHTTPRequestHandler):
        server_version = "tvlite-relay"

        def _reply(self, status: int) -> None:
            self.send_response(status)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _discard_body(self) -> None:
            """Lee y descarta el cuerpo (con tope) antes de rechazar: si se cierra con datos sin leer, Windows envia
            un RST y el cliente puede perder la respuesta (WinError 10053) en vez de ver el 403/413."""
            try:
                left = min(int(self.headers.get("Content-Length", "0")), DISCARD_MAX_BYTES)
            except ValueError:
                return
            while left > 0:
                chunk = self.rfile.read(min(left, 65536))
                if not chunk:
                    return
                left -= len(chunk)

        def _ip(self) -> str:
            if trust_proxy and self.headers.get("X-Forwarded-For"):
                return self.headers["X-Forwarded-For"].split(",")[0].strip()
            return self.client_address[0]

        def do_POST(self) -> None:  # noqa: N802 (nombre fijado por http.server)
            if not (self.headers.get("User-Agent") or "").startswith("tvlite/"):
                self._discard_body()
                return self._reply(403)
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self._reply(400)
            if length > MAX_BYTES:
                self._discard_body()
                return self._reply(413)
            try:
                event = json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return self._reply(400)
            if not valid(event):
                return self._reply(400)
            if not limiter.hit(self._ip()):
                return self._reply(429)
            self._reply(204 if sender(format_message(event), token, chat_id) else 502)

        def _not_allowed(self) -> None:
            self._reply(405)

        do_GET = do_PUT = do_DELETE = do_PATCH = _not_allowed  # noqa: N815

        def log_message(self, fmt, *args) -> None:  # no se registran IP ni contenido
            return

    return Handler


def main() -> int:
    load_env(Path(__file__).resolve().parent / ".env")
    token, chat_id = os.environ.get("TELEGRAM_BOT_TOKEN", ""), os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("Faltan TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID (en el entorno o en tools/telemetry-relay/.env)", file=sys.stderr)
        return 1
    host, port = os.environ.get("HOST", "0.0.0.0"), int(os.environ.get("PORT", "8787"))  # noqa: S104
    handler = make_handler(token, chat_id, RateLimiter(), trust_proxy=os.environ.get("TRUST_PROXY") == "1")
    print(f"Relé escuchando en http://{host}:{port} (ponlo detras de HTTPS)")
    ThreadingHTTPServer((host, port), handler).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
