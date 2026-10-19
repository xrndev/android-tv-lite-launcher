"""Relé en Python (tools/telemetry-relay/server.py): validacion, limite, y paridad exacta con worker.js."""

import importlib.util
import json
import shutil
import subprocess
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib import request as urlrequest
from urllib.error import HTTPError

import pytest

from fake_adb import FakeAdb
from tests_helpers import run_flow
from tvlite import device, telemetry

RELAY_DIR = Path(__file__).resolve().parents[2] / "tools" / "telemetry-relay"
spec = importlib.util.spec_from_file_location("relay_server", RELAY_DIR / "server.py")
relay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(relay)


def sample_events(tmp_path, apk):
    info = device.detect(FakeAdb())
    events = {}
    _, ok = run_flow({}, tmp_path / "a", apk)
    events["success"] = telemetry.build_event(info, ok)
    _, bad = run_flow({"unhealthy_after_uninstalls": 2}, tmp_path / "b", apk)
    events["failure"] = telemetry.build_event(info, bad)
    _, part = run_flow({"play_installs": False}, tmp_path / "c", apk, apps=["nordvpn"])
    events["partial"] = telemetry.build_event(info, part)
    try:
        raise RuntimeError("fallo raro 10.1.2.3")
    except RuntimeError as exc:
        events["exception"] = telemetry.build_event(info, None, exc=exc)
    events["minimal"] = {"schema": 1, "tvlite": "0.1.0", "kind": "success", "pc": {"os": "x"}, "tv": {"model": "m"}}
    return events


@pytest.fixture
def server():
    sent = []
    limiter = relay.RateLimiter(limit=3)
    handler = relay.make_handler("TOKEN", "42", limiter, sender=lambda text, token, chat: sent.append((text, token, chat)) or True)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/", sent
    httpd.shutdown()


def post(url, body, ua="tvlite/0.1.0", method="POST"):
    data = body if isinstance(body, bytes) else json.dumps(body).encode()
    req = urlrequest.Request(url, data=data if method == "POST" else None, method=method, headers={"User-Agent": ua})
    try:
        with urlrequest.urlopen(req, timeout=10) as resp:
            return resp.status
    except HTTPError as exc:
        return exc.code


def test_valid_event_is_forwarded_as_plain_text_with_the_secret_chat(server, tmp_path, apk):
    url, sent = server
    assert post(url, sample_events(tmp_path, apk)["success"]) == 204
    text, token, chat = sent[0]
    assert (token, chat) == ("TOKEN", "42") and "tvlite OK" in text


@pytest.mark.parametrize("what,expected", [
    (("GET", b""), 405), (("POST-ua", b"{}"), 403), (("POST", b"{no json"), 400),
    (("POST", json.dumps({"schema": 2, "kind": "x"}).encode()), 400),
    (("POST", json.dumps({"schema": 1, "kind": "hack", "tvlite": "x", "tv": {}, "pc": {}}).encode()), 400),
    (("POST", b"x" * 13000), 413),
])
def test_invalid_requests_are_rejected(server, what, expected):
    url, sent = server
    kind, body = what
    if kind == "GET":
        assert post(url, body, method="GET") == expected
    elif kind == "POST-ua":
        assert post(url, body, ua="curl/8") == expected
    else:
        assert post(url, body) == expected
    assert sent == []  # nada de lo rechazado llega a Telegram


def test_oversized_bodies_always_get_their_413_not_a_connection_reset(server):
    """El rele lee y descarta el cuerpo antes de rechazar; si no, Windows a veces resetea la conexion (WinError 10053)."""
    url, sent = server
    assert [post(url, b"x" * 400_000) for _ in range(40)] == [413] * 40
    assert sent == []


def test_rate_limit_returns_429(server, tmp_path, apk):
    url, sent = server
    event = sample_events(tmp_path, apk)["minimal"]
    assert [post(url, event) for _ in range(5)] == [204, 204, 204, 429, 429]


def test_rate_limiter_forgets_the_previous_hour_and_stores_no_plain_ip():
    now = [3600 * 10.0]
    limiter = relay.RateLimiter(limit=1, clock=lambda: now[0])
    assert limiter.hit("1.2.3.4") and not limiter.hit("1.2.3.4")
    now[0] += 3600
    assert limiter.hit("1.2.3.4")
    assert "1.2.3.4" not in repr(limiter._counts)


def test_load_env_reads_key_values_without_overriding(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# comentario\nTELEGRAM_CHAT_ID=\"99\"\nTELEGRAM_BOT_TOKEN='abc'\nVACIA\n", encoding="utf-8")
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "del-entorno")
    relay.load_env(env)
    assert relay.os.environ["TELEGRAM_CHAT_ID"] == "99"
    assert relay.os.environ["TELEGRAM_BOT_TOKEN"] == "del-entorno"  # el entorno manda sobre el archivo


def test_the_env_file_is_ignored_by_git():
    gitignore = (Path(__file__).resolve().parents[2] / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in gitignore.split()


@pytest.mark.skipif(not shutil.which("node"), reason="Node no esta instalado")
def test_python_and_javascript_relays_produce_identical_messages(tmp_path, apk):
    events = sample_events(tmp_path, apk)
    shutil.copy(RELAY_DIR / "worker.js", tmp_path / "worker.mjs")
    (tmp_path / "events.json").write_text(json.dumps(events), encoding="utf-8")
    (tmp_path / "run.mjs").write_text(
        'import fs from "node:fs"; import { format } from "./worker.mjs";\n'
        'const ev = JSON.parse(fs.readFileSync(new URL("./events.json", import.meta.url)));\n'
        'console.log(JSON.stringify(Object.fromEntries(Object.entries(ev).map(([k, v]) => [k, format(v)]))));\n',
        encoding="utf-8",
    )
    out = subprocess.run(["node", "run.mjs"], cwd=tmp_path, capture_output=True, text=True, encoding="utf-8", check=True)
    js = json.loads(out.stdout)
    for name, event in events.items():
        assert relay.format_message(event) == js[name], f"el texto de '{name}' difiere entre server.py y worker.js"
