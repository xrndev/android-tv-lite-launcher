"""Dossier: recoge senales de paquetes de sistema sin modificar la tele ni filtrar datos personales."""

import json

from tvlite import device, dossier
from fake_adb import FakeAdb

DUMP = """Packages:
  Package [com.vendor.shelf] (abc123):
    userId=1000
    sharedUser=SharedUserSetting{1a2b android.uid.system/1000}
    versionName=2.3.1
    pkgFlags=[ SYSTEM HAS_CODE UPDATED_SYSTEM_APP ]
    privateFlags=[ PRIVILEGED ]
    requested permissions:
      android.permission.INTERNET
      android.permission.RECEIVE_BOOT_COMPLETED
    install permissions:
  Package [com.vendor.quiet] (def456):
    versionName=1.0
    pkgFlags=[ SYSTEM HAS_CODE ]
    privateFlags=[ ]
Hidden system packages:
  Package [com.vendor.shelf] (zzz):
    versionName=1.0.0
"""
MEM = "  120,345K: com.vendor.shelf (pid 100 / activities)\n   30,000K: com.vendor.shelf:remote (pid 101)\n"


def make(**kw):
    return FakeAdb(packages=["com.vendor.shelf", "com.vendor.quiet", "com.vendor.tuner", "com.android.printspooler"],
                   user_packages=["com.netflix.mediaclient"], package_dump=DUMP, meminfo_dump=MEM, **kw)


def build(adb):
    return dossier.collect(adb, device.detect(adb))


def by_pkg(d):
    return {p["pkg"]: p for p in d["packages"]}


def test_only_system_packages_and_known_ones_carry_just_the_name():
    d = build(make())
    pk = by_pkg(d)
    assert "com.netflix.mediaclient" not in pk  # app de usuario: nunca
    assert pk["com.android.printspooler"] == {"pkg": "com.android.printspooler", "known": True}
    assert pk["com.vendor.shelf"]["known"] is False


def test_signals_are_parsed_from_dumps():
    shelf = by_pkg(build(make(queries={"android.intent.action.BOOT_COMPLETED": ["com.vendor.shelf/.Boot"]})))["com.vendor.shelf"]
    assert shelf["version"] == "2.3.1"  # manda la seccion principal, no la de "Hidden system packages"
    assert shelf["updated_system_app"] and shelf["privileged"] and shelf["shared_uid_system"]
    assert shelf["perms"] == ["boot", "internet"]
    assert shelf["boot_receivers"] == 1
    assert shelf["ram_mb"] == 146 or shelf["ram_mb"] == 117 + 29  # 120345K y 30000K del mismo paquete
    assert shelf["running"] is True


def test_tv_input_means_core_and_quiet_package_is_low_signal():
    adb = make(queries={"android.media.tv.TvInputService": ["com.vendor.tuner/.TunerService"]})
    pk = by_pkg(build(adb))
    assert pk["com.vendor.tuner"]["tv_input"] is True and pk["com.vendor.tuner"]["hint"] == "core"
    assert pk["com.vendor.quiet"]["hint"] == "low-signal"
    assert pk["com.vendor.shelf"]["hint"] == "core"  # uid de sistema


def test_missing_commands_leave_signals_none_instead_of_failing():
    adb = FakeAdb(packages=["com.vendor.quiet"])  # sin dumps: salidas vacias
    d = build(adb)
    entry = by_pkg(d)["com.vendor.quiet"]
    assert entry["updated_system_app"] is None and entry["perms"] is None


def test_nothing_personal_leaves_in_the_dossier():
    adb = make(props={"ro.serialno": "ABC123SECRET", "ro.build.fingerprint": "Sony/KD/x:11/RKQ1/1:user/release-keys"})
    adb.serial = "192.168.1.50:5555"
    text = json.dumps(build(adb))
    for secret in ("ABC123SECRET", "192.168.1.50", "netflix"):
        assert secret not in text
    assert "serial" not in text.lower()
    assert '"build.fingerprint": "Sony/KD/x:11/RKQ1/1:user/release-keys"' in text


def test_collect_is_read_only():
    adb = make()
    build(adb)
    assert not any(c.startswith(("pm uninstall", "pm disable", "settings put", "cmd package install", "pm enable")) for c in adb.log)


def test_summary_mentions_counts_in_both_languages():
    d = build(make())
    assert "nuevos" in dossier.summarize(d, "es") and "new" in dossier.summarize(d, "en")
