"""Plan y aplicacion del debloat. Reglas de seguridad:
- solo se tocan paquetes de las listas revisadas (nada de 'lo que parezca bloat');
- los paquetes protegidos no se quitan nunca, aunque aparezcan en una lista;
- las listas sin 'verified_on' se ignoran salvo que se pida expresamente;
- se actua por lotes pequenos con comprobacion de salud y retroceso del lote si falla.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional

from . import android, restore as restore_mod
from .device import DeviceInfo
from .journal import Journal

DATA = Path(__file__).parent / "data"
TIERS = ("safe", "recommended", "aggressive", "optional")
# Que niveles se preseleccionan segun la RAM. 'optional' nunca se preselecciona.
PROFILE_TIERS = {
    "normal": {"safe"},
    "low": {"safe", "recommended"},
    "ultra_low": {"safe", "recommended", "aggressive"},
}
BATCH_SIZE = 8


@dataclass
class PlanItem:
    pkg: str
    label: str
    list_id: str
    list_name: str
    tier: str
    breaks: str = ""
    verified: bool = True
    selected: bool = False
    system: bool = True  # False = app de usuario: antes de quitarla se guarda su APK para poder restaurarla


@dataclass
class ApplyResult:
    done: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    rolled_back: list[str] = field(default_factory=list)
    aborted: bool = False


def load_catalog(extra_files: Iterable[Path] = ()) -> dict:
    """Carga packages.json y, si existen, las listas de la comunidad (data/community/*.json)."""
    catalog = json.loads((DATA / "packages.json").read_text(encoding="utf-8"))
    files = sorted((DATA / "community").glob("*.json")) if (DATA / "community").is_dir() else []
    # TVLITE_EXTRA_LISTS (rutas separadas por os.pathsep): para probar una lista propia antes de proponerla.
    env_files = [Path(p) for p in os.environ.get("TVLITE_EXTRA_LISTS", "").split(os.pathsep) if p]
    for path in [*files, *env_files, *extra_files]:
        extra = json.loads(Path(path).read_text(encoding="utf-8"))
        catalog["lists"].extend(extra.get("lists", []))
    return catalog


def is_protected(pkg: str, catalog: dict) -> bool:
    return (
        pkg in catalog["protected_exact"]
        or any(pkg.startswith(p) for p in catalog["protected_prefixes"])
        or any(pkg.endswith(s) for s in catalog["protected_suffixes"])
    )


def validate_catalog(catalog: dict) -> list[str]:
    """Problemas de una lista (para tests y CI de las contribuciones)."""
    problems: list[str] = []
    seen: dict[str, str] = {}
    for lst in catalog["lists"]:
        for entry in lst["packages"]:
            pkg = entry["pkg"]
            if is_protected(pkg, catalog):
                problems.append(f"{lst['id']}: {pkg} esta protegido y no puede estar en una lista")
            if entry["tier"] not in TIERS:
                problems.append(f"{lst['id']}: {pkg} tiene un tier desconocido ({entry['tier']})")
            if pkg in seen:
                problems.append(f"{pkg} aparece en {seen[pkg]} y en {lst['id']}")
            seen[pkg] = lst["id"]
        if not lst.get("verified_on") and not lst.get("notes"):
            problems.append(f"{lst['id']}: sin verified_on debe llevar 'notes' explicando de donde sale")
    return problems


def _matches(lst: dict, device: DeviceInfo) -> bool:
    match = lst.get("match") or {}
    for key, wanted in match.items():
        actual = {
            "manufacturer": device.manufacturer,
            "brand": device.brand,
            "model": device.model,
            "soc": device.soc,
        }.get(key, "").lower()
        if not any(w.lower() in actual for w in wanted):
            return False
    return True


def build_plan(
    device: DeviceInfo,
    installed: set[str],
    catalog: Optional[dict] = None,
    include_unverified: bool = False,
    system_packages: Optional[set[str]] = None,
) -> list[PlanItem]:
    """Paquetes de las listas que existen en esta tele, con su preseleccion segun la RAM.
    Las apps de usuario (no de sistema) tambien se preseleccionan: antes de quitarlas se guarda su APK.
    Si no se conoce la lista de apps de sistema (None) se asume que todas lo son."""
    catalog = catalog or load_catalog()
    preselect = PROFILE_TIERS[device.profile]
    plan: list[PlanItem] = []
    taken: set[str] = set()
    for lst in catalog["lists"]:
        verified = bool(lst.get("verified_on"))
        if not _matches(lst, device) or (not verified and not include_unverified):
            continue
        for entry in lst["packages"]:
            pkg = entry["pkg"]
            if pkg not in installed or pkg in taken or is_protected(pkg, catalog):
                continue
            taken.add(pkg)
            is_system = system_packages is None or pkg in system_packages
            plan.append(
                PlanItem(
                    pkg=pkg,
                    label=entry.get("label", pkg),
                    list_id=lst["id"],
                    list_name=lst["name"],
                    tier=entry["tier"],
                    breaks=entry.get("breaks", ""),
                    verified=verified,
                    selected=entry["tier"] in preselect and verified,
                    system=is_system,
                )
            )
    return plan


def backup_apks(adb, package: str, dest: Path) -> Optional[list[str]]:
    """Copia al PC los APK (base y splits) de una app de usuario. Devuelve los nombres de fichero o None
    si no se pudo guardar alguno: sin copia completa no se puede garantizar la restauracion."""
    out = adb.shell(f"pm path {package}")
    remote = [line.split(":", 1)[1].strip() for line in out.splitlines() if line.startswith("package:")]
    if not remote:
        return None
    dest.mkdir(parents=True, exist_ok=True)
    names: list[str] = []
    for index, path in enumerate(remote):
        local = dest / f"{index}-{path.rsplit('/', 1)[-1]}"
        res = adb.pull(path, local)
        if not res.ok or not local.is_file() or local.stat().st_size == 0:
            return None
        names.append(local.name)
    return names


def default_health_check(adb) -> bool:
    try:
        return android.boot_completed(adb) and adb.shell("echo ok") == "ok"
    except Exception:  # noqa: BLE001 - cualquier fallo de ADB cuenta como tele no sana
        return False


def apply_plan(
    adb,
    items: Iterable[PlanItem],
    journal: Journal,
    progress: Callable[[str], None] = lambda m: None,
    dry_run: bool = False,
    catalog: Optional[dict] = None,
    health_check: Callable[[object], bool] = default_health_check,
    allow_irreversible: bool = False,
) -> ApplyResult:
    """allow_irreversible: quitar una app de usuario aunque no se pueda guardar su APK (no se podra
    restaurar). Por defecto, si la copia falla, esa app NO se quita."""
    catalog = catalog or load_catalog()
    selected = [i for i in items if i.selected]
    result = ApplyResult()
    for start in range(0, len(selected), BATCH_SIZE):
        batch = selected[start : start + BATCH_SIZE]
        batch_done: list[str] = []
        reverses: dict[str, Optional[dict]] = {}
        for item in batch:
            if is_protected(item.pkg, catalog):  # defensa en profundidad
                result.failed.append((item.pkg, "paquete protegido"))
                continue
            if dry_run:
                progress(f"[simulacion] quitaria {item.pkg} ({item.label})")
                continue
            reverse: Optional[dict] = None
            action = "debloat"
            if item.system:
                reverse = {"op": "install_existing", "pkg": item.pkg}
            else:
                files = backup_apks(adb, item.pkg, journal.apk_dir(item.pkg))
                if files:
                    reverse = {"op": "install_apks", "pkg": item.pkg, "dir": f"apks/{item.pkg}", "files": files}
                    action = "debloat_user_app"
                elif not allow_irreversible:
                    result.failed.append((item.pkg, "no se pudo guardar su APK; no se quita para poder restaurarla"))
                    progress(f"No se quita {item.pkg}: no se pudo guardar su APK para restaurarla")
                    continue
                else:
                    action = "debloat_irreversible"
            ok, out = android.uninstall_user0(adb, item.pkg)
            journal.record(action, item.pkg, reverse=reverse if ok else None, ok=ok, detail=out)
            if ok:
                batch_done.append(item.pkg)
                reverses[item.pkg] = reverse
                note = {"debloat": "", "debloat_user_app": " (APK guardado para restaurar)",
                        "debloat_irreversible": " [NO reversible]"}[action]
                progress(f"Quitado {item.pkg} ({item.label}){note}")
            else:
                result.failed.append((item.pkg, out))
                progress(f"No se pudo quitar {item.pkg}: {out}")
        if dry_run:
            continue
        if not health_check(adb):
            progress("La tele no responde bien tras este lote: se deshace y se detiene el proceso")
            for pkg in reversed(batch_done):
                reverse = reverses.get(pkg)
                ok = bool(reverse) and restore_mod.undo(adb, reverse, journal.dir)[0]
                journal.record("debloat_rollback", pkg, ok=ok)
                if ok:
                    result.rolled_back.append(pkg)
            result.aborted = True
            return result
        result.done.extend(batch_done)
    return result
