"""Instalar el Lite Launcher y hacerlo launcher por defecto, con retroceso si algo falla.

Orden prudente: 1) instalar, 2) comprobar que arranca (sin tocar nada mas), 3) asignarlo
como HOME, 4) solo si Android sigue eligiendo el original, desactivar ESE paquete (no se
desinstala) y comprobar otra vez. Si no se consigue, se deja todo como estaba.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from . import android
from .journal import Journal

LITE_PKG = "dev.xrndev.litelauncher"
LITE_COMPONENT = f"{LITE_PKG}/.MainActivity"
MAX_DISABLE_ROUNDS = 3


class LauncherError(RuntimeError):
    """No se pudo dejar el launcher nuevo funcionando; la tele queda como estaba."""


@dataclass
class LauncherResult:
    original: Optional[str] = None
    disabled: list[str] = field(default_factory=list)
    used_role: bool = False


def find_launcher_apk() -> Optional[Path]:
    """APK del launcher: variable de entorno, incluido en el paquete o compilado en el repo."""
    candidates = []
    if os.environ.get("TVLITE_LAUNCHER_APK"):
        candidates.append(Path(os.environ["TVLITE_LAUNCHER_APK"]))
    here = Path(__file__).parent
    candidates += [
        here / "data" / "litelauncher.apk",
        here.parent.parent / "launcher" / "build" / "litelauncher.apk",
    ]
    return next((c for c in candidates if c.is_file()), None)


def _is_lite_home(adb) -> bool:
    return (
        android.package_of(android.resolve_home(adb)) == LITE_PKG
        and android.package_of(android.resumed_activity(adb)) == LITE_PKG
    )


def _press_home_and_check(adb, timeout: float = 15.0) -> bool:
    android.press(adb, "KEYCODE_HOME")
    return android.wait_for(lambda: _is_lite_home(adb), timeout=timeout, interval=1.0)


def _rollback(adb, journal: Journal, result: LauncherResult, progress) -> None:
    progress("Deshaciendo: se restaura el launcher original")
    for pkg in reversed(result.disabled):
        ok, _ = android.enable(adb, pkg)
        journal.record("launcher_rollback_enable", pkg, ok=ok)
    previous = android.package_of(result.original)
    if previous and previous != LITE_PKG:
        adb.shell(f"cmd role add-role-holder --user 0 {android.HOME_ROLE} {previous}")
    adb.uninstall(LITE_PKG)
    journal.record("launcher_rollback_uninstall", LITE_PKG)
    android.press(adb, "KEYCODE_HOME")


def activate(
    adb,
    journal: Journal,
    apk: Path,
    progress: Callable[[str], None] = lambda m: None,
    sdk: int = 30,
) -> LauncherResult:
    result = LauncherResult(original=android.resolve_home(adb))
    original_pkg = android.package_of(result.original)
    progress(f"Launcher original: {result.original or 'desconocido'}")

    progress("Instalando el launcher nuevo")
    with android.adb_verification_off(adb, journal):
        res = adb.install(apk)
    if not res.ok or "Success" not in res.stdout:
        raise LauncherError(f"No se pudo instalar el launcher: {res.stdout or res.stderr}")
    journal.record("launcher_install", LITE_PKG, reverse={"op": "uninstall", "pkg": LITE_PKG})

    # Paso 2: comprobar que arranca ANTES de cambiar el launcher por defecto.
    adb.shell(f"am start -n {LITE_COMPONENT}")
    if not android.wait_for(lambda: android.package_of(android.resumed_activity(adb)) == LITE_PKG, timeout=20):
        _rollback(adb, journal, result, progress)
        raise LauncherError("El launcher nuevo no llego a abrirse en la tele")

    # Paso 3: asignarlo como HOME (Android 10+ usa roles).
    if sdk >= 29:
        adb.shell(f"cmd role add-role-holder --user 0 {android.HOME_ROLE} {LITE_PKG}")
        journal.record(
            "launcher_role", LITE_PKG,
            reverse={"op": "role", "holder": original_pkg if original_pkg != LITE_PKG else None},
        )
        result.used_role = True
    else:
        adb.shell(f"cmd package set-home-activity {LITE_COMPONENT}")
    if _press_home_and_check(adb):
        progress("Launcher nuevo activo")
        return result

    # Paso 4: algunas teles siguen eligiendo el original: se desactiva (no se desinstala).
    for _ in range(MAX_DISABLE_ROUNDS):
        current = android.package_of(android.resolve_home(adb))
        if not current or current == LITE_PKG or current in result.disabled:
            break
        progress(f"Desactivando el launcher original {current} (reversible)")
        ok, out = android.disable_user(adb, current)
        journal.record(
            "launcher_disable", current,
            reverse={"op": "enable", "pkg": current} if ok else None, ok=ok, detail=out,
        )
        if not ok:
            break
        result.disabled.append(current)
        if _press_home_and_check(adb):
            progress("Launcher nuevo activo")
            return result

    _rollback(adb, journal, result, progress)
    raise LauncherError("Android no usa el launcher nuevo como pantalla de inicio; se ha restaurado el original")
