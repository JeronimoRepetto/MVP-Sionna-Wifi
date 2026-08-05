# Convenciones del proyecto

---

## 1. Los tres sistemas de coordenadas ⚠️

Es la fuente número uno de bugs silenciosos en este proyecto. Un signo o un eje mal puesto
no lanza excepción: coloca al humano dentro de una pared o boca abajo, y la simulación
sigue adelante como si nada.

| Sistema | Arriba | Ejes | Quién lo usa |
|---|---|---|---|
| **SMPL / Three.js nativo** | **Y** | X = derecha, Y = arriba, Z = profundidad | `smplx`, mallas `.obj` sin transformar |
| **Mitsuba / Sionna** | **Z** | X = ancho, Y = profundidad, Z = altura | `scenes/*.xml`, `PathSolver`, `config.py` |
| **Escena Three.js del proyecto** | **Z** | igual que Mitsuba (`camera.up.set(0,0,1)`) | `frontend/src/*.js` |

La escena de Three.js del frontend se configura deliberadamente Z-up para que coincida con
Sionna. Lo único Y-up son las mallas SMPL crudas.

### Conversión

```
Mitsuba/escena (Z-up)  [x, y_profundidad, z_altura]
        ↕
SMPL           (Y-up)  [x, z_altura,      y_profundidad]     ← se permutan los 2 últimos
```

### Dónde está resuelto — reutilízalo, no lo reinventes

**`backend/pose_library.py::generate_walk_sequence`** es la referencia canónica. Devuelve
por frame:

| Clave | Sistema | Uso |
|---|---|---|
| `display_position` | Z-up | posición para Three.js |
| `sionna_position` | Y-up | posición para hornear en la malla SMPL |
| `transl` | — | **siempre `[0,0,0]`** |
| `global_orient` | Y-up | `[0, rot_z, 0]` |

> `transl = [0,0,0]` es deliberado: la posición **no** se hornea en los vértices de la
> malla; la aplica el frontend al grupo. Si además la hornearas, se aplicaría dos veces.
> No lo «arregles».

**`backend/smpl_manager.py::save_obj(for_sionna=)`** hace la permutación de vértices:

```python
for_sionna=True    # permuta Y↔Z → malla de pie en la escena Z-up de Mitsuba
for_sionna=False   # deja Y-up nativo → Three.js aplica rotation.x = π/2
```

Elegir mal este flag deja al humano tumbado. Es el error más frecuente de esta zona.

---

## 2. Fuente de verdad de los parámetros

**`backend/config.py` es la única.** Geometría de la sala, grosor de paredes, frecuencia,
ancho de banda, subportadoras, posiciones de Tx y de los 8 Rx, parámetros de ray tracing y
materiales.

Reglas:

- No dupliques valores. Si necesitas la profundidad de la sala, impórtala.
- No hardcodees en `simulation.py` lo que ya está en `config.py`.
  > Hoy hay dos casos: `subcarrier_spacing = 312.5e3` y `np.arange(-57, 57)` están
  > escritos a mano en `_compute_csi` cuando `WIFI_BANDWIDTH` y `NUM_SUBCARRIERS` ya
  > existen. No añadas más.
- Si una constante de `config.py` no se usa en ningún sitio, o la cableas o la borras. No
  la dejes como decoración.
  > Hoy están sin usar: `RT_REFRACTION`, `RT_SPECULAR`, `ANTENNA_PATTERN`,
  > `NUM_DATA_SUBCARRIERS`, `COVERAGE_HEIGHT`, y `MATERIALS` (solo se usa en el mock).
- `frontend/src/main.js::getDefaultSceneInfo()` duplica posiciones como fallback y **está
  desincronizado** con `config.py` (defecto D-17). Al tocarlo, sincronízalo o elimínalo.

---

## 3. Reutilizar antes de escribir

Antes de crear una función nueva, comprueba si ya existe. Inventario de lo reutilizable:

### En este repo

| Símbolo | Fichero | Qué hace |
|---|---|---|
| `load_scene(scene_path=, human_mesh_path=)` | `backend/scene_loader.py` | Carga XML, añade Tx + 8 Rx, inyecta malla humana. Acepta ruta explícita — úsalo en tests |
| `get_scene_info(scene)` | `backend/scene_loader.py` | Serializa la escena para el frontend |
| `run_simulation(scene, **params)` | `backend/simulation.py` | Punto de entrada único de simulación, con fallback a mock |
| `_mock_simulation(...)` | `backend/simulation.py` | Datos sintéticos coherentes. Úsalo para tests sin GPU |
| `generate_walk_sequence(n)` | `backend/pose_library.py` | Secuencia de marcha con ambos sistemas de coordenadas |
| `generate_rectangular_trajectory(...)` | `backend/pose_library.py` | Trayectoria rectangular + orientaciones |
| `interpolate_poses(a, b, t)` | `backend/pose_library.py` | Interpolación lineal de `body_pose` |
| `SMPLManager.save_obj(...)` | `backend/smpl_manager.py` | Malla → `.obj`, con el flag `for_sionna` |
| `SMPLManager.save_walk_sequence_objs(...)` | `backend/smpl_manager.py` | Todos los frames de golpe |

### En `wifi-csi-capture` (para el puente, F2+)

| Símbolo | Fichero | Qué hace |
|---|---|---|
| `load_csi_file(path)` | `tools/analyze_csi.py` | **Parser canónico** del CSV real → amplitud, fase, RSSI, timestamps, metadatos |
| `align_nodes_by_timestamp(...)` | `tools/spatial_filter.py` | Join temporal multinodo con ventana de ±20 ms. La mejor pieza de ingeniería de ambos repos |
| `SpatialZoneFilter` | `tools/spatial_filter.py` | Consenso espacial con pesos de zona |
| `compute_zone_weights(...)` | `tools/spatial_filter.py` | Fracción del segmento Tx→Rx dentro de la zona |
| `launch_parallel_capture(...)` | `tools/capture_csi.py` | Captura multinodo con barrier de sincronización |
| `parse_csi_line(line)` | `tools/capture_csi.py` | Parser de la línea `CSI_DATA,…` del serial |

⛔ **No** uses `tools/digital_twin_sionna.py` como referencia: usa la API de Sionna 0.x y
está roto (defecto D-24).

---

## 4. Estilo de código

- **Idioma**: identificadores, docstrings, comentarios y mensajes de log en **inglés**. La
  documentación de `docs/` va en **español**.
  > El código actual mezcla comentarios en español. No es necesario traducirlos, pero el
  > código **nuevo** va en inglés.
- **Python**: 4 espacios, `snake_case`, prefijo `_` para funciones internas de módulo.
  Docstrings con `Args:` / `Returns:` cuando la firma no sea obvia.
- **JavaScript**: 4 espacios, `camelCase`, módulos ES con exports nombrados. Un módulo por
  responsabilidad, como está ahora.
- **Emojis en logs**: el código existente los usa (`✅ 🟢 🟡 ⚠️ 🔴 📡`) y son útiles para
  escanear la salida. Mantén el criterio, pero recuerda que exigen UTF-8 en la consola
  (regla R3 de `AGENTS.md`).
- Los ficheros nuevos de Python empiezan con un docstring de módulo que diga **qué** hace y
  **por qué** existe.

---

## 5. Commits y ramas

```
WP-01: use complex path amplitudes from paths.a tuple

paths.a returns (real, imag) in Sionna RT 1.x. Using only a[0] as the
complex amplitude understated magnitudes by up to 26 dB and collapsed
CIR phases to {0, pi}.

Closes D-01.
Refs docs/agent/SIONNA_API_CONTRACT.md
```

- Prefijo `WP-NN:` cuando el commit forma parte de un paquete de trabajo.
- Asunto en inglés, imperativo, ≤ 72 caracteres.
- El cuerpo explica **por qué**, no qué (el diff ya dice el qué).
- `Closes D-NN` para cerrar defectos.
- Ramas: `wp/NN-slug-corto`.
- Nunca `--no-verify` ni saltarse hooks.

---

## 6. Qué nunca se commitea

| Patrón | Motivo |
|---|---|
| `backend/models/smpl/**` | Licencia MPI-IS. Regla R1 |
| Cualquier malla derivada de SMPL | Misma licencia. Hoy `frontend/public/human.obj` la incumple (defecto D-19) |
| `data/`, `output/`, `*.csv`, `*.npz` | Datos capturados o generados |
| `build/`, `sdkconfig`, `managed_components/` | Artefactos de ESP-IDF |
| `node_modules/`, `frontend/dist/`, `.vite/` | Artefactos de Node |
| `__pycache__/`, `.pytest_cache/` | Artefactos de Python |
| `tests/tmp/` | Temporales de pytest (en `wifi-csi-capture`) |
| `*.deb`, `*.deb.*` | Paquetes descargados. Hoy hay uno commiteado (defecto D-11) |

Antes de commitear: `git status --short` y revisa cada línea.

---

## 7. Estructura de directorios

| Ruta | Qué va aquí |
|---|---|
| `backend/` | Lógica de simulación y API. Sin lógica de presentación |
| `frontend/src/` | Un módulo por responsabilidad visual. Sin lógica de física |
| `blender/` | Scripts que solo corren dentro de Blender |
| `scenes/` | Escenas Mitsuba (XML). Ver defecto D-05 sobre su estado en git |
| `scripts/` | Herramientas de desarrollo y verificación. Ejecutables sueltos, sin dependencias exóticas |
| `tests/` | Suite de tests. Todo lo nuevo con pytest y markers |
| `docs/` | Documentación de usuario |
| `docs/agent/` | Documentación para agentes de IA |
| `docs/contracts/` | Contratos compartidos con `wifi-csi-capture` |
| `docs/work-packages/` | Fichas de trabajo ejecutables |

---

## 8. Cuándo actualizar documentación

Documentación que miente es peor que no tener documentación. Este repositorio ya tiene tres
casos registrados (D-08, D-18): el README dice que las paredes son `itu_brick` cuando la
escena usa `itu_concrete`, la UI anuncia difracción que está apagada, y `HOW_IT_WORKS.md`
describe una inyección de ruido gaussiano que ya se eliminó del código.

Actualiza documentación en el mismo commit que el código cuando cambies:

- Un parámetro físico o un material → `README.md`, `docs/HOW_IT_WORKS.md`
- La API de Sionna que usas → `docs/agent/SIONNA_API_CONTRACT.md`
- Un requisito de entorno → `docs/agent/ENVIRONMENT.md`
- El formato de datos → `docs/contracts/`
- Un invariante o su estado → `docs/agent/PHYSICS_INVARIANTS.md`
- El estado de un defecto → `docs/DEFECTS.md`
