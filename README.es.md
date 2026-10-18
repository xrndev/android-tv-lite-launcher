# android-tv-lite-launcher

[English](README.md) · **Español**

Optimiza una Android TV con poca RAM **de forma reversible**: limpieza segura, un launcher nativo diminuto y las apps que elijas, todo desde tu PC por ADB.

<!-- Botón de donaciones (DESACTIVADO hasta tener el enlace de PayPal): sustituye PAYPAL_URL y quita este comentario.
[![Donar con PayPal](https://img.shields.io/badge/Donar-PayPal-00457C?logo=paypal&logoColor=white)](PAYPAL_URL)
-->

> **Alfa.** Probado en **una tele real** (TCL, Android 11, 940 MB de RAM) y en emuladores. El instalador solo se ha usado en parte en esa tele. Ver [qué está probado](#qué-está-probado).

![Home de la tele con Lite Launcher y 9 apps](docs/img/launcher-home.png)

## Descarga: sin instalar nada

No necesitas Python ni nada más. Descarga tu archivo desde [Releases](../../releases) y haz doble clic (macOS/Linux: antes `chmod +x`):

| Sistema | Archivo |
|---|---|
| Windows 10/11 | `tvlite-windows-x64.exe` |
| macOS (Apple Silicon) | `tvlite-macos-arm64` |
| Linux (x86-64) | `tvlite-linux-x64` |

Detecta tu sistema y descarga, verifica y usa el ADB de Google él solo. Comprueba lo descargado con `SHA256SUMS`; los archivos no están firmados, así que Windows/macOS te pedirán confirmar una vez.

> **Aún no hay ningún release publicado** (hace falta la clave de firma del mantenedor, ver [RELEASING](docs/RELEASING.md)). Mientras tanto: [compilar desde el código](docs/DEVELOPMENT.es.md).

## Qué teles funcionan

Solo teles con **Android TV o Google TV** y Google Play Store (*Ajustes → Acerca de* lo dice). Sony, Philips, TCL, Xiaomi, TD Systems… **si** ese modelo lleva Android. **No soportadas:** LG (webOS), Samsung (Tizen), Roku TV, VIDAA (p. ej. Hisense 50A7100F), Fire TV. La marca por sí sola no decide.

## Qué hace

1. **Detecta tu tele** (modelo, Android, procesador, RAM, Play Store) y elige un perfil de optimización.
2. **Guarda un backup antes**: listas de paquetes, launcher, ajustes y el APK de cada app de usuario que quite.
3. **Limpia** solo paquetes de listas revisadas. Play Store y el sistema están protegidos.
4. **Instala las apps que elijas** (streaming, Stremio, VPN), de forma automática.
5. **Cambia a [Lite Launcher](launcher/)** (16 KB, nativo, sin animaciones) tras comprobar que abre. El launcher original solo se desactiva.
6. **Restaura todo** desde el backup con un clic, o solo si algo falla.

<details>
<summary>Paso a paso: 7 capturas del asistente</summary>

[Guía completa](docs/GUIDE.es.md) · [1 Bienvenida](docs/img/gui-es-1-welcome.png) · [2 Conectar](docs/img/gui-es-2-connect.png) · [3 Tu tele](docs/img/gui-es-3-your-tv.png) · [4 Limpieza](docs/img/gui-es-4-cleanup.png) · [5 Apps](docs/img/gui-es-5-apps.png) · [6 Resumen](docs/img/gui-es-6-summary.png) · [7 Resultado](docs/img/gui-es-7-result.png)

<img src="docs/img/gui-es-4-cleanup.png" width="48%"> <img src="docs/img/gui-es-5-apps.png" width="48%">
<img src="docs/img/gui-es-3-your-tv.png" width="48%"> <img src="docs/img/gui-es-7-result.png" width="48%">

</details>

## Seguridad en un minuto

Solo listas revisadas (nunca "lo que parezca bloat"), paquetes protegidos, backup antes de cualquier cambio, lotes pequeños con comprobación de salud y retroceso automático. Todo es reversible; las apps de usuario se guardan antes como APK. Detalles y limitaciones conocidas: [docs/SAFETY.es.md](docs/SAFETY.es.md).

## Qué está probado

| Entorno | Tipo | Qué se probó |
|---|---|---|
| TCL Smart TV (mt5867, 940 MB, Android 11) | **Hardware real** | Listas, launcher y apps a mano; `tvlite`: comandos de lectura, simulación y una eliminación + restauración reales de una app de 4 APK |
| Emuladores: Android 9, 11, 14 (1–2 GB) | Emulado | Flujo completo: limpieza, cambio de launcher, restauración |
| Perfiles de modelos reales: TCL, TD Systems ×3, Xiaomi, Philips, Sony | Simulado | La lógica, con la identidad, la RAM y los paquetes de cada modelo: 4 de 4 pruebas cada uno |

Un emulador no es una tele real: valida la lógica, no el hardware ni que quitar los paquetes de una marca sea seguro. Detalle por modelo, nivel de evidencia y fuentes: [docs/DEVICES.es.md](docs/DEVICES.es.md).

## Privacidad

`tvlite` **no envía nada** por sí solo. Al terminar puede ofrecerte un **informe anónimo del resultado** (modelo de la tele, Android, procesador, RAM, qué fue bien y el error, sin IP, usuario ni número de serie). Ves el contenido exacto antes y solo **Enviar** lo envía. [Detalles](docs/TELEMETRY.md).

## Contribuir

La ayuda más útil es **informar de tu tele**: `tvlite report <ip>` y pega el resultado en un issue. Faltan listas de paquetes de otras marcas. [CONTRIBUTING](CONTRIBUTING.es.md) · [Desarrollo](docs/DEVELOPMENT.es.md) · [Apache-2.0](LICENSE)
