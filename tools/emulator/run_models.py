#!/usr/bin/env python3
"""Ejecuta la suite de MODELOS REALES (installer/tests/integration/test_models.py) arrancando, para cada modelo,
el emulador que le corresponde (por RAM y version de Android) y parandolo al terminar.

    python tools/emulator/run_models.py                 # todos
    python tools/emulator/run_models.py sony-kd43x80j   # uno o varios

Necesita el SDK de Android con las imagenes de sistema de cada perfil (python tools/emulator/emu.py setup <perfil>)."""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent


def load_emu():
    spec = importlib.util.spec_from_file_location("emu", HERE / "emu.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def avd_exists(name: str) -> bool:
    return (Path.home() / ".android" / "avd" / f"{name}.avd").is_dir()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("models", nargs="*", help="ids de modelos (por defecto, todos)")
    args = parser.parse_args()
    emu = load_emu()
    data = emu.load_models()["models"]
    wanted = args.models or list(data)
    unknown = [m for m in wanted if m not in data]
    if unknown:
        sys.exit(f"Modelos desconocidos: {unknown}. Disponibles: {list(data)}")
    wanted.sort(key=lambda m: data[m]["avd"])  # un arranque por AVD

    results: dict[str, str] = {}
    running = None
    env_base = {**os.environ, "TVLITE_EMULATOR": "1", "ANDROID_SDK_ROOT": str(emu.sdk_root()),
                "PYTHONPATH": str(REPO / "installer")}
    try:
        for model_id in wanted:
            avd = data[model_id]["avd"]
            if running != avd:
                if running:
                    emu.cmd_stop(None)
                    time.sleep(6)
                if not avd_exists(avd):
                    emu.cmd_setup(SimpleNamespace(profile=avd))
                emu.cmd_start(SimpleNamespace(profile=avd, window=False))
                running = avd
            print(f"\n=== {model_id} ({data[model_id]['display']}) en el AVD {avd}")
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", str(REPO / "installer" / "tests" / "integration" / "test_models.py"), "-v", "-s"],
                env={**env_base, "TVLITE_MODEL": model_id}, cwd=REPO / "installer",
            )
            results[model_id] = "OK" if proc.returncode == 0 else f"FALLO (codigo {proc.returncode})"
    finally:
        if running:
            emu.cmd_stop(None)

    print("\n=== Resumen")
    for model_id, status in results.items():
        print(f"  {status:8} {model_id}  ({data[model_id]['display']})")
    return 0 if all(s == "OK" for s in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
