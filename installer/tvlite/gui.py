"""Asistente grafico (Tkinter). Es una capa fina sobre runner/debloat/appinstall: la logica
vive alli y esta probada sin interfaz. Las tareas largas corren en un hilo para no congelar la ventana."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from typing import Callable, Optional

from . import android, appinstall, debloat, device as devmod, runner
from .adb import Adb, AdbError, ensure_adb
from .i18n import default_language, translate
from .restore import restore


class App:
    STEPS = ("welcome", "connect", "device", "clean", "apps", "run")

    def __init__(self, root: tk.Tk, adb_factory: Optional[Callable[[Callable[[str], None]], Adb]] = None,
                 lang: Optional[str] = None) -> None:
        self.root = root
        self.lang = lang or default_language()
        self.adb_factory = adb_factory or (lambda progress: Adb(ensure_adb(progress)))
        self.adb: Optional[Adb] = None
        self.info: Optional[devmod.DeviceInfo] = None
        self.plan: list[debloat.PlanItem] = []
        self.plan_vars: list[tk.BooleanVar] = []
        self.app_vars: dict[str, tk.BooleanVar] = {}
        self.launcher_var = tk.BooleanVar(value=True)
        self.dry_var = tk.BooleanVar(value=False)
        self.summary: Optional[runner.Summary] = None
        self.step = 0
        self.events: "queue.Queue[tuple]" = queue.Queue()
        self.busy = False

        self.header = ttk.Frame(root, padding=(16, 12, 16, 0))
        self.header.pack(fill="x")
        self.title = ttk.Label(self.header, font=("TkDefaultFont", 14, "bold"))
        self.title.pack(side="left")
        self.lang_btn = ttk.Button(self.header, command=self.toggle_language)
        self.lang_btn.pack(side="right")
        self.body = ttk.Frame(root, padding=16)
        self.body.pack(fill="both", expand=True)
        self.nav = ttk.Frame(root, padding=(16, 0, 16, 12))
        self.nav.pack(fill="x")
        self.back_btn = ttk.Button(self.nav, command=self.go_back)
        self.back_btn.pack(side="left")
        self.next_btn = ttk.Button(self.nav, command=self.go_next)
        self.next_btn.pack(side="right")
        self.root.after(100, self._poll)
        self.show()

    # --- utilidades ---
    def t(self, key: str, **kw) -> str:
        return translate(self.lang, key, **kw)

    def toggle_language(self) -> None:
        self.lang = "en" if self.lang == "es" else "es"
        self.show()

    def clear(self) -> None:
        for child in self.body.winfo_children():
            child.destroy()

    def work(self, fn: Callable[[], object], done: Callable[[object], None]) -> None:
        """Ejecuta fn en un hilo; done(resultado_o_excepcion) corre en el hilo de la interfaz."""
        self.busy = True

        def target() -> None:
            try:
                self.events.put(("done", done, fn()))
            except Exception as exc:  # noqa: BLE001 - se muestra al usuario
                self.events.put(("done", done, exc))

        threading.Thread(target=target, daemon=True).start()

    def _poll(self) -> None:
        try:
            while True:
                kind, *rest = self.events.get_nowait()
                if kind == "done":
                    self.busy = False
                    rest[0](rest[1])
                elif kind == "log":
                    self._log(rest[0])
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def log_line(self, message: str) -> None:
        self.events.put(("log", message))

    def _log(self, message: str) -> None:
        widget = getattr(self, "log_box", None)
        if widget is not None and widget.winfo_exists():
            widget.insert("end", message + "\n")
            widget.see("end")

    # --- navegacion ---
    def show(self) -> None:
        self.root.title(self.t("title"))
        self.title.config(text=self.t(f"step_{self.STEPS[self.step]}"))
        self.lang_btn.config(text=self.t("language"))
        self.back_btn.config(text=self.t("back"), state="normal" if self.step > 0 else "disabled")
        self.next_btn.config(text=self.t("next"), state="normal", command=self.go_next)
        self.clear()
        getattr(self, f"build_{self.STEPS[self.step]}")()

    def go_next(self) -> None:
        if self.busy:
            return
        name = self.STEPS[self.step]
        if name == "connect":
            return self.do_connect()
        if name == "run":
            return
        self.step += 1
        self.show()

    def go_back(self) -> None:
        if not self.busy and self.step > 0:
            self.step -= 1
            self.show()

    # --- pasos ---
    def build_welcome(self) -> None:
        ttk.Label(self.body, text=self.t("welcome_text"), justify="left", wraplength=640).pack(anchor="w")

    def build_connect(self) -> None:
        ttk.Label(self.body, text=self.t("ip_label")).pack(anchor="w")
        self.ip_var = getattr(self, "ip_var", tk.StringVar())
        ttk.Entry(self.body, textvariable=self.ip_var, width=24).pack(anchor="w", pady=4)
        self.status = ttk.Label(self.body, text="", foreground="#b00020", wraplength=640, justify="left")
        self.status.pack(anchor="w", pady=8)
        ttk.Separator(self.body).pack(fill="x", pady=8)
        ttk.Label(self.body, text=self.t("pair_hint"), wraplength=640, justify="left").pack(anchor="w")
        row = ttk.Frame(self.body)
        row.pack(anchor="w", pady=4)
        self.pair_addr = tk.StringVar()
        self.pair_code = tk.StringVar()
        ttk.Label(row, text=self.t("pair_addr")).grid(row=0, column=0, sticky="w")
        ttk.Entry(row, textvariable=self.pair_addr, width=22).grid(row=0, column=1, padx=6)
        ttk.Label(row, text=self.t("pair_code")).grid(row=0, column=2, sticky="w")
        ttk.Entry(row, textvariable=self.pair_code, width=10).grid(row=0, column=3, padx=6)
        ttk.Button(row, text=self.t("pair_btn"), command=self.do_pair).grid(row=0, column=4)
        self.next_btn.config(text=self.t("connect"))

    def do_pair(self) -> None:
        addr, code = self.pair_addr.get().strip(), self.pair_code.get().strip()  # Tk solo en el hilo principal

        def job():
            return self.adb_factory(self.log_line).pair(addr, code)

        def done(result) -> None:
            text = str(result) if isinstance(result, Exception) else (result.stdout + result.stderr).strip()
            self.status.config(text=text, foreground="#1b5e20" if "paired" in text.lower() else "#b00020")

        self.status.config(text=self.t("preparing_adb"), foreground="#444")
        self.work(job, done)

    def do_connect(self) -> None:
        target = self.ip_var.get()  # Tk solo en el hilo principal: el hilo de trabajo recibe el valor ya leido
        try:
            runner.normalize_target(target)
        except ValueError as exc:
            self.status.config(text=str(exc), foreground="#b00020")
            return
        self.status.config(text=self.t("preparing_adb"), foreground="#444")
        self.next_btn.config(state="disabled")

        def job():
            adb = self.adb_factory(self.log_line)
            info = runner.connect(adb, target, self.log_line)
            plan = debloat.build_plan(
                info, android.list_packages(adb), system_packages=android.list_system_packages(adb))
            return adb, info, plan

        def done(result) -> None:
            self.next_btn.config(state="normal")
            if isinstance(result, runner.NotAuthorized):
                self.status.config(text=self.t("need_auth"), foreground="#b00020")
            elif isinstance(result, (AdbError, ValueError)):
                self.status.config(text=str(result), foreground="#b00020")
            elif isinstance(result, Exception):
                raise result
            else:
                self.adb, self.info, self.plan = result
                self.step += 1
                self.show()

        self.work(job, done)

    def build_device(self) -> None:
        ttk.Label(self.body, text=devmod.describe(self.info), justify="left", font=("TkDefaultFont", 11)).pack(anchor="w")

    def _scroll_area(self) -> ttk.Frame:
        canvas = tk.Canvas(self.body, highlightthickness=0, height=400)
        bar = ttk.Scrollbar(self.body, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=bar.set)
        canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        return inner

    def build_clean(self) -> None:
        ttk.Label(self.body, text=self.t("clean_hint"), wraplength=640, justify="left").pack(anchor="w", pady=(0, 6))
        if not self.plan:
            ttk.Label(self.body, text=self.t("nothing_to_clean")).pack(anchor="w")
            return
        if not self.plan_vars:
            self.plan_vars = [tk.BooleanVar(value=i.selected) for i in self.plan]
        inner = self._scroll_area()
        group = None
        for item, var in zip(self.plan, self.plan_vars):
            if item.list_name != group:
                group = item.list_name
                ttk.Label(inner, text=group, font=("TkDefaultFont", 10, "bold")).pack(anchor="w", pady=(8, 0))
            text = f"{item.label}  ({item.pkg})"
            if not item.verified:
                text += f"  [{self.t('unverified')}]"
            if not item.system:
                text += f"  [{self.t('irreversible')}]"
            if item.breaks:
                text += f"\n    (!) {item.breaks}"
            ttk.Checkbutton(inner, text=text, variable=var).pack(anchor="w")

    def build_apps(self) -> None:
        ttk.Label(self.body, text=self.t("apps_hint"), wraplength=640, justify="left").pack(anchor="w", pady=(0, 6))
        data = appinstall.load_apps()
        # La casilla del launcher va abajo y fija; la lista de apps hace scroll por encima.
        ttk.Checkbutton(self.body, text=self.t("launcher_check"), variable=self.launcher_var).pack(
            side="bottom", anchor="w", pady=(8, 0))
        inner = self._scroll_area()
        installed = android.list_packages(self.adb)
        for key, name in data["categories"].items():
            apps = [a for a in data["apps"] if a["category"] == key]
            frame = ttk.LabelFrame(inner, text=name, padding=6)
            frame.pack(fill="x", pady=4, padx=2)
            for i, app in enumerate(apps):
                var = self.app_vars.setdefault(app["id"], tk.BooleanVar(value=False))
                label = app["name"] + (" ✓" if app["package"] in installed else "")
                ttk.Checkbutton(frame, text=label, variable=var,
                                state="disabled" if app["package"] in installed else "normal").grid(
                    row=i // 3, column=i % 3, sticky="w", padx=8)

    def chosen_packages(self) -> set[str]:
        if not self.plan_vars:  # no se llego a abrir el paso de limpieza: valen las preselecciones
            return {i.pkg for i in self.plan if i.selected}
        return {i.pkg for i, v in zip(self.plan, self.plan_vars) if v.get()}

    def chosen_apps(self) -> list[str]:
        return [k for k, v in self.app_vars.items() if v.get()]

    def build_run(self) -> None:
        text = self.t("run_summary", n=len(self.chosen_packages()), a=len(self.chosen_apps()),
                      l=self.t("with_launcher") if self.launcher_var.get() else "")
        ttk.Label(self.body, text=text, wraplength=640, justify="left").pack(anchor="w")
        ttk.Checkbutton(self.body, text=self.t("dry_run"), variable=self.dry_var).pack(anchor="w", pady=6)
        self.log_box = scrolledtext.ScrolledText(self.body, height=14, width=88)
        self.log_box.pack(fill="both", expand=True, pady=6)
        self.next_btn.config(text=self.t("apply"), command=self.do_run)

    def do_run(self) -> None:
        if self.busy:
            return
        opts = runner.Options(
            debloat_packages=self.chosen_packages(), app_ids=self.chosen_apps(),
            activate_launcher=self.launcher_var.get(), dry_run=self.dry_var.get(),
        )
        self.next_btn.config(state="disabled")
        self.back_btn.config(state="disabled")

        def job():
            return runner.run(self.adb, self.info, opts, progress=self.log_line)

        def done(result) -> None:
            self.next_btn.config(text=self.t("restore"), command=self.do_restore, state="normal")
            if isinstance(result, Exception):
                self._log(f"{self.t('error')}: {result}")
                return
            self.summary = result
            if result.launcher_error:
                self._log(self.t("launcher_failed") + result.launcher_error)
            self._log(self.t("done"))
            self._log(f"{self.t('backup_at')} {result.backup_dir}")
            if result.dry_run:
                self.next_btn.config(state="disabled")

        self.work(job, done)

    def do_restore(self) -> None:
        if self.busy or not self.summary:
            return
        if not messagebox.askyesno(self.t("restore"), self.t("confirm_restore")):
            return
        self.next_btn.config(state="disabled")

        def done(result) -> None:
            self._log(f"{self.t('error')}: {result}" if isinstance(result, Exception) else self.t("restore_done"))

        self.work(lambda: restore(self.adb, self.summary.backup_dir, self.log_line), done)


def main() -> None:
    root = tk.Tk()
    root.geometry("820x700")
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
