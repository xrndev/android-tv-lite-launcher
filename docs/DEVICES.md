# Teles y entornos probados

Esta tabla solo recoge lo que **se ha probado de verdad**. Tres niveles de confianza:

| Nivel | Significa |
|---|---|
| **Hardware real** | Alguien ejecutó la herramienta (o los mismos comandos) en una tele física y comprobó el resultado. |
| **Emulado** | Pasa la suite de integración en un emulador de Android TV. Valida la lógica, no el hardware. |
| **Reportado** | Un usuario informó (con el formulario de [Device report](../.github/ISSUE_TEMPLATE/device_report.yml)) de que funciona, sin que lo hayamos reproducido. |

## Hardware real

| Marca / modelo | SoC | RAM | Android | ABI | Qué se probó | Resultado | Fecha |
|---|---|---|---|---|---|---|---|
| TCL Smart TV | MediaTek mt5867 | 940 MB | 11 (API 30) | armeabi-v7a | Debloat (unas decenas de paquetes de Google, AOSP y TCL; no se anotó cuáles eran de sistema y cuáles de usuario), Lite Launcher como inicio (el launcher de Google hubo que **desactivarlo**: Android lo seguía eligiendo pese al rol HOME), Stremio, NordVPN y Red Bull TV desde Play Store, animaciones a 0. Todo aplicado **a mano** con los mismos comandos que automatiza `tvlite`. | Funciona. RAM libre ~250 → ~350–450 MB; el launcher usa ~40 MB frente a ~130 MB. | 2026-10 |

> `tvlite` (el instalador automático) **no se ha ejecutado todavía en una tele física**. Si lo pruebas, abre un Device report.

Hallazgos de esta tele que han dado forma al diseño:

- `pm uninstall -k --user 0` solo es reversible en apps de **sistema**; en apps de usuario el APK se borra y `install-existing` deja un registro fantasma.
- En esta tele, asignar el rol HOME **no bastó**: hubo que desactivar el launcher de Google (`pm disable-user`).
- La mayoría de las apps que ocupaban RAM eran Google Play Services y Play Store (~260 MB), que se conservan.
- El `load average` (~47) se queda alto en reposo por hilos del kernel del chip de vídeo en estado "D"; es normal en esta tele y no indica un problema.

## Emulado

Perfiles de [`tools/emulator/profiles.json`](../tools/emulator/profiles.json). Suite: `installer/tests/integration` (6 pruebas: detección, flujo completo y restauración con fixtures `tcl` y `acme` en modo por defecto y `--allow-irreversible`, y `--dry-run`).

| Perfil | Android | RAM | ABI | Estado |
|---|---|---|---|---|
| `atv9-1gb` | 9 (API 28) | 1 GB | x86 | 6/6 pruebas pasan (2026-10-18). Ruta de launcher sin roles (`set-home-activity`). |
| `atv11-1gb` | 11 (API 30) | 1 GB | x86 | 6/6 pruebas pasan (2026-10-18). |
| `atv14-2gb` | 14 (API 34) | 2 GB | x86 | 6/6 pruebas pasan (2026-10-18), tras corregir lo de Play Protect (ver abajo). |
| `atv11-2gb`, `atv14-4gb` | 11 / 14 | 2 / 4 GB | x86 | definidos, sin ejecutar (el perfil `normal` solo está cubierto por pruebas unitarias). |

Hallazgos del emulador que han cambiado el código:

- **Play Protect (Android 14 con Play Store):** al instalar un APK desconocido por ADB aparece un diálogo en pantalla y la instalación se queda esperando indefinidamente (en la TCL real no ocurrió). Ahora `tvlite` desactiva **solo** `verifier_verify_adb_installs` durante la instalación de sus APK, lo anota en el diario y lo devuelve siempre a su valor original.
- **Apps de usuario no restaurables:** el emulador reprodujo el "registro fantasma" de `install-existing` que ya se había visto en la TCL con Red Bull TV (ver arriba).
- **Android 14 exige `targetSdk` ≥ 23** para instalar un APK; y ya trae paquetes de sistema (p. ej. Play Juegos) con nombres que usan los fixtures.

Qué **no** cubre el emulador: la GPU y el SoC reales, los paquetes específicos de cada fabricante (los fixtures solo crean apps vacías con esos nombres), ni el comportamiento de Play Store (la imagen `android-tv` no la incluye).

## Reportado por usuarios

_Aún ninguno._ Añade el tuyo abriendo un issue con la plantilla *Device report* y pegando la salida de `tvlite detect <ip>`.

## Procesadores probados

| SoC | Nivel |
|---|---|
| MediaTek mt5867 | Hardware real |
| x86 (emulador Android TV) | Emulado |
