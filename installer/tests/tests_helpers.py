"""Utilidad de pruebas: ejecuta el flujo completo contra un FakeAdb y devuelve (mensajes, resumen)."""

from fake_adb import LITE, FakeAdb
from tvlite import device, runner

PACKAGES = ["com.tcl.esticker", "com.tcl.messagebox", "com.google.android.play.games"]
USER_PACKAGES = ["com.tcl.hearaid"]


def run_flow(adb_kwargs, tmp_path, apk, apps=None, dry_run=False, allow_irreversible=False, preinstall_lite=False):
    adb = FakeAdb(packages=PACKAGES, user_packages=USER_PACKAGES, **adb_kwargs)
    if preinstall_lite:
        adb.pkgs[LITE] = {"installed": True, "enabled": True, "home": True, "system": False}
        adb.signature_conflict = True
    messages = []
    options = runner.Options(
        debloat_packages=set(PACKAGES + USER_PACKAGES), app_ids=apps or [], launcher_apk=apk,
        dry_run=dry_run, allow_irreversible=allow_irreversible,
    )
    summary = runner.run(adb, device.detect(adb), options, messages.append, backup_base=tmp_path / "bk")
    return messages, summary
