"""Apps de usuario (/data/app): al quitarlas con 'pm uninstall -k --user 0' se borra su APK y
'install-existing' deja un registro 'fantasma'. Por eso, antes de quitarlas, se guarda su APK en el
backup y la restauracion las reinstala desde ahi."""

from fake_adb import FakeAdb
from tvlite import android, debloat, device, restore
from tvlite.journal import Journal

SYSTEM_BLOAT = "com.tcl.esticker"
USER_BLOAT = "com.tcl.hearaid"


def make(**kw):
    return FakeAdb(packages=[SYSTEM_BLOAT], user_packages=[USER_BLOAT], **kw)


def plan_for(adb):
    info = device.detect(adb)
    return debloat.build_plan(info, android.list_packages(adb), system_packages=android.list_system_packages(adb))


def test_user_apps_are_preselected_because_they_are_now_restorable():
    plan = {i.pkg: i for i in plan_for(make())}
    assert plan[SYSTEM_BLOAT].selected and plan[SYSTEM_BLOAT].system
    assert plan[USER_BLOAT].selected and not plan[USER_BLOAT].system


def test_user_app_is_backed_up_removed_and_restored_from_its_apk(tmp_path):
    adb = make()
    journal = Journal(tmp_path / "j")
    result = debloat.apply_plan(adb, plan_for(adb), journal)
    assert USER_BLOAT in result.done and USER_BLOAT not in android.list_packages(adb)
    entry = next(e for e in journal.entries() if e["target"] == USER_BLOAT)
    assert entry["action"] == "debloat_user_app" and entry["reverse"]["op"] == "install_apks"
    saved = [journal.dir / entry["reverse"]["dir"] / name for name in entry["reverse"]["files"]]
    assert saved and all(f.is_file() and f.stat().st_size > 0 for f in saved)

    restored = restore.restore(adb, journal.dir)
    assert restored.ok
    assert USER_BLOAT in android.list_packages(adb) and SYSTEM_BLOAT in android.list_packages(adb)
    assert android.package_exists(adb, USER_BLOAT)  # un paquete real, no un registro fantasma


def test_user_app_is_not_removed_if_its_apk_cannot_be_saved(tmp_path):
    adb = make(pull_fails=True)
    result = debloat.apply_plan(adb, plan_for(adb), Journal(tmp_path / "j"))
    assert USER_BLOAT in android.list_packages(adb)  # se queda: sin copia no se garantiza la restauracion
    assert any(pkg == USER_BLOAT and "APK" in why for pkg, why in result.failed)
    assert SYSTEM_BLOAT in result.done  # las de sistema no dependen de la copia


def test_allow_irreversible_removes_it_anyway_and_says_so(tmp_path):
    adb = make(pull_fails=True)
    journal = Journal(tmp_path / "j")
    messages = []
    result = debloat.apply_plan(adb, plan_for(adb), journal, messages.append, allow_irreversible=True)
    assert USER_BLOAT in result.done
    entry = next(e for e in journal.entries() if e["target"] == USER_BLOAT)
    assert entry["action"] == "debloat_irreversible" and entry["reverse"] is None
    assert any("NO reversible" in m for m in messages)
    restore.restore(adb, journal.dir)
    assert SYSTEM_BLOAT in android.list_packages(adb)  # la de sistema vuelve
    assert USER_BLOAT not in android.list_packages(adb)  # la de usuario sin copia no: no se finge lo contrario


def test_restore_reports_failure_when_the_saved_apk_is_missing(tmp_path):
    adb = make()
    journal = Journal(tmp_path / "j")
    debloat.apply_plan(adb, plan_for(adb), journal)
    for f in (journal.dir / "apks").rglob("*.apk"):
        f.unlink()
    result = restore.restore(adb, journal.dir)
    assert not result.ok and USER_BLOAT in result.failed


def test_unhealthy_tv_rolls_back_user_apps_from_their_backup(tmp_path):
    adb = make(unhealthy_after_uninstalls=2)
    result = debloat.apply_plan(adb, plan_for(adb), Journal(tmp_path / "j"))
    assert result.aborted and not result.done
    assert USER_BLOAT in android.list_packages(adb) and SYSTEM_BLOAT in android.list_packages(adb)


def test_ghost_record_is_still_detected_if_a_user_app_is_restored_without_backup():
    adb = make()
    android.uninstall_user0(adb, USER_BLOAT)
    ok, detail = android.restore_package(adb, USER_BLOAT)
    assert not ok and "Play Store" in detail and USER_BLOAT not in adb.pkgs
