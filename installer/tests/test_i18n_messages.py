"""La salida en ingles no debe dejar espanol: se recorren los flujos principales (tambien los de error)
y se traducen todos los mensajes que emite el nucleo."""

import re

import pytest

from fake_adb import FakeAdb
from tests_helpers import run_flow  # noqa: F401  (ver tests_helpers.py)
from tvlite import device
from tvlite.i18n import translate_message

SPANISH_MARKERS = re.compile(
    r"\b(Quitado|Quitando|Abriendo|Descargando|Guardando|Instalando|Desactivando|Restaurando|Deshaciendo|"
    r"Conectando|Animaciones|simulacion|Simulacion|[Cc]opia de seguridad|conexion|No se |Se perdio|"
    r"la tele|se pudo|se quita|paquetes:|disponible)\b"
)


def collect(adb_kwargs, tmp_path, apk, **run_kwargs):
    messages, summary = run_flow(adb_kwargs, tmp_path, apk, **run_kwargs)
    texts = list(messages)
    if summary.error:
        texts.append(summary.error)
    if summary.launcher_error:
        texts.append(summary.launcher_error)
    texts += [a.detail for a in summary.apps if a.detail]
    return texts


SCENARIOS = {
    "normal": dict(adb_kwargs={}, run_kwargs={}),
    "dry-run": dict(adb_kwargs={}, run_kwargs={"dry_run": True}),
    "apk-not-saved": dict(adb_kwargs={"pull_fails": True}, run_kwargs={}),
    "apk-not-saved-forced": dict(adb_kwargs={"pull_fails": True}, run_kwargs={"allow_irreversible": True}),
    "tv-unhealthy": dict(adb_kwargs={"unhealthy_after_uninstalls": 2}, run_kwargs={}),
    "launcher-broken": dict(adb_kwargs={"lite_broken": True, "stubborn_launcher": True}, run_kwargs={}),
    "play-unavailable": dict(adb_kwargs={"play_installs": False}, run_kwargs={"apps": ["nordvpn"]}),
    "signature-conflict": dict(adb_kwargs={"stubborn_launcher": True}, run_kwargs={"preinstall_lite": True}),
}


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_no_spanish_left_in_english_output(name, tmp_path, apk):
    scenario = SCENARIOS[name]
    texts = collect(scenario["adb_kwargs"], tmp_path, apk, **scenario["run_kwargs"])
    assert texts, "el escenario no produjo mensajes"
    leftovers = [t for t in (translate_message("en", m) for m in texts) if SPANISH_MARKERS.search(t)]
    assert not leftovers, f"Faltan traducciones: {leftovers}"


def test_spanish_is_returned_unchanged():
    assert translate_message("es", "Quitado com.x (X)") == "Quitado com.x (X)"


def test_specific_translations():
    assert translate_message("en", "Quitado com.x (X) (APK guardado para restaurar)") == \
        "Removed com.x (X) (APK saved so it can be restored)"
    assert translate_message("en", "RAM disponible: 300 MB -> 350 MB | paquetes: 10 -> 7 (la RAM suele mejorar mas tras reiniciar la tele)") == \
        "Available RAM: 300 MB -> 350 MB | packages: 10 -> 7 (RAM usually improves more after rebooting the TV)"
    assert translate_message("en", "Un mensaje que no conocemos") == "Un mensaje que no conocemos"


def test_describe_is_localized():
    info = device.detect(FakeAdb())
    es, en = device.describe(info, "es"), device.describe(info, "en")
    assert "Perfil" in es and "Profile" in en and "Perfil" not in en and "Procesador" not in en
