# Guía paso a paso

[English](GUIDE.md) · **Español**

## Antes de empezar

Activa las opciones de desarrollador en la tele: *Ajustes → Preferencias del dispositivo → Acerca de → pulsa 7 veces en "Compilación"*, y luego activa la depuración USB y la **depuración por red** (en Android 11+ puede llamarse *Depuración inalámbrica* y pedir un código de emparejamiento). El PC y la tele deben estar en la misma red; anota la IP de la tele (*Ajustes → Red*). El asistente lo explica todo en su primera pantalla.

> **Al terminar, desactiva de nuevo la depuración por red.** Mientras esté activa, cualquier dispositivo de tu red puede conectarse a la tele.

## El asistente

Capturas de `tvlite` recorriendo una **tele simulada** (la misma que usan las pruebas); en una tele real los datos serán los de tu tele. Se regeneran con `python tools/docs/capture_gui.py docs/img es`.

**1. Antes de empezar** — cómo activar las opciones de desarrollador y la depuración por red.

![Paso 1](img/gui-es-1-welcome.png)

**2. Conectar** — escribe la IP de la tele (o la dirección y el código de emparejamiento de la *Depuración inalámbrica* de Android 11+). La tele puede pedirte aceptar la clave de este PC. ADB se descarga y se verifica solo.

![Paso 2](img/gui-es-2-connect.png)

**3. Tu tele** — marca, modelo, Android, procesador, RAM, almacenamiento, si tiene Play Store y el perfil de optimización. Un botón copia un informe anónimo para los issues de GitHub.

![Paso 3](img/gui-es-3-your-tv.png)

**4. Limpieza** — solo paquetes de listas revisadas, preseleccionados según la RAM. Los marcados con `(!)` pueden quitar una función; las apps de usuario llevan etiqueta porque se guarda su APK antes de quitarlas.

![Paso 4](img/gui-es-4-cleanup.png)

**5. Apps a instalar** — streaming, reproductores, Stremio y VPN. La mayoría vienen de **Play Store** (la tele debe tener la sesión de Google iniciada); Stremio se descarga de su web oficial y se verifica.

![Paso 5](img/gui-es-5-apps.png)

**6. Resumen** — qué se va a hacer. Marca *Solo simular* para ver el plan sin cambiar nada.

![Paso 6](img/gui-es-6-summary.png)

**7. Resultado** — copia de seguridad primero, cambios aplicados, RAM antes y después, el recordatorio de desactivar la depuración por red y el botón **Restaurar la tele**.

![Paso 7](img/gui-es-7-result.png)

**8. En la tele** — ejemplo de la Home final con 9 apps (una tele real): banners a pantalla completa con esquinas redondeadas, reloj y Play Store siempre la primera. Una pulsación larga sobre cualquier app la mueve, la oculta o muestra su información.

![Home final](img/launcher-home.png)

## Línea de comandos

```bash
tvlite plan 192.168.1.50                 # qué se quitaría, sin tocar nada
tvlite apply 192.168.1.50 --dry-run
tvlite apply 192.168.1.50 --apps stremio,nordvpn
tvlite metrics 192.168.1.50              # RAM disponible y paquetes ahora mismo
tvlite report 192.168.1.50               # informe anónimo para pegar en un issue (no se envía nada)
tvlite backups                           # copias de seguridad guardadas
tvlite restore 192.168.1.50 <carpeta-del-backup>
```
