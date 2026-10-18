"""Tele simulada para tests: implementa la misma interfaz que tvlite.adb.Adb y entiende los
comandos de shell que usa tvlite. Permite probar el flujo completo sin hardware, incluidos
los fallos (launcher roto, tele que deja de responder, launcher original 'terco')."""

from __future__ import annotations

import re
from pathlib import Path

from tvlite.adb import Result

STOCK = "com.google.android.tvlauncher"
LITE = "dev.xrndev.litelauncher"
PLAY = "com.android.vending"


class FakeAdb:
    def __init__(
        self,
        props=None,
        ram_kb=940628,
        packages=None,
        user_packages=None,
        stubborn_launcher=False,
        lite_broken=False,
        unhealthy_after_uninstalls=None,
        play_installs=True,
        authorized=True,
    ):
        self.serial = None
        self.props = {
            "ro.product.manufacturer": "TCL",
            "ro.product.brand": "TCL",
            "ro.product.model": "Smart TV",
            "ro.product.device": "mt5867",
            "ro.build.version.release": "11",
            "ro.build.version.sdk": "30",
            "ro.product.cpu.abilist": "armeabi-v7a,armeabi",
            "ro.board.platform": "mt5867",
            "sys.boot_completed": "1",
        }
        self.props.update(props or {})
        self.ram_kb = ram_kb
        # nombre -> estado. home=True significa que declara la categoria HOME.
        self.pkgs = {
            STOCK: {"installed": True, "enabled": True, "home": True, "system": True},
            PLAY: {"installed": True, "enabled": True, "home": False, "system": True},
            "com.android.systemui": {"installed": True, "enabled": True, "home": False, "system": True},
        }
        for name in packages or []:
            self.pkgs[name] = {"installed": True, "enabled": True, "home": False, "system": True}
        # Apps de usuario (/data/app): al quitarlas con -k el APK se borra y no se pueden restaurar.
        for name in user_packages or []:
            self.pkgs[name] = {"installed": True, "enabled": True, "home": False, "system": False}
        self.settings = {"global": {}}
        self.role_holder = None
        self.foreground = STOCK + "/.MainActivity"
        self.stubborn_launcher = stubborn_launcher
        self.lite_broken = lite_broken
        self.unhealthy_after = unhealthy_after_uninstalls
        self.play_installs = play_installs
        self.authorized = authorized
        self.uninstall_count = 0
        self.pending_play_pkg = None
        self.log: list[str] = []

    # --- estado derivado ---
    def _homes(self):
        return [n for n, p in self.pkgs.items() if p["installed"] and p["enabled"] and p["home"]]

    def _resolve_home(self):
        homes = self._homes()
        if not homes:
            return None
        if self.role_holder in homes and not self.stubborn_launcher:
            return self.role_holder
        stock = [h for h in homes if h != LITE]
        return (stock or homes)[0]

    def _healthy(self):
        return not (self.unhealthy_after is not None and self.uninstall_count >= self.unhealthy_after)

    # --- interfaz Adb ---
    def run(self, args, timeout=60):
        return Result(0, "", "")

    def connect(self, host_port):
        if not self.authorized:
            return Result(0, f"failed to authenticate to {host_port}", "")
        return Result(0, f"connected to {host_port}", "")

    def pair(self, host_port, code):
        return Result(0, "Successfully paired", "")

    def devices(self):
        state = "device" if self.authorized else "unauthorized"
        return f"List of devices attached\n{self.serial or '192.168.1.50:5555'}\t{state}\n"

    def install(self, apk, timeout=300):
        name = Path(str(apk)).stem
        pkg = LITE if "litelauncher" in name else f"installed.{name}"
        self.pkgs[pkg] = {"installed": True, "enabled": True, "home": pkg == LITE, "system": False}
        self.log.append(f"install {pkg}")
        return Result(0, "Performing Streamed Install\nSuccess", "")

    def uninstall(self, package):
        if package in self.pkgs:
            self.pkgs[package]["installed"] = False
            if self.role_holder == package:
                self.role_holder = None
        return Result(0, "Success", "")

    def pull(self, remote, local):
        return Result(0, "", "")

    def shell(self, command, timeout=60):
        self.log.append(command)
        c = command.strip()
        if c == "getprop":
            return "\n".join(f"[{k}]: [{v}]" for k, v in self.props.items())
        if c.startswith("getprop "):
            return self.props.get(c.split()[1], "")
        if c == "cat /proc/meminfo":
            return f"MemTotal:        {self.ram_kb} kB\nMemFree:  1000 kB"
        if c == "df /data":
            return "Filesystem 1K-blocks Used Available Use% Mounted on\n/dev/block/dm-12 3647536 2348352 1207352 67% /data"
        if c == "wm density":
            return "Physical density: 213"
        if c == "wm size":
            return "Physical size: 1280x720"
        if c == "echo ok":
            return "ok" if self._healthy() else ""
        if c.startswith("pm list packages"):
            flag = c.replace("pm list packages", "").strip()
            names = [
                n for n, p in self.pkgs.items()
                if p["installed"] and (flag != "-d" or not p["enabled"]) and (flag != "-s" or p["system"])
            ]
            return "\n".join(f"package:{n}" for n in names)
        m = re.match(r"pm uninstall -k --user 0 (\S+)", c)
        if m:
            pkg = m.group(1)
            if pkg in self.pkgs and self.pkgs[pkg]["installed"]:
                self.pkgs[pkg]["installed"] = False
                self.pkgs[pkg]["apk_gone"] = not self.pkgs[pkg]["system"]
                self.uninstall_count += 1
                return "Success"
            return "Failure [DELETE_FAILED_INTERNAL_ERROR]"
        m = re.match(r"pm path (\S+)", c)
        if m:
            p = self.pkgs.get(m.group(1))
            return f"package:/data/app/{m.group(1)}/base.apk" if p and p["installed"] else ""
        m = re.match(r"pm uninstall (\S+)$", c)
        if m:  # sin -k: limpia el registro (tambien el fantasma)
            self.pkgs.pop(m.group(1), None)
            return "Success"
        m = re.match(r"cmd package install-existing (\S+)", c)
        if m:
            pkg = m.group(1)
            if pkg in self.pkgs:
                if not self.pkgs[pkg].get("apk_gone"):
                    self.pkgs[pkg]["installed"] = True
                # Con el APK borrado Android dice "installed" pero no lo lista: registro fantasma.
                return f"Package {pkg} installed for user: 0"
            return "android.content.pm.PackageManager$NameNotFoundException"
        m = re.match(r"pm disable-user --user 0 (\S+)", c)
        if m:
            self.pkgs[m.group(1)]["enabled"] = False
            return f"Package {m.group(1)} new state: disabled-user"
        m = re.match(r"pm enable (\S+)", c)
        if m:
            self.pkgs[m.group(1)]["enabled"] = True
            return f"Package {m.group(1)} new state: enabled"
        m = re.match(r"settings get (\w+) (\S+)", c)
        if m:
            return self.settings.get(m.group(1), {}).get(m.group(2), "null")
        m = re.match(r"settings put (\w+) (\S+) (\S+)", c)
        if m:
            self.settings.setdefault(m.group(1), {})[m.group(2)] = m.group(3)
            return ""
        m = re.match(r"settings delete (\w+) (\S+)", c)
        if m:
            self.settings.get(m.group(1), {}).pop(m.group(2), None)
            return ""
        m = re.match(r"cmd role add-role-holder --user 0 \S+ (\S+)", c)
        if m:
            self.role_holder = m.group(1)
            return ""
        if c.startswith("cmd package set-home-activity"):
            self.role_holder = c.split()[-1].split("/")[0]
            return "Success"
        if c.startswith("cmd package resolve-activity"):
            home = self._resolve_home()
            return f"priority=0 preferredOrder=0\n{home}/.MainActivity" if home else "No activity found"
        if c.startswith("cmd package query-activities"):
            return "\n".join(f"{h}/.MainActivity" for h in self._homes())
        m = re.match(r"am start -n (\S+)", c)
        if m:
            comp = m.group(1)
            if not (comp.startswith(LITE) and self.lite_broken):
                self.foreground = comp
            return f"Starting: Intent {{ cmp={comp} }}"
        if c.startswith("am start -a android.intent.action.VIEW"):
            pkg = re.search(r"id=([\w.]+)", c).group(1)
            self.foreground = PLAY + "/.MainActivity"
            self.pending_play_pkg = pkg
            return "Starting: Intent { act=android.intent.action.VIEW }"
        if c == "input keyevent KEYCODE_HOME":
            home = self._resolve_home()
            if home and not (home == LITE and self.lite_broken):
                self.foreground = f"{home}/.MainActivity"
            return ""
        if c == "input keyevent KEYCODE_DPAD_CENTER":
            if self.pending_play_pkg and self.play_installs:
                self.pkgs[self.pending_play_pkg] = {"installed": True, "enabled": True, "home": False, "system": False}
                self.pending_play_pkg = None
            return ""
        if c.startswith("input keyevent"):
            return ""
        if c == "dumpsys activity activities":
            return f"  mResumedActivity: ActivityRecord{{1a2b u0 {self.foreground} t7}}"
        if c.startswith("uiautomator dump"):
            if self.pending_play_pkg:
                return '<node text="Instalar" /><node text="App" />'
            return '<node text="Abrir" />'
        raise AssertionError(f"FakeAdb no entiende el comando: {command}")
