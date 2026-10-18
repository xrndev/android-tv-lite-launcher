"""Informe anonimo del resultado, que el USUARIO decide enviar (nunca se envia solo).

Principios:
- Opt-in explicito: el programa muestra EXACTAMENTE lo que se enviaria y solo lo manda si el usuario pulsa
  "Enviar". No hay envios automaticos, ni identificadores persistentes, ni IP del usuario en el contenido.
- Sin token en el cliente: se envia a un relé (tools/telemetry-relay) que es quien guarda el token del bot de
  Telegram. Si no hay relé configurado (URL vacia) la funcion queda inactiva y no se ofrece nada.
- Lo que se manda: modelo/Android/SoC/RAM de la tele, sistema operativo del PC, que paso bien o mal y el
  error (con IP, rutas con el nombre de usuario, MAC y numeros de serie sustituidos). NUNCA: apps del usuario,
  cuentas, nombre de la red ni numero de serie.
- Enviar nunca puede romper tvlite: timeout corto y cualquier fallo se ignora."""

from __future__ import annotations

import getpass
import json
import os
import platform
import re
import traceback
import urllib.request
from typing import Optional

from . import __version__

SCHEMA = 1
# URL del relé (se rellena cuando el mantenedor lo despliega). Vacia = funcion inactiva. TVLITE_REPORT_URL la sobrescribe.
DEFAULT_REPORT_URL = "https://tvlite-relay.telemetry-relay.workers.dev"
MAX_ERROR_CHARS = 1500
MAX_PACKAGES = 60

_SCRUB = [
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b"), "<ip>"),
    (re.compile(r"(?i)\b[0-9a-f]{2}(?::[0-9a-f]{2}){5}\b"), "<mac>"),
    # rutas de Windows, tambien con barras dobles (asi salen las lineas de codigo dentro de una traza)
    (re.compile(r"(?i)\b[a-z]:\\{1,2}users\\{1,2}[^\\\s\"']+"), "~"),
    (re.compile(r"(?i)\b[a-z]:/users/[^/\s\"']+"), "~"),
    (re.compile(r"/(?:home|Users)/[^/\s\"']+"), "~"),
    (re.compile(r"\b[0-9A-Fa-f]{12,}\b"), "<id>"),
]


def report_url() -> str:
    return os.environ.get("TVLITE_REPORT_URL", DEFAULT_REPORT_URL).strip()


def enabled() -> bool:
    """True solo si hay un relé configurado: si no, no se ofrece nada al usuario."""
    return bool(report_url())


def scrub(text: str) -> str:
    """Sustituye datos personales: IP, MAC, rutas con el usuario, numeros de serie largos y el propio nombre de usuario."""
    text = text or ""
    for rx, repl in _SCRUB:
        text = rx.sub(repl, text)
    try:
        user = getpass.getuser()
        if len(user) >= 3:
            text = re.sub(re.escape(user), "<user>", text, flags=re.I)
    except Exception:  # noqa: BLE001
        pass
    home = os.path.expanduser("~")
    if home and len(home) > 3:
        text = text.replace(home, "~")
    return text


def format_traceback(exc: BaseException) -> str:
    return scrub("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))[-MAX_ERROR_CHARS:]


def classify(summary) -> str:
    """'success' | 'partial' | 'failure' segun lo que paso en la ejecucion."""
    if summary is None:
        return "failure"
    if summary.error or (summary.debloat and summary.debloat.aborted):
        return "failure"
    if summary.launcher_error or any(not a.ok for a in summary.apps) or (summary.debloat and summary.debloat.failed):
        return "partial"
    return "success"


def build_event(info, summary=None, exc: Optional[BaseException] = None, kind: Optional[str] = None) -> dict:
    """Evento anonimo. 'info' es un DeviceInfo; 'summary' un runner.Summary; 'exc' una excepcion inesperada."""
    kind = kind or ("failure" if exc is not None else classify(summary))
    event: dict = {
        "schema": SCHEMA,
        "tvlite": __version__,
        "kind": kind,
        "pc": {
            "os": platform.system(), "release": platform.release(), "arch": platform.machine(),
            "frozen": bool(getattr(__import__("sys"), "frozen", False)),
        },
        "tv": {
            "manufacturer": info.manufacturer, "brand": info.brand, "model": info.model,
            "android": info.android_release, "sdk": info.sdk, "abis": info.abis, "soc": info.soc,
            "ram_mb": info.ram_mb, "profile": info.profile, "play_store": info.has_play_store,
            "storage_free_mb": info.storage_free_mb, "resolution": info.resolution, "density": info.density,
            "simulated": info.simulated,
        } if info is not None else {},
    }
    errors: list[str] = []
    if summary is not None:
        deb = summary.debloat
        removed = list(deb.done) if deb else []
        event["result"] = {
            "removed": removed[:MAX_PACKAGES], "removed_count": len(removed),
            "failed": [{"pkg": p, "why": scrub(w)[:200]} for p, w in (deb.failed if deb else [])][:MAX_PACKAGES],
            "rolled_back": len(deb.rolled_back) if deb else 0,
            "aborted": bool(deb and deb.aborted),
            "apps": {a.app_id: ("ok" if a.ok else scrub(a.detail)[:200]) for a in summary.apps},
            "launcher": "ok" if summary.launcher else (scrub(summary.launcher_error)[:200] or "skipped"),
            "dry_run": summary.dry_run,
        }
        event["metrics"] = {"before": summary.metrics_before, "after": summary.metrics_after}
        if summary.error:
            errors.append(summary.error)
        if summary.launcher_error:
            errors.append(summary.launcher_error)
        errors += [f"{a.app_id}: {a.detail}" for a in summary.apps if not a.ok and a.detail]
        if getattr(summary, "trace", ""):
            errors.append(summary.trace)
    if exc is not None:
        errors.append(format_traceback(exc))
    event["error"] = scrub("\n".join(e for e in errors if e))[-MAX_ERROR_CHARS:]
    return event


def preview(event: dict) -> str:
    """Texto EXACTO que se enviara (el JSON), para que el usuario lo revise antes de aceptar."""
    return json.dumps(event, indent=2, ensure_ascii=False)


def send(event: dict, url: Optional[str] = None, timeout: float = 8.0) -> tuple[bool, str]:
    """Envia el evento al relé. Nunca lanza: devuelve (ok, detalle)."""
    target = url or report_url()
    if not target:
        return False, "no hay relé configurado"
    try:
        request = urllib.request.Request(
            target,
            data=json.dumps(event, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": f"tvlite/{__version__}"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (URL del mantenedor)
            return 200 <= response.status < 300, f"HTTP {response.status}"
    except Exception as exc:  # noqa: BLE001 - enviar nunca debe romper tvlite
        return False, str(exc)[:200]
