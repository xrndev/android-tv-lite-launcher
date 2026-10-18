"""Backup y diario de cambios. Cada accion se escribe y se sincroniza a disco al momento,
para poder restaurar aunque el programa se interrumpa a mitad."""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Optional

from . import android
from .adb import data_dir
from .device import DeviceInfo

# Ajustes globales que tocamos y que guardamos para restaurar.
TRACKED_SETTINGS = ("window_animation_scale", "transition_animation_scale", "animator_duration_scale")


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-") or "tv"


class Journal:
    def __init__(self, directory: Path) -> None:
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "journal.jsonl"

    @classmethod
    def new(cls, device: DeviceInfo, base: Optional[Path] = None) -> "Journal":
        stamp = time.strftime("%Y%m%d-%H%M%S")
        name = f"{_slug(device.model or device.device or 'tv')}-{stamp}"
        return cls((base or data_dir() / "backups") / name)

    def record(self, action: str, target: str, reverse: Optional[dict] = None, ok: bool = True, detail: str = "") -> None:
        entry = {
            "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "action": action,
            "target": target,
            "ok": ok,
            "reverse": reverse,
            "detail": detail,
        }
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        with open(self.path, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def write_json(self, name: str, data) -> None:
        (self.dir / name).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def read_json(self, name: str):
        return json.loads((self.dir / name).read_text(encoding="utf-8"))


def snapshot(adb, journal: Journal, device: DeviceInfo) -> None:
    """Foto del estado original: paquetes, launcher y ajustes que vamos a tocar.
    Solo guardamos lo necesario: nada de cuentas ni identificadores."""
    journal.write_json("device.json", device.to_dict())
    (journal.dir / "packages_all.txt").write_text(adb.shell("pm list packages -f", timeout=120), encoding="utf-8")
    (journal.dir / "packages_disabled.txt").write_text(adb.shell("pm list packages -d"), encoding="utf-8")
    (journal.dir / "packages_user.txt").write_text(adb.shell("pm list packages -3"), encoding="utf-8")
    journal.write_json(
        "home.json",
        {"resolved": android.resolve_home(adb), "candidates": android.home_packages(adb)},
    )
    journal.write_json(
        "settings.json",
        {key: android.get_setting(adb, "global", key) for key in TRACKED_SETTINGS},
    )
