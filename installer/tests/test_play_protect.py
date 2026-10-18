"""Una tele con Play Protect abre un dialogo al instalar un APK desconocido por ADB y la instalacion se
queda colgada. tvlite desactiva SOLO esa verificacion durante la instalacion y la devuelve siempre."""

import pytest

from fake_adb import LITE, FakeAdb
from tvlite import android, launcher
from tvlite.journal import Journal

KEY = android.VERIFY_ADB_KEY


def test_setting_is_restored_to_unset(tmp_path):
    adb = FakeAdb()
    with android.adb_verification_off(adb, Journal(tmp_path / "j")):
        assert adb.settings["global"][KEY] == "0"
    assert KEY not in adb.settings["global"]


def test_setting_is_restored_to_previous_value(tmp_path):
    adb = FakeAdb()
    adb.settings["global"][KEY] = "1"
    with android.adb_verification_off(adb):
        assert adb.settings["global"][KEY] == "0"
    assert adb.settings["global"][KEY] == "1"


def test_setting_is_restored_even_if_the_install_fails(tmp_path):
    adb = FakeAdb()
    with pytest.raises(RuntimeError):
        with android.adb_verification_off(adb):
            raise RuntimeError("fallo a mitad")
    assert KEY not in adb.settings["global"]


def test_change_is_journaled_so_restore_can_undo_it_after_a_crash(tmp_path):
    adb = FakeAdb()
    journal = Journal(tmp_path / "j")
    with android.adb_verification_off(adb, journal):
        entries = journal.entries()
        assert entries[-1]["target"] == KEY and entries[-1]["reverse"]["value"] is None


def test_launcher_install_uses_the_window_and_leaves_setting_clean(tmp_path, apk):
    adb = FakeAdb()
    seen = []
    original = adb.install

    def spy(path, timeout=300):
        seen.append(adb.settings["global"].get(KEY))
        return original(path, timeout)

    adb.install = spy
    launcher.activate(adb, Journal(tmp_path / "j"), apk, sdk=30)
    assert seen == ["0"]  # durante la instalacion la verificacion estaba desactivada...
    assert KEY not in adb.settings["global"]  # ...y despues vuelve a como estaba
    assert LITE in android.list_packages(adb)
