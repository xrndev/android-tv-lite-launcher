"""Informe anonimo de una tele, listo para pegar en un issue de GitHub (es lo que alimenta la tabla de
dispositivos y las listas de paquetes de cada marca).

Privacidad: solo incluye datos del modelo y los NOMBRES de paquetes de SISTEMA. No incluye el numero de
serie, la IP, cuentas, nombres de red ni las apps que haya instalado el usuario. El usuario debe
revisarlo antes de publicarlo."""

from __future__ import annotations

from typing import Optional

from . import __version__, android, debloat
from .device import DeviceInfo, describe

# Paquetes de sistema "normales" de Android/Google: no son candidatos a lista de una marca.
_STANDARD_PREFIXES = ("android.", "com.android.", "com.google.android.", "com.google.", "org.chromium")


def vendor_packages(adb, catalog: Optional[dict] = None) -> list[str]:
    """Paquetes de sistema que no son de Android/Google, no estan protegidos ni salen en ninguna lista:
    los que habria que revisar para crear una lista nueva para esta marca."""
    catalog = catalog or debloat.load_catalog()
    known = {entry["pkg"] for lst in catalog["lists"] for entry in lst["packages"]}
    return sorted(
        pkg
        for pkg in android.list_system_packages(adb)
        if not pkg.startswith(_STANDARD_PREFIXES) and not debloat.is_protected(pkg, catalog) and pkg not in known
    )


def build_report(adb, info: DeviceInfo, catalog: Optional[dict] = None) -> str:
    catalog = catalog or debloat.load_catalog()
    installed = android.list_packages(adb)
    system = android.list_system_packages(adb)
    plan = debloat.build_plan(info, installed, catalog, system_packages=system)
    metrics = android.memory_snapshot(adb)
    homes = android.home_packages(adb)
    selected = [i for i in plan if i.selected]
    vendor = vendor_packages(adb, catalog)

    lines = [
        f"### TV report (tvlite {__version__})",
        "",
        f"- **Device:** {' '.join(p for p in (info.manufacturer or info.brand, info.model) if p) or 'unknown'}",
        f"- **Android:** {info.android_release} (API {info.sdk}) - **ABI:** {', '.join(info.abis) or 'unknown'}",
        f"- **SoC / platform:** {info.soc or 'unknown'}",
        f"- **RAM:** {info.ram_mb} MB (profile: {info.profile}) - **available now:** {metrics['ram_available_mb']} MB",
        f"- **Play Store:** {'yes' if info.has_play_store else 'NO (apps cannot be installed from it)'}",
        f"- **Free storage:** {info.storage_free_mb if info.storage_free_mb is not None else 'unknown'} MB",
        f"- **Screen:** {info.resolution or 'unknown'} ({info.density or '?'} dpi)",
        f"- **Launcher(s):** {', '.join(homes) or 'unknown'}",
        f"- **Packages:** {len(installed)} installed, {len(system)} system",
        "",
        f"**tvlite plan:** {len(selected)} of {len(plan)} known packages would be removed "
        f"({sum(1 for i in selected if i.system)} system, {sum(1 for i in selected if not i.system)} user apps)",
    ]
    if plan:
        lines += ["", "<details><summary>Plan</summary>", ""]
        lines += [f"- `{i.pkg}` ({i.tier}{'' if i.system else ', user app'}){' - ' + i.breaks if i.breaks else ''}" for i in plan]
        lines += ["", "</details>"]
    lines += [
        "",
        f"**Vendor system packages not in any list ({len(vendor)}) - candidates for a new list:**",
        "",
    ]
    lines += [f"- `{pkg}`" for pkg in vendor[:120]] or ["- (none)"]
    if len(vendor) > 120:
        lines.append(f"- ... and {len(vendor) - 120} more")
    lines += [
        "",
        "> Only the model and the names of *system* packages are listed: no serial number, IP, accounts or user "
        "apps. Please review before posting.",
    ]
    return "\n".join(lines) + "\n"


def describe_for_cli(info: DeviceInfo) -> str:
    return describe(info)
