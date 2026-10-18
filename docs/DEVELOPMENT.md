# Development

**English** · [Español](DEVELOPMENT.es.md)

## From source

You need Python 3.9+ (with Tkinter):

```bash
cd installer
pip install -e ".[dev]"
python -m pytest                 # unit tests against a simulated TV (no hardware)
tvlite gui                       # the wizard
```

## Launcher

Needs JDK 17+ and the Android SDK with build-tools ≥ 35 and platform `android-30`:

```bash
ANDROID_SDK_ROOT=/path/to/sdk bash launcher/build.sh     # -> launcher/build/litelauncher.apk
```

## Executables (no Python for the end user)

```bash
python installer/build_exe.py    # needs launcher/build/litelauncher.apk; produces installer/dist/tvlite-<os>-<arch>
tvlite-<os>-<arch> selftest      # checks data, GUI and the bundled launcher without a TV
```

## Android TV emulators

Configurable RAM and Android; need hardware acceleration (WHPX/KVM/HVF):

```bash
python tools/emulator/emu.py list
python tools/emulator/emu.py setup atv11-1gb
python tools/emulator/emu.py start atv11-1gb
TVLITE_EMULATOR=1 TVLITE_EXPECT_RAM_MB=1024 python -m pytest installer/tests/integration -v
```

### Real-model profiles

```bash
python tools/emulator/emu.py models                  # list models and evidence level
python tools/emulator/run_models.py sony-kd43x80j    # starts the right emulator, runs, stops it
```

Run models **one at a time** on machines with little free memory: several emulator boots in a row can exhaust it.

## Layout

`launcher/` (Android app) · `installer/tvlite/` (core, CLI, GUI) · `installer/tests/` (unit + integration) · `tools/emulator/` (emulators, fixtures, models) · `tools/telemetry-relay/` (optional result-report relay) · `docs/`.

See also: [RELEASING.md](RELEASING.md), [TELEMETRY.md](TELEMETRY.md), [CONTRIBUTING](../CONTRIBUTING.md).
