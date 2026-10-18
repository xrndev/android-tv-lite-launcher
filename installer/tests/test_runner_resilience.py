"""Tele que se duerme, conexion que se cae a mitad y comparacion antes/despues."""

from fake_adb import LITE, PLAY, STOCK, FakeAdb
from tvlite import android, device, restore, runner
from tvlite.adb import AdbError

PACKAGES = ["com.tcl.esticker", "com.tcl.messagebox", "com.google.android.play.games"]


class FlakyAdb(FakeAdb):
    """FakeAdb que pierde la conexion al llegar a cierto comando, como una tele que se queda dormida."""

    def __init__(self, *a, drop_on=None, **k):
        super().__init__(*a, **k)
        self.drop_on = drop_on
        self.dropped = False

    def shell(self, command, timeout=60):
        if self.drop_on and command.startswith(self.drop_on):
            self.dropped = True
        if self.dropped:
            raise AdbError("Se perdio la conexion con la tele: error: device offline")
        return super().shell(command, timeout)


def options(apk, **kw):
    return runner.Options(debloat_packages=set(PACKAGES), launcher_apk=apk, **kw)


def test_stay_awake_is_enabled_during_the_run_and_restored_after(tmp_path, apk):
    adb = FakeAdb(packages=PACKAGES)
    seen = []
    original = adb.install

    def spy(path, timeout=300):
        seen.append(adb.settings["global"].get(android.STAY_ON_KEY))
        return original(path, timeout)

    adb.install = spy
    runner.run(adb, device.detect(adb), options(apk), backup_base=tmp_path)
    assert seen == ["7"]  # durante el proceso la tele no se duerme...
    assert android.STAY_ON_KEY not in adb.settings["global"]  # ...y despues vuelve a como estaba


def test_dry_run_does_not_touch_the_stay_awake_setting(tmp_path, apk):
    adb = FakeAdb(packages=PACKAGES)
    runner.run(adb, device.detect(adb), options(apk, dry_run=True), backup_base=tmp_path)
    assert not any("stay_on_while_plugged_in" in c for c in adb.log)


def test_metrics_before_and_after_are_collected_and_saved(tmp_path, apk):
    adb = FakeAdb(packages=PACKAGES)
    messages = []
    summary = runner.run(adb, device.detect(adb), options(apk), messages.append, backup_base=tmp_path)
    before, after = summary.metrics_before, summary.metrics_after
    assert after["packages"] < before["packages"]
    assert after["ram_available_mb"] > before["ram_available_mb"]  # cada paquete quitado libera algo
    assert (summary.backup_dir / "metrics.json").is_file()
    assert any("RAM disponible" in m for m in messages)


def test_connection_lost_midway_returns_a_summary_instead_of_crashing(tmp_path, apk):
    adb = FlakyAdb(packages=PACKAGES, stubborn_launcher=True, drop_on="pm disable-user")
    summary = runner.run(adb, device.detect(FakeAdb(packages=PACKAGES)), options(apk), backup_base=tmp_path)
    assert "perdio la conexion" in summary.error and str(summary.backup_dir) in summary.error
    assert summary.backup_dir.joinpath("journal.jsonl").is_file()  # el diario ya estaba en disco


def test_after_a_lost_connection_restore_undoes_what_was_applied(tmp_path, apk):
    adb = FlakyAdb(packages=PACKAGES, stubborn_launcher=True, drop_on="pm disable-user")
    original = android.list_packages(FakeAdb(packages=PACKAGES))
    summary = runner.run(adb, device.detect(FakeAdb(packages=PACKAGES)), options(apk), backup_base=tmp_path)
    assert summary.error
    adb.dropped, adb.drop_on = False, None  # la tele vuelve a responder
    result = restore.restore(adb, summary.backup_dir)
    assert result.ok
    assert android.list_packages(adb) >= original - {LITE}
    assert android.package_of(android.resolve_home(adb)) == STOCK and PLAY in android.list_packages(adb)
