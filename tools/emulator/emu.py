#!/usr/bin/env python3
"""Emuladores de Android TV para probar tvlite con distintas RAM y versiones de Android.

  python tools/emulator/emu.py list
  python tools/emulator/emu.py setup atv11-1gb      # descarga la imagen y crea el AVD
  python tools/emulator/emu.py start atv11-1gb      # arranca y espera al boot (--window para verlo)
  python tools/emulator/emu.py fixture tcl          # instala los paquetes de prueba de una "marca"
  python tools/emulator/emu.py stop

Necesita el SDK de Android (variable ANDROID_SDK_ROOT o tools/android-sdk) con cmdline-tools.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
IS_WIN = platform.system() == "Windows"
SERIAL = os.environ.get("TVLITE_EMULATOR_SERIAL", "emulator-5554")


def sdk_root() -> Path:
    for candidate in (os.environ.get("ANDROID_SDK_ROOT"), os.environ.get("ANDROID_HOME"), REPO / "tools" / "android-sdk"):
        if candidate and Path(candidate).exists():
            return Path(candidate)
    sys.exit("No encuentro el SDK de Android: define ANDROID_SDK_ROOT o instala tools/android-sdk")


def tool(*parts: str) -> str:
    path = sdk_root().joinpath(*parts)
    for suffix in (("",) if not IS_WIN else (".bat", ".exe", "")):
        if Path(str(path) + suffix).exists():
            return str(path) + suffix
    sys.exit(f"Falta {path} en el SDK")


def profiles() -> dict:
    return json.loads((HERE / "profiles.json").read_text(encoding="utf-8"))["profiles"]


def adb(*args: str, check: bool = True, timeout: int = 120) -> subprocess.CompletedProcess:
    exe = tool("platform-tools", "adb")
    return subprocess.run([exe, "-s", SERIAL, *args], capture_output=True, text=True, timeout=timeout, check=check)


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    env = {**os.environ, "ANDROID_SDK_ROOT": str(sdk_root())}
    return subprocess.run(cmd, env=env, text=True, **kw)


def cmd_list(_args) -> None:
    for name, p in profiles().items():
        print(f"{name:12} Android API {p['api']:>2}  {p['ram_mb']:>4} MB  {p['approximates']}")


def cmd_setup(args) -> None:
    p = profiles()[args.profile]
    sdkmanager = tool("cmdline-tools", "latest", "bin", "sdkmanager")
    run([sdkmanager, f"--sdk_root={sdk_root()}", "emulator", "platform-tools", p["image"]], input="y\n" * 20)
    avdmanager = tool("cmdline-tools", "latest", "bin", "avdmanager")
    run([avdmanager, "create", "avd", "-n", args.profile, "-k", p["image"], "-d", p["device"], "--force"], input="no\n")
    config = Path.home() / ".android" / "avd" / f"{args.profile}.avd" / "config.ini"
    text = config.read_text(encoding="utf-8")
    for key, value in {"hw.ramSize": p["ram_mb"], "hw.keyboard": "yes", "disk.dataPartition.size": "3GB"}.items():
        text = re.sub(rf"^{re.escape(key)}=.*$", "", text, flags=re.M) + f"\n{key}={value}"
    config.write_text(text, encoding="utf-8")
    print(f"AVD '{args.profile}' listo ({p['ram_mb']} MB de RAM)")


def wait_boot(timeout: int = 600) -> None:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        res = adb("shell", "getprop", "sys.boot_completed", check=False)
        if res.stdout.strip() == "1":
            return
        time.sleep(5)
    sys.exit("El emulador no termino de arrancar a tiempo")


def cmd_start(args) -> None:
    emulator = tool("emulator", "emulator")
    cmd = [emulator, "-avd", args.profile, "-no-snapshot", "-no-audio", "-gpu", "swiftshader_indirect"]
    if not args.window:
        cmd.append("-no-window")
    log = open(HERE / "build" / f"{args.profile}.log", "w") if (HERE / "build").mkdir(exist_ok=True) is None else None
    subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env={**os.environ, "ANDROID_SDK_ROOT": str(sdk_root())})
    print("Arrancando el emulador (la primera vez tarda varios minutos)...")
    time.sleep(10)
    wait_boot()
    print(f"Listo: {SERIAL}")


def cmd_stop(_args) -> None:
    adb("emu", "kill", check=False)


def make_stub(package: str, out_dir: Path) -> Path:
    """APK sin codigo con el nombre de paquete dado (solo existe para que 'pm' lo vea)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    apk = out_dir / f"{package}.apk"
    if apk.exists():
        return apk
    bt = sorted((sdk_root() / "build-tools").iterdir())[-1]
    jar = next((sdk_root() / "platforms").glob("android-*/android.jar"))
    manifest = out_dir / f"{package}.xml"
    manifest.write_text(
        f'<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="{package}">'
        f'<application android:hasCode="false" android:label="{package}"/></manifest>',
        encoding="utf-8",
    )
    unsigned = out_dir / f"{package}.unsigned.apk"
    suffix = ".exe" if IS_WIN else ""
    subprocess.run([str(bt / f"aapt2{suffix}"), "link", "--manifest", str(manifest), "-I", str(jar),
                    "--min-sdk-version", "21", "--target-sdk-version", "30", "-o", str(unsigned)], check=True)
    keystore = out_dir / "stub.keystore"
    if not keystore.exists():
        subprocess.run(["keytool", "-genkeypair", "-keystore", str(keystore), "-storepass", "android", "-keypass", "android",
                        "-alias", "stub", "-keyalg", "RSA", "-keysize", "2048", "-validity", "10000", "-dname", "CN=stub"],
                       check=True, capture_output=True)
    signer = str(bt / ("apksigner.bat" if IS_WIN else "apksigner"))
    subprocess.run([signer, "sign", "--ks", str(keystore), "--ks-pass", "pass:android", "--key-pass", "pass:android",
                    "--out", str(apk), str(unsigned)], check=True)
    unsigned.unlink(missing_ok=True)
    manifest.unlink(missing_ok=True)
    return apk


def fixture(name: str) -> dict:
    return json.loads((HERE / "fixtures.json").read_text(encoding="utf-8"))["fixtures"][name]


def install_packages(packages: list[str]) -> None:
    """Instala apps vacias (stubs) con esos nombres de paquete, sin pisar paquetes de sistema reales."""
    out = HERE / "build" / "stubs"

    # 'pm list packages -u' incluye los paquetes quitados para el usuario: si la imagen de Android
    # ya trae un paquete de sistema con ese nombre (p. ej. Play Juegos en Android 14) no se pisa.
    def listed(*flags: str) -> set[str]:
        res = adb("shell", "pm", "list", "packages", *flags, check=False).stdout
        return {line.split(":", 1)[1].strip() for line in res.splitlines() if line.startswith("package:")}

    system_known = listed("-s", "-u")
    all_known = listed("-u")
    for package in packages:
        installed = adb("shell", "pm", "path", package, check=False).stdout.strip()
        if installed or package in system_known:
            continue
        if package in all_known:  # resto 'fantasma' de un stub quitado: se limpia antes de reinstalarlo
            adb("shell", "pm", "uninstall", package, check=False)
        res = adb("install", str(make_stub(package, out)), check=False)
        if "Success" not in res.stdout:
            sys.exit(f"No se pudo instalar el stub {package}: {res.stdout} {res.stderr}")


def install_fixture(name: str) -> dict:
    fx = fixture(name)
    install_packages([*fx["stubs"], *fx.get("protected_stubs", [])])
    return fx


def load_models() -> dict:
    return json.loads((HERE / "models.json").read_text(encoding="utf-8"))


def install_model(model_id: str) -> dict:
    """Instala los paquetes de fabricante de un modelo real y, si procede, el stub de Play Store."""
    model = load_models()["models"][model_id]
    packages = list(model["vendor_packages"])
    if model["play_store"]:
        packages.append("com.android.vending")
    install_packages(packages)
    return model


def model_simulation(model: dict) -> dict:
    """Valores para TVLITE_SIMULATE: identidad y hardware del modelo (la RAM real la fija el AVD)."""
    sim = {"manufacturer": model["manufacturer"], "brand": model["brand"], "model": model["model"],
           "soc": model["soc"], "ram_mb": model["ram_mb"], "has_play_store": model["play_store"]}
    if model.get("abis"):
        sim["abis"] = model["abis"]
    return sim


def cmd_models(_args) -> None:
    data = load_models()
    for model_id, m in data["models"].items():
        ev = m["evidence"]
        print(f"{model_id:24} Android {m['android']:>2}  {m['ram_mb']:>4} MB  AVD {m['avd']:10} "
              f"hw={ev['hardware'].split(' ')[0]:12} pkgs={ev['packages'].split(' ')[0]}")
    print("\nNo soportadas (no son Android):")
    for u in data["unsupported"]:
        print(f"  {u['name']}: {u['reason']}")


def cmd_fixture(args) -> None:
    fx = install_fixture(args.name)
    simulate = json.dumps(fx["simulate"])
    print(f"Fixture '{args.name}' instalado. Para que tvlite lo vea como esa marca:")
    print(f"  TVLITE_SIMULATE='{simulate}'")
    if fx.get("extra_list"):
        print(f"  TVLITE_EXTRA_LISTS={HERE / fx['extra_list']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list").set_defaults(func=cmd_list)
    for name, func in (("setup", cmd_setup), ("start", cmd_start)):
        p = sub.add_parser(name)
        p.add_argument("profile", choices=list(profiles()))
        if name == "start":
            p.add_argument("--window", action="store_true", help="mostrar la ventana del emulador")
        p.set_defaults(func=func)
    sub.add_parser("stop").set_defaults(func=cmd_stop)
    sub.add_parser("models", help="lista los modelos reales simulables").set_defaults(func=cmd_models)
    p = sub.add_parser("fixture")
    p.add_argument("name", choices=list(json.loads((HERE / "fixtures.json").read_text(encoding="utf-8"))["fixtures"]))
    p.set_defaults(func=cmd_fixture)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
