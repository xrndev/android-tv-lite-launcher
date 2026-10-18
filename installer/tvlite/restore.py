"""Deshace los cambios de un backup, de lo ultimo a lo primero."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import android
from .journal import Journal


@dataclass
class RestoreResult:
    restored: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failed


def undo(adb, reverse: dict, journal_dir: Path) -> tuple[bool, str]:
    """Deshace una operacion del diario. journal_dir resuelve las rutas relativas a los APK guardados."""
    op = reverse["op"]
    if op == "install_existing":
        return android.restore_package(adb, reverse["pkg"])
    if op == "install_apks":
        pkg = reverse["pkg"]
        files = [Path(journal_dir) / reverse["dir"] / name for name in reverse["files"]]
        if not all(f.is_file() for f in files):
            return False, "faltan los APK guardados de " + pkg
        adb.shell(f"pm uninstall {pkg}")  # limpia un posible registro 'fantasma' antes de reinstalar
        with android.adb_verification_off(adb):
            res = adb.install_multiple(files)
        ok = res.ok and "Success" in res.stdout and android.package_exists(adb, pkg)
        return ok, (res.stdout or res.stderr).strip()
    if op == "enable":
        return android.enable(adb, reverse["pkg"])
    if op == "setting":
        if reverse["value"] is None:
            android.delete_setting(adb, reverse["ns"], reverse["key"])
        else:
            android.put_setting(adb, reverse["ns"], reverse["key"], reverse["value"])
        return True, ""
    if op == "role":
        holder = reverse.get("holder")
        if holder:
            out = adb.shell(f"cmd role add-role-holder --user 0 {android.HOME_ROLE} {holder}")
            return True, out
        return True, ""
    if op == "uninstall":
        res = adb.uninstall(reverse["pkg"])
        return res.ok, res.stdout
    return False, f"operacion desconocida: {op}"


def restore(
    adb,
    journal_dir: Path,
    progress: Callable[[str], None] = lambda m: None,
    include_apps: bool = False,
) -> RestoreResult:
    """Revierte el diario. Las apps que el usuario eligio instalar se conservan salvo include_apps."""
    journal = Journal(journal_dir)
    result = RestoreResult()
    entries = [e for e in journal.entries() if e.get("ok") and e.get("reverse")]
    for entry in reversed(entries):
        reverse = entry["reverse"]
        if reverse["op"] == "uninstall" and entry["action"] == "app_install" and not include_apps:
            result.skipped.append(entry["target"])
            continue
        progress(f"Restaurando {entry['action']}: {entry['target']}")
        ok, detail = undo(adb, reverse, journal.dir)
        (result.restored if ok else result.failed).append(entry["target"])
        if not ok:
            progress(f"  No se pudo: {detail}")
    # El launcher original debe volver a ser el de Home.
    android.press(adb, "KEYCODE_HOME")
    return result
