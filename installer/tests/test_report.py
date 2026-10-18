"""El informe debe ser util para ampliar las listas y NO filtrar nada personal."""

from fake_adb import FakeAdb
from tvlite import android, cli, device, report


def make():
    adb = FakeAdb(packages=["com.tcl.esticker", "com.tcl.unknownvendorapp", "com.acme.preload", "com.google.android.foo"],
                  user_packages=["com.mi.private.app"])
    adb.serial = "SERIAL-ABC123-PRIVADO"
    adb.pkgs["com.tcl.esticker.overlay"] = {"installed": True, "enabled": True, "home": False, "system": True}
    return adb


def test_report_lists_vendor_system_packages_that_no_list_covers():
    text = report.build_report(make(), device.detect(make()))
    assert "com.tcl.unknownvendorapp" in text and "com.acme.preload" in text
    assert "com.tcl.esticker" in text  # sale en el plan, no como candidato
    assert "candidates for a new list" in text
    candidates = text.split("candidates for a new list")[1]
    assert "com.tcl.esticker`" not in candidates  # ya lo cubre una lista
    assert "com.google.android.foo" not in candidates  # paquete estandar de Google
    assert ".overlay" not in candidates and "com.android.vending" not in candidates


def test_report_does_not_leak_user_apps_or_identifiers():
    adb = make()
    text = report.build_report(adb, device.detect(adb, serial=adb.serial))
    assert "com.mi.private.app" not in text  # apps instaladas por el usuario
    assert "SERIAL-ABC123-PRIVADO" not in text and "192.168" not in text
    assert "review before posting" in text


def test_report_includes_what_maintainers_need():
    adb = make()
    text = report.build_report(adb, device.detect(adb))
    for needle in ("TCL Smart TV", "11 (API 30)", "mt5867", "armeabi-v7a", "ultra_low", "known packages would be removed"):
        assert needle in text


def test_vendor_packages_excludes_protected_and_known():
    adb = make()
    found = report.vendor_packages(adb)
    assert "com.android.vending" not in found and "com.tcl.esticker" not in found
    assert found == sorted(found)


def test_cli_metrics_and_report_commands_exist():
    parser = cli.build_parser()
    assert parser.parse_args(["report", "192.168.1.50"]).func is cli.cmd_report
    assert parser.parse_args(["metrics", "192.168.1.50"]).func is cli.cmd_metrics
