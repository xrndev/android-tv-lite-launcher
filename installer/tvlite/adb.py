"""Acceso a ADB: localizar o descargar platform-tools (verificando su checksum) y ejecutar comandos,
reconectando solo si la tele se duerme o la conexion cae."""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import stat
import subprocess
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

PLATFORM_TOOLS_URL = "https://dl.google.com/android/repository/platform-tools-latest-{os}.zip"
REPOSITORY_XML_URL = "https://dl.google.com/android/repository/repository2-3.xml"
# Claves de host-os en el XML de Google.
_XML_OS = {"windows": "windows", "darwin": "macosx", "linux": "linux"}
# Mensajes de adb que indican problema de conexion (no un fallo del comando remoto).
_CONNECTION_ERRORS = ("device offline", "no devices/emulators found", "error: closed", "error: device ", "unauthorized")


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


def sha1_of(path: Path) -> str:
    digest = hashlib.sha1()  # noqa: S324 (Google publica SHA-1; solo se usa para comparar)
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def expected_platform_tools_sha1(repository_xml: str, os_key: str) -> Optional[str]:
    """SHA-1 que Google publica para platform-tools de este sistema operativo (None si no aparece)."""
    root = ET.fromstring(repository_xml)

    def local(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    for package in root.iter():
        if local(package.tag) != "remotePackage" or package.get("path") != "platform-tools":
            continue
        for archive in package.iter():
            if local(archive.tag) != "archive":
                continue
            host = next((c.text for c in archive if local(c.tag) == "host-os"), None)
            if host != _XML_OS[os_key]:
                continue
            for node in archive.iter():
                if local(node.tag) == "checksum" and node.get("type") == "sha1":
                    return (node.text or "").strip().lower()
    return None


def download_adb(progress: Callable[[str], None] = lambda m: None) -> Path:
    """Descarga platform-tools de Google (HTTPS), comprueba su SHA-1 contra el que Google publica y
    solo entonces lo descomprime. Devuelve la ruta a adb."""
    os_key = _os_key()
    url = PLATFORM_TOOLS_URL.format(os=os_key)
    dest = data_dir()
    archive = dest / "platform-tools.zip"
    progress(f"Descargando platform-tools de Google ({url})")
    try:
        urllib.request.urlretrieve(url, archive)  # noqa: S310 (URL fija de Google)
        with urllib.request.urlopen(REPOSITORY_XML_URL, timeout=60) as response:  # noqa: S310
            xml_text = response.read().decode("utf-8")
    except OSError as exc:
        raise AdbError(f"No se pudo descargar ADB: {exc}") from exc
    expected = expected_platform_tools_sha1(xml_text, os_key)
    if not expected:
        archive.unlink(missing_ok=True)
        raise AdbError("No se pudo obtener el checksum oficial de platform-tools; no se instala por seguridad")
    actual = sha1_of(archive)
    if actual != expected:
        archive.unlink(missing_ok=True)
        raise AdbError(
            "El checksum de platform-tools no coincide con el que publica Google "
            f"(esperado {expected[:10]}..., obtenido {actual[:10]}...). Si Google acaba de publicar una "
            "version nueva, reintentalo en unos minutos."
        )
    progress("Checksum de platform-tools verificado")
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


def is_connection_error(result: Result) -> bool:
    text = (result.stderr + result.stdout).lower()
    return result.returncode != 0 and any(marker in text for marker in _CONNECTION_ERRORS)


class Adb:
    """Envoltorio fino sobre el binario adb. Los tests lo sustituyen por FakeAdb."""

    def __init__(
        self,
        exe: Optional[Path] = None,
        serial: Optional[str] = None,
        runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
        reconnect_attempts: int = 3,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.exe = str(exe) if exe else "adb"
        self.serial = serial
        self._runner = runner
        self.reconnect_attempts = reconnect_attempts
        self._sleep = sleep

    def _base(self) -> list[str]:
        cmd = [self.exe]
        if self.serial:
            cmd += ["-s", self.serial]
        return cmd

    def _run_once(self, args: Sequence[str], timeout: int) -> Result:
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

    def _is_network_serial(self) -> bool:
        return bool(self.serial) and ":" in self.serial and self.serial[0].isdigit()

    def _reconnect(self) -> None:
        """La tele en reposo o un corte de Wi-Fi tiran la conexion: se vuelve a conectar sin preguntar."""
        raw = [self.exe, "connect", self.serial]
        try:
            self._runner(raw, capture_output=True, text=True, timeout=30)
        except (subprocess.TimeoutExpired, OSError):
            pass
        self._sleep(2)

    def run(self, args: Sequence[str], timeout: int = 60) -> Result:
        result = self._run_once(args, timeout)
        attempts = 0
        while is_connection_error(result) and self._is_network_serial() and attempts < self.reconnect_attempts:
            attempts += 1
            self._reconnect()
            result = self._run_once(args, timeout)
        return result

    def shell(self, command: str, timeout: int = 60) -> str:
        """Ejecuta un comando en la tele y devuelve stdout sin saltos de linea sobrantes. Si la
        conexion se ha perdido (y no se pudo recuperar) lanza AdbError en vez de devolver vacio, que
        el resto del codigo confundiria con 'el comando no hizo nada'."""
        result = self.run(["shell", command], timeout=timeout)
        if is_connection_error(result):
            raise AdbError(f"Se perdio la conexion con la tele: {(result.stderr or result.stdout).strip()}")
        return result.stdout.replace("\r\n", "\n").strip()

    # --- conexion ---
    def connect(self, host_port: str) -> Result:
        return self._run_once(["connect", host_port], timeout=30)

    def pair(self, host_port: str, code: str) -> Result:
        return self._run_once(["pair", host_port, code], timeout=30)

    def devices(self) -> str:
        return self._run_once(["devices"], timeout=60).stdout

    # --- ficheros ---
    def install(self, apk: Path, timeout: int = 300) -> Result:
        return self.run(["install", "-r", str(apk)], timeout=timeout)

    def install_multiple(self, apks: Sequence[Path], timeout: int = 300) -> Result:
        """Para apps con APK divididos (base + splits), como las que se instalan desde Play Store."""
        return self.run(["install-multiple", "-r", *[str(a) for a in apks]], timeout=timeout)

    def uninstall(self, package: str) -> Result:
        return self.run(["uninstall", package])

    def pull(self, remote: str, local: Path) -> Result:
        return self.run(["pull", remote, str(local)], timeout=300)
