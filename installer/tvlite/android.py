"""Operaciones de Android por ADB. Todo comando de la tele pasa por aqui, para poder simularlo en tests."""

from __future__ import annotations

import contextlib
import re
import time
from typing import Iterator, Optional

HOME_ROLE = "android.app.role.HOME"
_RESUMED = re.compile(r"ResumedActivity: ActivityRecord\{\S+ u\d+ ([\w.]+)/(\S+?)(?: t\d+)?\}")
_COMPONENT = re.compile(r"^([\w.]+)/(\S+)$")


def list_packages(adb, flag: str = "") -> set[str]:
    out = adb.shell(f"pm list packages {flag}".strip(), timeout=120)
    return {line.split(":", 1)[1].strip() for line in out.splitlines() if line.startswith("package:")}


def list_system_packages(adb) -> set[str]:
    """Apps de sistema: son las unicas cuya eliminacion para el usuario 0 se puede deshacer."""
    return list_packages(adb, "-s")


def package_exists(adb, package: str) -> bool:
    """True si el paquete tiene APK real (un registro 'fantasma' no devuelve ruta)."""
    return adb.shell(f"pm path {package}").strip().startswith("package:")


def is_installed(adb, package: str) -> bool:
    return package in list_packages(adb)


def uninstall_user0(adb, package: str) -> tuple[bool, str]:
    """Quita el paquete solo para el usuario 0 (-k conserva datos): reversible con restore_package."""
    out = adb.shell(f"pm uninstall -k --user 0 {package}")
    return "Success" in out, out


def restore_package(adb, package: str) -> tuple[bool, str]:
    """Reactiva un paquete quitado con uninstall_user0. Solo funciona con apps de sistema: en una
    app de usuario el APK se borro, install-existing dice 'installed' pero deja un registro fantasma,
    asi que se verifica que el paquete exista de verdad y, si no, se limpia el fantasma."""
    out = adb.shell(f"cmd package install-existing {package}")
    if "installed for user" not in out:
        return False, out
    if package_exists(adb, package):
        return True, out
    adb.shell(f"pm uninstall {package}")
    return False, "sin APK (app de usuario): hay que reinstalarla desde Play Store"


def disable_user(adb, package: str) -> tuple[bool, str]:
    out = adb.shell(f"pm disable-user --user 0 {package}")
    return "disabled" in out, out


def enable(adb, package: str) -> tuple[bool, str]:
    out = adb.shell(f"pm enable {package}")
    return "enabled" in out, out


def get_setting(adb, namespace: str, key: str) -> Optional[str]:
    out = adb.shell(f"settings get {namespace} {key}")
    return None if out in ("", "null") else out


def put_setting(adb, namespace: str, key: str, value: str) -> None:
    adb.shell(f"settings put {namespace} {key} {value}")


def delete_setting(adb, namespace: str, key: str) -> None:
    adb.shell(f"settings delete {namespace} {key}")


VERIFY_ADB_KEY = "verifier_verify_adb_installs"


@contextlib.contextmanager
def adb_verification_off(adb, journal=None) -> Iterator[None]:
    """Desactiva SOLO la verificacion de Play Protect de las instalaciones hechas por ADB mientras dura
    el bloque. Sin esto, una tele con Play Protect abre un dialogo en pantalla al instalar un APK
    desconocido y la instalacion se queda esperando indefinidamente. El ajuste se anota en el diario
    (por si el programa se interrumpe) y siempre se devuelve a su valor original."""
    previous = get_setting(adb, "global", VERIFY_ADB_KEY)
    put_setting(adb, "global", VERIFY_ADB_KEY, "0")
    if journal is not None:
        journal.record(
            "setting", VERIFY_ADB_KEY,
            reverse={"op": "setting", "ns": "global", "key": VERIFY_ADB_KEY, "value": previous},
        )
    try:
        yield
    finally:
        if previous is None:
            delete_setting(adb, "global", VERIFY_ADB_KEY)
        else:
            put_setting(adb, "global", VERIFY_ADB_KEY, previous)


def press(adb, key: str) -> None:
    adb.shell(f"input keyevent {key}")


def boot_completed(adb) -> bool:
    return adb.shell("getprop sys.boot_completed") == "1"


def resumed_activity(adb) -> Optional[str]:
    """Componente en primer plano ('paquete/Actividad') o None si no se puede leer."""
    out = adb.shell("dumpsys activity activities", timeout=120)
    match = _RESUMED.search(out)
    return f"{match.group(1)}/{match.group(2)}" if match else None


def resolve_home(adb) -> Optional[str]:
    """Componente que Android usaria ahora para el boton Home."""
    out = adb.shell(
        "cmd package resolve-activity --brief -c android.intent.category.HOME "
        "-a android.intent.action.MAIN"
    )
    for line in reversed(out.splitlines()):
        line = line.strip()
        if _COMPONENT.match(line):
            return line
    return None


def home_packages(adb) -> list[str]:
    """Paquetes que declaran un launcher (categoria HOME), incluido el original."""
    out = adb.shell(
        "cmd package query-activities --brief -a android.intent.action.MAIN "
        "-c android.intent.category.HOME"
    )
    found: list[str] = []
    for line in out.splitlines():
        line = line.strip()
        match = _COMPONENT.match(line)
        if match and match.group(1) not in found:
            found.append(match.group(1))
    current = resolve_home(adb)
    if current:
        pkg = current.split("/", 1)[0]
        if pkg not in found:
            found.append(pkg)
    return found


def package_of(component: Optional[str]) -> Optional[str]:
    return component.split("/", 1)[0] if component else None


def wait_for(predicate, timeout: float = 20.0, interval: float = 1.0) -> bool:
    """Espera a que predicate() sea cierto; los tests la parchean para no dormir."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(interval)
    return bool(predicate())
