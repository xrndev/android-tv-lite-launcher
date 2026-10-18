"""Orquesta el flujo completo: conectar, detectar, backup, debloat, ajustes, apps y launcher."""

from __future__ import annotations

import contextlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from . import android, appinstall, debloat, device as devmod, launcher
from .adb import Adb, AdbError
from .journal import Journal, TRACKED_SETTINGS, snapshot

ANIMATION_BY_PROFILE = {"ultra_low": "0", "low": "0.5"}
_IP = re.compile(r"^\d{1,3}(\.\d{1,3}){3}(:\d{1,5})?$")


class NotAuthorized(AdbError):
    """La tele aun no ha aceptado esta clave de depuracion."""


@dataclass
class Options:
    debloat_packages: set[str] = field(default_factory=set)  # paquetes del plan elegidos por el usuario
    app_ids: list[str] = field(default_factory=list)
    activate_launcher: bool = True
    tweaks: bool = True
    dry_run: bool = False
    include_unverified: bool = False
    allow_irreversible: bool = False  # quitar apps de usuario aunque no se pueda guardar su APK
    keep_awake: bool = True  # evita que la tele se duerma (y corte ADB) a mitad del proceso
    launcher_apk: Optional[Path] = None


@dataclass
class Summary:
    backup_dir: Optional[Path] = None
    debloat: Optional[debloat.ApplyResult] = None
    apps: list[appinstall.AppResult] = field(default_factory=list)
    launcher: Optional[launcher.LauncherResult] = None
    launcher_error: str = ""
    dry_run: bool = False
    error: str = ""  # conexion perdida u otro fallo a mitad: el backup permite restaurar
    metrics_before: Optional[dict] = None
    metrics_after: Optional[dict] = None


def normalize_target(text: str) -> str:
    """'192.168.1.5' -> '192.168.1.5:5555'. Valida el formato antes de llamar a ADB."""
    text = text.strip()
    if not _IP.match(text):
        raise ValueError("La direccion IP debe tener el formato 192.168.1.50 (o 192.168.1.50:5555)")
    host = text.split(":")[0]
    if any(int(p) > 255 for p in host.split(".")):
        raise ValueError("La direccion IP no es valida")
    return text if ":" in text else f"{text}:5555"


def _device_status(devices_output: str, target: str) -> str:
    for line in devices_output.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == target:
            return parts[1]
    return ""


def connect(adb: Adb, target: str, progress: Callable[[str], None] = lambda m: None) -> devmod.DeviceInfo:
    target = normalize_target(target)
    progress(f"Conectando con {target}")
    res = adb.connect(target)
    text = (res.stdout + res.stderr).lower()
    if "failed to authenticate" in text or "unauthorized" in text:
        raise NotAuthorized("Acepta el dialogo 'Permitir depuracion USB' en la tele y vuelve a intentarlo")
    if "connected" not in text:
        raise AdbError(f"No se pudo conectar: {(res.stdout + res.stderr).strip()}")
    adb.serial = target
    status = _device_status(adb.devices(), target)
    if status == "unauthorized":
        raise NotAuthorized("Acepta el dialogo 'Permitir depuracion USB' en la tele y vuelve a intentarlo")
    if status != "device":
        raise AdbError(f"La tele aparece como '{status or 'no encontrada'}'; comprueba la depuracion por red")
    return devmod.detect(adb, serial=target)


def apply_tweaks(adb, journal: Journal, profile: str, progress) -> None:
    value = ANIMATION_BY_PROFILE.get(profile)
    if not value:
        return
    for key in TRACKED_SETTINGS:
        previous = android.get_setting(adb, "global", key)
        android.put_setting(adb, "global", key, value)
        journal.record("setting", key, reverse={"op": "setting", "ns": "global", "key": key, "value": previous})
    progress(f"Animaciones del sistema a {value}x")


def format_metrics(before: Optional[dict], after: Optional[dict]) -> str:
    if not before or not after:
        return ""
    return (
        f"RAM disponible: {before['ram_available_mb']} MB -> {after['ram_available_mb']} MB | "
        f"paquetes: {before['packages']} -> {after['packages']} "
        "(la RAM suele mejorar mas tras reiniciar la tele)"
    )


def run(
    adb: Adb,
    info: devmod.DeviceInfo,
    options: Options,
    progress: Callable[[str], None] = lambda m: None,
    backup_base: Optional[Path] = None,
) -> Summary:
    summary = Summary(dry_run=options.dry_run)
    journal = Journal.new(info, base=backup_base)
    summary.backup_dir = journal.dir
    try:
        awake = android.keep_awake(adb, journal) if options.keep_awake and not options.dry_run else contextlib.nullcontext()
        with awake:
            _run_steps(adb, info, options, progress, journal, summary)
    except AdbError as exc:
        # La tele se durmio o se cayo la red y no se pudo recuperar: no se pierde nada, el diario ya
        # esta en disco y 'restore' deshace lo aplicado hasta ahora.
        summary.error = f"Se perdio la conexion con la tele ({exc}). Copia de seguridad en {journal.dir}"
        progress(summary.error)
    return summary


def _run_steps(adb, info, options, progress, journal, summary) -> None:
    progress(f"Guardando el estado original en {journal.dir}")
    snapshot(adb, journal, info)
    summary.metrics_before = android.memory_snapshot(adb)

    catalog = debloat.load_catalog()
    plan = debloat.build_plan(
        info, android.list_packages(adb), catalog, options.include_unverified,
        system_packages=android.list_system_packages(adb),
    )
    for item in plan:
        item.selected = item.pkg in options.debloat_packages
    summary.debloat = debloat.apply_plan(
        adb, plan, journal, progress, dry_run=options.dry_run, catalog=catalog,
        allow_irreversible=options.allow_irreversible,
    )
    if summary.debloat.aborted:
        return

    if options.dry_run:
        progress("Simulacion terminada: no se ha cambiado nada en la tele")
        return

    if options.tweaks:
        apply_tweaks(adb, journal, info.profile, progress)

    catalog_apps = {a["id"]: a for a in appinstall.load_apps()["apps"]}
    for app_id in options.app_ids:
        app = catalog_apps.get(app_id)
        if app:
            summary.apps.append(appinstall.install_app(adb, app, info.abis, journal, progress))

    if options.activate_launcher:
        apk = options.launcher_apk or launcher.find_launcher_apk()
        if not apk:
            summary.launcher_error = "No se encuentra el APK del launcher (litelauncher.apk)"
        else:
            try:
                summary.launcher = launcher.activate(adb, journal, apk, progress, sdk=info.sdk)
            except launcher.LauncherError as exc:
                summary.launcher_error = str(exc)

    summary.metrics_after = android.memory_snapshot(adb)
    journal.write_json("metrics.json", {"before": summary.metrics_before, "after": summary.metrics_after})
    line = format_metrics(summary.metrics_before, summary.metrics_after)
    if line:
        progress(line)
