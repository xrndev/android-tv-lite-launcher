"""Punto de entrada del ejecutable (PyInstaller): sin argumentos (doble clic) abre el asistente grafico."""

import os
import sys

from tvlite.cli import main


def _hide_console_on_windows() -> None:
    """Al hacer doble clic en el .exe Windows abre una consola negra detras del asistente: se oculta.
    Con argumentos (uso desde la terminal) no se toca."""
    if os.name != "nt":
        return
    try:
        import ctypes

        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
    except Exception:  # noqa: BLE001 - es solo estetica
        pass


if __name__ == "__main__":
    if len(sys.argv) == 1:
        _hide_console_on_windows()
        sys.exit(main(["gui"]))
    sys.exit(main())
