# Teles y entornos probados

[English](DEVICES.md) · **Español**

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

**`tvlite` en sí en esta tele (2026-10-18):** `detect`, `plan`, `report`, `metrics` y `apply --dry-run` funcionaron como se esperaba (el plan salió vacío porque la tele ya estaba limpia a mano). Una **ejecución real** quitó una app de usuario, Red Bull TV, que viene en 4 APK (base + 3 divisiones): los 4 se guardaron en el backup, los ajustes temporales (tele despierta, Play Protect) se restauraron, y `restore` reinstaló la app desde los APK guardados (5 restauraciones, 0 fallos); arrancó sin ningún fallo. Es justo el caso que se rompió la primera vez a mano.

> **Aún no probado en hardware real con `tvlite`:** una limpieza completa desde estado de fábrica, el cambio de launcher y las instalaciones desde Play Store. Si lo pruebas en otra tele, abre un Device report (`tvlite report <ip>` genera el texto).

Hallazgos de esta tele que han dado forma al diseño:

- `pm uninstall -k --user 0` solo es reversible en apps de **sistema**; en apps de usuario el APK se borra y `install-existing` deja un registro fantasma. (`tvlite` ahora guarda antes el APK de las apps de usuario.)
- En esta tele, asignar el rol HOME **no bastó**: hubo que desactivar el launcher de Google (`pm disable-user`).
- La mayoría de la RAM era de Google Play Services y Play Store (~260 MB), que se conservan.
- El `load average` (~47) se queda alto en reposo por hilos del kernel del chip de vídeo en estado "D"; es normal en esta tele y no indica un problema.
- La tele se cae de la red al entrar en reposo, por eso `tvlite` la mantiene despierta y reconecta.

## Emulado

Perfiles de [`tools/emulator/profiles.json`](../tools/emulator/profiles.json). Suite: `installer/tests/integration` (detección, medición de memoria, flujo completo y restauración con los fixtures `tcl` y `acme`, `--dry-run` y el informe anónimo).

| Perfil | Android | RAM | ABI | Estado |
|---|---|---|---|---|
| `atv9-1gb` | 9 (API 28) | 1 GB | x86 | 6/6 pruebas pasan (2026-10-18). Ruta de launcher sin roles (`set-home-activity`). |
| `atv11-1gb` | 11 (API 30) | 1 GB | x86 | 6/6 pruebas pasan (2026-10-18). |
| `atv14-2gb` | 14 (API 34) | 2 GB | x86 | 6/6 pruebas pasan (2026-10-18), incluido Play Protect. |
| `atv11-2gb`, `atv14-4gb` | 11 / 14 | 2 / 4 GB | x86 | definidos, sin ejecutar (el perfil `normal` solo está cubierto por pruebas unitarias). |

Hallazgos del emulador que han cambiado el código:

- **Play Protect (Android 14 con Play Store):** al instalar un APK desconocido por ADB aparece un diálogo en pantalla y la instalación se queda esperando indefinidamente (en la TCL real no ocurrió). Ahora `tvlite` desactiva **solo** `verifier_verify_adb_installs` durante la instalación de sus APK, lo anota en el diario y lo devuelve siempre a su valor original.
- **Las apps de usuario no se restauran con `install-existing`:** el emulador reprodujo el "registro fantasma" que ya se vio en la TCL con Red Bull TV. Ahora la restauración las reinstala desde el APK guardado en el backup, y la prueba de integración comprueba después que el paquete es real.
- **Android 14 exige `targetSdk` ≥ 23** para instalar un APK, y ya trae paquetes de sistema (p. ej. Play Juegos) con nombres que usan también los fixtures.

Qué **no** cubre el emulador: la GPU y el SoC reales, los paquetes específicos de cada fabricante (los fixtures solo crean apps vacías con esos nombres), ni el comportamiento de las apps de Play Store con `tvlite` (las imágenes `android-tv` de API 28/30 no incluyen Play Store).

Las pruebas unitarias (74 más 6 de integración) corren contra una tele simulada (`installer/tests/fake_adb.py`).

## Reportado por usuarios

_Aún ninguno._ Añade el tuyo abriendo un issue con la plantilla *Device report* y pegando la salida de `tvlite report <ip>`.

## Procesadores probados

| SoC | Nivel |
|---|---|
| MediaTek mt5867 | Hardware real |
| x86 (emulador Android TV) | Emulado |
