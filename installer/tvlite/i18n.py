"""Textos de la interfaz en español e inglés. Añadir un idioma = añadir un diccionario."""

from __future__ import annotations

import locale

STRINGS = {
    "es": {
        "title": "TV Lite - optimiza tu Android TV",
        "next": "Siguiente", "back": "Atrás", "connect": "Conectar", "apply": "Aplicar",
        "restore": "Restaurar la tele", "close": "Cerrar", "dry_run": "Solo simular (no cambia nada en la tele)",
        "step_welcome": "Antes de empezar",
        "welcome_text": (
            "Este programa limpia tu Android TV, instala un launcher ligero y las apps que elijas.\n"
            "Todo es reversible: antes de tocar nada se guarda una copia del estado original.\n\n"
            "Primero activa las opciones de desarrollador en la tele:\n"
            "  1. Ajustes > Preferencias del dispositivo > Información (o 'Acerca de').\n"
            "  2. Pulsa 7 veces sobre 'Compilación' (número de compilación) hasta ver 'Eres desarrollador'.\n"
            "  3. Vuelve atrás: aparece 'Opciones de desarrollador'. Entra y activa la depuración USB "
            "y la 'Depuración por red' (o 'Depuración inalámbrica' en Android 11+).\n"
            "  4. Anota la IP de la tele: Ajustes > Red e Internet > tu Wi-Fi o cable.\n\n"
            "El PC y la tele deben estar en la misma red."
        ),
        "step_connect": "Conectar con la tele",
        "ip_label": "IP de la tele (ej. 192.168.1.50):",
        "pair_hint": "Si tu tele usa 'Depuración inalámbrica' con código de emparejamiento, rellena también:",
        "pair_addr": "Dirección de emparejamiento (IP:puerto)", "pair_code": "Código", "pair_btn": "Emparejar",
        "connecting": "Conectando...", "need_auth": "Mira la tele y acepta el diálogo 'Permitir depuración USB'.",
        "preparing_adb": "Preparando ADB (se descarga solo la primera vez)...",
        "step_device": "Tu tele",
        "step_clean": "Limpieza (debloat)",
        "clean_hint": "Preseleccionado según la RAM de tu tele. Las marcadas con aviso pueden quitar alguna función.",
        "nothing_to_clean": "No se encontraron paquetes conocidos que quitar.",
        "unverified": "sin verificar",
        "irreversible": "NO reversible: habría que reinstalarla",
        "step_apps": "Apps a instalar",
        "apps_hint": (
            "La mayoría se instalan desde Play Store: la tele debe tener la sesión de Google iniciada y "
            "puede que tengas que mirar la pantalla por si pide algo. Stremio se descarga de su web oficial. "
            "Puedes dejarlo todo sin marcar."
        ),
        "launcher_check": "Instalar el Lite Launcher y usarlo como pantalla de inicio (recomendado)",
        "step_run": "Resumen y ejecución",
        "run_summary": "Se va a: guardar copia de seguridad, quitar {n} paquetes, instalar {a} apps{l}.",
        "with_launcher": " y cambiar el launcher",
        "done": "Terminado.", "backup_at": "Copia de seguridad en:", "restore_done": "Tele restaurada.",
        "error": "Error", "launcher_failed": "No se pudo activar el launcher: ",
        "confirm_restore": "Se deshacen los cambios usando la copia de seguridad. ¿Continuar?",
        "language": "English",
    },
    "en": {
        "title": "TV Lite - optimize your Android TV",
        "next": "Next", "back": "Back", "connect": "Connect", "apply": "Apply",
        "restore": "Restore the TV", "close": "Close", "dry_run": "Dry run only (changes nothing on the TV)",
        "step_welcome": "Before you start",
        "welcome_text": (
            "This tool cleans your Android TV, installs a lightweight launcher and the apps you choose.\n"
            "Everything is reversible: a backup of the original state is saved before touching anything.\n\n"
            "First enable developer options on the TV:\n"
            "  1. Settings > Device Preferences > About.\n"
            "  2. Press 'Build' 7 times until it says 'You are now a developer'.\n"
            "  3. Go back: 'Developer options' appears. Open it and enable USB debugging "
            "and 'Network debugging' (or 'Wireless debugging' on Android 11+).\n"
            "  4. Note the TV's IP: Settings > Network & Internet > your Wi-Fi or cable.\n\n"
            "The PC and the TV must be on the same network."
        ),
        "step_connect": "Connect to the TV",
        "ip_label": "TV IP address (e.g. 192.168.1.50):",
        "pair_hint": "If your TV uses 'Wireless debugging' with a pairing code, also fill in:",
        "pair_addr": "Pairing address (IP:port)", "pair_code": "Code", "pair_btn": "Pair",
        "connecting": "Connecting...", "need_auth": "Look at the TV and accept the 'Allow USB debugging' dialog.",
        "preparing_adb": "Preparing ADB (downloaded automatically the first time)...",
        "step_device": "Your TV",
        "step_clean": "Cleanup (debloat)",
        "clean_hint": "Preselected based on your TV's RAM. Items with a warning may remove a feature.",
        "nothing_to_clean": "No known packages to remove were found.",
        "unverified": "unverified",
        "irreversible": "NOT reversible: you would have to reinstall it",
        "step_apps": "Apps to install",
        "apps_hint": (
            "Most are installed from Play Store: the TV must be signed in to a Google account, and you may "
            "need to watch the screen in case it asks for something. Stremio is downloaded from its official "
            "site. You can leave everything unchecked."
        ),
        "launcher_check": "Install Lite Launcher and use it as the home screen (recommended)",
        "step_run": "Summary and run",
        "run_summary": "This will: save a backup, remove {n} packages, install {a} apps{l}.",
        "with_launcher": " and switch the launcher",
        "done": "Done.", "backup_at": "Backup saved at:", "restore_done": "TV restored.",
        "error": "Error", "launcher_failed": "Could not activate the launcher: ",
        "confirm_restore": "This undoes the changes using the backup. Continue?",
        "language": "Espanol",
    },
}


def default_language() -> str:
    code = (locale.getlocale()[0] or "").lower()
    return "es" if code.startswith("es") or code.startswith("spanish") else "en"


def translate(lang: str, key: str, **kwargs) -> str:
    text = STRINGS.get(lang, STRINGS["en"]).get(key) or STRINGS["en"][key]
    return text.format(**kwargs) if kwargs else text
