# Contribuir

[English](CONTRIBUTING.md) · **Español**

Gracias por querer ayudar. Este proyecto toca el software de teles ajenas, así que **la seguridad y la honestidad sobre lo probado van por delante de la cantidad**.

## La forma más útil de ayudar: informar de tu tele

1. Activa las opciones de desarrollador y la depuración por red en la tele (ver el README).
2. Ejecuta, **sin cambiar nada**:
   ```bash
   tvlite report <ip-de-tu-tele>
   ```
   Imprime un informe anónimo (modelo, Android, procesador, RAM, qué paquetes quitaría `tvlite` y los paquetes de sistema del fabricante que ninguna lista cubre aún). **No se envía nada**: léelo y pégalo en un issue **Device report**. No lleva número de serie, IP, cuentas ni apps instaladas por el usuario.
3. Opcionalmente prueba lo de verdad y cuéntanos cómo fue:
   ```bash
   tvlite apply <ip> --dry-run      # muestra el plan
   tvlite apply <ip>                # lo aplica (antes guarda todo)
   tvlite restore <ip> <backup>     # ¿devolvió el estado original?
   ```
   ¿Arrancó bien? ¿Home abre el launcher nuevo? ¿Restore devolvió todos los paquetes?

Con eso entra en [docs/DEVICES.es.md](docs/DEVICES.es.md) como *reportado*.

## Añadir una lista de paquetes (otra marca o procesador)

Las listas están en [`installer/tvlite/data/packages.json`](installer/tvlite/data/packages.json) y, para contribuciones, en `installer/tvlite/data/community/*.json` (mismo formato, solo la clave `lists`).

Reglas, todas comprobadas por `validate_catalog` y por las pruebas:

- **`verified_on` obligatorio** y con dispositivos **reales** ("Marca Modelo, SoC, Android X"). Sin eso la lista se ignora por defecto. Si no la has probado en una tele física, no pongas `verified_on`: pon `notes` explicando de dónde sale cada paquete.
- **Nunca** paquetes protegidos (Play Store, GMS, SystemUI, ajustes, proveedores, red, Bluetooth, launchers…). El validador falla si aparecen.
- **`tier`** honesto: `safe` (nadie lo notará), `recommended` (prescindible en una tele con poca RAM), `aggressive` (puede quitar una función, y entonces añade `breaks` explicándolo), `optional` (nunca se preselecciona: voz, accesibilidad…).
- **`match`** lo más estrecho posible (`manufacturer`, `brand`, `model`, `soc`).
- Las apps de sistema se quitan y restauran con `install-existing`. Si un paquete es una app de *usuario* en tu tele, `tvlite` guarda antes su APK para poder restaurarla; dilo en el PR.
- Prueba la lista **antes** de proponerla, también la restauración:
  ```bash
  TVLITE_EXTRA_LISTS=mi_lista.json tvlite plan <ip>
  TVLITE_EXTRA_LISTS=mi_lista.json tvlite apply <ip> --only paquete.uno,paquete.dos
  tvlite restore <ip> <carpeta-del-backup>
  ```
- Indica en el PR el resultado de `tvlite restore`: ¿volvió cada paquete?

## Código

```bash
cd installer
pip install -e ".[dev]"
python -m pytest                       # unitarias, con FakeAdb (sin hardware)
```

- Toda la interacción con Android pasa por `tvlite/android.py` y se simula en `tests/fake_adb.py`. Si añades un comando nuevo, enséñaselo al `FakeAdb`.
- Prueba los **fallos**, no solo el camino feliz (launcher roto, tele que no responde, conexión perdida, app que no se restaura).
- Si cambias algo de seguridad (protegidos, reversibilidad, restauración), comprueba que tu cambio **hace fallar** un test al quitarlo (una prueba de mutación manual vale).
- La interfaz gráfica es una capa fina: la lógica va en el núcleo, donde se puede probar sin pantalla. En Tkinter, **no accedas a variables de Tk desde hilos**.
- Pruebas contra emulador: ver README → *Emuladores de Android TV*. Añade una fila a `docs/DEVICES.es.md` solo cuando hayas ejecutado el perfil.
- Los comentarios del código están sobre todo en español; para código nuevo el inglés es bienvenido.

## Pull requests

`main` está protegida: nadie empuja a ella directamente. Haz un fork (o crea una rama), sube ahí tu cambio y abre una pull request; el mantenedor la revisa y la fusiona. La plantilla de la PR lista lo que hay que comprobar.

## Honestidad sobre lo probado

No marques un dispositivo como *probado* si solo lo has visto en emulador, ni una app como `verified` si no has visto su paquete en una tele real. La tabla de [docs/DEVICES.es.md](docs/DEVICES.es.md) separa **hardware real**, **emulado** y **reportado** a propósito.

## Licencia

Al contribuir aceptas que tu aportación se publique bajo [Apache-2.0](LICENSE).
