#!/usr/bin/env python3
"""Genera las capturas del asistente para el README (docs/img/). Solo Windows.

Recorre el asistente contra una tele SIMULADA (FakeAdb) y guarda cada paso como PNG usando
PrintWindow sobre la propia ventana: no se captura el resto de la pantalla y la ventana se
coloca fuera de la vista para no molestar. Sin dependencias externas (el PNG se escribe a mano).

    python tools/docs/capture_gui.py [carpeta_de_salida] [es|en]
"""

from __future__ import annotations

import ctypes
import os
import shutil
import struct
import sys
import tempfile
import time
import tkinter as tk
import zlib
from ctypes import wintypes
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "installer"))
sys.path.insert(0, str(REPO / "installer" / "tests"))

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "docs" / "img"
LANG = sys.argv[2] if len(sys.argv) > 2 else "es"
# Ruta neutra: las capturas del README no deben mostrar la carpeta personal de quien las genera.
_home = Path(os.path.splitdrive(tempfile.gettempdir())[0] + "\\") / "tvlite-demo"
_home.mkdir(parents=True, exist_ok=True)
os.environ["TVLITE_HOME"] = str(_home)
_apk = _home / "litelauncher.apk"
_apk.write_bytes(b"demo")
os.environ["TVLITE_LAUNCHER_APK"] = str(_apk)

from fake_adb import FakeAdb  # noqa: E402
from tvlite.gui import App  # noqa: E402

user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


def window_pixels(hwnd: int) -> tuple[int, int, bytes]:
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    hdc = user32.GetWindowDC(hwnd)
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mem, bmp)
    user32.PrintWindow(hwnd, mem, 2)  # PW_RENDERFULLCONTENT: solo el contenido de ESTA ventana
    info = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(info), 0)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem)
    user32.ReleaseDC(hwnd, hdc)
    return w, h, buf.raw


def crop(w: int, h: int, bgra: bytes, left: int, top: int, right: int, bottom: int) -> tuple[int, int, bytes]:
    nw, nh = w - left - right, h - top - bottom
    rows = [bgra[((y + top) * w + left) * 4:((y + top) * w + left + nw) * 4] for y in range(nh)]
    return nw, nh, b"".join(rows)


def write_png(path: Path, w: int, h: int, bgra: bytes) -> None:
    rgb = bytearray(w * h * 3)
    rgb[0::3], rgb[1::3], rgb[2::3] = bgra[2::4], bgra[1::4], bgra[0::4]
    raw = b"".join(b"\x00" + bytes(rgb[y * w * 3:(y + 1) * w * 3]) for y in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def make_unobtrusive(hwnd: int) -> None:
    """Ventana casi invisible (1 % de opacidad), que no se activa ni recibe el raton: PrintWindow
    necesita que la ventana este compuesta en pantalla, pero asi no molesta (ni quita el foco a un juego)."""
    GWL_EXSTYLE, LWA_ALPHA = -20, 0x2
    WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x80000, 0x20, 0x80, 0x08000000
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
    user32.SetLayeredWindowAttributes(hwnd, 0, 3, LWA_ALPHA)


def main() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:  # noqa: BLE001
        pass
    OUT.mkdir(parents=True, exist_ok=True)
    fake = FakeAdb(
        packages=["com.tcl.esticker", "com.tcl.hearaid", "com.tcl.messagebox", "com.tcl.dashboard", "com.tcl.ttvs",
                  "com.google.android.play.games", "com.google.android.katniss", "com.android.printspooler",
                  "com.android.htmlviewer", "com.google.android.backdrop"],
        user_packages=["com.tcl.waterfall.overseas"],
        stubborn_launcher=True,
    )
    root = tk.Tk()
    root.geometry("820x700+40+40")
    root.update()
    make_unobtrusive(user32.GetAncestor(root.winfo_id(), 2))
    app = App(root, adb_factory=lambda progress: fake, lang=LANG)

    def pump(seconds: float = 0.5) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            root.update()
            time.sleep(0.02)

    def shot(name: str) -> None:
        pump(0.6)
        hwnd = user32.GetAncestor(root.winfo_id(), 2)
        w, h, data = window_pixels(hwnd)
        w, h, data = crop(w, h, data, left=11, top=0, right=11, bottom=11)  # marco negro que anade PrintWindow
        write_png(OUT / f"gui-{LANG}-{name}.png", w, h, data)
        print("guardada", name, f"{w}x{h}")

    shot("1-bienvenida")
    app.go_next()
    app.ip_var.set("192.168.1.50")
    shot("2-conectar")
    app.go_next()
    pump(1.5)
    shot("3-tu-tele")
    app.go_next()
    shot("4-limpieza")
    app.go_next()
    for key in ("stremio", "nordvpn", "netflix", "youtube"):
        app.app_vars[key].set(True)
    shot("5-apps")
    app.go_next()
    shot("6-resumen")
    app.do_run()
    for _ in range(300):
        pump(0.1)
        if app.summary is not None:
            break
    shot("7-resultado")
    root.destroy()
    shutil.rmtree(_home, ignore_errors=True)  # carpeta temporal de la demo


if __name__ == "__main__":
    main()
