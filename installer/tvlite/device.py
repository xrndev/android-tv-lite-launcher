"""Detecta que tele es (marca, modelo, SoC, RAM...) y decide el perfil de optimizacion."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Optional

# Umbrales sobre MemTotal (una tele "de 1 GB" reporta ~940 MB, una de 2 GB ~1,8 GB).
ULTRA_LOW_MB = 1200
LOW_MB = 2200


@dataclass
class DeviceInfo:
    serial: str = ""
    manufacturer: str = ""
    brand: str = ""
    model: str = ""
    device: str = ""
    android_release: str = ""
    sdk: int = 0
    abis: list[str] = field(default_factory=list)
    soc: str = ""
    ram_mb: int = 0
    storage_free_mb: Optional[int] = None
    density: Optional[int] = None
    resolution: Optional[str] = None
    simulated: bool = False

    @property
    def profile(self) -> str:
        return ram_profile(self.ram_mb)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["profile"] = self.profile
        return data


def ram_profile(ram_mb: int) -> str:
    """'ultra_low' | 'low' | 'normal'. Sin dato de RAM se asume lo mas prudente: 'normal'."""
    if ram_mb <= 0:
        return "normal"
    if ram_mb <= ULTRA_LOW_MB:
        return "ultra_low"
    if ram_mb <= LOW_MB:
        return "low"
    return "normal"


def _props(adb) -> dict[str, str]:
    out = adb.shell("getprop", timeout=60)
    props: dict[str, str] = {}
    for line in out.splitlines():
        match = re.match(r"\[(.+?)\]: \[(.*)\]", line.strip())
        if match:
            props[match.group(1)] = match.group(2)
    return props


def _first(props: dict[str, str], *keys: str) -> str:
    for key in keys:
        if props.get(key):
            return props[key]
    return ""


def _mem_total_mb(adb) -> int:
    for line in adb.shell("cat /proc/meminfo").splitlines():
        if line.startswith("MemTotal:"):
            return int(re.sub(r"\D", "", line) or 0) // 1024
    return 0


def _storage_free_mb(adb) -> Optional[int]:
    lines = adb.shell("df /data").splitlines()
    if len(lines) >= 2:
        cols = lines[-1].split()
        if len(cols) >= 4 and cols[3].isdigit():
            return int(cols[3]) // 1024
    return None


def detect(adb, serial: str = "") -> DeviceInfo:
    props = _props(adb)
    info = DeviceInfo(serial=serial)
    info.manufacturer = _first(props, "ro.product.manufacturer")
    info.brand = _first(props, "ro.product.brand")
    info.model = _first(props, "ro.product.model")
    info.device = _first(props, "ro.product.device")
    info.android_release = _first(props, "ro.build.version.release")
    info.sdk = int(_first(props, "ro.build.version.sdk") or 0)
    info.abis = [a for a in _first(props, "ro.product.cpu.abilist").split(",") if a]
    info.soc = _first(props, "ro.soc.model", "ro.board.platform", "ro.hardware")
    info.ram_mb = _mem_total_mb(adb)
    info.storage_free_mb = _storage_free_mb(adb)
    density = re.search(r"(\d+)\s*$", adb.shell("wm density"))
    info.density = int(density.group(1)) if density else None
    size = re.search(r"(\d+x\d+)\s*$", adb.shell("wm size"))
    info.resolution = size.group(1) if size else None
    return _simulate(info)


def _simulate(info: DeviceInfo) -> DeviceInfo:
    """Solo para pruebas en emulador: TVLITE_SIMULATE='{"manufacturer":"Sony","soc":"MT5895"}' hace que
    la herramienta crea que la tele es de otra marca/procesador. Queda marcado como simulado."""
    raw = os.environ.get("TVLITE_SIMULATE")
    if not raw:
        return info
    for key, value in json.loads(raw).items():
        if hasattr(info, key) and key != "simulated":
            setattr(info, key, value)
    info.simulated = True
    return info


def describe(info: DeviceInfo) -> str:
    """Descripcion legible de la tele para mostrar al usuario."""
    name = " ".join(p for p in (info.manufacturer or info.brand, info.model) if p) or "Dispositivo desconocido"
    lines = [
        name,
        f"Android {info.android_release} (API {info.sdk})",
        f"Procesador/plataforma: {info.soc or 'desconocido'} ({', '.join(info.abis) or 'ABI desconocida'})",
        f"RAM: {info.ram_mb} MB" if info.ram_mb else "RAM: desconocida",
    ]
    if info.storage_free_mb is not None:
        lines.append(f"Almacenamiento libre: {info.storage_free_mb} MB")
    if info.resolution:
        lines.append(f"Pantalla: {info.resolution} ({info.density or '?'} dpi)")
    labels = {
        "ultra_low": "RAM muy baja: optimización máxima",
        "low": "RAM baja: optimización recomendada",
        "normal": "RAM suficiente: solo limpieza segura",
    }
    lines.append(f"Perfil: {labels[info.profile]}")
    if info.simulated:
        lines.append("(SIMULADO: datos sobrescritos con TVLITE_SIMULATE, solo para pruebas)")
    return "\n".join(lines)
