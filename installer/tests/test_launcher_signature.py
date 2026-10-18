"""Pasar de la clave de depuracion a la de lanzamiento cambia la firma: no se puede actualizar encima."""

from fake_adb import LITE, FakeAdb
from tvlite import android, launcher
from tvlite.journal import Journal


def test_incompatible_signature_triggers_reinstall(tmp_path, apk):
    adb = FakeAdb()
    adb.pkgs[LITE] = {"installed": True, "enabled": True, "home": True, "system": False}  # ya instalado (otra firma)
    adb.signature_conflict = True
    messages = []
    original_install = adb.install
    calls = []

    def install(path, timeout=300):
        calls.append(adb.pkgs.get(LITE, {}).get("installed"))
        res = original_install(path, timeout)
        if res.ok:
            adb.signature_conflict = False
        return res

    adb.install = install
    launcher.activate(adb, Journal(tmp_path / "j"), apk, messages.append, sdk=30)
    assert LITE in android.list_packages(adb)
    assert any("otra firma" in m for m in messages)
    assert calls == [True, False]  # primer intento sobre el existente; segundo tras desinstalarlo
