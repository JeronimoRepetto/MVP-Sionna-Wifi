# WP-03 — Reconstruir `_extract_paths`

| | |
|---|---|
| **Fase** | F1 · Física correcta |
| **Estado** | `PENDIENTE` |
| **Defectos que cierra** | D-04 |
| **Invariantes que pone en verde** | INV-01, INV-02, INV-03, INV-04 |
| **Depende de** | `WP-01` (necesita las amplitudes complejas para las potencias) |
| **Nivel de verificación** | `gpu` |
| **Requiere intervención del usuario** | no |

## Objetivo

Que los rayos que se dibujan sean los rayos que Sionna calculó. Hoy `_extract_paths` produce
geometría falsa: los caminos no salen del router ni llegan al ESP32, la línea directa nunca
se dibuja, aparecen vértices bajo el suelo, y todas las potencias valen exactamente
`-60,0 dB` porque están hardcodeadas.

## Contexto

**Lectura obligatoria**:
[`../agent/SIONNA_API_CONTRACT.md §3`](../agent/SIONNA_API_CONTRACT.md).

Cuatro problemas encadenados en `backend/simulation.py:125-185`:

**1. Falta el Tx y el Rx.** `paths.vertices` contiene **solo** puntos de interacción.
Medido — camino 0 de `ESP32_1`:

```
vertices: [0.962, 3.500, 0.901] → [0.614, 2.406, 0.000] → [-0.000, 0.477, 1.589]
Tx real:  [1.000, 3.620, 1.000]      ← no aparece
Rx real:  [-0.120, 0.100, 1.900]     ← no aparece
```

**2. Filtro de padding erróneo** (`:158`): `valid = np.any(path_verts != 0, axis=-1)`.
Sionna no rellena con ceros; se observó un vértice en `[1.0, 3.62, -3.0]`, bajo el suelo.

**3. El LOS se descarta siempre** (`:159`): tiene cero interacciones, así que
`np.sum(valid) < 2` lo elimina. El camino más importante nunca se ve.

**4. Potencia hardcodeada** (`:170`): `power = 1e-6` → todos a `-60,0 dB` (verificado). El
coloreado por potencia de `rays.js` y su opacidad variable son decorativos.
`num_interactions = len(coords) - 2` (`:176`) también es incorrecto al faltar los extremos.

Sionna expone `paths.valid`, `paths.interactions`, `paths.objects` y `paths.primitives`
(verificado con `hasattr`). El código los ignora.

## Ficheros a tocar

| Fichero | Qué cambia |
|---|---|
| `backend/simulation.py` | Reescribir `_extract_paths` (`:125-185`) |
| `frontend/src/rays.js` | Posible reajuste de los umbrales de `POWER_COLORS` (`:9-16`) al pasar a potencias reales |
| `tests/test_physics_invariants.py` | Quitar `xfail` de INV-01…INV-04 |
| `docs/agent/SIONNA_API_CONTRACT.md` | Documentar la shape y semántica reales de `paths.valid` e `paths.interactions` |
| `docs/DEFECTS.md` | D-04 → `CERRADO` |

**NO tocar**: `_compute_cir` ni `_compute_csi` (`WP-01`), ni los parámetros del solver
(`WP-02`).

## Pasos

### Paso 0 — verificar la semántica de `valid` e `interactions` (hazlo primero)

`hasattr` confirma que existen, pero su shape y codificación no están medidas. **Antes de
escribir código**, ejecuta:

```bash
python -c "
import sys, numpy as np; sys.path.insert(0,'backend')
from scene_loader import load_scene
from sionna import rt
p = rt.PathSolver()(scene=load_scene(), max_depth=3)
for name in ('valid','interactions','objects','primitives'):
    v = np.array(getattr(p, name))
    print(f'{name:14s} shape={v.shape} dtype={v.dtype} unicos={np.unique(v)[:8]}')
print('vertices', np.array(p.vertices).shape)"
```

Anota el resultado en `SIONNA_API_CONTRACT.md §3`. Si `interactions` codifica el **tipo** de
interacción (especular / difusa / refracción / difracción), esa información es valiosa: sirve
para colorear los rayos por tipo, y para INV-03.

### Resto de pasos

1. Reescribir `_extract_paths` con esta estructura:

   ```python
   def _extract_paths(paths, max_paths_per_rx=50):
       """Extract ray path polylines for visualization.

       paths.vertices holds ONLY interaction points — neither the transmitter nor
       the receiver. Validity comes from paths.valid, never from coordinate
       heuristics: Sionna's padding is not zero (a vertex at Z=-3.0 was observed).
       See docs/agent/SIONNA_API_CONTRACT.md section 3.
       """
       tx_pos = list(TRANSMITTER["position"])
       vertices = np.array(paths.vertices)      # (max_depth, num_rx, num_tx, num_paths, 3)
       valid = np.array(paths.valid)
       inter = np.array(paths.interactions)
       amps = _complex_amplitudes(paths)        # de WP-01
       ...
       for rx_idx, (rx_name, rx_cfg) in enumerate(RECEIVERS.items()):
           rx_pos = list(rx_cfg["position"])
           for p in range(num_paths):
               if not _is_valid(valid, rx_idx, p):
                   continue
               hops = _interaction_points(vertices, inter, rx_idx, p)   # puede estar vacío → LOS
               coords = [tx_pos] + hops + [rx_pos]
               power = float(np.abs(amps[rx_idx, 0, 0, 0, p]) ** 2)
               ...
   ```

2. **El camino LOS se conserva.** `hops == []` es un caso válido, no un error: produce
   `[tx_pos, rx_pos]` con `num_interactions = 0`. Es el camino más importante de todos.

3. `num_interactions = len(hops)`, derivado de `paths.interactions`. No `len(coords) - 2`.

4. Potencia real: `power_linear = |a_p|²`, `power_db = 10·log10(power_linear + 1e-30)`.

5. **Ordenar por potencia descendente** antes de truncar a `max_paths_per_rx`. Hoy se
   trunca con `rx_paths[:50]` en orden arbitrario, así que se pueden descartar los caminos
   más fuertes. Si se recorta, que sea siempre lo menos relevante.

6. Registrar en el resultado cuántos caminos se han truncado, para que el frontend pueda
   avisar en lugar de mentir por omisión:

   ```python
   {"receiver": rx_name, "num_paths": total_valid,
    "num_paths_shown": len(shown), "paths": shown}
   ```

7. Revisar los umbrales de `POWER_COLORS` en `frontend/src/rays.js`. Están en −20…−100 dB;
   las potencias reales medidas rondan −94 dB de potencia total por receptor, así que las
   individuales serán más bajas. Ajustar los umbrales a los rangos reales o normalizar por
   el máximo del frame.

8. Quitar los `xfail` de INV-01…INV-04.

## Criterios de aceptación

```bash
# 1. Los cuatro invariantes pasan
python scripts/verify.py --level gpu
# Esperado: INV-01…INV-04 en "passed". Cero xpassed.
```

```bash
# 2. Los caminos conectan Tx con Rx (INV-01)
python -c "
import sys, numpy as np; sys.path.insert(0,'backend')
from config import TRANSMITTER, RECEIVERS
from scene_loader import load_scene
from simulation import run_simulation
tx = np.array(TRANSMITTER['position'])
for rx in run_simulation(load_scene(), max_depth=3)['paths']:
    rxp = np.array(RECEIVERS[rx['receiver']]['position'])
    for p in rx['paths']:
        v = np.array(p['vertices'])
        assert np.linalg.norm(v[0]-tx) < 0.01, (rx['receiver'], v[0])
        assert np.linalg.norm(v[-1]-rxp) < 0.01, (rx['receiver'], v[-1])
print('todos los caminos van de Tx a Rx')"
```

```bash
# 3. El LOS existe y domina (INV-02)
python -c "
import sys; sys.path.insert(0,'backend')
from scene_loader import load_scene
from simulation import run_simulation
for rx in run_simulation(load_scene(), max_depth=3)['paths']:
    los = [p for p in rx['paths'] if p['num_interactions'] == 0]
    assert los, f\"{rx['receiver']}: sin camino LOS\"
    refl = [p for p in rx['paths'] if p['num_interactions'] > 0]
    if refl:
        assert los[0]['power_db'] >= max(p['power_db'] for p in refl), rx['receiver']
print('LOS presente y dominante en los 8 receptores')"
```

```bash
# 4. Las potencias son reales y variadas (INV-03)
python -c "
import sys; sys.path.insert(0,'backend')
from scene_loader import load_scene
from simulation import run_simulation
for rx in run_simulation(load_scene(), max_depth=3)['paths']:
    pw = [p['power_db'] for p in rx['paths']]
    assert all(x < 0 for x in pw), rx['receiver']
    if len(pw) > 1:
        assert len(set(round(x,3) for x in pw)) > 1, f\"{rx['receiver']}: potencias identicas\"
print('potencias reales y no constantes')"
```

```bash
# 5. Ningún vértice fuera de la caja de la escena
python -c "
import sys, numpy as np; sys.path.insert(0,'backend')
from config import ROOM_WIDTH, ROOM_DEPTH, ROOM_HEIGHT
from scene_loader import load_scene
from simulation import run_simulation
m = 0.5   # margen: Tx y Rx estan fuera de las paredes
for rx in run_simulation(load_scene(), max_depth=3)['paths']:
    for p in rx['paths']:
        for v in p['vertices']:
            assert -m <= v[0] <= ROOM_WIDTH+m,  v
            assert -m <= v[1] <= ROOM_DEPTH+m,  v
            assert -m <= v[2] <= ROOM_HEIGHT+m, v
print('geometria dentro de la escena')"
```

- [ ] Los cinco criterios pasan
- [ ] **Comprobación visual obligatoria**: abrir el navegador con `Show Rays` activo y
      confirmar que los rayos salen del router naranja, terminan en los ESP32, se ve la
      línea directa, y los colores varían entre caminos
- [ ] `SIONNA_API_CONTRACT.md §3` actualizado con la shape real de `valid` e `interactions`
- [ ] D-04 marcado `CERRADO`

## Fuera de alcance

- Que el mapa de cobertura use la nueva información → ya funciona por otra vía.
- Colorear rayos por **tipo** de interacción. Es una mejora atractiva ahora que
  `paths.interactions` está disponible, pero es un paquete nuevo, no este.
- La suite legada de tests → `WP-04`.

## Riesgos y trampas

| Riesgo | Mitigación |
|---|---|
| `paths.valid` tiene una shape distinta a la esperada | El paso 0 la mide antes de escribir código. No asumir |
| Al conservar el LOS aparecen muchos más caminos y el frontend se ralentiza | `max_paths_per_rx` sigue acotando, pero ahora ordenado por potencia. Medir FPS y ajustar el límite si baja |
| Los umbrales de color hacen que todo se vea del mismo color | Paso 7. Considerar normalizar por el máximo del frame en vez de umbrales absolutos |
| `interactions` codifica los tipos de forma no documentada | El paso 0 imprime los valores únicos. Si no queda claro, usar solo el **conteo** para `num_interactions` y dejar el tipo para un paquete futuro |
| INV-02 falla porque el «LOS» atraviesa hormigón y no es el más fuerte | Físicamente sigue siendo el de menor pérdida. Si falla de verdad, revisar `refraction=True` (`WP-02`) antes de relajar el invariante |
