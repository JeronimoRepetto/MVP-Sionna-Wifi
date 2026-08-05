# WP-04 — Migrar la suite a pytest

| | |
|---|---|
| **Fase** | F1 · Física correcta |
| **Estado** | `PENDIENTE` |
| **Defectos que cierra** | D-06, D-16 |
| **Invariantes que pone en verde** | INV-13 |
| **Depende de** | `WP-01`, `WP-02`, `WP-03` |
| **Nivel de verificación** | `gpu` |
| **Requiere intervención del usuario** | no |

## Objetivo

Unificar las dos suites en una sola de pytest, arreglar los tests obsoletos y hacer que
todos ejerciten el motor **real** además del mock. Hoy hay dos mundos: seis ficheros que se
ejecutan como scripts sueltos vía `tests/run_all.py`, y la suite nueva de invariantes en
pytest. Y los tests que pasan solo validan el mock.

## Contexto

Resultado real de `python tests/run_all.py` con Sionna instalado:

```
test_config       11 passed        ✅
test_pose_library 13 passed        ✅
test_animation     6 passed        ✅
test_scene_loader  6 passed        ✅
test_simulation    8 passed, 3 FAILED
test_api          CRASH (falta httpx → D-16)
────────────────────────────────────
Final: 4 suites passed, 2 failed
```

Los tres fallos:

```
❌ test_paths_start_at_tx : ESP32_3 empieza en [0.389,3.5,1.491], Tx en [1.0,3.62,1.0]
❌ test_paths_end_at_rx   : ESP32_1 acaba en [1.0,3.62,-3.0], Rx en [-0.12,0.1,1.9]
❌ test_coverage_map_dimensions : esperaba malla X=40, obtuvo 90
```

Los dos primeros los cierra `WP-03`. El tercero es un **test obsoleto**: espera
`coverage["data"]` y malla `ROOM/res` (40×70), pero el formato pasó a volumétrico
(`coverage["slices"]`, 10 rebanadas) con la malla ampliada 1 m (90×60). El mismo desfase
rompe `test_api.py::test_get_coverage_endpoint`, que también busca `"data"`.

**El problema de fondo**: `test_paths_start_at_tx` y `test_paths_end_at_rx` **pasan en modo
mock** (donde los caminos sí incluyen Tx y Rx) y fallan con el motor real. Cuatro suites en
verde daban una falsa sensación de seguridad.

## Ficheros a tocar

| Fichero | Qué cambia |
|---|---|
| `tests/test_config.py` … `tests/test_api.py` | Quitar los bloques `if __name__ == "__main__"` y los runners manuales; añadir markers |
| `tests/test_simulation.py` | Arreglar `test_coverage_map_dimensions` (formato volumétrico); parametrizar mock vs real |
| `tests/test_api.py` | Arreglar `test_get_coverage_endpoint` (`slices`, no `data`) |
| `tests/conftest.py` | Añadir fixtures de nivel y un helper de doble proceso para INV-13 |
| `tests/test_physics_invariants.py` | Implementar INV-13 |
| `tests/run_all.py` | **Eliminar.** Lo reemplaza `scripts/verify.py` |
| `backend/requirements.txt` | Añadir `pytest` y `httpx` (D-16) |
| `pytest.ini` | Añadir `testpaths`/`addopts` si hace falta |
| `docs/agent/VERIFICATION.md` | Quitar la fila «suite legada» |

## Pasos

1. Añadir `pytest>=8.0` y `httpx>=0.27` a `backend/requirements.txt`, en una sección de
   desarrollo claramente separada de las de runtime.

2. Convertir los seis ficheros a pytest puro: quitar los runners `if __name__ == "__main__"`
   con sus contadores y `sys.exit`. Los asertos ya son `assert` de Python, así que el cuerpo
   de los tests casi no cambia.

3. Marcar cada test con su nivel:
   - `@pytest.mark.mock` → `test_config`, `test_pose_library`, y todo lo que no necesite
     Sionna.
   - `@pytest.mark.sionna` → los que carguen escena real o corran el solver.
   - `@pytest.mark.gpu` → INV-13 y cualquier cosa que exija CUDA.
   - `@pytest.mark.hardware` → nada todavía.

4. **Parametrizar mock vs real** donde tenga sentido. Es la lección principal de D-06:

   ```python
   @pytest.fixture(params=["mock", "real"])
   def sim_result(request, real_scene):
       if request.param == "mock":
           return run_simulation({"type": "mock"})
       return run_simulation(real_scene)
   ```

   Un test que solo pasaba en mock ahora falla visiblemente en real.

5. Arreglar `test_coverage_map_dimensions` para el formato actual:
   - `coverage["slices"]` es una lista de 10 rebanadas con `height` y `data`.
   - La malla es `(ROOM_WIDTH + 1.0) / res` × `(ROOM_DEPTH + 1.0) / res` = 60 × 90 — el
     margen de 1 m es deliberado, para visualizar la penetración por las paredes.
   - Comprobar también `min_db`/`max_db`/`physical_size`/`source`.

6. Arreglar `test_api.py::test_get_coverage_endpoint`: buscar `slices`, no `data`.

7. Implementar **INV-13** (GPU vs CPU). El variant de Mitsuba no se puede cambiar en
   caliente de forma fiable, así que hace falta doble proceso:

   ```python
   @pytest.mark.gpu
   def test_inv13_gpu_matches_cpu(tmp_path):
       """Same seed, both backends, results must match within float32 tolerance."""
       gpu = _run_in_subprocess(variant="cuda_ad_mono_polarized")
       cpu = _run_in_subprocess(variant="llvm_ad_mono_polarized")
       # comparar total_power_db por receptor
   ```

   El helper `_run_in_subprocess` lanza un script pequeño que fuerza el variant vía variable
   de entorno, corre la simulación con `seed` fija y devuelve JSON por stdout. Tolerancia:
   0,5 dB (los dos backends usan órdenes de reducción distintos).

   > Si `scene_loader` no permite forzar el variant por entorno, añadir ese soporte es parte
   > de este paquete: una variable `WIFIVISION_MITSUBA_VARIANT` respetada por
   > `scene_loader.py`. Es un cambio pequeño y desbloquea la verificación cruzada.

8. Eliminar `tests/run_all.py`. `scripts/verify.py` cubre todo y además controla el
   encoding, los niveles y el build del frontend.

9. Quitar de `VERIFICATION.md` la fila «suite legada / EXPECTED-FAIL».

## Criterios de aceptación

```bash
# 1. Una sola suite, todo verde, sin xfail
python scripts/verify.py --level gpu
# Esperado: 13 invariantes + los ~50 tests migrados, todos passed.
#           0 failed, 0 xfailed, 0 xpassed. Sin la fila "suite legada"
```

```bash
# 2. Los markers funcionan
python -m pytest -m mock -q                    # sin Sionna, sirve el Python de Windows
python -m pytest -m "mock or sionna" -q
python -m pytest -m gpu -q
```

```bash
# 3. Los tests parametrizados corren en ambos modos
python -m pytest tests/test_simulation.py -v -k "mock or real"
# Esperado: cada test aparece dos veces, [mock] y [real], y ambos pasan
```

```bash
# 4. run_all.py ya no existe y nada lo referencia
test ! -f tests/run_all.py && grep -rn "run_all" --include=*.py --include=*.md . | grep -v DEFECTS
# Esperado: el fichero no existe; solo referencias históricas en DEFECTS.md
```

```bash
# 5. INV-13 compara de verdad los dos backends
python -m pytest tests/test_physics_invariants.py -k inv13 -v
# Esperado: passed, y la salida indica los dos variants usados
```

- [ ] Los cinco criterios pasan
- [ ] D-06 y D-16 marcados `CERRADO`
- [ ] `VERIFICATION.md` y `PHYSICS_INVARIANTS.md` actualizados

## Fuera de alcance

- Ampliar la cobertura de tests del frontend (no hay ninguno; sería un paquete propio).
- CI en GitHub Actions → `WP-19`.
- Los 73 tests de `wifi-csi-capture` (ya son pytest) → `WP-09`.

## Riesgos y trampas

| Riesgo | Mitigación |
|---|---|
| Al parametrizar mock/real aparecen más fallos de los esperados | **Es el objetivo**. Cada fallo nuevo es un defecto que estaba oculto: regístralo en `DEFECTS.md` |
| `test_animation` necesita los `.pkl` de SMPL y falla en máquinas sin ellos | `skipif` con motivo explícito, no `xfail`. Ya hay un patrón así en el fichero |
| El doble proceso de INV-13 es lento (dos imports de Sionna, ~10 s) | Marcarlo `gpu` para que no entre en los niveles rápidos. Considerar `--durations` para vigilarlo |
| Eliminar `run_all.py` rompe el hábito o algún script | `verify.py` lo sustituye y `AGENTS.md` lo documenta. Mencionarlo en el mensaje del commit |
| Las fixtures de sesión mantienen escenas grandes en memoria | `real_scene` y `real_paths` son de sesión a propósito: cargar la escena es lo caro. Vigilar la RAM con la suite completa |
