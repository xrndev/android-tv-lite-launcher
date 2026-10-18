# Desarrollo

[English](DEVELOPMENT.md) · **Español**

## Desde el código

Necesitas Python 3.9+ (con Tkinter):

```bash
cd installer
pip install -e ".[dev]"
python -m pytest                 # pruebas unitarias con una tele simulada (sin hardware)
tvlite gui                       # el asistente
```

## Launcher

Necesita JDK 17+ y el SDK de Android con build-tools ≥ 35 y plataforma `android-30`:

```bash
ANDROID_SDK_ROOT=/ruta/al/sdk bash launcher/build.sh     # -> launcher/build/litelauncher.apk
```

## Ejecutables (sin Python para el usuario final)

```bash
python installer/build_exe.py    # necesita launcher/build/litelauncher.apk; genera installer/dist/tvlite-<so>-<arq>
tvlite-<so>-<arq> selftest       # comprueba datos, interfaz y launcher incluido, sin tele
```

## Emuladores de Android TV

RAM y Android configurables; necesitan aceleración de hardware (WHPX/KVM/HVF):

```bash
python tools/emulator/emu.py list
python tools/emulator/emu.py setup atv11-1gb
python tools/emulator/emu.py start atv11-1gb
TVLITE_EMULATOR=1 TVLITE_EXPECT_RAM_MB=1024 python -m pytest installer/tests/integration -v
```

### Perfiles de modelos reales

```bash
python tools/emulator/emu.py models                  # lista modelos y nivel de evidencia
python tools/emulator/run_models.py sony-kd43x80j    # arranca el emulador adecuado, prueba y lo para
```

Ejecuta los modelos **de uno en uno** en equipos con poca memoria libre: varios arranques de emulador seguidos pueden agotarla.

## Estructura

`launcher/` (app Android) · `installer/tvlite/` (núcleo, CLI, GUI) · `installer/tests/` (unitarias + integración) · `tools/emulator/` (emuladores, fixtures, modelos) · `tools/telemetry-relay/` (relé opcional de informes) · `docs/`.

Ver también: [RELEASING.md](RELEASING.md), [TELEMETRY.md](TELEMETRY.md), [CONTRIBUTING](../CONTRIBUTING.es.md).
