import copy

from fake_adb import PLAY, FakeAdb
from tvlite import android, debloat, device
from tvlite.journal import Journal

TCL_PACKAGES = [
    "com.tcl.esticker", "com.tcl.ttvs", "com.tcl.hearaid",
    "com.google.android.katniss", "com.google.android.play.games",
    "com.android.printspooler", "com.android.providers.settings",
]


def make(ram_kb=940628, **kw):
    return FakeAdb(ram_kb=ram_kb, packages=TCL_PACKAGES, **kw)


def test_detect_tcl():
    info = device.detect(make())
    assert info.manufacturer == "TCL" and info.soc == "mt5867"
    assert info.ram_mb == 918 and info.profile == "ultra_low"
    assert info.abis[0] == "armeabi-v7a" and info.sdk == 30
    assert "TCL Smart TV" in device.describe(info)


def test_ram_profiles():
    assert device.ram_profile(940) == "ultra_low"
    assert device.ram_profile(1800) == "low"
    assert device.ram_profile(3500) == "normal"
    assert device.ram_profile(0) == "normal"  # sin dato: lo prudente


def test_catalog_is_valid():
    assert debloat.validate_catalog(debloat.load_catalog()) == []


def test_play_store_is_protected():
    catalog = debloat.load_catalog()
    for pkg in (PLAY, "com.google.android.gms", "com.android.providers.media", "com.android.systemui"):
        assert debloat.is_protected(pkg, catalog)


def test_validate_flags_protected_package_in_list():
    catalog = copy.deepcopy(debloat.load_catalog())
    catalog["lists"].append({
        "id": "evil", "name": "x", "match": {}, "verified_on": ["x"],
        "packages": [{"pkg": PLAY, "label": "Play Store", "tier": "safe"}],
    })
    assert any(PLAY in p for p in debloat.validate_catalog(catalog))


def test_plan_preselects_by_profile_and_never_selects_optional():
    adb = make()
    info = device.detect(adb)
    plan = {i.pkg: i for i in debloat.build_plan(info, android.list_packages(adb))}
    assert plan["com.tcl.ttvs"].selected  # aggressive en ultra_low
    assert plan["com.tcl.esticker"].selected
    assert not plan["com.google.android.katniss"].selected  # optional: nunca preseleccionado
    assert "com.android.providers.settings" not in plan  # protegido


def test_plan_normal_ram_only_safe():
    adb = make(ram_kb=3_500_000)
    plan = {i.pkg: i for i in debloat.build_plan(device.detect(adb), android.list_packages(adb))}
    assert plan["com.android.printspooler"].selected
    assert not plan["com.tcl.esticker"].selected and not plan["com.tcl.ttvs"].selected


def test_brand_lists_only_match_their_brand():
    adb = make(props={"ro.product.manufacturer": "Sony", "ro.product.brand": "sony"})
    plan = {i.pkg for i in debloat.build_plan(device.detect(adb), android.list_packages(adb))}
    assert "com.tcl.esticker" not in plan and "com.google.android.play.games" in plan


def test_unverified_lists_are_ignored_by_default():
    catalog = copy.deepcopy(debloat.load_catalog())
    catalog["lists"].append({
        "id": "community", "name": "x", "match": {}, "notes": "reportado por un usuario",
        "packages": [{"pkg": "com.example.junk", "label": "Junk", "tier": "safe"}],
    })
    adb = make()
    adb.pkgs["com.example.junk"] = {"installed": True, "enabled": True, "home": False}
    info, installed = device.detect(adb), android.list_packages(adb)
    assert "com.example.junk" not in {i.pkg for i in debloat.build_plan(info, installed, catalog)}
    unverified = debloat.build_plan(info, installed, catalog, include_unverified=True)
    item = next(i for i in unverified if i.pkg == "com.example.junk")
    assert not item.selected  # incluso si se pide, no se preselecciona


def test_apply_uninstalls_and_journals(tmp_path):
    adb = make()
    info = device.detect(adb)
    plan = debloat.build_plan(info, android.list_packages(adb))
    journal = Journal(tmp_path / "j")
    result = debloat.apply_plan(adb, plan, journal)
    assert "com.tcl.esticker" in result.done and not result.failed
    assert "com.tcl.esticker" not in android.list_packages(adb)
    assert PLAY in android.list_packages(adb)  # Play Store siempre se conserva
    assert any(e["target"] == "com.tcl.esticker" and e["reverse"] for e in journal.entries())


def test_dry_run_changes_nothing(tmp_path):
    adb = make()
    plan = debloat.build_plan(device.detect(adb), android.list_packages(adb))
    before = android.list_packages(adb)
    debloat.apply_plan(adb, plan, Journal(tmp_path / "j"), dry_run=True)
    assert android.list_packages(adb) == before


def test_apply_refuses_protected_even_if_forced(tmp_path):
    adb = make()
    item = debloat.PlanItem(PLAY, "Play Store", "x", "x", "safe", selected=True)
    result = debloat.apply_plan(adb, [item], Journal(tmp_path / "j"))
    assert PLAY in android.list_packages(adb) and result.failed


def test_unhealthy_tv_rolls_back_batch_and_aborts(tmp_path):
    adb = make(unhealthy_after_uninstalls=2)
    plan = debloat.build_plan(device.detect(adb), android.list_packages(adb))
    result = debloat.apply_plan(adb, plan, Journal(tmp_path / "j"))
    assert result.aborted and result.rolled_back and not result.done
    assert "com.tcl.esticker" in android.list_packages(adb)  # restaurado


def test_simulation_override_is_flagged(monkeypatch):
    monkeypatch.setenv("TVLITE_SIMULATE", '{"manufacturer": "Sony", "soc": "MT5895", "ram_mb": 1500}')
    info = device.detect(make())
    assert info.manufacturer == "Sony" and info.soc == "MT5895" and info.profile == "low"
    assert info.simulated and "SIMULADO" in device.describe(info)


def test_extra_lists_from_env(tmp_path, monkeypatch):
    extra = tmp_path / "mine.json"
    extra.write_text(
        '{"lists": [{"id": "mine", "name": "Mi lista", "match": {"manufacturer": ["Acme"]},'
        ' "verified_on": ["Acme 1 (probada)"], "packages": [{"pkg": "acme.junk", "label": "Junk", "tier": "safe"}]}]}',
        encoding="utf-8",
    )
    monkeypatch.setenv("TVLITE_EXTRA_LISTS", str(extra))
    adb = FakeAdb(props={"ro.product.manufacturer": "Acme"}, packages=["acme.junk"])
    plan = debloat.build_plan(device.detect(adb), android.list_packages(adb))
    assert any(i.pkg == "acme.junk" and i.selected for i in plan)
