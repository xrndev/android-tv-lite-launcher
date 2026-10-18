"""Las apps de usuario (/data/app) pierden el APK al quitarlas: no se pueden restaurar con
install-existing, que ademas deja un registro 'fantasma'. Estas pruebas fijan ese comportamiento."""

from fake_adb import FakeAdb
from tvlite import android, debloat, device, restore
from tvlite.journal import Journal

SYSTEM_BLOAT = "com.tcl.esticker"
USER_BLOAT = "com.tcl.hearaid"


def make():
    return FakeAdb(packages=[SYSTEM_BLOAT], user_packages=[USER_BLOAT])


def plan_for(adb, **kw):
    info = device.detect(adb)
    return {
        i.pkg: i
        for i in debloat.build_plan(
            info, android.list_packages(adb), system_packages=android.list_system_packages(adb), **kw
        )
    }


def test_user_apps_are_not_preselected():
    plan = plan_for(make())
    assert plan[SYSTEM_BLOAT].selected and plan[SYSTEM_BLOAT].system
    assert not plan[USER_BLOAT].selected and not plan[USER_BLOAT].system


def test_allow_irreversible_preselects_user_apps():
    assert plan_for(make(), allow_irreversible=True)[USER_BLOAT].selected


def test_restore_package_detects_ghost_and_cleans_it():
    adb = make()
    android.uninstall_user0(adb, USER_BLOAT)
    ok, detail = android.restore_package(adb, USER_BLOAT)
    assert not ok and "Play Store" in detail
    assert USER_BLOAT not in adb.pkgs  # el registro fantasma se limpia


def test_system_app_restores_fine():
    adb = make()
    android.uninstall_user0(adb, SYSTEM_BLOAT)
    assert SYSTEM_BLOAT not in android.list_packages(adb)
    ok, _ = android.restore_package(adb, SYSTEM_BLOAT)
    assert ok and SYSTEM_BLOAT in android.list_packages(adb)


def test_forced_removal_of_user_app_is_journaled_as_irreversible(tmp_path):
    adb = make()
    plan = plan_for(adb, allow_irreversible=True)
    journal = Journal(tmp_path / "j")
    result = debloat.apply_plan(adb, list(plan.values()), journal)
    assert USER_BLOAT in result.done and SYSTEM_BLOAT in result.done
    entry = next(e for e in journal.entries() if e["target"] == USER_BLOAT)
    assert entry["action"] == "debloat_irreversible" and entry["reverse"] is None
    restore.restore(adb, journal.dir)
    assert SYSTEM_BLOAT in android.list_packages(adb)  # la app de sistema vuelve
    assert USER_BLOAT not in android.list_packages(adb)  # la de usuario no: no se finge lo contrario
