"""Genera un ejecutable de un solo archivo con PyInstaller (el usuario final no necesita Python).

    python installer/build_exe.py

Antes compila el launcher (bash launcher/build.sh) para incluir el APK dentro del ejecutable.
El resultado queda en installer/dist/.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
APK = HERE.parent / "launcher" / "build" / "litelauncher.apk"
BUNDLED = HERE / "tvlite" / "data" / "litelauncher.apk"


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
    print(f"Listo: {HERE / 'dist'}")


if __name__ == "__main__":
    main()
