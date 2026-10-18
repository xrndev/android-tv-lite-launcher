"""Dossier de la tele: inventario de paquetes de sistema con senales objetivas (docs/specs/device-dossier.md).

Solo lee (nunca modifica la tele) y es tolerante a fallos: si un comando no existe en esa version de Android,
esa senal queda a None y el resto sigue. Las pistas de riesgo son orientativas para quien revise: nunca activan
ni preseleccionan una eliminacion.
"""

from __future__ import annotations

import re
from typing import Callable, Optional

from . import __version__, android, debloat
from .adb import AdbError
from .device import DeviceInfo, _props
from .telemetry import scrub

SCHEMA = 1
HEURISTIC = 1
MAX_PACKAGES = 600

# Propiedades de identidad (ninguna identifica a la persona; el numero de serie NO se pide nunca).
_PROP_KEYS = (
    "ro.product.manufacturer", "ro.product.brand", "ro.product.model", "ro.product.device", "ro.product.name",
    "ro.product.board", "ro.board.platform", "ro.hardware", "ro.soc.manufacturer", "ro.soc.model",
    "ro.build.fingerprint", "ro.build.version.release", "ro.build.version.sdk", "ro.build.version.security_patch",
    "ro.product.cpu.abilist", "ro.build.characteristics",
)
_FEATURE_WORDS = ("leanback", "live_tv", "television", "software.leanback", "hdmi", "tv.")
_KEY_PERMS = {
    "android.permission.INTERNET": "internet",
    "android.permission.RECEIVE_BOOT_COMPLETED": "boot",
    "android.permission.SYSTEM_ALERT_WINDOW": "overlay",
}

_COMPONENT = re.compile(r"\b([A-Za-z][\w]*(?:\.[\w]+)+)/[\w.$]+")
_PACKAGE_NAME = re.compile(r"packageName=([A-Za-z][\w]*(?:\.[\w]+)+)")


def _safe(fn: Callable[[], object], default=None):
    """Una senal que falla no tumba el dossier."""
    try:
        return fn()
    except AdbError:
        raise  # perdida de conexion: que lo gestione quien llama
    except Exception:  # noqa: BLE001
        return default


def _packages_in(text: str) -> list[str]:
    """Paquetes citados en la salida de 'cmd package query-*' (formato 'pkg/.Clase' o 'packageName=pkg')."""
    found = _PACKAGE_NAME.findall(text) + _COMPONENT.findall(text)
    return found


def _query(adb, kind: str, action: str, category: Optional[str] = None) -> Optional[dict[str, int]]:
    """Cuantos componentes de cada paquete responden a esa accion. None si el comando no existe."""
    cmd = f"cmd package query-{kind} --brief -a {action}" + (f" -c {category}" if category else "")
    out = adb.shell(cmd, timeout=60)
    if "Unknown command" in out or "Error" in out[:40]:
        return None
    counts: dict[str, int] = {}
    for line in out.splitlines():
        match = _COMPONENT.search(line)
        if match:
            counts[match.group(1)] = counts.get(match.group(1), 0) + 1
    return counts


def parse_package_dump(text: str) -> dict[str, dict]:
    """Extrae version, banderas y permisos clave de 'dumpsys package packages' (Android 9-14)."""
    result: dict[str, dict] = {}
    current: Optional[dict] = None
    in_perms = False
    for line in text.splitlines():
        head = re.match(r"^  Package \[([\w.]+)\]", line)
        if head:
            name = head.group(1)
            # la seccion "Hidden system packages" repite el nombre con la version original: manda la primera
            current = None
            if name not in result:
                current = result[name] = {"version": "", "flags": "", "private_flags": "", "shared_user": "", "perms": set()}
            in_perms = False
            continue
        if re.match(r"^\S", line):  # nueva seccion de primer nivel
            current = None
            continue
        if current is None:
            continue
        stripped = line.strip()
        if stripped.startswith("versionName="):
            current["version"] = stripped.split("=", 1)[1]
        elif stripped.startswith("pkgFlags="):
            current["flags"] = stripped
        elif stripped.startswith("privateFlags="):
            current["private_flags"] = stripped
        elif stripped.startswith("sharedUser="):
            current["shared_user"] = stripped
        elif stripped.endswith("permissions:"):
            in_perms = stripped.startswith("requested permissions")
        elif in_perms:
            perm = stripped.split(":")[0]
            if perm in _KEY_PERMS:
                current["perms"].add(_KEY_PERMS[perm])
            elif not perm.startswith("android.") and not perm.startswith("com."):
                in_perms = False
    return result


def parse_meminfo(text: str) -> dict[str, int]:
    """PSS en MB por paquete a partir de 'dumpsys meminfo' (suma los procesos del mismo paquete)."""
    mem: dict[str, int] = {}
    for kb, proc in re.findall(r"^\s*([\d.,]+)K:\s+([\w.]+)(?::[\w.]+)?\s+\(pid", text, re.M):
        mem[proc] = mem.get(proc, 0) + int(re.sub(r"\D", "", kb) or 0) // 1024
    return mem


def risk_hint(entry: dict, protected: bool) -> str:
    """'core' | 'unknown' | 'low-signal'. Orientativo: lo decide una persona probando en una tele real."""
    shared = entry.get("shared_uid_system")
    if protected or entry.get("tv_input") or entry.get("home") or entry.get("ime") or entry.get("accessibility") or shared:
        return "core"
    quiet = (
        not entry.get("running") and not entry.get("boot_receivers")
        and not entry.get("privileged") and not entry.get("updated_system_app")
    )
    return "low-signal" if quiet else "unknown"


def known_packages(catalog: dict) -> set[str]:
    return {p["pkg"] for lst in catalog["lists"] for p in lst["packages"]}


def collect(adb, info: DeviceInfo, catalog: Optional[dict] = None, progress: Callable[[str], None] = lambda _m: None) -> dict:
    """Construye el dossier. Solo lectura. Nunca incluye apps de usuario, cuentas, red ni identificadores."""
    catalog = catalog or debloat.load_catalog()
    known = known_packages(catalog)
    props = _props(adb)

    progress("paquetes de sistema")
    system = sorted(android.list_system_packages(adb))
    progress("componentes de TV, launcher, teclado y accesibilidad")
    tv_input = _safe(lambda: _query(adb, "services", "android.media.tv.TvInputService"))
    home = _safe(lambda: _query(adb, "activities", "android.intent.action.MAIN", "android.intent.category.HOME"))
    ime = _safe(lambda: _query(adb, "services", "android.view.InputMethod"))
    access = _safe(lambda: _query(adb, "services", "android.accessibilityservice.AccessibilityService"))
    boot = _safe(lambda: _query(adb, "receivers", "android.intent.action.BOOT_COMPLETED"))
    progress("versiones y permisos")
    details = _safe(lambda: parse_package_dump(adb.shell("dumpsys package packages", timeout=180)), {}) or {}
    progress("memoria en uso")
    memory = _safe(lambda: parse_meminfo(adb.shell("dumpsys meminfo", timeout=120)), {}) or {}
    features = _safe(lambda: [
        line.split(":", 1)[1].split("=")[0] for line in adb.shell("pm list features").splitlines()
        if line.startswith("feature:") and any(w in line.lower() for w in _FEATURE_WORDS)
    ], []) or []

    def flag(table: Optional[dict], pkg: str) -> Optional[bool]:
        return None if table is None else pkg in table

    packages = []
    for pkg in system[:MAX_PACKAGES]:
        if pkg in known:
            packages.append({"pkg": pkg, "known": True})
            continue
        d = details.get(pkg, {})
        entry = {
            "pkg": pkg, "known": False, "version": scrub(d.get("version", ""))[:40],
            "updated_system_app": "UPDATED_SYSTEM_APP" in d.get("flags", "") if d else None,
            "privileged": "PRIVILEGED" in d.get("private_flags", "") if d else None,
            "shared_uid_system": "android.uid.system" in d.get("shared_user", "") if d else None,
            "tv_input": flag(tv_input, pkg), "home": flag(home, pkg), "ime": flag(ime, pkg), "accessibility": flag(access, pkg),
            "boot_receivers": (boot or {}).get(pkg, 0) if boot is not None else None,
            "ram_mb": memory.get(pkg), "running": (pkg in memory) if memory else None,
            "perms": sorted(d.get("perms", [])) if d else None,
        }
        entry["hint"] = risk_hint(entry, debloat.is_protected(pkg, catalog))
        packages.append(entry)

    return {
        "schema": SCHEMA, "kind": "dossier", "tvlite": __version__, "heuristic": HEURISTIC,
        "device": {
            **{k.replace("ro.", "", 1): scrub(props.get(k, ""))[:160] for k in _PROP_KEYS if props.get(k)},
            "ram_mb": info.ram_mb, "resolution": info.resolution, "density": info.density,
            "play_store": info.has_play_store, "simulated": info.simulated,
        },
        "features": sorted(features)[:60],
        "packages": packages,
        "system_total": len(system),
    }


def summarize(dossier: dict, lang: str = "es") -> str:
    """Resumen legible para el consentimiento: lo que se enviaria, en pocas lineas."""
    pk = dossier["packages"]
    unknown = [p for p in pk if not p.get("known")]
    hints = {h: sum(1 for p in unknown if p.get("hint") == h) for h in ("core", "unknown", "low-signal")}
    dev = dossier["device"]
    name = " ".join(x for x in (dev.get("product.manufacturer") or dev.get("product.brand"), dev.get("product.model")) if x)
    if lang == "es":
        return (f"Tele: {name or 'desconocida'} | Android {dev.get('build.version.release', '?')} | huella: {dev.get('build.fingerprint', '?')}\n"
                f"Paquetes de sistema: {dossier['system_total']} ({len(pk) - len(unknown)} ya conocidos, {len(unknown)} nuevos)\n"
                f"Pistas de los nuevos: {hints['core']} parecen esenciales, {hints['unknown']} sin clasificar, "
                f"{hints['low-signal']} con poca actividad (orientativo: nada se quita por esto)\n"
                "No incluye: apps instaladas por ti, cuentas, red, IP, MAC ni numero de serie.")
    return (f"TV: {name or 'unknown'} | Android {dev.get('build.version.release', '?')} | fingerprint: {dev.get('build.fingerprint', '?')}\n"
            f"System packages: {dossier['system_total']} ({len(pk) - len(unknown)} already known, {len(unknown)} new)\n"
            f"Hints for the new ones: {hints['core']} look essential, {hints['unknown']} unclassified, "
            f"{hints['low-signal']} low activity (advisory: nothing is removed because of this)\n"
            "Not included: apps you installed, accounts, network, IP, MAC or serial number.")
