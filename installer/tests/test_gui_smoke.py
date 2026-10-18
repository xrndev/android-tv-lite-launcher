"""Recorre el asistente con una tele simulada. Se salta si no hay pantalla (CI sin xvfb)."""

import time
import tkinter as tk

import pytest

from fake_adb import LITE, FakeAdb
from tvlite import android, runner
from tvlite.gui import App


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("sin pantalla para Tk")
    r.withdraw()
    yield r
    r.destroy()


def pump(root, app, cond, seconds=10.0):
    """Procesa eventos de Tk hasta que se cumpla cond (los hilos de trabajo necesitan tiempo real)."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        root.update()
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_wizard_end_to_end(root, tmp_path, monkeypatch):
    fake = FakeAdb(packages=["com.tcl.esticker", "com.google.android.play.games"], stubborn_launcher=True)
    apk = tmp_path / "litelauncher.apk"
    apk.write_bytes(b"x")
    monkeypatch.setenv("TVLITE_LAUNCHER_APK", str(apk))
    app = App(root, adb_factory=lambda progress: fake, lang="es")
    assert app.step == 0
    app.go_next()                                  # bienvenida -> conectar
    assert app.STEPS[app.step] == "connect"
    app.ip_var.set("no-es-una-ip")
    app.go_next()
    assert "IP" in app.status.cget("text") and app.step == 1   # valida antes de llamar a ADB
    app.ip_var.set("192.168.1.50")
    app.go_next()
    assert pump(root, app, lambda: app.step == 2)  # conectado: muestra la tele
    assert app.info.model == "Smart TV" and app.plan
    app.go_next(); app.go_next()                   # limpieza -> apps
    app.app_vars["nordvpn"].set(True)
    app.go_next()                                  # -> resumen
    assert app.STEPS[app.step] == "run"
    app.do_run()
    assert pump(root, app, lambda: app.summary is not None)
    assert not app.summary.launcher_error
    assert android.package_of(android.resolve_home(fake)) == LITE
    assert "com.nordvpn.android" in android.list_packages(fake)
    assert "com.tcl.esticker" not in android.list_packages(fake)
    # idioma y volver atras
    app.toggle_language()
    assert app.lang == "en"
