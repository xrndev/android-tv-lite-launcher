# Contribuir

Gracias por querer ayudar. Este proyecto toca el software de teles ajenas, así que **la seguridad y la honestidad sobre lo probado van por delante de la cantidad**.

## La forma más útil de ayudar: probar tu tele

1. Activa las opciones de desarrollador y la depuración por red (ver el README).
2. Ejecuta, **sin cambiar nada**:
   ```bash
   tvlite detect <ip-de-tu-tele>
   tvlite plan <ip-de-tu-tele>
   tvlite apply <ip-de-tu-tele> --dry-run
   ```
3. Abre un issue con la plantilla **Device report** y pega la salida. Con eso entra en [docs/DEVICES.md](docs/DEVICES.md) como *reportado*.
4. Si además ejecutas `tvlite apply` de verdad, cuéntanos si arrancó bien, si Home abre el launcher nuevo y si `tvlite restore` te devolvió el original.

## Añadir una lista de paquetes (otra marca o procesador)

Las listas están en [`installer/tvlite/data/packages.json`](installer/tvlite/data/packages.json) y, para contribuciones, en `installer/tvlite/data/community/*.json` (mismo formato, solo la clave `lists`).

Reglas, todas comprobadas por `validate_catalog` y por los tests:

- **`verified_on` obligatorio** y con dispositivos **reales** ("Marca Modelo, SoC, Android X"). Sin eso la lista se ignora por defecto. Si no la has probado en una tele física, no pongas `verified_on`: pon `notes` explicando de dónde sale cada paquete.
- **Nunca** paquetes protegidos (Play Store, GMS, SystemUI, ajustes, proveedores, red, Bluetooth, launcher…). El validador falla si aparecen.
- **Solo paquetes de sistema.** Quitar una app de usuario no se puede deshacer; si un paquete solo existe como app de usuario en tu tele, no va en la lista.
- **`tier`** honesto: `safe` (nadie lo notará), `recommended` (prescindible en una tele con poca RAM), `aggressive` (puede quitar una función, y entonces añade `breaks` explicándolo), `optional` (nunca se preselecciona: voz, accesibilidad…).
- **`match`** lo más estrecho posible (`manufacturer`, `brand`, `model`, `soc`).
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
- Prueba los **fallos**, no solo el camino feliz (launcher roto, tele que no responde, app que no se restaura).
- Si cambias algo de seguridad (protegidos, reversibilidad, restauración), comprueba que tu cambio **hace fallar** un test al quitarlo (una prueba de mutación manual vale).
- La interfaz gráfica es una capa fina: la lógica va en el núcleo, donde se puede probar sin pantalla. En Tkinter, **no accedas a variables de Tk desde hilos**.
- Pruebas contra emulador: ver README → *Emuladores de Android TV*. Si añades un perfil, añade su fila a `docs/DEVICES.md` solo cuando lo hayas ejecutado.

## Honestidad sobre lo probado

No marques un dispositivo como *probado* si solo lo has visto en emulador, ni una app como `verified` si no has visto su paquete en una tele real. La tabla de [docs/DEVICES.md](docs/DEVICES.md) separa **hardware real**, **emulado** y **reportado** a propósito.

## Licencia

Al contribuir aceptas que tu aportación se publique bajo [Apache-2.0](LICENSE).
