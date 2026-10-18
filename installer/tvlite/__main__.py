import sys

from .cli import main

if __name__ == "__main__":
    # Sin argumentos (doble clic en el ejecutable) se abre el asistente grafico.
    sys.exit(main(["gui"] if len(sys.argv) == 1 else None))
