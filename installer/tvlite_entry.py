"""Punto de entrada del ejecutable (PyInstaller): sin argumentos (doble clic) abre el asistente grafico."""

import sys

from tvlite.cli import main

if __name__ == "__main__":
    sys.exit(main(["gui"] if len(sys.argv) == 1 else None))
