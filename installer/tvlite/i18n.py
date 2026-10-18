"""Textos de la interfaz en español e inglés. Añadir un idioma = añadir un diccionario."""

from __future__ import annotations

import locale
import re

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
        "user_app": "app de usuario: se guarda su APK para poder restaurarla",
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
        "finish_security": (
            "IMPORTANTE: cuando termines, desactiva la 'Depuración por red' (o 'Depuración inalámbrica') en "
            "las Opciones de desarrollador de la tele. Mientras esté activa, cualquier dispositivo de tu red "
            "puede conectarse a la tele."
        ),
        "connection_lost_hint": (
            "Cuando la tele vuelva a responder, pulsa 'Restaurar la tele' para deshacer lo aplicado hasta ahora."
        ),
        "copy_report": "Copiar informe de mi tele",
        "report_copied": "Informe copiado: revísalo antes de pegarlo en un issue de GitHub.",
        "report_wait": "Preparando el informe...",
        "share_title": "¿Ayudar a mejorar tvlite?",
        "share_intro": (
            "Puedes enviar al desarrollador un informe ANÓNIMO de cómo ha ido. Es voluntario: no se envía nada "
            "si no pulsas «Enviar». Incluye modelo, Android, procesador y RAM de la tele, tu sistema operativo, qué "
            "pasos fueron bien o mal y el error (sin IP, nombre de usuario ni número de serie). No incluye tus apps, "
            "cuentas ni el nombre de tu red. Este es el contenido exacto:"
        ),
        "share_send": "Enviar informe", "share_skip": "No, gracias",
        "share_sent": "Informe enviado. ¡Gracias!", "share_failed": "No se pudo enviar el informe: ",
        "share_sending": "Enviando...",
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
        "user_app": "user app: its APK is saved so it can be restored",
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
        "language": "Español",
        "finish_security": (
            "IMPORTANT: when you are done, turn off 'Network debugging' (or 'Wireless debugging') in the TV's "
            "Developer options. While it stays on, any device on your network can connect to the TV."
        ),
        "connection_lost_hint": (
            "When the TV answers again, press 'Restore the TV' to undo what was applied so far."
        ),
        "copy_report": "Copy my TV report",
        "report_copied": "Report copied: review it before pasting it into a GitHub issue.",
        "report_wait": "Preparing the report...",
        "share_title": "Help improve tvlite?",
        "share_intro": (
            "You can send the developer an ANONYMOUS report of how it went. It is voluntary: nothing is sent unless "
            "you press 'Send'. It includes the TV's model, Android, SoC and RAM, your operating system, which steps "
            "worked or failed and the error (with IPs, user names and serial numbers removed). It does not include "
            "your apps, accounts or network name. This is the exact content:"
        ),
        "share_send": "Send report", "share_skip": "No, thanks",
        "share_sent": "Report sent. Thank you!", "share_failed": "Could not send the report: ",
        "share_sending": "Sending...",
    },
}


def default_language() -> str:
    code = (locale.getlocale()[0] or "").lower()
    return "es" if code.startswith("es") or code.startswith("spanish") else "en"


def translate(lang: str, key: str, **kwargs) -> str:
    text = STRINGS.get(lang, STRINGS["en"]).get(key) or STRINGS["en"][key]
    return text.format(**kwargs) if kwargs else text


# --- Mensajes del nucleo (escritos en espanol) -> ingles -------------------------------------------------
# El nucleo emite texto en espanol; la interfaz en ingles lo traduce con esta tabla. Hay una prueba que
# falla si un flujo principal deja espanol en la salida en ingles.

def _removed(m: "re.Match[str]") -> str:
    text = m.group(1)
    text = text.replace(" (APK guardado para restaurar)", " (APK saved so it can be restored)")
    text = text.replace(" [NO reversible]", " [NOT restorable]")
    return "Removed " + text


_EN_RULES: list = [
    (r"^\[simulacion\] quitaria (.+)$", r"[dry run] would remove \1"),
    (r"^No se quita (\S+): no se pudo guardar su APK para restaurarla$",
     r"Not removing \1: its APK could not be saved, so it could not be restored"),
    (r"^Quitado (.+)$", _removed),
    (r"^No se pudo quitar (\S+): (.*)$", r"Could not remove \1: \2"),
    (r"^La tele no responde bien tras este lote: se deshace y se detiene el proceso$",
     "The TV stopped responding after this batch: undoing it and stopping"),
    (r"^Restaurando (\S+): (.+)$", r"Restoring \1: \2"),
    (r"^  No se pudo: (.*)$", r"  Could not: \1"),
    (r"^(.+?) se fijo hace (\d+) dias: .*$",
     r"\1 was pinned \2 days ago: a newer version may exist (the installer keeps using the pinned, verified one)"),
    (r"^Descargando platform-tools de Google \((.*)\)$", r"Downloading Google's platform-tools (\1)"),
    (r"^Descargando (.+) \((https?://.*)\)$", r"Downloading \1 (\2)"),
    (r"^Checksum de platform-tools verificado$", "platform-tools checksum verified"),
    (r"^Abriendo (.+) en Play Store$", r"Opening \1 in Play Store"),
    (r"^(.+): la descarga directa fallo, se prueba con Play Store$", r"\1: the direct download failed, trying Play Store"),
    (r"^Deshaciendo: se restaura el launcher original$", "Rolling back: restoring the original launcher"),
    (r"^Launcher original: desconocido$", "Original launcher: unknown"),
    (r"^Launcher original: (.+)$", r"Original launcher: \1"),
    (r"^Instalando el launcher nuevo$", "Installing the new launcher"),
    (r"^Hay un Lite Launcher con otra firma: .*$",
     "A Lite Launcher with a different signature is installed: reinstalling it (only its own settings are lost: order and hidden apps)"),
    (r"^Launcher nuevo activo$", "New launcher active"),
    (r"^Desactivando el launcher original (\S+) \(reversible\)$", r"Disabling the original launcher \1 (reversible)"),
    (r"^Conectando con (.+)$", r"Connecting to \1"),
    (r"^Animaciones del sistema a (.+)$", r"System animations set to \1"),
    (r"^Guardando el estado original en (.+)$", r"Saving the original state to \1"),
    (r"^Simulacion terminada: no se ha cambiado nada en la tele$", "Dry run finished: nothing was changed on the TV"),
    (r"^RAM disponible: (.+?) -> (.+?) \| paquetes: (.+?) -> (.+?) \(.*\)$",
     r"Available RAM: \1 -> \2 | packages: \3 -> \4 (RAM usually improves more after rebooting the TV)"),
    (r"^Se perdio la conexion con la tele \((.*)\)\. Copia de seguridad en (.+)$",
     r"Lost the connection to the TV (\1). Backup at \2"),
    (r"^Se perdio la conexion con la tele: (.*)$", r"Lost the connection to the TV: \1"),
    (r"^No se encuentra el APK del launcher \(litelauncher\.apk\)$", "Launcher APK (litelauncher.apk) not found"),
    (r"^No se pudo instalar el launcher: (.*)$", r"Could not install the launcher: \1"),
    (r"^El launcher nuevo no llego a abrirse en la tele$", "The new launcher never opened on the TV"),
    (r"^Android no usa el launcher nuevo como pantalla de inicio; se ha restaurado el original$",
     "Android does not use the new launcher as the home screen; the original was restored"),
    (r"^La direccion IP debe tener el formato (.+)$", r"The IP address must look like \1"),
    (r"^La direccion IP no es valida$", "The IP address is not valid"),
    (r"^No se pudo conectar: (.*)$", r"Could not connect: \1"),
    (r"^La tele aparece como '(.*)'; comprueba la depuracion por red$", r"The TV shows up as '\1'; check network debugging"),
    (r"^No hay APK oficial para la arquitectura de esta tele$", "There is no official APK for this TV's architecture"),
    (r"^Descarga fallida: (.*)$", r"Download failed: \1"),
    (r"^El APK descargado no coincide con el SHA-256 verificado.*$",
     "The downloaded APK does not match the verified SHA-256 (corrupt download or an unverified newer version): not installing it"),
    (r"^Play Store no se abrio$", "Play Store did not open"),
    (r"^Play Store no muestra el boton Instalar.*$",
     "Play Store does not show the Install button (app not available for this TV, or no Google account signed in)"),
    (r"^No se completo la instalacion a tiempo$", "The installation did not finish in time"),
    (r"^ya instalada$", "already installed"),
    (r"^No se pudo descargar ADB: (.*)$", r"Could not download ADB: \1"),
    (r"^No se pudo obtener el checksum oficial de platform-tools.*$",
     "Could not get platform-tools' official checksum; not installing it for safety"),
    (r"^El checksum de platform-tools no coincide con el que publica Google.*$",
     "platform-tools' checksum does not match the one Google publishes. If Google has just released a new version, retry in a few minutes."),
    (r"^Play Store no esta instalado en esta tele: no se instala (.+)$",
     r"Play Store is not installed on this TV: not installing \1"),
    (r"^Error inesperado \((.*)\)\. Copia de seguridad en (.+)$", r"Unexpected error (\1). Backup at \2"),
    (r"^Mira la tele y acepta el dialogo.*$", "Look at the TV and accept the 'Allow USB debugging' dialog."),
]
_EN_COMPILED = [(re.compile(pattern, re.S), repl) for pattern, repl in _EN_RULES]


def translate_message(lang: str, message: str) -> str:
    """Traduce un mensaje del nucleo al idioma de la interfaz. En espanol (o si no hay regla) no cambia."""
    if lang == "es":
        return message
    for regex, repl in _EN_COMPILED:
        if regex.match(message):
            return regex.sub(repl, message, count=1)
    return message
