"""Informe opt-in: contenido anonimo, limpieza de datos personales y nada se envia sin que el usuario lo decida."""

import json

import pytest

from fake_adb import FakeAdb
from tests_helpers import run_flow
from tvlite import cli, device, telemetry


def test_disabled_by_default_so_nothing_is_offered(monkeypatch):
    monkeypatch.delenv("TVLITE_REPORT_URL", raising=False)
    monkeypatch.setattr(telemetry, "DEFAULT_REPORT_URL", "")
    assert not telemetry.enabled()


@pytest.mark.parametrize("raw,leaked", [
    ("fallo conectando con 192.168.1.50:5555", "192.168.1.50"),
    ("mac aa:bb:cc:dd:ee:ff", "aa:bb:cc:dd:ee:ff"),
    ("File C:\\Users\\MariaGarcia\\AppData\\x.py", "MariaGarcia"),
    ("File /home/pedro/.tvlite/x.py", "pedro"),
    ("File /Users/lucia/x.py", "lucia"),
    ("serial 0123456789ABCDEF0123", "0123456789ABCDEF0123"),
])
def test_scrub_removes_personal_data(raw, leaked):
    assert leaked not in telemetry.scrub(raw)


def test_scrub_removes_the_current_os_username(monkeypatch):
    monkeypatch.setattr(telemetry.getpass, "getuser", lambda: "usuarioraro")
    assert "usuarioraro" not in telemetry.scrub("ruta D:\\datos\\usuarioraro\\x")


def test_event_for_a_successful_run_has_what_maintainers_need_and_no_personal_data(tmp_path, apk):
    messages, summary = run_flow({}, tmp_path, apk)
    adb = FakeAdb()
    adb.serial = "SERIE-PRIVADA-123456"
    info = device.detect(adb, serial=adb.serial)
    event = telemetry.build_event(info, summary)
    text = telemetry.preview(event)
    assert event["kind"] in ("success", "partial") and event["schema"] == 1
    assert event["tv"]["model"] == "Smart TV" and event["tv"]["soc"] == "mt5867" and event["tv"]["ram_mb"] == 918
    assert event["pc"]["os"] and event["tvlite"]
    assert event["result"]["removed_count"] >= 1 and event["metrics"]["before"] and event["metrics"]["after"]
    for forbidden in ("SERIE-PRIVADA", "192.168", "serial"):
        assert forbidden not in text
    assert json.loads(text) == event  # lo que se previsualiza es exactamente lo que se envia


def test_failure_event_carries_the_error_scrubbed(tmp_path, apk):
    _, summary = run_flow({"lite_broken": True, "stubborn_launcher": True}, tmp_path, apk)
    summary.error = "Se perdio la conexion con 192.168.1.50:5555 en C:\\Users\\Ana\\x"
    event = telemetry.build_event(device.detect(FakeAdb()), summary)
    assert event["kind"] == "failure"
    assert "192.168" not in event["error"] and "Ana" not in event["error"] and "<ip>" in event["error"]


def test_unexpected_exception_goes_into_the_event_with_its_traceback():
    try:
        raise ValueError("algo raro en C:\\Users\\Ana\\proyecto 10.0.0.5")
    except ValueError as exc:
        event = telemetry.build_event(device.detect(FakeAdb()), None, exc=exc)
    assert event["kind"] == "failure" and "ValueError" in event["error"] and "Traceback" in event["error"]
    assert "Ana" not in event["error"] and "10.0.0.5" not in event["error"]


def test_classification(tmp_path, apk):
    _, ok = run_flow({}, tmp_path / "a", apk)
    assert telemetry.classify(ok) == "success"
    _, partial = run_flow({"play_installs": False}, tmp_path / "b", apk, apps=["nordvpn"])
    assert telemetry.classify(partial) == "partial"
    _, broken = run_flow({"unhealthy_after_uninstalls": 2}, tmp_path / "c", apk)
    assert telemetry.classify(broken) == "failure"


def test_event_never_lists_user_apps_beyond_the_catalog(tmp_path, apk):
    adb_kwargs = {}
    messages, summary = run_flow(adb_kwargs, tmp_path, apk)
    event = telemetry.build_event(device.detect(FakeAdb()), summary)
    assert all(pkg.startswith(("com.tcl.", "com.google.", "com.android.")) for pkg in event["result"]["removed"])


def test_send_never_raises_and_reports_failure(monkeypatch):
    def boom(*a, **k):
        raise OSError("sin red")

    monkeypatch.setattr(telemetry.urllib.request, "urlopen", boom)
    ok, detail = telemetry.send({"schema": 1}, url="https://relay.example/x")
    assert not ok and "sin red" in detail
    assert telemetry.send({"schema": 1}, url="") == (False, "no hay relé configurado")


def test_send_posts_json_with_a_tvlite_user_agent(monkeypatch):
    seen = {}

    class Resp:
        status = 204
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(request, timeout=0):
        seen["url"], seen["data"], seen["ua"] = request.full_url, request.data, request.headers.get("User-agent")
        return Resp()

    monkeypatch.setattr(telemetry.urllib.request, "urlopen", fake_urlopen)
    ok, _ = telemetry.send({"schema": 1, "kind": "success"}, url="https://relay.example/x")
    assert ok and seen["ua"].startswith("tvlite/") and json.loads(seen["data"])["kind"] == "success"


# ---- CLI: nunca se envia sin consentimiento
class SendSpy:
    def __init__(self):
        self.calls = []

    def __call__(self, event, *a, **k):
        self.calls.append(event)
        return True, "HTTP 204"


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv("TVLITE_REPORT_URL", "https://relay.example/x")
    spy = SendSpy()
    monkeypatch.setattr(telemetry, "send", spy)
    return spy


def _summary(tmp_path, apk):
    return run_flow({}, tmp_path, apk)[1]


def test_cli_asks_and_does_not_send_if_the_user_declines(enabled, tmp_path, apk, capsys):
    cli.offer_report(device.detect(FakeAdb()), _summary(tmp_path, apk), send_flag=False, ask=lambda prompt: "n")
    assert enabled.calls == []
    assert '"schema": 1' in capsys.readouterr().out  # se enseno el contenido exacto antes de preguntar


def test_cli_sends_only_after_the_user_confirms(enabled, tmp_path, apk):
    cli.offer_report(device.detect(FakeAdb()), _summary(tmp_path, apk), send_flag=False, ask=lambda prompt: "s")
    assert len(enabled.calls) == 1


def test_cli_send_report_flag_is_an_explicit_consent(enabled, tmp_path, apk):
    cli.offer_report(device.detect(FakeAdb()), _summary(tmp_path, apk), send_flag=True, ask=lambda p: pytest.fail("no debe preguntar"))
    assert len(enabled.calls) == 1


def test_cli_offers_nothing_when_no_relay_is_configured(monkeypatch, tmp_path, apk, capsys):
    monkeypatch.delenv("TVLITE_REPORT_URL", raising=False)
    monkeypatch.setattr(telemetry, "DEFAULT_REPORT_URL", "")
    cli.offer_report(device.detect(FakeAdb()), _summary(tmp_path, apk), send_flag=True, ask=lambda p: "s")
    assert capsys.readouterr().out == ""


def test_yes_flag_alone_never_sends(enabled):
    parser = cli.build_parser()
    args = parser.parse_args(["apply", "192.168.1.50", "--yes"])
    assert args.yes and not args.send_report  # --yes no equivale a aceptar el envio
