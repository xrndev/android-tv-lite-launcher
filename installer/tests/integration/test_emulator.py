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


@pytest.mark.parametrize("fixture_name", ["tcl", "acme"])
@pytest.mark.parametrize("forced", [False, True], ids=["default", "allow-irreversible"])
def test_full_flow_and_restore(adb, emu, monkeypatch, tmp_path, fixture_name, forced):
    fx = emu.install_fixture(fixture_name)
    simulate(monkeypatch, fx)
    info = device.detect(adb, serial=SERIAL)
    assert info.simulated

    apk = launcher.find_launcher_apk()
    assert apk, "compila el launcher antes: bash launcher/build.sh"
    original = android.list_packages(adb)
    original_home = android.package_of(android.resolve_home(adb))

    plan = debloat.build_plan(
        info, original, system_packages=android.list_system_packages(adb), allow_irreversible=forced
    )
    options = runner.Options(
        debloat_packages={i.pkg for i in plan if i.selected}, allow_irreversible=forced, launcher_apk=apk
    )
    summary = runner.run(adb, info, options, backup_base=tmp_path / "bk")
    try:
        after = android.list_packages(adb)
        for pkg in fx["system_removed"]:
            if pkg in original:  # solo si esa imagen de Android lo trae
                assert pkg not in after, f"{pkg} (sistema) deberia haberse quitado"
        removed_user = fx["expect_removed_forced"] if forced else []
        for pkg in removed_user:
            assert pkg not in after, f"{pkg} deberia haberse quitado con --allow-irreversible"
        for pkg in fx["expect_kept"]:
            if pkg not in removed_user:
                assert pkg in after, f"{pkg} deberia conservarse"
        assert not summary.launcher_error, summary.launcher_error
        assert android.package_of(android.resolve_home(adb)) == launcher.LITE_PKG
    finally:
        result = restore.restore(adb, summary.backup_dir)

    after_restore = android.list_packages(adb)
    assert result.ok, result  # las apps de usuario quitadas no estan en el diario como reversibles
    assert launcher.LITE_PKG not in after_restore
    # Todo lo de sistema vuelve; lo de usuario quitado a la fuerza no (hay que reinstalarlo).
    forced_removed = {i.pkg for i in plan if i.selected and not i.system}
    assert (original - {launcher.LITE_PKG} - forced_removed) <= after_restore
    assert android.package_of(android.resolve_home(adb)) == original_home
    emu.install_fixture(fixture_name)  # deja el emulador como estaba para la siguiente prueba


def test_dry_run_changes_nothing_on_real_device(adb, emu, monkeypatch, tmp_path):
    fx = emu.install_fixture("tcl")
    simulate(monkeypatch, fx)
    info = device.detect(adb, serial=SERIAL)
    before = android.list_packages(adb)
    plan = debloat.build_plan(info, before, system_packages=android.list_system_packages(adb), allow_irreversible=True)
    runner.run(adb, info, runner.Options(debloat_packages={i.pkg for i in plan}, dry_run=True), backup_base=tmp_path)
    assert android.list_packages(adb) == before
