"""Genera un ejecutable de un solo archivo con PyInstaller (el usuario final no necesita Python).

    python installer/build_exe.py

Antes compila el launcher (bash launcher/build.sh) para incluir el APK dentro del ejecutable.
El resultado queda en installer/dist/.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
APK = HERE.parent / "launcher" / "build" / "litelauncher.apk"
BUNDLED = HERE / "tvlite" / "data" / "litelauncher.apk"


def artifact_name() -> str:
    """tvlite-windows-x64.exe, tvlite-macos-arm64, tvlite-linux-x64..."""
    system = {"Windows": "windows", "Darwin": "macos", "Linux": "linux"}.get(platform.system(), platform.system().lower())
    machine = platform.machine().lower()
    arch = {"amd64": "x64", "x86_64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(machine, machine)
    return f"tvlite-{system}-{arch}" + (".exe" if system == "windows" else "")


def main() -> None:
    if not APK.exists():
        sys.exit("Falta el APK del launcher: ejecuta antes 'bash launcher/build.sh'")
    shutil.copy2(APK, BUNDLED)
    sep = ";" if os.name == "nt" else ":"
    try:
        subprocess.run(
            [
                sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--name", "tvlite",
                "--add-data", f"{HERE / 'tvlite' / 'data'}{sep}tvlite/data",
                "--distpath", str(HERE / "dist"), "--workpath", str(HERE / "build"),
                "--specpath", str(HERE / "build"),
                str(HERE / "tvlite_entry.py"),
            ],
            check=True,
            cwd=HERE,
            env={**os.environ, "PYTHONPATH": str(HERE)},
        )
    finally:
        BUNDLED.unlink(missing_ok=True)  # el APK empaquetado no se versiona
    built = HERE / "dist" / ("tvlite.exe" if os.name == "nt" else "tvlite")
    final = HERE / "dist" / artifact_name()
    shutil.copy2(built, final)
    print(f"Listo: {final}")


if __name__ == "__main__":
    main()
