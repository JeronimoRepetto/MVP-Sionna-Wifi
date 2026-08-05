# WP-06 — Higiene de repo y documentación

| | |
|---|---|
| **Fase** | F1 · Física correcta |
| **Estado** | `PENDIENTE` |
| **Defectos que cierra** | D-09, D-10, D-11, D-12, D-13, D-14, D-15, D-17, D-18, D-19, D-20, D-21, D-22, D-37 (resto) |
| **Invariantes que pone en verde** | — |
| **Depende de** | — (paralelizable). D-18 conviene hacerlo **después** de WP-02 y WP-05 |
| **Nivel de verificación** | `sionna` |
| **Requiere intervención del usuario** | **sí — solo para D-19 (licencia SMPL)** |

## Objetivo

Cerrar la deuda acumulada que no es física: controles de UI muertos, código muerto, un
paquete `.deb` en git, un bug de scope en el backend, CORS permisivo, y documentación que
contradice al código. Ninguno rompe la simulación; en conjunto hacen el proyecto confuso y
difícil de mantener.

**Este paquete se puede partir** si resulta grande. Los grupos son independientes.

## Grupo 1 — Backend

### D-09 · `is_animating` sin `global`

`backend/main.py:246, 252, 265, 281` asignan `is_animating = False` sin declarar `global`
(sí se declara para `scene`, `last_simulation_result`, `animation_task`, `sim_walk_paused`).
Python la trata como **local** en toda `websocket_simulation()`, así que las asignaciones no
tocan el flag del módulo.

Efecto: un *stop* seguido de *start* rápido puede encontrar `is_animating == True` y abortar
en silencio (`⚠️ Sim walk already in progress, ignoring`).

**Arreglo**: añadir `is_animating` a una declaración `global` al principio de la función.
Considerar además encapsular el estado de animación en una pequeña clase, que elimina toda
esta familia de bugs — pero el arreglo mínimo es la declaración.

### D-10 · `sim_walk_complete` se envía siempre

`main.py:535`: `if is_animating is False:` es siempre verdadero porque el `finally` anterior
acaba de ponerlo en `False`. Se envía `sim_walk_complete` incluso cuando el usuario ha
parado, además del `sim_walk_stopped`.

**Arreglo**: capturar el motivo de salida del bucle (`completed` vs `stopped` vs `cancelled`)
en una variable local y decidir el mensaje con ella.

### D-20 · `heatmap_height` se descarta y el slider está mal etiquetado

`simulation.py:308`: `_compute_coverage(scene, max_depth, _)` — el tercer parámetro se
descarta; el mapa usa siempre 10 rebanadas fijas de 0,1 a 1,9 m. Y el control
`#heatmap-height` de `index.html:154-160` es en realidad de **opacidad**
(`heatmap.js:132 setHeatmapHeight(opacity)`).

**Arreglo** (elige uno y sé coherente):
- **A**: renombrar el control a `#heatmap-opacity` en HTML, `controls.js` y `heatmap.js`;
  eliminar `heatmap_height` del payload y `COVERAGE_HEIGHT` de `config.py`. Honesto y
  simple. **Recomendado.**
- **B**: implementar de verdad la altura configurable, permitiendo elegir el rango de
  rebanadas. Más trabajo, valor dudoso ahora que el heatmap es volumétrico.

### D-21 · CORS permisivo y backend expuesto en la LAN

`main.py:92-98` usa `allow_origins=["*"]` con `allow_credentials=True` (combinación que los
navegadores rechazan) y `config.py:82` pone `API_HOST = "0.0.0.0"`: accesible desde toda la
red local, sin autenticación.

**Arreglo**:

```python
# config.py
API_HOST = os.environ.get("WIFIVISION_HOST", "127.0.0.1")
CORS_ORIGINS = os.environ.get("WIFIVISION_CORS", "http://localhost:5173").split(",")
```

```python
# main.py
app.add_middleware(CORSMiddleware,
    allow_origins=CORS_ORIGINS, allow_credentials=False,
    allow_methods=["GET", "POST"], allow_headers=["*"])
```

Quien necesite exponerlo lo hace explícitamente con la variable de entorno.

## Grupo 2 — Frontend

| Defecto | Ubicación | Arreglo |
|---|---|---|
| **D-12** | `index.html:16-17` | Eliminar el `<div class="header-left">` duplicado |
| **D-13** + **D-22** | `index.html:164`, `sensors.js:13,18,40` | Decidir: implementar las etiquetas 3D (rellenar `labels[]` con sprites y cablear `#toggle-labels`) **o** eliminar el control. No dejar a medias |
| **D-14** | `controls.js:510-516` | `paths` es un **array** de `{receiver, num_paths, paths}`, no un mapa; y la clave es `power_linear`, no `power_lin`. Usar `.find(p => p.receiver === name)` y sumar `power_linear`. Tras `WP-03` estas potencias serán reales y el RSSI dejará de ser un `-90` fijo |
| **D-15** | `package.json` | Eliminar `three-obj-loader`: el código importa `three/addons/loaders/OBJLoader.js` |
| **D-17** | `main.js:103-121` | `getDefaultSceneInfo()` está desincronizado con `config.py` (ESP dentro de la sala, Tx en Z=1.8). Sincronizarlo, o mejor: mostrar un error visible en lugar de inventar una escena falsa cuando `/api/scene` no responde |

Para D-17, la opción honesta es la segunda: una escena de fallback plausible pero incorrecta
es peor que un mensaje de error, porque el usuario no sabe que está viendo algo inventado.

## Grupo 3 — Higiene de repo

| Defecto | Acción |
|---|---|
| **D-11** | `git rm --cached backend/cuda-keyring_1.1-1_all.deb.1` y borrar el fichero. Añadir `*.deb*` al `.gitignore` |
| **D-37** (resto) | Cablear o eliminar `ANTENNA_PATTERN` (importado en `scene_loader.py:62` y no usado: el `"dipole"` está hardcodeado en `PlanarArray`), `NUM_DATA_SUBCARRIERS`, `MATERIALS` (nunca se aplica a la escena real), `COVERAGE_HEIGHT` (ver D-20). `WP-02` ya cableó `RT_REFRACTION`/`RT_SPECULAR` |

Para `ANTENNA_PATTERN`: pasarlo a `PlanarArray(pattern=ANTENNA_PATTERN, ...)` es trivial y
convierte una constante decorativa en configuración real.

## Grupo 4 — Documentación

### D-18 · Documentación desactualizada

| Ubicación | Afirmación falsa | Realidad |
|---|---|---|
| `HOW_IT_WORKS.md:40` | «el frontend inyecta micro-turbulencia (ruido gaussiano)» | `csi_panel.js` solo empuja frames reales; el ruido se eliminó |
| `HOW_IT_WORKS.md:68-72` | SMPL es «the next major evolution» | Ya está implementado, animación incluida |
| `HOW_IT_WORKS.md:15` | grosor aplicado a «brick, concrete, wood, etc.» | Solo existe `itu_concrete` en la escena |
| `README.md:31` | paredes `itu_brick` | `itu_concrete` — lo cierra `WP-05` (D-08) |
| `README.md` / UI | difracción activa | Estaba apagada — lo cierra `WP-02` (D-03) |
| `INSTALL_WSL2_GPU.md:81` | `apt install cuda-toolkit` | Puede arrastrar el driver nativo que rompe CUDA en WSL2 (D-26). Usar `cuda-toolkit-12-6` y añadir la comprobación |

Además: actualizar la tabla de roadmap del README para que apunte a
[`../ROADMAP.md`](../ROADMAP.md) en lugar de mantener una versión paralela que se
desincronizará.

**Hacer este grupo al final**, cuando `WP-02` y `WP-05` ya hayan cambiado la realidad que se
documenta.

## Grupo 5 — Licencia (requiere decisión del usuario)

### D-19 · `frontend/public/human.obj` derivado de SMPL, versionado

467 KB, **6.890 vértices** — exactamente el recuento de SMPL. Está trackeado en git. El
propio README advierte que los `.pkl` se excluyen por las restricciones de
[MPI-IS](https://smpl.is.tue.mpg.de/), y una malla derivada del modelo cae razonablemente
bajo la misma restricción.

**Opciones**:

| Opción | Detalle |
|---|---|
| **A · Eliminarlo del repositorio** | `git rm --cached`, añadir a `.gitignore`. `main.py:55-61` **ya lo genera** al arrancar si falta, así que no se pierde funcionalidad. Para el historial haría falta `git filter-repo`, con reescritura de commits — decisión tuya |
| **B · Confirmar con MPI-IS** | Preguntar si una malla concreta en pose neutra es redistribuible. Si la respuesta es sí, documentarlo en el README con la referencia |
| **C · Sustituirlo por un maniquí genérico** | Una malla humanoide no derivada de SMPL, solo para el placeholder visual. La malla real se genera en local |

Recomendación: **A**, por ser reversible y de coste cero — el backend ya cubre el caso.

⚠️ **Resolver esto antes de hacer público el repositorio**, no en F7.

## Criterios de aceptación

```bash
# 1. Ningún control muerto en la UI
grep -o 'id="toggle-[a-z]*"' frontend/index.html | sed 's/.*id="//;s/"//' | while read id; do
  grep -q "$id" frontend/src/*.js || echo "HUÉRFANO: $id"
done
# Esperado: sin salida
```

```bash
# 2. is_animating se declara global
python -c "
import ast, sys
src = open('backend/main.py').read()
fn = next(n for n in ast.walk(ast.parse(src))
          if isinstance(n, ast.AsyncFunctionDef) and n.name == 'websocket_simulation')
globals_declared = {nm for g in ast.walk(fn) if isinstance(g, ast.Global) for nm in g.names}
assert 'is_animating' in globals_declared, 'sigue siendo local'
print('is_animating declarada global')"
```

```bash
# 3. No hay basura versionada
git ls-files | grep -E '\.deb|\.obj$|\.pkl$'
# Esperado: sin salida (o solo lo que se haya decidido conservar de forma justificada)
```

```bash
# 4. CORS restringido y host local por defecto
python -c "
import sys; sys.path.insert(0,'backend')
from config import API_HOST
assert API_HOST == '127.0.0.1', API_HOST
import main
mw = [m for m in main.app.user_middleware if 'CORS' in str(m)]
print('API_HOST =', API_HOST, '| middleware CORS presente:', bool(mw))"
```

```bash
# 5. Dependencias del frontend limpias y build OK
grep -q "three-obj-loader" frontend/package.json && echo "SIGUE PRESENTE" || echo "eliminada"
cd frontend && node ./node_modules/vite/bin/vite.js build --outDir /tmp/vd
```

```bash
# 6. Todo sigue verde
python scripts/verify.py --level sionna
```

- [ ] Los seis criterios pasan
- [ ] Comprobación visual: la UI no tiene controles que no hagan nada
- [ ] Todos los defectos del grupo marcados `CERRADO` en [`../DEFECTS.md`](../DEFECTS.md)
- [ ] D-19: decisión tomada y documentada (aunque sea `ACEPTADO` con justificación)

## Fuera de alcance

| Tema | Paquete |
|---|---|
| D-34 (frames borrados a los 600 s) y D-35 (recarga de escena por frame) | Sin asignar; D-35 es candidato a F5 |
| D-36 (bundle de 526 kB) | Sin asignar; irrelevante en local |
| Defectos de `wifi-csi-capture` (D-23, D-28…D-33) | `WP-09` |
| Reescribir el historial de git para purgar `human.obj` | Decisión del usuario, fuera de este paquete |

## Riesgos y trampas

| Riesgo | Mitigación |
|---|---|
| Cambiar `API_HOST` a `127.0.0.1` rompe el acceso desde Windows al backend de WSL2 | WSL2 reenvía `localhost` de Windows a la instancia por defecto. Si falla, `WIFIVISION_HOST=0.0.0.0` lo restaura explícitamente |
| Eliminar `human.obj` deja el placeholder vacío en un clon nuevo | `main.py:55-61` lo genera al arrancar si hay modelos SMPL. Sin ellos no había humano de todos modos. `human.js:53-55` ya maneja el fallo de carga sin reventar |
| Implementar etiquetas 3D crece más de lo previsto | Si pasa de una hora, elimina el control (D-13) y abre un paquete nuevo para la funcionalidad |
| Actualizar docs antes de que WP-02/WP-05 cambien el código | Hacer el grupo 4 **al final**. Si no, se documenta un estado que aún no existe |
| Reescribir el historial de git rompe clones y forks | No hacerlo sin decisión explícita del usuario. `git rm --cached` es suficiente para dejar de distribuirlo en adelante |
