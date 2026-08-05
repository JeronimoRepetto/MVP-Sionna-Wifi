# Registro de defectos

> Cada defecto tiene un **ID estable**. Los tests, los paquetes de trabajo y los mensajes
> de commit los referencian. No renumeres: si un defecto se descarta, márcalo `DESCARTADO`
> y deja el hueco.
>
> Todos los hallazgos vienen de una revisión con verificación empírica contra Sionna RT
> 1.2.2 real (2026-08-05). Las líneas son indicativas y pueden desplazarse con los cambios.

## Leyenda

| Severidad | Criterio |
|---|---|
| 🔴 **P0** | Produce resultados incorrectos, o impide reproducir el proyecto |
| 🟠 **P1** | Funcionalidad muerta, deuda técnica con impacto, o riesgo legal / de seguridad |
| 🟡 **P2** | Higiene, rendimiento, documentación desactualizada |

| Estado | Significado |
|---|---|
| `ABIERTO` | Sin arreglar |
| `EN CURSO` | Alguien está trabajando en él |
| `CERRADO` | Arreglado y verificado. Añade el hash del commit |
| `ACEPTADO` | Se conoce y se decide convivir con él. Debe justificarse |
| `DESCARTADO` | No era un defecto |

---

## Resumen

| Grupo | Defectos | P0 | P1 | P2 |
|---|---|---|---|---|
| A · Física de la simulación | D-01 … D-04 | 4 | — | — |
| B · Reproducibilidad | D-05 … D-08 | 4 | — | — |
| C · Backend y API | D-09 … D-10, D-20 … D-21, D-34 … D-35 | — | 4 | 2 |
| D · Frontend | D-12 … D-15, D-17, D-22, D-36 | — | 4 | 3 |
| E · Higiene y legal | D-11, D-16, D-18, D-19, D-37 … D-38 | — | 3 | 3 |
| F · `wifi-csi-capture` | D-23 … D-24, D-28 … D-33 | 1 | 3 | 4 |
| G · Entorno | D-25 … D-27 | — | 3 | — |
| **Total** | **38** | **9** | **17** | **12** |

---

## A · Física de la simulación 🔴

Los cuatro defectos que hacen que los números mostrados no sean físicamente válidos.
Detalle técnico y forma correcta de hacerlo en
[`agent/SIONNA_API_CONTRACT.md`](agent/SIONNA_API_CONTRACT.md).

### D-01 🔴 `paths.a` se usa como complejo cuando es `(real, imag)`

| | |
|---|---|
| **Estado** | `ABIERTO` |
| **Componente** | `backend/simulation.py` |
| **Ubicación** | `:134-140` (`_extract_paths`), `:196-201` (`_compute_cir`), `:262-266` (`_compute_csi`) |
| **Invariantes** | INV-05, INV-06, INV-07 |
| **Lo cierra** | `WP-01` |

En Sionna RT 1.x, `paths.a` devuelve una tupla `(parte_real, parte_imaginaria)`. El código
toma `np.array(a_tuple[0])` y lo trata como la amplitud compleja, descartando la parte
imaginaria por completo.

**Evidencia medida** (`ESP32_1`, 3 caminos):

| | valor |
|---|---|
| `\|a\|` correcto | `[1.895e-05, 2.019e-04, 1.223e-04]` |
| `\|a\|` que calcula el código | `[9.531e-06, 1.681e-05, 5.952e-06]` |
| ratio | `0,503` / `0,083` / `0,049` → hasta **26,2 dB de error** |

Consecuencias: `total_power_db` erróneo hasta 26 dB; `np.angle()` de un real solo devuelve
`0` o `π`, así que las fases del CIR **no contienen información**; y `H(f)` se calcula con
coeficientes reales, invalidando el patrón de interferencia entre subportadoras.

**Es el defecto más grave del proyecto**: todo lo que muestra el panel CSI en modo Sionna
real es incorrecto.

### D-02 🔴 `num_samples` nunca llega al solver

| | |
|---|---|
| **Estado** | `ABIERTO` |
| **Componente** | `backend/simulation.py` |
| **Ubicación** | `:94` |
| **Invariante** | INV-10 |
| **Lo cierra** | `WP-02` |

```python
result = solver(scene=scene, max_depth=max_depth)   # falta samples_per_src
```

El slider «Ray Density» (100 K – 2 M) viaja por WebSocket, se registra en `parameters`, se
imprime en consola… y se descarta. `PathSolver` acepta `samples_per_src`.

### D-03 🔴 Los conmutadores de física son inertes

| | |
|---|---|
| **Estado** | `ABIERTO` |
| **Componente** | `backend/simulation.py` |
| **Ubicación** | `:87-91` |
| **Invariante** | INV-11 |
| **Lo cierra** | `WP-02` |

```python
try:
    scene.diffraction = diffraction    # Scene NO tiene este atributo
    scene.scattering  = scattering
except Exception:
    pass
```

Verificado: `hasattr(scene, 'diffraction') == False`, y la asignación **no lanza
excepción** — crea un atributo Python que nadie lee. En Sionna 1.x son argumentos de
`PathSolver`.

⚠️ Como el valor por omisión de `diffraction` en `PathSolver` es `False`, **la difracción
está siempre apagada**, mientras la UI, el README y `HOW_IT_WORKS.md` afirman lo contrario.
Además `RT_REFRACTION` y `RT_SPECULAR` de `config.py` no se importan en ningún sitio (ver
D-37).

### D-04 🔴 `_extract_paths` produce geometría y potencias falsas

| | |
|---|---|
| **Estado** | `ABIERTO` |
| **Componente** | `backend/simulation.py` |
| **Ubicación** | `:125-185`, en particular `:155-177` |
| **Invariantes** | INV-01, INV-02, INV-03, INV-04 |
| **Lo cierra** | `WP-03` |

Cuatro problemas encadenados:

1. **Falta el Tx y el Rx** (`:155`): `paths.vertices` solo contiene puntos de interacción.
   Medido — camino 0 de `ESP32_1`:
   `[0.962,3.500,0.901] → [0.614,2.406,0.000] → [-0.000,0.477,1.589]`, mientras
   Tx `[1.0,3.62,1.0]` y Rx `[-0.12,0.1,1.9]` no aparecen. Los rayos dibujados flotan entre
   paredes.
2. **Filtro de padding erróneo** (`:158`): `valid = np.any(path_verts != 0, axis=-1)`.
   Sionna no rellena con ceros — se observó un vértice en `[1.0, 3.62, -3.0]`, bajo el
   suelo. Existen `paths.valid` y `paths.interactions` (verificado) y el código los ignora.
3. **El camino LOS se descarta siempre** (`:159`): tiene cero interacciones, así que
   `np.sum(valid) < 2` lo elimina. El camino más importante nunca se dibuja.
4. **Potencia hardcodeada** (`:170`): `power = 1e-6` → todos los caminos salen a
   `-60,0 dB` exactos (verificado). El coloreado por potencia de `rays.js` y la opacidad
   variable son decorativos. `num_interactions = len(coords)-2` (`:176`) también es
   incorrecto al faltar los extremos.

---

## B · Reproducibilidad 🔴

### D-05 🔴 La escena no está en git

| | |
|---|---|
| **Estado** | `ABIERTO` |
| **Componente** | `.gitignore` |
| **Ubicación** | `:46-47` (`scenes/*.xml`, `!scenes/.gitkeep`) |
| **Lo cierra** | `WP-05` |

`scenes/room_simple.xml` está excluido. Un clon limpio no tiene escena → `rt.load_scene()`
lanza → `main.py` cae a **modo mock permanente**. El proyecto no es reproducible.

Es la entrada crítica del sistema: 79 líneas de XML escritas a mano que definen la sala.

### D-06 🔴 Tests desactualizados que enmascaran el estado real

| | |
|---|---|
| **Estado** | `ABIERTO` |
| **Componente** | `tests/` |
| **Ubicación** | `test_simulation.py:139-156`, `test_api.py:78-92` |
| **Lo cierra** | `WP-04` |

Resultado real con Sionna instalado: **4 de 6 suites verdes**.

```
test_config       11 passed        ✅
test_pose_library 13 passed        ✅
test_animation     6 passed        ✅
test_scene_loader  6 passed        ✅
test_simulation    8 passed, 3 FAILED
test_api          CRASH (falta httpx → D-16)
```

Los 3 fallos:

```
❌ test_paths_start_at_tx : ESP32_3 empieza en [0.389,3.5,1.491], Tx en [1.0,3.62,1.0]
❌ test_paths_end_at_rx   : ESP32_1 acaba en [1.0,3.62,-3.0], Rx en [-0.12,0.1,1.9]
❌ test_coverage_map_dimensions : esperaba malla X=40, obtuvo 90
```

Los dos primeros son manifestaciones legítimas de D-04. El tercero es un **test obsoleto**:
espera `coverage["data"]` y malla `ROOM/res` (40×70), pero el formato pasó a volumétrico
(`coverage["slices"]`) con la malla ampliada 1 m (90×60).

**El problema de fondo**: los tests que pasan solo ejercitan el mock. `test_paths_start_at_tx`
y `test_paths_end_at_rx` pasan en modo mock (donde los caminos sí incluyen Tx y Rx) y fallan
con el motor real. Dan una falsa sensación de seguridad.

### D-07 🔴 `generate_room.py` es código huérfano y peligroso

| | |
|---|---|
| **Estado** | `ABIERTO` |
| **Componente** | `blender/generate_room.py` |
| **Ubicación** | `:32` (`OUTPUT_XML`), `:161` (`mat_itu_brick` creado y nunca usado) |
| **Lo cierra** | `WP-05` |

La escena en uso (`scenes/room_simple.xml`) está **escrita a mano**: 6
`<shape type="rectangle">` con comentarios explicativos redactados por una persona. No la
generó Blender.

`generate_room.py` produciría una escena **distinta** (mallas exportadas por
`mitsuba-blender`, no primitivas `rectangle`) y escribe en la **misma ruta**. Ejecutarlo
destruye la única copia de la escena buena, que además no está en git (D-05).

Crea `mat_itu_brick` y nunca lo asigna: las 6 superficies llevan `itu_concrete`.

El pipeline «Blender → Mitsuba → Sionna» que anuncia el README nunca se ha usado.

### D-08 🔴 Los materiales documentados no son los usados

| | |
|---|---|
| **Estado** | `ABIERTO` |
| **Componente** | `README.md`, `scenes/room_simple.xml`, `backend/config.py` |
| **Lo cierra** | `WP-05` |

| Fuente | Paredes |
|---|---|
| `README.md` (tabla de configuración) | `itu_brick` (ITU-R P.2040) |
| `backend/config.py::MATERIALS` | `itu_brick` |
| `scenes/room_simple.xml` — **lo que se usa** | `itu_concrete` en las 6 superficies |
| `blender/generate_room.py` | `itu_concrete` en las 6 |

El XML declara `itu_brick` pero ninguna `<shape>` lo referencia. Log de arranque real:
`Material 'itu_concrete': thickness=0.12m` — un solo material. Y `MATERIALS` de
`config.py` **nunca se aplica** a la escena real: solo aparece en el mock y en los tests.

---

## C · Backend y API

### D-09 🟠 `is_animating` sin `global` → parada no efectiva

| | |
|---|---|
| **Estado** | `ABIERTO` · **Severidad** 🟠 P1 |
| **Componente** | `backend/main.py` |
| **Ubicación** | `:246`, `:252`, `:265`, `:281` |
| **Lo cierra** | `WP-06` |

En `websocket_simulation()` se asigna `is_animating = False` sin declarar `global` (sí se
declara para `scene`, `last_simulation_result`, `animation_task`, `sim_walk_paused`).
Python la trata como **local** en toda la función, así que esas asignaciones no tocan el
flag del módulo.

Efecto: `stop_animation` y `stop_sim_walk` cancelan la `asyncio.Task` pero no limpian el
flag. El `finally` de `handle_sim_walk` sí lo limpia, así que en el caso normal funciona —
pero hay una carrera: un *stop* seguido de *start* rápido puede encontrar
`is_animating == True` y abortar en silencio (`⚠️ Sim walk already in progress, ignoring`).

### D-10 🟡 `sim_walk_complete` se envía siempre

| | |
|---|---|
| **Estado** | `ABIERTO` · **Severidad** 🟡 P2 |
| **Componente** | `backend/main.py` |
| **Ubicación** | `:535` |
| **Lo cierra** | `WP-06` |

`if is_animating is False:` es siempre verdadero, porque el `finally` inmediatamente
anterior acaba de ponerlo en `False`. Se envía `sim_walk_complete` incluso cuando el
usuario ha parado la animación, además del `sim_walk_stopped`.

### D-20 🟠 `heatmap_height` se descarta y el slider está mal etiquetado

| | |
|---|---|
| **Estado** | `ABIERTO` · **Severidad** 🟠 P1 |
| **Componente** | `backend/simulation.py`, `frontend/index.html` |
| **Ubicación** | `simulation.py:308` (`_compute_coverage(scene, max_depth, _)`), `index.html:154-160` |
| **Lo cierra** | `WP-06` |

`heatmap_height` viaja UI → WS → `coverage_height` → y el tercer parámetro de
`_compute_coverage` es `_`: se descarta. El mapa siempre usa 10 rebanadas fijas de 0,1 a
1,9 m.

Y el control `#heatmap-height` es en realidad de **opacidad** (`setHeatmapHeight(opacity)`
en `heatmap.js:132`) con un `id` y una etiqueta engañosos. `COVERAGE_HEIGHT` de
`config.py` queda sin uso efectivo.

### D-21 🟠 CORS permisivo y backend expuesto en la LAN

| | |
|---|---|
| **Estado** | `ABIERTO` · **Severidad** 🟠 P1 |
| **Componente** | `backend/main.py`, `backend/config.py` |
| **Ubicación** | `main.py:92-98`, `config.py:82` (`API_HOST = "0.0.0.0"`) |
| **Lo cierra** | `WP-06` |

`allow_origins=["*"]` junto con `allow_credentials=True` es una combinación que los
navegadores rechazan, y el servidor escucha en `0.0.0.0` sin autenticación: accesible desde
toda la red local. Aceptable en desarrollo local, peligroso si se despliega.

Mínimo: restringir `allow_origins` a `http://localhost:5173`, poner
`allow_credentials=False`, y dejar `API_HOST` en `127.0.0.1` por defecto con override por
variable de entorno.

### D-34 🟡 Los frames de animación se borran a los 600 s

| | |
|---|---|
| **Estado** | `ABIERTO` · **Severidad** 🟡 P2 |
| **Componente** | `backend/main.py` |
| **Ubicación** | `:375`, `:532` |
| **Lo cierra** | Sin asignar |

`call_later(600, _cleanup_animation_dir, …)` borra los `.obj`, pero el frontend hace bucle
indefinido sobre ellos (`controls.js:292` `setInterval`). Tras 10 minutos, cada frame
produce un 404 y la animación se congela sin mensaje.

### D-35 🟡 `sim_walk` recarga la escena completa en cada frame

| | |
|---|---|
| **Estado** | `ABIERTO` · **Severidad** 🟡 P2 |
| **Componente** | `backend/main.py` |
| **Ubicación** | `:489` |
| **Lo cierra** | Sin asignar (candidato a F5) |

`load_scene(human_mesh_path=…)` por frame reparsea el XML, reconstruye la escena de Mitsuba
y vuelve a dar de alta Tx + 8 Rx. Debería actualizar solo los vértices de la malla humana
vía la API de Mitsuba. Es el cuello de botella para la generación de datasets a escala.

---

## D · Frontend

### D-12 🟡 `<div class="header-left">` duplicado

| | |
|---|---|
| **Estado** | `ABIERTO` · **Severidad** 🟡 P2 · **Ubicación** `frontend/index.html:16-17` · **Lo cierra** `WP-06` |

Dos aperturas consecutivas del mismo `div` sin cierre correspondiente.

### D-13 🟠 El conmutador «Show Labels» no hace nada

| | |
|---|---|
| **Estado** | `ABIERTO` · **Severidad** 🟠 P1 · **Ubicación** `frontend/index.html:164` · **Lo cierra** `WP-06` |

`#toggle-labels` no tiene ningún listener en `controls.js`. Es un control muerto en la UI.
Relacionado con D-22.

### D-14 🟠 Cálculo de RSSI desde caminos es código muerto

| | |
|---|---|
| **Estado** | `ABIERTO` · **Severidad** 🟠 P1 · **Ubicación** `frontend/src/controls.js:510-516` · **Lo cierra** `WP-06` |

```javascript
if (lastSimResult.paths && lastSimResult.paths[name]) {      // paths es un ARRAY
    lastSimResult.paths[name].forEach(p => totalPowerLin += p.power_lin);  // es power_linear
}
```

Dos errores: `paths` es un array de `{receiver, num_paths, paths}`, no un mapa por nombre;
y la clave es `power_linear`. La condición nunca se cumple y el RSSI se queda en el
`-90` por defecto.

### D-15 🟡 Dependencia `three-obj-loader` sin usar

| | |
|---|---|
| **Estado** | `ABIERTO` · **Severidad** 🟡 P2 · **Ubicación** `frontend/package.json` · **Lo cierra** `WP-06` |

El código importa `three/addons/loaders/OBJLoader.js` (`human.js:2`). La dependencia
`three-obj-loader@^1.1.3` no se usa.

### D-17 🟠 `getDefaultSceneInfo()` desincronizado con `config.py`

| | |
|---|---|
| **Estado** | `ABIERTO` · **Severidad** 🟠 P1 · **Ubicación** `frontend/src/main.js:103-121` · **Lo cierra** `WP-06` |

El fallback usado cuando `/api/scene` falla coloca los ESP32 **dentro** de la sala
(`0.1`/`1.9` en X, Z `1.8`/`0.15`) y el Tx en `[1.0, 3.4, 1.8]`. La configuración real los
pone **fuera** de las paredes (`-0.12`/`2.12`, Z `1.9`/`0.1`) y el Tx en `[1.0, 3.62, 1.0]`.
Si el backend no responde, la visualización miente sin avisar.

### D-22 🟡 Las etiquetas de sensores nunca se renderizan

| | |
|---|---|
| **Estado** | `ABIERTO` · **Severidad** 🟡 P2 · **Ubicación** `frontend/src/sensors.js:13`, `:18`, `:40` · **Lo cierra** `WP-06` |

`labels = []` se inicializa y se vacía, pero nunca se rellena. `LABEL_OFFSET_Y` no se usa.
Junto con D-13, la funcionalidad de etiquetas está a medio implementar: o se completa o se
elimina el control.

### D-36 🟡 Bundle de 526 kB en un solo chunk

| | |
|---|---|
| **Estado** | `ABIERTO` · **Severidad** 🟡 P2 · **Ubicación** `frontend/vite.config.js` · **Lo cierra** Sin asignar |

Vite avisa: `Some chunks are larger than 500 kB`. Casi todo es Three.js. Irrelevante en
local, relevante si se publica una demo.

---

## E · Higiene y legal

### D-19 🟠 Malla derivada de SMPL commiteada

| | |
|---|---|
| **Estado** | `ABIERTO` · **Severidad** 🟠 P1 |
| **Componente** | `frontend/public/human.obj` |
| **Lo cierra** | `WP-06` |

`frontend/public/human.obj` (467 KB, **6.890 vértices** — exactamente el recuento de SMPL)
está trackeado en git. El propio README advierte que los `.pkl` se excluyen por las
restricciones de licencia de [MPI-IS](https://smpl.is.tue.mpg.de/), y una malla derivada
del modelo cae razonablemente bajo la misma restricción.

**Requiere decisión del propietario del repo antes de publicar.** Opciones: eliminarlo del
historial y generarlo en el arranque (`main.py` ya lo hace si falta, `:59-61`), o confirmar
con MPI-IS que una malla concreta es redistribuible.

### D-11 🟡 Paquete `.deb` commiteado

| | |
|---|---|
| **Estado** | `ABIERTO` · **Severidad** 🟡 P2 · **Ubicación** `backend/cuda-keyring_1.1-1_all.deb.1` · **Lo cierra** `WP-06` |

4,2 KB de basura en git. `.gitignore` cubre `*.deb` pero no `.deb.1`. Hay también un
`cuda-keyring_1.1-1_all.deb` sin trackear.

### D-16 🟠 Falta `httpx` → los tests de API no arrancan

| | |
|---|---|
| **Estado** | `ABIERTO` · **Severidad** 🟠 P1 · **Ubicación** `backend/requirements.txt`, `tests/test_api.py:13-19` · **Lo cierra** `WP-04` |

`starlette.testclient` requiere `httpx`. No está en `requirements.txt` ni instalado.
`test_api.py` lanza `RuntimeError` al importar. También falta `pytest`.

### D-18 🟡 Documentación desactualizada

| | |
|---|---|
| **Estado** | `ABIERTO` · **Severidad** 🟡 P2 · **Ubicación** `docs/HOW_IT_WORKS.md:40`, `:68-72`; `README.md:31` · **Lo cierra** `WP-06` |

- `§3` afirma que el frontend «inyecta micro-turbulencia (ruido gaussiano)» en el CSI.
  `csi_panel.js` ya no lo hace: solo empuja frames reales.
- `§6` presenta la integración SMPL como *«the next major evolution»* cuando ya está
  implementada, animación incluida.
- `§1` afirma que el grosor de material se fija «desde `config.py`» para «brick, concrete,
  wood, etc.» — solo existe `itu_concrete` en la escena.
- El README dice paredes de `itu_brick` (ver D-08) y difracción activa (ver D-03).

### D-37 🟡 Constantes de configuración sin usar

| | |
|---|---|
| **Estado** | `ABIERTO` · **Severidad** 🟡 P2 · **Ubicación** `backend/config.py:20`, `:51`, `:61-62`, `:67-71`, `:77` · **Lo cierra** `WP-02` / `WP-06` |

| Constante | Situación |
|---|---|
| `RT_REFRACTION`, `RT_SPECULAR` | No se importan en ningún fichero |
| `ANTENNA_PATTERN` | Se importa en `scene_loader.py:62` y no se usa (el patrón `"dipole"` está hardcodeado en `PlanarArray`) |
| `NUM_DATA_SUBCARRIERS` | Sin usar |
| `MATERIALS` | Solo en el mock y en tests; nunca se aplica a la escena real |
| `COVERAGE_HEIGHT` | Se calcula y se descarta (ver D-20) |
| `WIFI_BANDWIDTH` | Solo en tests |

`RT_REFRACTION` y `RT_SPECULAR` se cablean en `WP-02`; el resto se cablea o se borra en
`WP-06`.

### D-38 🟡 Parámetros de OFDM hardcodeados

| | |
|---|---|
| **Estado** | `ABIERTO` · **Severidad** 🟡 P2 · **Ubicación** `backend/simulation.py:270-272` · **Lo cierra** `WP-01` |

```python
subcarrier_spacing = 312.5e3
subcarrier_indices = np.arange(-57, 57)
```

Deberían derivarse de `WIFI_BANDWIDTH` y `NUM_SUBCARRIERS` de `config.py`. Hoy hay dos
fuentes de verdad para el mismo dato.

---

## F · `wifi-csi-capture`

Repositorio hermano: `C:\Users\jeron\Desktop\wifi-csi-capture`.

### D-24 🔴 `digital_twin_sionna.py` usa la API de Sionna 0.x

| | |
|---|---|
| **Estado** | `ABIERTO` · **Severidad** 🔴 P0 |
| **Ubicación** | `tools/digital_twin_sionna.py:140-191` |
| **Lo cierra** | `WP-07` / `WP-08` |

Usa `Scene()` como constructor, `scene.compute_paths(max_depth=6)` y
`paths.cfr(frequencies=…)`. Nada de eso existe en Sionna 1.2.2. Es el **único** fichero que
intenta unir los dos repos, y está roto.

Además define una geometría distinta a la del MVP (escalera 3,0×4,0×2,8 vs sala
2,0×3,5×2,0) — ver [`contracts/SCENE_GEOMETRY.md`](contracts/SCENE_GEOMETRY.md).

### D-23 🟠 `CSI_UART_BAUD` de Kconfig es inerte

| | |
|---|---|
| **Estado** | `ABIERTO` · **Severidad** 🟠 P1 |
| **Ubicación** | `main/Kconfig.projbuild` (config `CSI_UART_BAUD`) vs `main/csi_capture_main.c:347`, `:351` |
| **Lo cierra** | `WP-09` |

El firmware hace `#define CSI_BAUD_RATE 921600` y
`uart_set_baudrate(CONFIG_ESP_CONSOLE_UART_NUM, CSI_BAUD_RATE)`. Nunca lee
`CONFIG_CSI_UART_BAUD`.

`ADVANCED.md` lo documenta como configurable y su sección de troubleshooting dice
«asegúrate de que `CSI_UART_BAUD` coincide con `--baud`» — pero cambiarlo no tiene efecto.

### D-28 🟠 `xQueueSendFromISR` desde contexto de tarea

| | |
|---|---|
| **Estado** | `ABIERTO` · **Severidad** 🟠 P1 · **Ubicación** `main/csi_capture_main.c:190` · **Lo cierra** `WP-09` |

El callback de CSI corre en el contexto de la **tarea Wi-Fi**, no en una ISR. Usar la
variante `FromISR` funciona en la práctica en ESP-IDF pero no es el contrato documentado:
se salta el manejo de yield. Debería ser `xQueueSend(..., 0)`.

### D-29 🟠 Formateo costoso dentro del callback de CSI

| | |
|---|---|
| **Estado** | `ABIERTO` · **Severidad** 🟠 P1 · **Ubicación** `main/csi_capture_main.c:169-183` · **Lo cierra** `WP-09` |

El diseño declarado es «callback no bloqueante → cola → tarea de salida», pero el
`snprintf` de la cabecera **más un `snprintf` por cada uno de los 228 valores** se ejecuta
dentro del callback — que es justamente el trabajo caro que se pretendía sacar del stack
Wi-Fi.

Encolar el buffer `int8` crudo (228 bytes) y formatear en `csi_output_task` sería fiel al
objetivo y reduciría la cola de 45 KB a ~8 KB (ver D-33).

### D-30 🟡 `PING_TARGET_IP` definido y sin usar

| | |
|---|---|
| **Estado** | `ABIERTO` · **Severidad** 🟡 P2 · **Ubicación** `main/csi_capture_main.c:44` · **Lo cierra** `WP-09` |

`#define PING_TARGET_IP "0.0.0.0"` nunca se usa: `start_icmp_ping()` toma la IP del gateway
real (`s_gateway_ip`). Define muerto que induce a error.

### D-31 🟡 `tests/tmp/` no está en `.gitignore`

| | |
|---|---|
| **Estado** | `ABIERTO` · **Severidad** 🟡 P2 · **Ubicación** `.gitignore`, `tests/conftest.py` · **Lo cierra** `WP-09` |

El `conftest.py` redirige `tmp_path` a `tests/tmp/` dentro del workspace y no limpia.
Ejecutar pytest deja ficheros sin trackear en el repo.

### D-32 🟡 Nombres de fichero inconsistentes en `measurement_protocol.py`

| | |
|---|---|
| **Estado** | `ABIERTO` · **Severidad** 🟡 P2 · **Ubicación** `tools/measurement_protocol.py:225` · **Lo cierra** `WP-10` |

Pasa `--position str(args.round)` a `capture_csi.py`, que calcula
`node_id = (position-1)*2+1`. El mapeo de nodos sale bien, pero el nombre del CSV usa
`pos{position_id:02d}`: los ficheros de la ronda 2 (nodos en posiciones 3 y 4) se llaman
`pos02`. `record_session.py`, más reciente, lo hace correctamente.

Nota menor asociada: `POSITIONS[*]["zone"]` vale `"ceiling"`/`"floor"` en el código pero
`ADVANCED.md` documenta `techo`/`suelo`.

### D-33 🟡 Cola de 45 KB copiada por valor

| | |
|---|---|
| **Estado** | `ABIERTO` · **Severidad** 🟡 P2 · **Ubicación** `main/csi_capture_main.c:48`, `:71-74`, `:360` · **Lo cierra** `WP-09` |

`csi_line_t` son 1.404 bytes; `xQueueCreate(32, sizeof(csi_line_t))` reserva ~45 KB y cada
envío copia la estructura completa. Con el cambio de D-29 bajaría a ~8 KB.

---

## G · Entorno

### D-25 🟠 Las variables de GPU están tras el guard de no-interactividad

| | |
|---|---|
| **Estado** | `ABIERTO` · **Severidad** 🟠 P1 |
| **Ubicación** | `~/.bashrc:135-137` (fuera del repo) |
| **Lo cierra** | `WP-00` |

`LD_LIBRARY_PATH` y `DRJIT_LIBOPTIX_PATH` están definidas después de
`case $- in *i*) ;; *) return;; esac`. En cualquier shell no interactiva no se aplican y
Sionna cae a CPU **en silencio**: 0,13 s/frame al 100 % de CPU en vez de 0,027 s en GPU.

Afecta a scripts, tareas de VS Code, CI y a cualquier agente de IA ejecutando comandos.
Detalle en [`agent/ENVIRONMENT.md §4`](agent/ENVIRONMENT.md).

### D-26 🟠 Driver NVIDIA nativo instalado dentro de WSL2

| | |
|---|---|
| **Estado** | `ABIERTO` · **Severidad** 🟠 P1 |
| **Ubicación** | `/usr/lib/x86_64-linux-gnu/libcuda.so.580.173.02` (fuera del repo) |
| **Lo cierra** | `WP-00b` |

Paquetes `libnvidia-compute-495/510/535/580`, `nvidia-kernel-common-580`,
`nvidia-cuda-toolkit 11.5.1` y un `NVIDIA-Linux-x86_64-580.142.run` de 398 MB en el home.

`libdrjit-core.so` hace `dlopen("libcuda.so")` (sin versionar), que **solo** resuelve al
driver nativo. Éste busca `/dev/nvidia0`, inexistente en WSL2, y devuelve
`cuInit(): no CUDA-capable device is detected`. PyTorch no se afecta porque carga
`libcuda.so.1`.

Origen probable: el paso 3 de `docs/INSTALL_WSL2_GPU.md` (`apt install cuda-toolkit`), cuyo
metapaquete puede arrastrar el driver. La fecha del fichero (29-jun-2026) encaja con una
actualización que rompió lo que antes funcionaba.

`LD_LIBRARY_PATH=/usr/lib/wsl/lib` es un parche; `WP-00b` elimina la causa. `WP-06` corrige
la instrucción de la guía.

### D-27 🟠 ESP-IDF roto por incompatibilidad de `click`

| | |
|---|---|
| **Estado** | `ABIERTO` · **Severidad** 🟠 P1 |
| **Ubicación** | `C:\Espressif\python_env\idf5.5_py3.13_env` (fuera del repo) |
| **Lo cierra** | `WP-00c` |

`click 8.3.2` instalado vs `click<8.2,>=7.0` requerido por esp-idf 5.5.3. `idf.py` no
funciona → no se puede compilar ni flashear el firmware → **F3 del roadmap está
bloqueada**.

El error aparece al abrir PowerShell porque el perfil hace dot-source de `export.ps1`. El
perfil **no se aborta** (los wrappers `npm`→`pnpm` posteriores sí se cargan) y **no afecta
a Sionna**, que vive en WSL2.

Arreglo: `C:\Espressif\install.bat`, o
`…\idf5.5_py3.13_env\Scripts\python.exe -m pip install "click<8.2"`.

---

## Cómo cerrar un defecto

1. Arréglalo dentro del paquete de trabajo que lo tiene asignado.
2. Si tenía un invariante en `xfail`, quita la marca — la suite es `strict=True` y un
   `xpass` la rompe a propósito.
3. Cambia el estado a `CERRADO` y añade el hash del commit y la fecha.
4. Si el arreglo invalida documentación, actualízala en el mismo commit.
5. Si al arreglarlo descubres un defecto nuevo, añádelo al final con el siguiente ID libre.
