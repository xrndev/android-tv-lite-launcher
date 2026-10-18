"""TVs Android sin Play Store (p. ej. algunas 'Android 9 AOSP') y listas de otras marcas (sin verificar)."""

import pytest

from fake_adb import PLAY, FakeAdb
from tvlite import android, debloat, device, runner


def tv(**props):
    adb = FakeAdb(props=props)
    return adb


def test_detects_a_tv_without_play_store_and_says_so():
    adb = FakeAdb()
    adb.pkgs[PLAY]["installed"] = False
    info = device.detect(adb)
    assert not info.has_play_store
    text_es, text_en = device.describe(info, "es"), device.describe(info, "en")
    assert "Play Store: NO" in text_es and "Sin Play Store" in text_es
    assert "Play Store: NO" in text_en and "Without Play Store" in text_en


def test_tv_with_play_store_reports_yes():
    info = device.detect(FakeAdb())
    assert info.has_play_store and "Play Store: sí" in device.describe(info, "es")


def test_play_apps_are_skipped_with_a_clear_message_when_there_is_no_play_store(tmp_path, apk):
    adb = FakeAdb()
    adb.pkgs[PLAY]["installed"] = False
    messages = []
    summary = runner.run(
        adb, device.detect(adb),
        runner.Options(app_ids=["nordvpn"], launcher_apk=apk), messages.append, backup_base=tmp_path,
    )
    result = next(a for a in summary.apps if a.app_id == "nordvpn")
    assert not result.ok and "Play Store no esta instalado" in result.detail
    assert any("Play Store no esta instalado" in m for m in messages)
    assert "com.nordvpn.android" not in android.list_packages(adb)  # no se intento nada a ciegas


def test_xiaomi_launcher_packages_are_protected():
    catalog = debloat.load_catalog()
    for pkg in ("com.mitv.tvhome", "com.mitv.tvhome.atv", "com.mitv.tvhome.michannel"):
        assert debloat.is_protected(pkg, catalog)


@pytest.mark.parametrize("maker,expected", [
    ("Sony", "com.sony.dtv.sonyselect"),
    ("Xiaomi", "com.xiaomi.mitv.advertise"),
])
def test_community_lists_are_ignored_by_default_and_never_preselected(maker, expected):
    adb = FakeAdb(props={"ro.product.manufacturer": maker, "ro.product.brand": maker}, packages=[expected])
    info, installed = device.detect(adb), android.list_packages(adb)
    assert expected not in {i.pkg for i in debloat.build_plan(info, installed)}  # por defecto no se aplican
    plan = {i.pkg: i for i in debloat.build_plan(info, installed, include_unverified=True)}
    assert expected in plan and not plan[expected].selected and not plan[expected].verified


def test_community_lists_only_match_their_own_brand():
    adb = FakeAdb(props={"ro.product.manufacturer": "TCL"}, packages=["com.sony.dtv.sonyselect"])
    plan = debloat.build_plan(device.detect(adb), android.list_packages(adb), include_unverified=True)
    assert "com.sony.dtv.sonyselect" not in {i.pkg for i in plan}


def test_catalog_with_community_lists_is_still_valid():
    catalog = debloat.load_catalog()
    assert debloat.validate_catalog(catalog) == []
    ids = {lst["id"] for lst in catalog["lists"]}
    assert {"sony-community-unverified", "xiaomi-community-unverified"} <= ids
    for lst in catalog["lists"]:
        if lst["id"].endswith("-unverified"):
            assert not lst.get("verified_on") and lst.get("sources") and lst.get("notes")


def test_sony_shelf_warning_is_recorded():
    catalog = debloat.load_catalog()
    sony = next(lst for lst in catalog["lists"] if lst["id"] == "sony-community-unverified")
    shelf = next(p for p in sony["packages"] if p["pkg"] == "com.sony.dtv.sonyshelf")
    assert "entradas" in shelf["breaks"]
