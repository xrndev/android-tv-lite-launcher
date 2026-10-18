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

Las pruebas unitarias (126, más las suites de emulador) corren contra una tele simulada (`installer/tests/fake_adb.py`).

## Modelos reales simulados

**No existe un emulador de marcas de tele reales**: los fabricantes no publican su firmware y los emuladores solo ofrecen imágenes genéricas de Android TV. Lo que hay aquí son **perfiles de modelos reales** ([`tools/emulator/models.json`](../tools/emulator/models.json)): la identidad, la RAM y la versión de Android de cada modelo, más nombres de paquetes de fabricante sacados de listas públicas de la comunidad, aplicados a un emulador con la RAM y la API que corresponden. Prueban la **lógica de tvlite**, no que quitar esos paquetes sea seguro en la tele física. Se ejecutan con `python tools/emulator/run_models.py <id>`.

Cada campo de un perfil indica su evidencia: **real** (visto en una tele física), **ficha pública** (con fuente citada) o **supuesto** (no se encontró y se dice). Los valores reales de `getprop` de estos modelos **no se encontraron**: los nombres de modelo son comerciales.

| Modelo | Android / RAM | SoC | Evidencia (hardware / paquetes) | Resultado en emulador |
|---|---|---|---|---|
| TCL Smart TV (mt5867) | 11 / 917 MB | mt5867 | real / real | **4 de 4 pasaron** (2026-10-18) |
| TD Systems M32C14GLE | 11 / 1 GB | desconocido | ficha pública / ninguno encontrado | **4 de 4 pasaron** (2026-10-18) |
| Xiaomi Mi TV 4A 32" | 9 (sin confirmar) / 1 GB | Amlogic T962 | ficha pública / comunidad (sin verificar) | **4 de 4 pasaron** (2026-10-18) |
| TD Systems K32DLX15GLE | 9 / 1 GB | ARM Cortex quad-core | ficha pública / ninguno encontrado | **4 de 4 pasaron** (2026-10-18) |
| TD Systems K32DLX10HS | 9 AOSP (se supone sin Play Store) / 1,5 GB | ARM Cortex-A55 | ficha pública / ninguno encontrado | **4 de 4 pasaron** (2026-10-18), incluido que las apps de Play se omiten con un aviso claro |
| Philips 43PUS7406 | 10 / 2 GB **supuesto** | desconocido | versión de Android de fichas; chipset y RAM **no encontrados** | **4 de 4 pasaron** (2026-10-18; hicieron falta tres intentos porque el PC se quedó sin memoria dos veces) |
| Sony KD-43X80J | 10 / 2 GB **supuesto** | desconocido | versión de Android de fichas; RAM **no encontrada**; paquetes de listas de comunidad | **4 de 4 pasaron** (2026-10-18) |

Las fuentes de cada modelo están en `models.json`. Lo que **no** se encontró: ninguna lista pública de paquetes de fabricante para **Philips, Hisense ni TD Systems**, así que para esas marcas `tvlite` solo hace la limpieza genérica de Android y Google.

**Ejemplos de teles que no funcionan** por no ser Android: **Hisense 50A7100F** (VIDAA U3), LG (webOS), Samsung (Tizen), Roku TV. Amazon Fire TV se basa en Android pero no está soportada (sin Play Store y con otro launcher).

Las listas de Sony y Xiaomi de `tvlite` salen de fuentes públicas de la comunidad, están **sin verificar** y nunca se aplican ni se preseleccionan por defecto. Un usuario informó de que en una Sony, quitar `sonyshelf` hizo desaparecer las entradas de la pantalla de inicio.

## Reportado por usuarios

_Aún ninguno._ Añade el tuyo abriendo un issue con la plantilla *Device report* y pegando la salida de `tvlite report <ip>`.

## Procesadores probados

| SoC | Nivel |
|---|---|
| MediaTek mt5867 | Hardware real |
| x86 (emulador Android TV) | Emulado |
