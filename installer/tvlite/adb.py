"""Acceso a ADB: localizar o descargar platform-tools y ejecutar comandos."""

from __future__ import annotations

import os
import platform
import shutil
import stat
import subprocess
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

PLATFORM_TOOLS_URL = "https://dl.google.com/android/repository/platform-tools-latest-{os}.zip"


class AdbError(RuntimeError):
    """Fallo al hablar con ADB o con la tele."""


@dataclass
class Result:
    returncode: int
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def data_dir() -> Path:
    """Carpeta donde guardamos platform-tools y los backups (TVLITE_HOME la sobrescribe)."""
    override = os.environ.get("TVLITE_HOME")
    base = Path(override) if override else Path.home() / ".tvlite"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _os_key() -> str:
    system = platform.system().lower()
    if system.startswith("win"):
        return "windows"
    if system == "darwin":
        return "darwin"
    return "linux"


def _exe_name() -> str:
    return "adb.exe" if _os_key() == "windows" else "adb"


def find_adb() -> Optional[Path]:
    """Devuelve un adb ya instalado (en PATH o descargado por nosotros), si existe."""
    local = data_dir() / "platform-tools" / _exe_name()
    if local.exists():
        return local
    found = shutil.which("adb")
    return Path(found) if found else None


def download_adb(progress: Callable[[str], None] = lambda m: None) -> Path:
    """Descarga platform-tools oficiales de Google (HTTPS) y devuelve la ruta a adb."""
    url = PLATFORM_TOOLS_URL.format(os=_os_key())
    dest = data_dir()
    archive = dest / "platform-tools.zip"
    progress(f"Descargando platform-tools de Google ({url})")
    try:
        urllib.request.urlretrieve(url, archive)  # noqa: S310 (URL fija de Google)
    except OSError as exc:
        raise AdbError(f"No se pudo descargar ADB: {exc}") from exc
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(dest)
    archive.unlink(missing_ok=True)
    exe = dest / "platform-tools" / _exe_name()
    if not exe.exists():
        raise AdbError("La descarga de platform-tools no contiene adb")
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    return exe


def ensure_adb(progress: Callable[[str], None] = lambda m: None) -> Path:
    """Usa el adb que haya o lo instala solo."""
    return find_adb() or download_adb(progress)


class Adb:
    """Envoltorio fino sobre el binario adb. Los tests lo sustituyen por FakeAdb."""

    def __init__(
        self,
        exe: Optional[Path] = None,
        serial: Optional[str] = None,
        runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    ) -> None:
        self.exe = str(exe) if exe else "adb"
        self.serial = serial
        self._runner = runner

    def _base(self) -> list[str]:
        cmd = [self.exe]
        if self.serial:
            cmd += ["-s", self.serial]
        return cmd

    def run(self, args: Sequence[str], timeout: int = 60) -> Result:
        try:
            done = self._runner(
                self._base() + list(args),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise AdbError(f"adb {' '.join(args)} tardo mas de {timeout}s") from exc
        except OSError as exc:
            raise AdbError(f"No se pudo ejecutar adb: {exc}") from exc
        return Result(done.returncode, done.stdout or "", done.stderr or "")

    def shell(self, command: str, timeout: int = 60) -> str:
        """Ejecuta un comando en la tele y devuelve stdout sin saltos de linea sobrantes."""
        result = self.run(["shell", command], timeout=timeout)
        return result.stdout.replace("\r\n", "\n").strip()

    # --- conexion ---
    def connect(self, host_port: str) -> Result:
        return self.run(["connect", host_port], timeout=30)

    def pair(self, host_port: str, code: str) -> Result:
        return self.run(["pair", host_port, code], timeout=30)

    def devices(self) -> str:
        return self.run(["devices"]).stdout

    # --- ficheros ---
    def install(self, apk: Path, timeout: int = 300) -> Result:
        return self.run(["install", "-r", str(apk)], timeout=timeout)

    def uninstall(self, package: str) -> Result:
        return self.run(["uninstall", package])

    def pull(self, remote: str, local: Path) -> Result:
        return self.run(["pull", remote, str(local)])
