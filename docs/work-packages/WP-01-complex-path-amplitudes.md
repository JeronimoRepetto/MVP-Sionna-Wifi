# WP-01 — Amplitudes complejas desde `paths.a`

| | |
|---|---|
| **Fase** | F1 · Física correcta |
| **Estado** | `PENDIENTE` |
| **Defectos que cierra** | D-01, D-38 |
| **Invariantes que pone en verde** | INV-05, INV-06, INV-07 |
| **Depende de** | — |
| **Nivel de verificación** | `gpu` (o `sionna` si no hay GPU) |
| **Requiere intervención del usuario** | no |

> **Es el cambio más importante de todo el roadmap y son dos líneas.** Empieza aquí.

## Objetivo

Reconstruir correctamente la amplitud compleja de cada camino de propagación. En Sionna RT
1.x, `paths.a` devuelve una tupla `(parte_real, parte_imaginaria)`; el código toma solo
`a[0]` y lo trata como si fuera el número complejo. Resultado: potencias con hasta **26 dB
de error** y fases del CIR **sin información** (solo pueden valer 0 o π). Todo lo que
muestra el panel CSI en modo Sionna real es hoy incorrecto.

## Contexto

**Lectura obligatoria**:
[`../agent/SIONNA_API_CONTRACT.md §2`](../agent/SIONNA_API_CONTRACT.md).

Evidencia medida — `ESP32_1`, 3 caminos:

| | valor |
|---|---|
| `a[0]` (real) | `[ 9.531e-06,  1.681e-05, -5.952e-06]` |
| `a[1]` (imag) | `[-1.638e-05, -2.012e-04,  1.222e-04]` |
| `\|a\|` **correcto** | `[ 1.895e-05,  2.019e-04,  1.223e-04]` |
| `\|a\|` que calcula el código | `[ 9.531e-06,  1.681e-05,  5.952e-06]` |
| ratio | `0,503` / `0,083` / `0,049` → hasta **26,2 dB** |

Shape medida: `a[0].shape == a[1].shape == (8, 1, 1, 1, 3)` =
`(num_rx, rx_ant, num_tx, tx_ant, num_paths)`.

## Ficheros a tocar

| Fichero | Qué cambia |
|---|---|
| `backend/simulation.py` | `_compute_cir` (`:196-201`), `_compute_csi` (`:262-266`), `_extract_paths` (`:132-140`): reconstruir el complejo. Y `:270-272`: derivar los parámetros OFDM de `config.py` (D-38) |
| `tests/test_physics_invariants.py` | Quitar `xfail` de INV-05, INV-06, INV-07 |
| `docs/DEFECTS.md` | D-01 y D-38 → `CERRADO` |

**NO tocar**: `_extract_paths` más allá del cálculo de amplitudes — la reconstrucción de la
geometría de caminos es `WP-03`. Tampoco los parámetros del solver: es `WP-02`.

## Pasos

1. **Extraer un helper** para no repetir la lógica en tres sitios:

   ```python
   def _complex_amplitudes(paths):
       """Rebuild complex path amplitudes from Sionna RT's (real, imag) tuple.

       Sionna RT 1.x returns paths.a as a 2-tuple of separate real and imaginary
       tensors, NOT as complex numbers. Using only the real part understates
       magnitudes by up to 26 dB and collapses phases to {0, pi}.
       See docs/agent/SIONNA_API_CONTRACT.md section 2.
       """
       a = paths.a
       if isinstance(a, tuple):
           return np.array(a[0]) + 1j * np.array(a[1])
       return np.array(a)
   ```

2. Usarlo en `_compute_cir`, `_compute_csi` y `_extract_paths`, sustituyendo los tres
   bloques `if isinstance(a_tuple, tuple): a_raw = np.array(a_tuple[0])`.

3. **Indexar explícitamente** en lugar de encadenar `[rx_idx, 0]` + `flatten()`. Hoy
   funciona por coincidencia con `num_tx=1` y una sola antena; escribir la intención evita
   un bug futuro al añadir antenas:

   ```python
   a_rx = a_all[rx_idx, 0, 0, 0, :]     # (num_paths,) complex
   tau_rx = tau_all[rx_idx, 0, :]       # (num_paths,)
   ```

4. Los fallbacks `a = np.ones_like(tau) * 0.01` deben producir un array **complejo**
   (`dtype=complex`), no real. Si no, cuando se dispare el fallback vuelve el bug por otra
   puerta.

5. **D-38** — derivar los parámetros OFDM de `config.py` en lugar de hardcodearlos:

   ```python
   # antes:  subcarrier_spacing = 312.5e3 ;  subcarrier_indices = np.arange(-57, 57)
   from config import WIFI_BANDWIDTH, NUM_SUBCARRIERS
   subcarrier_spacing = WIFI_BANDWIDTH / 128          # HT40: FFT de 128 puntos
   half = NUM_SUBCARRIERS // 2
   subcarrier_indices = np.arange(-half, NUM_SUBCARRIERS - half)
   ```

   Comprobar que sigue dando exactamente `312500,0 Hz` e índices `-57…56` (INV-08 lo
   verifica).

6. Quitar los `xfail` de INV-05, INV-06 e INV-07 en
   `tests/test_physics_invariants.py`.

7. Ejecutar `scripts/verify.py --level gpu` y confirmar cero `xpass`.

## Criterios de aceptación

```bash
# 1. Los tres invariantes pasan sin xfail
python scripts/verify.py --level gpu
# Esperado: INV-05, INV-06, INV-07 en "passed". Cero xpassed. Cero failed.
```

```bash
# 2. Las fases del CIR contienen información
python -c "
import sys, numpy as np; sys.path.insert(0,'backend')
from scene_loader import load_scene
from simulation import run_simulation
r = run_simulation(load_scene(), max_depth=3)
ph = np.array(r['cir'][0]['phases_rad'])
assert ph.size > 0
collapsed = np.all(np.isclose(np.abs(ph) % np.pi, 0, atol=1e-6))
assert not collapsed, 'las fases siguen colapsadas en {0, pi}'
print('fases OK, rango:', ph.min().round(3), ph.max().round(3))"
```

```bash
# 3. La potencia total cuadra con las amplitudes reconstruidas
python -c "
import sys, numpy as np; sys.path.insert(0,'backend')
from scene_loader import load_scene
from sionna import rt
import simulation as S
scene = load_scene()
paths = rt.PathSolver()(scene=scene, max_depth=3)
a = np.array(paths.a[0]) + 1j*np.array(paths.a[1])
tau = np.array(paths.tau)
cir = S._compute_cir(paths)
for i in range(len(cir)):
    truth = 10*np.log10(np.sum(np.abs(a[i,0,0,0,:][tau[i,0,:]>0])**2) + 1e-30)
    got = cir[i]['total_power_db']
    assert abs(truth-got) < 0.1, (cir[i]['receiver'], truth, got)
print('potencia coherente en los 8 receptores')"
```

```bash
# 4. Los parámetros OFDM salen de config.py (D-38)
python -c "
import sys; sys.path.insert(0,'backend')
from scene_loader import load_scene
from simulation import run_simulation
c = run_simulation(load_scene(), max_depth=2)['csi'][0]
assert c['subcarrier_indices'][0] == -57 and c['subcarrier_indices'][-1] == 56
assert len(c['amplitude_db']) == 114
print('OFDM OK')"
```

```bash
# 5. Nada más se ha roto
python tests/run_all.py
# Esperado: los mismos 3 fallos conocidos de D-06, ni uno más
```

- [ ] Los cinco criterios pasan
- [ ] Comprobación visual: abrir el panel CSI de un receptor y confirmar que la curva de
      fase ya no es una escalera de dos niveles
- [ ] D-01 y D-38 marcados `CERRADO` en [`../DEFECTS.md`](../DEFECTS.md)
- [ ] `PHYSICS_INVARIANTS.md`: estado de INV-05/06/07 actualizado a ✅

## Fuera de alcance

| Tema | Paquete |
|---|---|
| Pasar `samples_per_src` / `diffraction` al solver | `WP-02` |
| Reconstruir la geometría de los caminos y sus potencias | `WP-03` |
| Arreglar los 3 tests obsoletos de la suite legada | `WP-04` |

## Riesgos y trampas

| Riesgo | Mitigación |
|---|---|
| Las potencias cambian de escala y el frontend recolorea todo | Es lo correcto: los valores anteriores estaban mal. Los umbrales de `rays.js` pueden necesitar reajuste — anótalo para `WP-03`, que ya toca las potencias |
| `np.angle` sobre un array complejo con ceros da 0 | Filtrar por `paths.valid` (o `tau > 0` mientras `WP-03` no esté) antes de calcular fases |
| El mock queda incoherente con el motor real | `_mock_simulation` ya genera fases aleatorias en `[-π,π)`: es **más** correcto que el real actual. No lo toques |
| Alguien «simplifica» el helper y vuelve a `a[0]` | El docstring explica el porqué y INV-05/06/07 fallarían de inmediato |
