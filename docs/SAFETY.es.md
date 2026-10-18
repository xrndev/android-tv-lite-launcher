# Modelo de seguridad y limitaciones conocidas

[English](SAFETY.md) · **Español**

Esto modifica el software de tu tele. Un error en una tele desconocida puede dejarla sin arrancar, así que:

- **Solo listas revisadas.** Nunca se quita "lo que parezca bloat". Cada lista indica en qué dispositivos reales se verificó (`verified_on`); las que no lo indican se ignoran salvo que se pida (`--include-unverified`) y nunca se preseleccionan.
- **Paquetes protegidos** (Play Store, GMS, SystemUI, ajustes, proveedores, red, Bluetooth, los launchers de Xiaomi…): no se quitan aunque aparezcan en una lista. Hay una prueba que lo comprueba y un validador de listas.
- **Eliminación reversible.** Las apps de sistema se quitan con `pm uninstall -k --user 0` y vuelven con `install-existing`. Las **apps de usuario** pierden su APK al quitarlas (y `install-existing` deja un registro fantasma que *dice* estar instalado), así que **antes se guarda su APK (base y splits) en el backup** y la restauración las reinstala. Si no se puede guardar el APK, esa app **no se quita** (salvo `--allow-irreversible`). La restauración siempre verifica que el paquete vuelve de verdad.
- **Por lotes y con comprobación de salud.** Si la tele deja de responder, se deshace el lote y se detiene el proceso.
- **Diario a disco.** Cada acción se escribe y sincroniza al momento: se puede restaurar aunque el programa se interrumpa o se pierda la conexión. Con la conexión perdida la herramienta se detiene, te dice dónde está el backup y deja disponible **Restaurar**.
- **Launcher con retroceso.** Se instala, se comprueba que abre, se asigna como inicio y se verifica que el botón Home lo abre; si no, se restaura el original y se retira el nuevo. El launcher original solo se desactiva, nunca se desinstala.
- **Play Protect.** Algunas teles abren un diálogo al instalar un APK desconocido por ADB y la instalación se queda esperando. `tvlite` desactiva **solo** `verifier_verify_adb_installs` mientras instala sus propios APK, lo anota en el diario y lo restaura siempre.
- **Tele despierta.** `stay_on_while_plugged_in` se activa solo mientras dura el proceso, anotado y restaurado.
- **Descargas verificadas.** Las herramientas de ADB contra el checksum de Google, Stremio contra un SHA-256 fijado.
- **Modo simulación** (`--dry-run`): enseña qué haría sin cambiar nada.

## Limitaciones conocidas

- **Instalar apps desde Play Store maneja su interfaz por ADB** (abre la ficha y pulsa Instalar): depende del diseño de Play Store y de que la tele tenga sesión de Google. Con `tvlite` todavía no se ha probado contra la Play Store de una tele real. No se redistribuyen APK de terceros; Stremio se descarga de su sitio oficial y se verifica.
- **Solo se han verificado los nombres de paquete de unas pocas apps** (marcadas `verified` en `apps.json`).
- **Listas de debloat solo de TCL** (más las genéricas de Android/Google). Las de Sony y Xiaomi salen de fuentes públicas de la comunidad y están **sin verificar**. No hay ninguna lista pública para Philips, Hisense ni TD Systems. [Contribuye](../CONTRIBUTING.es.md).
- **Interfaz gráfica**: probada con una prueba automática contra una tele simulada y revisada en capturas, no con personas usándola.
- Windows es la plataforma principal; Linux/macOS deberían funcionar pero no están probados.
- **Sin firma de lanzamiento aún**: el APK del launcher se firma con una clave de depuración y los ejecutables no están firmados ([RELEASING.md](RELEASING.md)).
- Los comentarios del código y de las pruebas están sobre todo en español; la interfaz es bilingüe (es/en).
