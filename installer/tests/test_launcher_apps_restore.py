import pytest

from fake_adb import LITE, PLAY, STOCK, FakeAdb
from tvlite import android, appinstall, device, launcher, restore, runner
from tvlite.journal import Journal


def active_home(adb):
    return android.package_of(android.resolve_home(adb))


def test_launcher_activation_with_role(tmp_path, apk):
    adb = FakeAdb()
    result = launcher.activate(adb, Journal(tmp_path / "j"), apk, sdk=30)
    assert active_home(adb) == LITE and android.package_of(android.resumed_activity(adb)) == LITE
    assert result.used_role and not result.disabled
    assert adb.pkgs[STOCK]["enabled"]  # el original sigue activo si no hizo falta desactivarlo


def test_stubborn_stock_launcher_gets_disabled_not_uninstalled(tmp_path, apk):
    adb = FakeAdb(stubborn_launcher=True)
    result = launcher.activate(adb, Journal(tmp_path / "j"), apk, sdk=30)
    assert active_home(adb) == LITE and result.disabled == [STOCK]
    assert adb.pkgs[STOCK]["installed"] and not adb.pkgs[STOCK]["enabled"]


def test_broken_launcher_leaves_tv_as_it_was(tmp_path, apk):
    adb = FakeAdb(lite_broken=True, stubborn_launcher=True)
    with pytest.raises(launcher.LauncherError):
        launcher.activate(adb, Journal(tmp_path / "j"), apk, sdk=30)
    assert active_home(adb) == STOCK and adb.pkgs[STOCK]["enabled"]
    assert not adb.pkgs[LITE]["installed"]  # el launcher roto se retira


def test_full_run_then_restore_returns_original_state(tmp_path):
    packages = ["com.tcl.esticker", "com.tcl.ttvs", "com.google.android.play.games"]
    adb = FakeAdb(packages=packages, stubborn_launcher=True)
    apk = tmp_path / "litelauncher.apk"
    apk.write_bytes(b"x")
    info = device.detect(adb)
    original = android.list_packages(adb)
    opts = runner.Options(debloat_packages=set(packages), launcher_apk=apk, app_ids=[])
    summary = runner.run(adb, info, opts, backup_base=tmp_path / "bk")
    assert summary.launcher and not summary.launcher_error
    assert active_home(adb) == LITE
    assert adb.settings["global"]["window_animation_scale"] == "0"  # ultra_low
    assert not set(packages) & android.list_packages(adb)

    result = restore.restore(adb, summary.backup_dir)
    assert result.ok
    assert active_home(adb) == STOCK
    assert set(packages) <= android.list_packages(adb)
    assert LITE not in android.list_packages(adb)
    assert "window_animation_scale" not in adb.settings["global"]  # estaba sin definir
    assert PLAY in android.list_packages(adb)


def test_dry_run_through_runner_changes_nothing(tmp_path):
    adb = FakeAdb(packages=["com.tcl.esticker"])
    info = device.detect(adb)
    before = android.list_packages(adb)
    runner.run(adb, info, runner.Options(debloat_packages={"com.tcl.esticker"}, dry_run=True), backup_base=tmp_path)
    assert android.list_packages(adb) == before and active_home(adb) == STOCK


def test_pick_apk_url_by_abi():
    stremio = next(a for a in appinstall.load_apps()["apps"] if a["id"] == "stremio")
    assert "armeabi-v7a" in appinstall.pick_apk_url(stremio, ["armeabi-v7a", "armeabi"])
    assert "arm64-v8a" in appinstall.pick_apk_url(stremio, ["arm64-v8a", "armeabi-v7a"])
    assert appinstall.pick_apk_url(stremio, ["mips"]) is None


def test_play_install_success_and_failure(tmp_path):
    app = {"id": "nordvpn", "name": "NordVPN", "package": "com.nordvpn.android", "method": "play"}
    adb = FakeAdb()
    journal = Journal(tmp_path / "j")
    result = appinstall.install_app(adb, app, ["x86"], journal)
    assert result.ok and "com.nordvpn.android" in android.list_packages(adb)
    assert appinstall.install_app(adb, app, ["x86"], journal).skipped  # ya instalada

    broken = FakeAdb(play_installs=False)
    assert not appinstall.install_app(broken, app, ["x86"], journal).ok


def test_catalog_apps_have_unique_packages_and_known_categories():
    data = appinstall.load_apps()
    pkgs = [a["package"] for a in data["apps"]]
    assert len(pkgs) == len(set(pkgs))
    assert all(a["category"] in data["categories"] for a in data["apps"])


def test_normalize_target_and_validation():
    assert runner.normalize_target(" 192.168.1.50 ") == "192.168.1.50:5555"
    assert runner.normalize_target("10.0.0.2:5556") == "10.0.0.2:5556"
    for bad in ("", "tele", "192.168.1", "999.1.1.1", "1.2.3.4:abc"):
        with pytest.raises(ValueError):
            runner.normalize_target(bad)


def test_connect_detects_unauthorized():
    adb = FakeAdb(authorized=False)
    with pytest.raises(runner.NotAuthorized):
        runner.connect(adb, "192.168.1.50")


def test_connect_ok_returns_device_info():
    info = runner.connect(FakeAdb(), "192.168.1.50")
    assert info.model == "Smart TV" and info.serial == "192.168.1.50:5555"
