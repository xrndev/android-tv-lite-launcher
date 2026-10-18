# Especificación: dossier de la tele (análisis de paquetes opcional)

[English](device-dossier.md) · **Español** · **Estado: BORRADOR para revisión, nada de esto está construido.**

## 1. Objetivo

Que cada persona que use `tvlite` pueda, **si quiere**, compartir un análisis anónimo de los paquetes de su tele **tal como viene de fábrica**, para que el proyecto aprenda qué paquetes tiene cada modelo y pueda construir listas y perfiles de emulador **reales** (identidad, `getprop`, inventario), que es justo lo que no se encuentra públicamente.

**No es un objetivo:** que el programa decida qué se puede quitar a partir de este análisis, ni quitar nada sin la prueba en una tele real (ver §8).

## 2. Cuándo y con qué permiso

- **Cuándo:** justo después de conectar y detectar la tele, **antes de aplicar nada**. Así se ve el inventario completo de fábrica y sirve aunque el usuario solo haga una simulación.
- **Permiso:** diálogo propio, **separado** del informe de resultado. Texto: "¿Compartir el análisis de tu tele para ayudar a otras?". Botones **Enviar** / **No, gracias**. El valor por defecto es **No**. Se muestra qué se enviaría (resumen en pantalla y un botón "ver el contenido completo").
- **Recordar la elección** (casilla, desmarcada por defecto, revocable): opcional. Sin ella se pregunta cada vez.
- **Línea de comandos:** `tvlite analyze <ip>` muestra el análisis sin enviar nada; `--share-analysis` lo envía tras mostrarlo. `--yes` no equivale a aceptar.
- Si no hay relé configurado, no se ofrece nada.

## 3. Qué se recoge (esquema `dossier` v1)

**Identidad y hardware:** fabricante, marca, modelo, dispositivo, placa, plataforma/SoC, versión de Android y SDK, **huella de firmware** (`ro.build.fingerprint`), ABI, RAM, resolución y densidad, si tiene Play Store, y las características de TV declaradas (`leanback`, `live_tv`…). Con esto salen perfiles de emulador con valores reales.

**Paquetes: solo los de sistema** (`pm list packages -s`). Por cada uno que **no esté ya en nuestra base de conocimiento** se envían estas señales; de los ya conocidos solo el nombre.

| Señal | Para qué sirve |
|---|---|
| nombre del paquete, nombre visible, versión | identificarlo |
| ¿es actualización de un paquete de sistema? ¿privilegiado? ¿`sharedUserId` de sistema? | cuánto está integrado en el firmware |
| ¿ofrece una **entrada de TV / sintonizador**? | casi seguro no se debe tocar |
| ¿es launcher (HOME)? ¿teclado? ¿servicio de accesibilidad? ¿administrador de dispositivo? | funciones básicas |
| nº de receptores de arranque, de servicios, permisos clave (red, arranque, superposición) | comportamiento en segundo plano |
| ¿se está ejecutando en reposo? RAM que usa | impacto real |
| ¿otros componentes del sistema dependen de él? (mejor esfuerzo) | riesgo al quitarlo |

**Nunca se recoge:** apps instaladas por el usuario, cuentas, nombre o contraseña de red, IP, MAC, número de serie, identificadores de publicidad o de Android, ningún identificador persistente de la tele ni del usuario. Las cadenas pasan por la misma limpieza que el informe de resultado.

## 4. Pistas de riesgo (orientativas)

El cliente añade a cada paquete una pista: `core` (entrada de TV, HOME, accesibilidad, teclado, o integrado y con dependientes), `unknown` o `low-signal`. **Es solo una ayuda para quien revise.** No activa ni preselecciona ninguna eliminación; la versión del heurístico va en el dossier. Una pista `low-signal` puede fallar: así pasó con `sonyshelf`.

## 5. Transporte y almacenamiento

```
tvlite --POST /v1/dossier--> relé (Cloudflare Worker) --guarda--> almacén (D1 o R2) --aviso corto--> Telegram
```

- Telegram **no guarda** datos (límite de unos 4.000 caracteres): solo recibe un aviso, p. ej. *"Nueva tele: Sony KD-43X80J · 214 paquetes de sistema · 9 desconocidos · id a1b2c3"*.
- El relé valida el esquema (**≤ 256 KB**, ≤ 600 paquetes, sin texto libre fuera de campos acotados), limita el ritmo por IP (guardada solo como hash) y guarda el JSON sin interpretarlo como HTML.
- **Deduplicación** sin identificadores personales: clave = hash(modelo + huella de firmware + conjunto de paquetes).
- **Retención:** propuesta 12 meses. Como no hay identificador persistente, **no se puede pedir el borrado de un envío concreto**: por eso solo se recogen datos no personales, y el diálogo lo dice.

## 6. Cómo se usa lo recogido

1. Revisión por modelo (tabla de desconocidos por frecuencia entre teles).
2. Investigación de cada candidato con fuentes (foros, listas públicas, `dumpsys`).
3. **Prueba real de quitar y restaurar por una persona con esa tele** (flujo existente: `TVLITE_EXTRA_LISTS`, `apply --only`, `restore`).
4. Una lista pasa a "verificada" con: **≥ 2 informes independientes**, restauración correcta en todos, sin pérdida de funciones tras unos días, y ámbito limitado a **modelo o SoC** (no a toda la marca). Entra como `optional`, sin marcar.
5. Del dossier se genera un perfil de emulador real: entrada de `models.json` con `getprop` reales y paquetes de verdad.

## 7. Cambios técnicos previstos

- `tvlite/dossier.py`: recogida (`dumpsys package`, `meminfo`, `pm`), señales, heurístico, limpieza. Tolerante a fallos por versión de Android.
- Base de conocimiento: índice de paquetes conocidos generado de las listas; las listas admiten `match` por **modelo** y `firmware`.
- Relé: ruta `/v1/dossier`, almacén, aviso corto. El informe de resultado actual no cambia.
- Asistente y CLI: diálogo y comandos de §2.
- `docs/TELEMETRY.md`: ampliar privacidad y retención.

## 8. Qué NO resuelve (para no engañarnos)

El análisis acelera la investigación, **no sustituye la prueba en una tele real**. Y ninguna señal automática garantiza que un paquete sea seguro de quitar.

## 9. Pruebas

- Unitarias con volcados de `dumpsys` reales de los emuladores (API 28, 29, 30, 34) y el `FakeAdb`.
- Privacidad: ninguna app de usuario ni identificador sale en el dossier; el texto pasa por la limpieza.
- Relé: esquema, tamaños, límites, deduplicación, y que Telegram solo recibe el aviso corto.
- Compatibilidad: que el dossier siga siendo válido en cada versión de Android probada.

## 10. Decisiones (tomadas por el mantenedor delegando en el criterio técnico)

1. **Almacén: D1** (SQL), por poder consultar por modelo, SoC y frecuencia de cada paquete.
2. **Retención: 12 meses.** Se dice en el diálogo.
3. **Recordar la elección:** casilla **opcional y desmarcada**, revocable. Sin ella se pregunta siempre.
4. **Huella de firmware: sí.** Identifica el software, no a la persona; permite agrupar por versión.
5. **Revisión:** semanal y corta. El relé enviará un **resumen automático** con los paquetes desconocidos más repetidos entre teles, para que la revisión sean unos minutos.
6. **Telegram:** un aviso corto por cada dossier mientras lleguen pocos; pasar a **resumen semanal** cuando superen unos 10 al día (se cambia con una variable, sin lanzar versión).

## 11. Fases

1. Recogida local + `tvlite analyze` (sin envío). Se prueba en emuladores y en tu tele.
2. Relé + almacén + aviso corto.
3. Diálogo de consentimiento en el asistente y la CLI.
4. Generador de perfiles de emulador a partir de un dossier.
