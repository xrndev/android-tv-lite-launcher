"""Linea de comandos: tvlite detect | plan | apply | restore | apps | gui."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import android, appinstall, debloat, device as devmod, report as reportmod, runner
from .adb import Adb, AdbError, data_dir, ensure_adb
from .i18n import default_language, translate, translate_message
from .restore import restore


def _say(message: str) -> None:
    """Imprime un mensaje del nucleo en el idioma del sistema."""
    print(translate_message(default_language(), message))


def _adb(args) -> Adb:
    return Adb(ensure_adb(_say))


def _connect(args):
    adb = _adb(args)
    info = runner.connect(adb, args.ip, _say)
    return adb, info


def cmd_detect(args) -> int:
    adb, info = _connect(args)
    print(devmod.describe(info, default_language()))
    return 0


def cmd_report(args) -> int:
    adb, info = _connect(args)
    print(reportmod.build_report(adb, info))
    print("(Revisa el informe antes de pegarlo en un issue. No se ha enviado nada.)", file=sys.stderr)
    return 0


def cmd_metrics(args) -> int:
    adb, _ = _connect(args)
    m = android.memory_snapshot(adb)
    print(f"RAM: {m['ram_available_mb']} MB disponibles de {m['ram_total_mb']} MB | swap usado: {m['swap_used_mb']} MB | "
          f"paquetes: {m['packages']}")
    return 0


def cmd_plan(args) -> int:
    adb, info = _connect(args)
    print(devmod.describe(info, default_language()), "\n")
    plan = debloat.build_plan(
        info, android.list_packages(adb), include_unverified=args.include_unverified,
        system_packages=android.list_system_packages(adb),
    )
    if not plan:
        print("No hay paquetes conocidos que quitar.")
    for item in plan:
        mark = "[x]" if item.selected else "[ ]"
        warn = f"  (!) {item.breaks}" if item.breaks else ""
        flag = ("" if item.verified else " [sin verificar]") + ("" if item.system else " [app de usuario: se guarda su APK]")
        print(f"{mark} {item.pkg:55} {item.label}{flag}{warn}")
    return 0


def cmd_apply(args) -> int:
    adb, info = _connect(args)
    plan = debloat.build_plan(
        info, android.list_packages(adb), include_unverified=args.include_unverified,
        system_packages=android.list_system_packages(adb),
    )
    chosen = {i.pkg for i in plan if i.selected} if not args.only else set(args.only.split(","))
    if args.no_debloat:
        chosen = set()
    apps = [a for a in (args.apps or "").split(",") if a]
    print(devmod.describe(info, default_language()))
    print(f"\nSe quitaran {len(chosen)} paquetes, se instalaran {len(apps)} apps"
          f"{'' if args.no_launcher else ' y se cambiara el launcher'}.")
    if not args.yes and not args.dry_run and input("Continuar? [s/N] ").strip().lower() not in ("s", "si", "y", "yes"):
        print("Cancelado.")
        return 1
    opts = runner.Options(
        debloat_packages=chosen, app_ids=apps, activate_launcher=not args.no_launcher,
        dry_run=args.dry_run, include_unverified=args.include_unverified,
        allow_irreversible=args.allow_irreversible,
    )
    summary = runner.run(adb, info, opts, progress=_say)
    print(f"\nCopia de seguridad: {summary.backup_dir}")
    line = runner.format_metrics(summary.metrics_before, summary.metrics_after)
    if line:
        print(line)
    if summary.error:
        _say(summary.error)
        print(translate(default_language(), "connection_lost_hint"))
    if summary.launcher_error:
        _say(f"Launcher: {summary.launcher_error}")
    failed = [a for a in summary.apps if not a.ok]
    for app in failed:
        print(f"No se pudo instalar {app.app_id}: {app.detail}")
    if not args.dry_run:
        print("\n" + translate(default_language(), "finish_security"))
    return 1 if (summary.error or summary.launcher_error or failed or (summary.debloat and summary.debloat.aborted)) else 0


def cmd_restore(args) -> int:
    adb, _ = _connect(args)
    result = restore(adb, Path(args.backup), _say, include_apps=args.include_apps)
    print(f"Restaurado: {len(result.restored)}; fallos: {len(result.failed)}")
    return 0 if result.ok else 1


def cmd_backups(args) -> int:
    base = data_dir() / "backups"
    for path in sorted(base.glob("*")) if base.exists() else []:
        print(path)
    return 0


def cmd_apps(args) -> int:
    data = appinstall.load_apps()
    for app in data["apps"]:
        extra = f"  v{app['version']} (verificada {app['checked']}, SHA-256 fijado)" if app.get("sha256") else ""
        print(f"{app['id']:12} {data['categories'][app['category']]:22} {app['name']}{extra}")
    return 0


def cmd_gui(args) -> int:
    from .gui import main as gui_main

    gui_main()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tvlite", description="Optimiza una Android TV con poca RAM, de forma reversible.")
    sub = parser.add_subparsers(dest="command", required=True)

    def with_ip(p):
        p.add_argument("ip", help="IP de la tele, p. ej. 192.168.1.50")
        return p

    with_ip(sub.add_parser("detect", help="muestra que tele es")).set_defaults(func=cmd_detect)
    with_ip(sub.add_parser("report", help="informe anonimo para pegar en un issue (no se envia nada)")).set_defaults(func=cmd_report)
    with_ip(sub.add_parser("metrics", help="RAM disponible y paquetes ahora mismo")).set_defaults(func=cmd_metrics)
    p = with_ip(sub.add_parser("plan", help="muestra que se quitaria, sin tocar nada"))
    p.add_argument("--include-unverified", action="store_true")
    p.set_defaults(func=cmd_plan)
    p = with_ip(sub.add_parser("apply", help="aplica la optimizacion"))
    p.add_argument("--dry-run", action="store_true", help="simula sin cambiar nada")
    p.add_argument("--yes", action="store_true", help="no pedir confirmacion")
    p.add_argument("--apps", help="ids separados por comas (ver 'tvlite apps')")
    p.add_argument("--only", help="paquetes concretos a quitar, separados por comas")
    p.add_argument("--no-debloat", action="store_true")
    p.add_argument("--no-launcher", action="store_true")
    p.add_argument("--include-unverified", action="store_true")
    p.add_argument("--allow-irreversible", action="store_true",
                   help="quita apps de usuario aunque no se pueda guardar su APK (no se podran restaurar)")
    p.set_defaults(func=cmd_apply)
    p = with_ip(sub.add_parser("restore", help="deshace los cambios de una copia de seguridad"))
    p.add_argument("backup", help="carpeta de la copia (ver 'tvlite backups')")
    p.add_argument("--include-apps", action="store_true", help="tambien desinstala las apps que instalo tvlite")
    p.set_defaults(func=cmd_restore)
    sub.add_parser("backups", help="lista las copias de seguridad").set_defaults(func=cmd_backups)
    sub.add_parser("apps", help="lista las apps instalables").set_defaults(func=cmd_apps)
    sub.add_parser("gui", help="abre el asistente grafico").set_defaults(func=cmd_gui)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (AdbError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
