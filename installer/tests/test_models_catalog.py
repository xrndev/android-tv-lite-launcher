"""El catalogo de modelos reales (tools/emulator/models.json) debe ser coherente y honesto."""

import json
from pathlib import Path

import pytest

from tvlite import debloat, device

TOOLS = Path(__file__).resolve().parents[2] / "tools" / "emulator"
MODELS = json.loads((TOOLS / "models.json").read_text(encoding="utf-8"))
PROFILES = json.loads((TOOLS / "profiles.json").read_text(encoding="utf-8"))["profiles"]
CATALOG = debloat.load_catalog()


@pytest.mark.parametrize("model_id", list(MODELS["models"]))
def test_model_is_complete_and_consistent(model_id):
    m = MODELS["models"][model_id]
    for key in ("display", "manufacturer", "brand", "model", "soc", "android", "api", "ram_mb", "play_store",
                "avd", "evidence", "sources", "vendor_packages", "protected_vendor"):
        assert key in m, f"{model_id}: falta {key}"
    assert m["avd"] in PROFILES, f"{model_id}: el perfil de emulador {m['avd']} no existe"
    assert PROFILES[m["avd"]]["api"] == m["api"], f"{model_id}: la API no coincide con su perfil"
    assert set(m["evidence"]) == {"hardware", "software", "packages"}
    assert m["sources"], f"{model_id}: sin fuentes"
    assert set(m["protected_vendor"]) <= set(m["vendor_packages"])
    assert len(set(m["vendor_packages"])) == len(m["vendor_packages"])


@pytest.mark.parametrize("model_id", list(MODELS["models"]))
def test_no_model_claims_to_be_real_unless_it_is_the_tested_tv(model_id):
    m = MODELS["models"][model_id]
    real = [k for k, v in m["evidence"].items() if v == "real"]
    if model_id == "tcl-smart-tv-mt5867":
        assert real  # la unica tele fisica probada
    else:
        assert not real, f"{model_id}: solo la TCL probada puede tener evidencia 'real'"
        assert any(w in " ".join(m["evidence"].values()) for w in ("public-specs", "assumed", "community"))


@pytest.mark.parametrize("model_id", list(MODELS["models"]))
def test_ram_profile_matches_the_expected_class(model_id):
    m = MODELS["models"][model_id]
    expected = "ultra_low" if m["ram_mb"] <= 1200 else "low" if m["ram_mb"] <= 2200 else "normal"
    assert device.ram_profile(m["ram_mb"]) == expected


def test_vendor_packages_that_a_list_may_remove_are_never_protected():
    """Si un paquete esta en una lista y a la vez protegido, el validador ya falla; aqui se comprueba
    ademas que lo que el modelo declara protegido (launchers, TV) esta realmente protegido o fuera de las listas."""
    listed = {e["pkg"] for lst in CATALOG["lists"] for e in lst["packages"]}
    for model_id, m in MODELS["models"].items():
        for pkg in m["protected_vendor"]:
            assert pkg not in listed, f"{model_id}: {pkg} esta protegido por el modelo pero una lista lo quita"


def test_unsupported_examples_are_documented():
    names = {u["name"] for u in MODELS["unsupported"]}
    assert any("Hisense" in n for n in names) and any("LG" in n for n in names) and any("Samsung" in n for n in names)
    hisense = next(u for u in MODELS["unsupported"] if "Hisense" in u["name"])
    assert hisense["sources"], "el ejemplo de Hisense VIDAA debe citar su fuente"
