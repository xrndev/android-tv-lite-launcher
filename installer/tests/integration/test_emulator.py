"""Pruebas contra un emulador de Android TV real (no un FakeAdb).

Preparacion (ver tools/emulator/emu.py):
    python tools/emulator/emu.py setup atv11-1gb && python tools/emulator/emu.py start atv11-1gb
Ejecucion:
    TVLITE_EMULATOR=1 TVLITE_EXPECT_RAM_MB=1024 python -m pytest installer/tests/integration -v

El emulador NO reproduce la GPU ni el SoC de una tele real: estas pruebas validan la logica en
distintas versiones de Android y RAM, no el rendimiento ni la compatibilidad de una marca concreta.
"""

import importlib.util
import json
import os
from pathlib import Path

import pytest

from tvlite import android, debloat, device, launcher, restore, runner
from tvlite.adb import Adb

pytestmark = pytest.mark.skipif(not os.environ.get("TVLITE_EMULATOR"), reason="define TVLITE_EMULATOR=1 con un emulador arrancado")

REPO = Path(__file__).resolve().parents[3]
SERIAL = os.environ.get("TVLITE_EMULATOR_SERIAL", "emulator-5554")


def load_emu():
    spec = importlib.util.spec_from_file_location("emu", REPO / "tools" / "emulator" / "emu.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def real_adb() -> Adb:
    exe = os.environ.get("TVLITE_ADB")
    if not exe:
        sdk = Path(os.environ.get("ANDROID_SDK_ROOT", REPO / "tools" / "android-sdk"))
        exe = next(iter((sdk / "platform-tools").glob("adb*")), "adb")
    return Adb(exe=Path(str(exe)), serial=SERIAL)


@pytest.fixture(scope="module")
def emu():
    return load_emu()


@pytest.fixture
def adb():
    return real_adb()


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("TVLITE_SIMULATE", raising=False)
    monkeypatch.delenv("TVLITE_EXTRA_LISTS", raising=False)


def simulate(monkeypatch, fx):
    monkeypatch.setenv("TVLITE_SIMULATE", json.dumps(fx["simulate"]))
    if fx.get("extra_list"):
        monkeypatch.setenv("TVLITE_EXTRA_LISTS", str(REPO / "tools" / "emulator" / fx["extra_list"]))


def test_detect_reports_real_emulator_values(adb):
    info = device.detect(adb, serial=SERIAL)
    assert info.sdk >= 21 and info.ram_mb > 0
    expected = os.environ.get("TVLITE_EXPECT_RAM_MB")
    if expected:  # la RAM reportada es algo menor que la asignada: margen del 20 %
        assert abs(info.ram_mb - int(expected)) / int(expected) < 0.2
    print("\n" + device.describe(info))


def test_memory_snapshot_on_a_real_device(adb):
    snap = android.memory_snapshot(adb)
    assert snap["ram_total_mb"] > 0 and 0 < snap["ram_available_mb"] <= snap["ram_total_mb"] and snap["packages"] > 10


@pytest.mark.parametrize("fixture_name", ["tcl", "acme"])
def test_full_flow_and_restore(adb, emu, monkeypatch, tmp_path, fixture_name):
    fx = emu.install_fixture(fixture_name)
    simulate(monkeypatch, fx)
    info = device.detect(adb, serial=SERIAL)
    assert info.simulated

    apk = launcher.find_launcher_apk()
    assert apk, "compila el launcher antes: bash launcher/build.sh"
    original = android.list_packages(adb)
    original_home = android.package_of(android.resolve_home(adb))

    plan = debloat.build_plan(info, original, system_packages=android.list_system_packages(adb))
    options = runner.Options(debloat_packages={i.pkg for i in plan if i.selected}, launcher_apk=apk)
    stay_before = android.get_setting(adb, "global", android.STAY_ON_KEY)
    verify_before = android.get_setting(adb, "global", android.VERIFY_ADB_KEY)
    summary = runner.run(adb, info, options, backup_base=tmp_path / "bk")
    try:
        assert not summary.error, summary.error
        after = android.list_packages(adb)
        for pkg in fx["system_removed"]:
            if pkg in original:  # solo si esa imagen de Android lo trae
                assert pkg not in after, f"{pkg} (sistema) deberia haberse quitado"
        for pkg in fx["expect_removed"]:
            assert pkg not in after, f"{pkg} (app de usuario) deberia haberse quitado"
        for pkg in fx["expect_kept"]:
            assert pkg in after, f"{pkg} deberia conservarse"
        # Las apps de usuario quitadas tienen su APK guardado en el backup.
        saved = [e for e in restore.Journal(summary.backup_dir).entries() if e["action"] == "debloat_user_app"]
        assert {e["target"] for e in saved} >= {p for p in fx["expect_removed"] if p in original}
        assert all((summary.backup_dir / e["reverse"]["dir"] / n).is_file() for e in saved for n in e["reverse"]["files"])
        assert not summary.launcher_error, summary.launcher_error
        assert android.package_of(android.resolve_home(adb)) == launcher.LITE_PKG
        assert summary.metrics_before and summary.metrics_after
        # Los ajustes temporales (tele despierta, verificacion de Play Protect) no dejan rastro.
        assert android.get_setting(adb, "global", android.STAY_ON_KEY) == stay_before
        assert android.get_setting(adb, "global", android.VERIFY_ADB_KEY) == verify_before
    finally:
        result = restore.restore(adb, summary.backup_dir)

    after_restore = android.list_packages(adb)
    assert result.ok, result
    assert launcher.LITE_PKG not in after_restore
    # TODO lo original vuelve, tambien las apps de usuario (reinstaladas desde su APK guardado).
    assert original - {launcher.LITE_PKG} <= after_restore
    for pkg in fx["expect_removed"]:
        if pkg in original:
            assert android.package_exists(adb, pkg), f"{pkg} deberia ser un paquete real, no un registro fantasma"
    assert android.package_of(android.resolve_home(adb)) == original_home


def test_dry_run_changes_nothing_on_real_device(adb, emu, monkeypatch, tmp_path):
    fx = emu.install_fixture("tcl")
    simulate(monkeypatch, fx)
    info = device.detect(adb, serial=SERIAL)
    before = android.list_packages(adb)
    plan = debloat.build_plan(info, before, system_packages=android.list_system_packages(adb))
    runner.run(adb, info, runner.Options(debloat_packages={i.pkg for i in plan}, dry_run=True), backup_base=tmp_path)
    assert android.list_packages(adb) == before


def test_report_on_a_real_device_lists_vendor_packages_without_user_apps(adb, emu, monkeypatch):
    from tvlite import report

    fx = emu.install_fixture("tcl")
    simulate(monkeypatch, fx)
    text = report.build_report(adb, device.detect(adb, serial=SERIAL))
    assert "TV report" in text and "candidates for a new list" in text
    assert "com.tcl.esticker" in text  # sale en el plan
