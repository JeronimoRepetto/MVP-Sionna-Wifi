# WP-02 — Parámetros de física al solver

| | |
|---|---|
| **Fase** | F1 · Física correcta |
| **Estado** | `PENDIENTE` |
| **Defectos que cierra** | D-02, D-03, D-37 (parcial) |
| **Invariantes que pone en verde** | INV-10, INV-11 |
| **Depende de** | `WP-01` (recomendado, no obligatorio) |
| **Nivel de verificación** | `gpu` |
| **Requiere intervención del usuario** | no |

## Objetivo

Que los controles de la UI y las constantes de `config.py` tengan efecto real. Hoy el slider
«Ray Density» y el conmutador «Diffraction» no hacen nada: el primero nunca llega al solver
y el segundo escribe en un atributo inexistente de la escena. Y como el valor por omisión de
`diffraction` en Sionna 1.x es `False`, **la difracción está siempre apagada** mientras la
UI, el README y `HOW_IT_WORKS.md` afirman lo contrario.

## Contexto

**Lectura obligatoria**:
[`../agent/SIONNA_API_CONTRACT.md §1 y §6`](../agent/SIONNA_API_CONTRACT.md).

El código actual:

```python
# backend/simulation.py:87-94
try:
    scene.diffraction = diffraction      # ← Scene NO tiene este atributo.
    scene.scattering  = scattering       #   NO lanza excepción: crea un atributo inerte
except Exception:
    pass

solver = rt.PathSolver()
result = solver(scene=scene, max_depth=max_depth)   # ← faltan TODOS los demás parámetros
```

Verificado: `hasattr(scene, 'diffraction') == False`, y `scene.diffraction = True` no lanza.

Firma real de `PathSolver.__call__` (medida con `inspect.signature`):

```python
(scene, max_depth=3, max_num_paths_per_src=1000000, samples_per_src=1000000,
 synthetic_array=True, los=True, specular_reflection=True, diffuse_reflection=False,
 refraction=True, diffraction=False, edge_diffraction=False,
 diffraction_lit_region=True, seed=42)
```

## Ficheros a tocar

| Fichero | Qué cambia |
|---|---|
| `backend/simulation.py` | `:87-94`: eliminar el bloque `scene.diffraction=…` y pasar los parámetros al solver. `_compute_coverage` (`:308-327`): pasar la misma física a `RadioMapSolver` |
| `backend/config.py` | Solo si hace falta añadir `RT_LOS` y `RT_SEED`. No cambiar los nombres existentes |
| `tests/test_physics_invariants.py` | Quitar `xfail` de INV-10 e INV-11; añadir la comprobación de comportamiento de la difracción |
| `docs/DEFECTS.md` | D-02, D-03 → `CERRADO`; D-37 parcial |
| `docs/HOW_IT_WORKS.md`, `README.md` | Corregir las afirmaciones sobre difracción y refracción |

**NO tocar**: el cálculo de amplitudes (`WP-01`) ni la extracción de geometría (`WP-03`).

## Pasos

1. Eliminar el bloque `try: scene.diffraction = … except: pass`. No hace nada y da la falsa
   impresión de que sí.

2. Pasar la física completa al solver:

   ```python
   from config import RT_REFRACTION, RT_SPECULAR   # hoy nadie los importa (D-37)

   solver = rt.PathSolver()
   paths = solver(
       scene=scene,
       max_depth=max_depth,
       samples_per_src=num_samples,          # D-02
       diffraction=diffraction,              # D-03
       diffuse_reflection=scattering,        # D-03 — en 1.x ya no se llama "scattering"
       specular_reflection=specular_reflection,
       refraction=refraction,
       synthetic_array=True,
       los=True,
       seed=RT_SEED,                         # fijo → resultados reproducibles
   )
   ```

3. `run_simulation` ya acepta `refraction` y `specular_reflection` en su firma pero no los
   usa. Cablearlos con `RT_REFRACTION` / `RT_SPECULAR` como valores por defecto (cierra la
   parte de D-37 que corresponde a estas dos constantes).

4. **Sincronizar `RadioMapSolver`** con la misma física. Si el mapa de cobertura y los rayos
   se calculan con configuraciones distintas, el usuario ve dos físicas diferentes en la
   misma pantalla sin ninguna pista de que lo son. Extraer un dict de parámetros compartido.

5. Añadir `RT_SEED = 42` a `config.py`. Una semilla fija hace la simulación reproducible, que
   es requisito de INV-13 (comparación GPU/CPU) y de la generación de datasets en F5.

6. Reflejar `refraction` y `specular_reflection` en el dict `results["parameters"]`, para que
   los resultados guardados registren la física con la que se calcularon.

7. Quitar los `xfail` de INV-10 e INV-11.

8. Añadir a INV-11 una **comprobación de comportamiento** además del cableado: con
   `diffraction=True` vs `False` sobre la misma escena y semilla, el número de caminos o la
   potencia total deben diferir en al menos un receptor. Si no difieren, la escena de 6
   rectángulos puede no tener aristas suficientes — en ese caso documéntalo en el test y
   deja solo la comprobación de cableado.

9. Corregir la documentación: `HOW_IT_WORKS.md §1` («refraction is explicitly enabled») ya
   será cierto tras este cambio; el README y la UI deben reflejar el estado real de la
   difracción.

## Criterios de aceptación

```bash
# 1. Los parámetros llegan al solver (INV-10, INV-11)
python scripts/verify.py --level gpu
# Esperado: INV-10 e INV-11 en "passed". Cero xpassed.
```

```bash
# 2. Verificación directa por monkeypatch
python -c "
import sys; sys.path.insert(0,'backend')
from sionna import rt
captured = {}
orig = rt.PathSolver.__call__
def spy(self, **kw):
    captured.update(kw); return orig(self, **kw)
rt.PathSolver.__call__ = spy
from scene_loader import load_scene
from simulation import run_simulation
run_simulation(load_scene(), max_depth=2, num_samples=12345, diffraction=True)
for k in ('samples_per_src','diffraction','diffuse_reflection','specular_reflection','refraction','seed'):
    assert k in captured, f'{k} NO llega al solver'
assert captured['samples_per_src'] == 12345, captured['samples_per_src']
assert captured['diffraction'] is True
print('todos los parametros llegan:', {k:captured[k] for k in ('samples_per_src','diffraction','refraction')})"
```

```bash
# 3. Ya no queda ningún atributo inerte en la escena
grep -n "scene.diffraction\|scene.scattering" backend/simulation.py
# Esperado: sin resultados
```

```bash
# 4. Reproducibilidad con semilla fija
python -c "
import sys, json; sys.path.insert(0,'backend')
from scene_loader import load_scene
from simulation import run_simulation
s = load_scene()
a = run_simulation(s, max_depth=3, num_samples=10000)['cir']
b = run_simulation(s, max_depth=3, num_samples=10000)['cir']
assert [x['total_power_db'] for x in a] == [x['total_power_db'] for x in b]
print('reproducible con semilla fija')"
```

```bash
# 5. Comprobación manual en la UI
# Mover «Ray Density» de 100K a 2M y confirmar que el tiempo de simulación
# y/o el número de caminos cambian de forma observable.
```

- [ ] Los cinco criterios pasan
- [ ] `RadioMapSolver` recibe la misma física que `PathSolver`
- [ ] D-02, D-03 marcados `CERRADO`; D-37 actualizado
- [ ] `README.md` y `HOW_IT_WORKS.md` corregidos

## Fuera de alcance

- Reconstrucción de `_extract_paths` → `WP-03`.
- Cablear o borrar `ANTENNA_PATTERN`, `NUM_DATA_SUBCARRIERS`, `MATERIALS`,
  `COVERAGE_HEIGHT` → `WP-06` (el resto de D-37).
- Exponer `edge_diffraction` o `diffraction_lit_region` en la UI. Añadir controles nuevos no
  es objetivo de este paquete.

## Riesgos y trampas

| Riesgo | Mitigación |
|---|---|
| Con difracción realmente activada la simulación se ralentiza | Es el coste de que funcione. Con GPU (0,027 s base) hay margen. Medir y documentar el nuevo tiempo |
| `samples_per_src=2_000_000` agota la VRAM | El defecto de Sionna ya es 1 M y funciona. Si aparece OOM, limitar el máximo del slider en `index.html` y documentarlo |
| `diffraction=True` no cambia nada en una escena de 6 rectángulos planos | Posible: sin aristas expuestas apenas hay difracción. Documentarlo en el test y quedarse con la comprobación de cableado |
| `RadioMapSolver` no acepta exactamente los mismos nombres de argumento | Verificar con `inspect.signature(rt.RadioMapSolver.__call__)` **antes** de escribir el código, y actualizar `SIONNA_API_CONTRACT.md §5` con la firma real |
