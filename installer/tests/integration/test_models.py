"""Simula modelos REALES de teles (tools/emulator/models.json) sobre un emulador de Android TV.

    python tools/emulator/run_models.py            # todos, arrancando el emulador que toque
    python tools/emulator/run_models.py sony-kd43x80j

(o a mano, con el emulador ya arrancado: TVLITE_EMULATOR=1 TVLITE_MODEL=<id> pytest este_fichero)

El emulador NO es el firmware de la marca. Esto prueba la LOGICA de tvlite con la identidad, la RAM, la version
de Android y los nombres de paquete de cada modelo; no demuestra que quitar esos paquetes sea seguro en la tele
fisica (las listas de otras marcas estan sin verificar y por defecto no se aplican)."""

import importlib.util
import json
import os
from pathlib import Path

import pytest

from tvlite import android, debloat, device, launcher, report, restore, runner
from tvlite.adb import Adb

MODEL_ID = os.environ.get("TVLITE_MODEL")
pytestmark = pytest.mark.skipif(
    not (os.environ.get("TVLITE_EMULATOR") and MODEL_ID), reason="define TVLITE_EMULATOR=1 y TVLITE_MODEL=<id>"
)

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


@pytest.fixture
def model(emu, monkeypatch):
    monkeypatch.delenv("TVLITE_EXTRA_LISTS", raising=False)
    data = emu.install_model(MODEL_ID)
    monkeypatch.setenv("TVLITE_SIMULATE", json.dumps(emu.model_simulation(data)))
    return data


def verified_package_names():
    return {e["pkg"] for lst in debloat.load_catalog()["lists"] if lst.get("verified_on") for e in lst["packages"]}


def test_identity_profile_and_play_store_are_detected(adb, model):
    info = device.detect(adb, serial=SERIAL)
    assert info.simulated and info.manufacturer == model["manufacturer"] and info.model == model["model"]
    expected = "ultra_low" if model["ram_mb"] <= 1200 else "low" if model["ram_mb"] <= 2200 else "normal"
    assert info.profile == expected
    assert info.has_play_store == model["play_store"]
    print("\n" + device.describe(info))


def test_default_run_never_touches_unverified_vendor_packages_and_restores(adb, model, tmp_path):
    info = device.detect(adb, serial=SERIAL)
    apk = launcher.find_launcher_apk()
    assert apk, "compila el launcher antes: bash launcher/build.sh"
    original = android.list_packages(adb)
    original_home = android.package_of(android.resolve_home(adb))

    plan = debloat.build_plan(info, original, system_packages=android.list_system_packages(adb))
    selected = {i.pkg for i in plan if i.selected}
    summary = runner.run(
        adb, info, runner.Options(debloat_packages=selected, app_ids=["nordvpn"], launcher_apk=apk),
        backup_base=tmp_path / "bk",
    )
    try:
        assert not summary.error, summary.error
        after = android.list_packages(adb)
        # PROPIEDAD DE SEGURIDAD: lo que no esta en una lista verificada no se toca.
        for pkg in model["vendor_packages"]:
            if pkg not in verified_package_names():
                assert pkg in after, f"{pkg} no esta en una lista verificada y no debia quitarse"
        for pkg in selected:
            assert pkg not in after, f"{pkg} estaba seleccionado y deberia haberse quitado"
        for pkg in model["protected_vendor"]:
            assert pkg in after
        if model["play_store"]:
            assert "com.android.vending" in after
        assert not summary.launcher_error, summary.launcher_error
        assert android.package_of(android.resolve_home(adb)) == launcher.LITE_PKG
        # Sin Play Store, la app de Play se omite con un aviso claro y no se intenta a ciegas.
        nord = next(a for a in summary.apps if a.app_id == "nordvpn")
        if not model["play_store"]:
            assert not nord.ok and "Play Store no esta instalado" in nord.detail
    finally:
        result = restore.restore(adb, summary.backup_dir)
    assert result.ok, result
    after_restore = android.list_packages(adb)
    assert original - {launcher.LITE_PKG} <= after_restore
    for pkg in selected:
        if pkg in original:
            assert android.package_exists(adb, pkg), f"{pkg} deberia ser un paquete real tras restaurar"
    assert android.package_of(android.resolve_home(adb)) == original_home


def test_including_unverified_lists_removes_and_restores_the_brand_packages(adb, model, tmp_path):
    info = device.detect(adb, serial=SERIAL)
    apk = launcher.find_launcher_apk()
    original = android.list_packages(adb)
    system = android.list_system_packages(adb)
    plan = debloat.build_plan(info, original, include_unverified=True, system_packages=system)
    offered = {i.pkg for i in plan}
    # lo protegido NUNCA se ofrece, ni siquiera en listas sin verificar
    assert not offered & set(model["protected_vendor"])
    summary = runner.run(
        adb, info,
        runner.Options(debloat_packages=offered, include_unverified=True, launcher_apk=apk, activate_launcher=False),
        backup_base=tmp_path / "bk",
    )
    try:
        assert not summary.error, summary.error
        after = android.list_packages(adb)
        assert not (offered & after), f"deberian haberse quitado: {offered & after}"
        for pkg in model["protected_vendor"]:
            assert pkg in after
    finally:
        result = restore.restore(adb, summary.backup_dir)
    assert result.ok, result
    assert original <= android.list_packages(adb)
    for pkg in offered:
        assert android.package_exists(adb, pkg)


def test_report_has_the_model_and_never_lists_user_installed_apps(adb, model):
    """Los paquetes de fabricante del emulador son apps de USUARIO (stubs): el informe solo lista paquetes de
    SISTEMA, asi que no deben aparecer como candidatos. Los que cubre una lista si salen en el plan."""
    info = device.detect(adb, serial=SERIAL)
    text = report.build_report(adb, info)
    assert model["model"] in text and "candidates for a new list" in text
    candidates = text.split("candidates for a new list")[1]
    for pkg in model["vendor_packages"]:
        assert pkg not in candidates, f"{pkg} es una app de usuario y no debe salir como candidato"
    covered = verified_package_names()
    plan_section = text.split("candidates for a new list")[0]
    for pkg in model["vendor_packages"]:
        if pkg in covered and pkg not in model["protected_vendor"]:
            assert pkg in plan_section, f"{pkg} esta en una lista verificada y deberia salir en el plan"
