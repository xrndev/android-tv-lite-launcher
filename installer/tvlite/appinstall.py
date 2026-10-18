"""Instalar apps populares (streaming, Stremio, VPN) en la tele.

- method 'apk': descarga oficial del desarrollador (p. ej. Stremio) e instalacion por ADB.
- method 'play': se abre la ficha de la app en Play Store y se pulsa "Instalar" por ADB. No se
  redistribuyen APK de terceros. Es la parte mas fragil: depende de la interfaz de Play Store,
  asi que si algo no cuadra se avisa y el usuario puede pulsar Instalar con el mando.
"""

from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from . import android
from .adb import data_dir
from .journal import Journal

DATA = Path(__file__).parent / "data"
PLAY_STORE = "com.android.vending"
INSTALL_LABELS = ("instalar", "install")


@dataclass
class AppResult:
    app_id: str
    ok: bool
    detail: str = ""
    skipped: bool = False


def load_apps() -> dict:
    return json.loads((DATA / "apps.json").read_text(encoding="utf-8"))


def pick_apk_url(app: dict, abis: list[str]) -> Optional[str]:
    """Elige la variante de APK segun las ABI de la tele (en su orden de preferencia)."""
    variants = app.get("apk") or {}
    for abi in abis:
        if abi in variants:
            return variants[abi]
    return None


def ui_texts(adb) -> list[str]:
    """Textos visibles en pantalla (uiautomator). Vacio si no se puede leer."""
    out = adb.shell(
        "uiautomator dump /sdcard/tvlite_ui.xml >/dev/null 2>&1; cat /sdcard/tvlite_ui.xml; rm -f /sdcard/tvlite_ui.xml",
        timeout=60,
    )
    return [t.strip() for t in re.findall(r'(?:text|content-desc)="([^"]*)"', out) if t.strip()]


def _has_install_button(texts: list[str]) -> bool:
    return any(t.lower() in INSTALL_LABELS for t in texts)


def install_apk(adb, app: dict, abis: list[str], journal: Journal, progress, downloader=None) -> AppResult:
    url = pick_apk_url(app, abis)
    if not url:
        return AppResult(app["id"], False, "No hay APK oficial para la arquitectura de esta tele")
    dest = data_dir() / "downloads" / f"{app['id']}.apk"
    dest.parent.mkdir(parents=True, exist_ok=True)
    progress(f"Descargando {app['name']} ({url})")
    try:
        (downloader or urllib.request.urlretrieve)(url, dest)
    except OSError as exc:
        return AppResult(app["id"], False, f"Descarga fallida: {exc}")
    with android.adb_verification_off(adb, journal):
        res = adb.install(dest)
    ok = res.ok and "Success" in res.stdout
    journal.record(
        "app_install", app["package"],
        reverse={"op": "uninstall", "pkg": app["package"]} if ok else None, ok=ok, detail=res.stdout,
    )
    return AppResult(app["id"], ok, "" if ok else (res.stdout or res.stderr))


def install_play(adb, app: dict, journal: Journal, progress, timeout: float = 240.0) -> AppResult:
    pkg = app["package"]
    progress(f"Abriendo {app['name']} en Play Store")
    adb.shell(f'am start -a android.intent.action.VIEW -d "market://details?id={pkg}" {PLAY_STORE}')
    if not android.wait_for(lambda: android.package_of(android.resumed_activity(adb)) == PLAY_STORE, timeout=20):
        return AppResult(app["id"], False, "Play Store no se abrio")
    android.wait_for(lambda: _has_install_button(ui_texts(adb)), timeout=15, interval=2)
    texts = ui_texts(adb)
    if texts and not _has_install_button(texts):
        return AppResult(
            app["id"], False,
            "Play Store no muestra el boton Instalar (app no disponible para esta tele o sin sesion de Google)",
        )
    android.press(adb, "KEYCODE_DPAD_CENTER")  # "Instalar" es el boton enfocado por defecto
    if android.wait_for(lambda: pkg in android.list_packages(adb), timeout=timeout, interval=5):
        journal.record("app_install", pkg, reverse={"op": "uninstall", "pkg": pkg})
        return AppResult(app["id"], True)
    return AppResult(app["id"], False, "No se completo la instalacion a tiempo")


def install_app(adb, app: dict, abis: list[str], journal: Journal, progress=lambda m: None) -> AppResult:
    if app["package"] in android.list_packages(adb):
        return AppResult(app["id"], True, "ya instalada", skipped=True)
    if app.get("method") == "apk":
        result = install_apk(adb, app, abis, journal, progress)
        if result.ok or app.get("fallback") != "play":
            return result
        progress(f"{app['name']}: la descarga directa fallo, se prueba con Play Store")
    return install_play(adb, app, journal, progress)
