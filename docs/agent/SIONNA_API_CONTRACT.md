# Contrato de API — Sionna RT 1.2.2

> **Lectura obligatoria antes de modificar `backend/simulation.py` o
> `backend/scene_loader.py`.**
>
> Sionna RT 1.x rompió la API de la 0.x de formas que **no lanzan excepción**: el código
> antiguo sigue ejecutándose y devuelve números incorrectos. Este repositorio ya cayó en
> cuatro de esas trampas. Este documento es la vacuna.

Todo lo que sigue está **medido empíricamente** contra la instalación real
(`sionna 1.2.2`, `sionna-rt 1.2.2`, `mitsuba 3.8.0`, `drjit 1.3.1`), no copiado de la
documentación oficial. Los valores concretos vienen de la escena
`scenes/room_simple.xml` con 1 Tx y 8 Rx.

**Cómo re-verificar este documento** si sospechas que ha envejecido:

```bash
python -c "import inspect; from sionna import rt; print(inspect.signature(rt.PathSolver.__call__))"
```

---

## 1. Firma real de `PathSolver.__call__`

```python
(self,
 scene: sionna.rt.scene.Scene,
 max_depth: int = 3,
 max_num_paths_per_src: int = 1000000,
 samples_per_src: int = 1000000,
 synthetic_array: bool = True,
 los: bool = True,
 specular_reflection: bool = True,
 diffuse_reflection: bool = False,
 refraction: bool = True,
 diffraction: bool = False,
 edge_diffraction: bool = False,
 diffraction_lit_region: bool = True,
 seed: int = 42
) -> sionna.rt.path_solvers.paths.Paths
```

**Todos los parámetros físicos son argumentos de esta llamada.** No son propiedades de la
escena. Repito: **no son propiedades de la escena.**

### Mapeo obligatorio `config.py` → argumento

| Constante en `backend/config.py` | Argumento de `PathSolver` | Valor por defecto de Sionna |
|---|---|---|
| `RT_MAX_DEPTH` | `max_depth` | `3` |
| `RT_NUM_SAMPLES` | `samples_per_src` | `1_000_000` |
| `RT_DIFFRACTION` | `diffraction` | **`False`** |
| `RT_SCATTERING` | `diffuse_reflection` | `False` |
| `RT_SPECULAR` | `specular_reflection` | `True` |
| `RT_REFRACTION` | `refraction` | `True` |

⚠️ Ojo con `diffraction`: su **valor por defecto es `False`**. Si no lo pasas
explícitamente, la difracción está apagada — independientemente de lo que diga la UI, el
README o `RT_DIFFRACTION`.

⚠️ Ojo con el nombre: en 0.x se llamaba «scattering»; en 1.x el argumento es
`diffuse_reflection`. No existe ningún argumento llamado `scattering`.

---

## 2. `paths.a` es una tupla `(parte_real, parte_imaginaria)`

**Esta es la trampa que más caro ha costado.** No es una lista de amplitudes complejas.

```python
a = paths.a                 # tuple de longitud 2
a_real = np.array(a[0])     # shape (num_rx, rx_ant, num_tx, tx_ant, num_paths)
a_imag = np.array(a[1])     # misma shape

# ✅ CORRECTO
amplitudes = a_real + 1j * a_imag

# ❌ INCORRECTO — es lo que hace el código hoy (defecto D-01)
amplitudes = a_real         # usa solo la parte real como si fuera compleja
```

### Evidencia medida — receptor `ESP32_1`, 3 caminos

| | valor |
|---|---|
| `a[0]` (real) | `[ 9.531e-06,  1.681e-05, -5.952e-06]` |
| `a[1]` (imag) | `[-1.638e-05, -2.012e-04,  1.222e-04]` |
| `\|a\|` **correcto** | `[ 1.895e-05,  2.019e-04,  1.223e-04]` |
| `\|a\|` usando solo `a[0]` | `[ 9.531e-06,  1.681e-05,  5.952e-06]` |
| **ratio** (incorrecto / correcto) | **`0,503` / `0,083` / `0,049`** |

Un ratio de 0,049 es un error de **26,2 dB**. Y como consecuencia adicional:

- `np.angle()` de un número real solo puede devolver `0` o `π` → **las fases del CIR son
  basura**, no hay información de fase.
- El CSI `H(f) = Σ aᵢ·e^{-j2πfτᵢ}` se calcula con coeficientes reales escalares, así que
  el patrón de interferencia entre subportadoras también es incorrecto.

### Shape de `a` medida

```
a[0].shape == a[1].shape == (8, 1, 1, 1, 3)
                             │  │  │  │  └─ num_paths
                             │  │  │  └──── tx_antennas
                             │  │  └─────── num_tx
                             │  └────────── rx_antennas
                             └───────────── num_rx
```

Con `synthetic_array=True` (el defecto) las dimensiones de antena son 1. Para indexar por
receptor: `amplitudes[rx_idx, 0, 0, 0, :]`.

---

## 3. `paths.vertices` — solo puntos de interacción, y el padding NO es cero

```
paths.vertices.shape == (max_depth, num_rx, num_tx, num_paths, 3)
```

Medido con `max_depth=3`: `(3, 8, 1, 3, 3)`.

### Dos hechos que rompen el código actual

**(a) NO contiene el Tx ni el Rx.** Solo los puntos donde el rayo interactúa con la
geometría. Si dibujas los vértices tal cual, obtienes segmentos flotando entre paredes.

Evidencia — `ESP32_1`, camino 0:

```
vertices:  [0.962, 3.500, 0.901] → [0.614, 2.406, 0.000] → [-0.000, 0.477, 1.589]
Tx real:   [1.000, 3.620, 1.000]     ← no aparece
Rx real:   [-0.120, 0.100, 1.900]    ← no aparece
```

Para reconstruir el camino visualizable: `[tx_pos] + vértices_válidos + [rx_pos]`.

**(b) El relleno de las posiciones no usadas NO es cero.** Se observó un vértice en
`[1.0, 3.62, -3.0]` — bajo el suelo. Cualquier heurístico del tipo
`valid = np.any(verts != 0, axis=-1)` es incorrecto y produce geometría falsa.

**Y hay un efecto colateral grave**: el camino de línea de vista (LOS) tiene **cero
interacciones**, así que un filtro que exija «al menos 2 vértices no nulos» lo **descarta
siempre**. El camino más importante de todos nunca se dibuja.

### La forma correcta: usar `paths.valid` y `paths.interactions`

Ambos existen (verificado con `hasattr`). También están disponibles `paths.objects` y
`paths.primitives`.

```python
valid = np.array(paths.valid)                # máscara booleana de caminos válidos
inter = np.array(paths.interactions)         # tipo de interacción por vértice
```

Usa estas máscaras. **Nunca** infieras validez de los valores de las coordenadas.

---

## 4. `paths.tau` — retardos

```
paths.tau.shape == (num_rx, num_tx, num_paths)     # medido: (8, 1, 3)
```

Retardos en segundos. Caminos inválidos aparecen con valores no positivos, pero **la
fuente de verdad de validez es `paths.valid`**, no `tau > 0`.

De las 24 posiciones `(8 rx × 1 tx × 3 paths)`, 20 tenían `tau > 0` en la medición.

---

## 5. `RadioMapSolver` → `PlanarRadioMap`

```python
solver = rt.RadioMapSolver()
rm = solver(scene=scene, max_depth=2,
            cell_size=[0.25, 0.25],
            center=[1.0, 1.75, 1.0],
            orientation=[0, 0, 0],
            size=[3.0, 4.5])
```

Devuelve un `PlanarRadioMap` con **ambos** atributos disponibles:

| Atributo | Presente | Notas |
|---|---|---|
| `rm.path_gain` | ✅ | Ganancia de camino lineal. Shape medida: `(1, 18, 12)` con `cell_size=0.25` |
| `rm.rss` | ✅ | Received signal strength |

La primera dimensión es el índice de transmisor. Hay que reducirla antes de tratar el
resultado como una malla 2D.

⚠️ `RadioMapSolver` **también** acepta parámetros de física (`diffraction`,
`diffuse_reflection`, …). Si `PathSolver` y `RadioMapSolver` reciben configuraciones
distintas, el heatmap y los rayos describen físicas diferentes y el usuario no tiene forma
de saberlo. Mantenlos sincronizados.

---

## 6. Lo que NO existe en Sionna RT 1.x

| Uso antiguo (0.x) | Qué pasa en 1.2.2 | Equivalente correcto |
|---|---|---|
| `scene.diffraction = True` | **No lanza error.** Crea un atributo Python nuevo que nadie lee. Silencioso y letal | `PathSolver(..., diffraction=True)` |
| `scene.scattering = True` | Igual: atributo huérfano | `PathSolver(..., diffuse_reflection=True)` |
| `Scene()` como constructor | `TypeError` / no es el camino soportado | `rt.load_scene(path)` |
| `scene.compute_paths(max_depth=…)` | `AttributeError` | `rt.PathSolver()(scene=scene, …)` |
| `paths.cfr(frequencies=…)` | `AttributeError` | Calcular `H(f) = Σ aᵢ·e^{-j2πfτᵢ}` a mano, o usar la API de OFDM de Sionna |
| `scene.coverage_map(...)` | `AttributeError` | `rt.RadioMapSolver()(scene=scene, …)` |

Verificado explícitamente:

```
hasattr(scene, 'diffraction') == False
scene.diffraction = True      → NO lanza excepción, queda un atributo inerte
```

> Las tres últimas filas son exactamente lo que usa
> `wifi-csi-capture/tools/digital_twin_sionna.py`. Ese fichero está **roto** con la versión
> instalada. No lo uses como referencia (defecto D-24).

---

## 7. Selección del variant de Mitsuba — no reordenar

`backend/scene_loader.py` hace algo que **parece** un detalle y no lo es:

```python
# 1. Elegir el variant
mi.set_variant('cuda_ad_mono_polarized')
mi.load_string('<scene version="2.0.0"></scene>')   # fuerza la init de OptiX

# 2. SOLO DESPUÉS importar Sionna
import sionna
from sionna import rt
```

**Razón**: Sionna registra sus plugins de Mitsuba (`itu-radio-material`, etc.) en el
momento del import, y ese registro queda **atado al variant activo**. Si importas Sionna
antes de fijar el variant, o cambias de variant después, los plugins no están registrados
para el variant en uso y la carga de la escena falla.

**Razón del `load_string` con escena vacía**: `set_variant('cuda_…')` puede tener éxito
(CUDA funciona) mientras OptiX **no** está disponible. La única forma fiable de detectarlo
antes es intentar una carga trivial. Sin esto, el fallo aparece mucho más tarde, en
`rt.load_scene()`, con un mensaje confuso.

Este patrón es correcto. **Preservarlo.** Ver `docs/agent/ENVIRONMENT.md` para la cadena
de fallos de CUDA/OptiX.

---

## 8. Anti-patrones que ya nos costaron caro

Tabla de reconocimiento rápido. Si ves el síntoma, ya sabes la causa.

| Síntoma observable | Causa | Defecto |
|---|---|---|
| Las fases del CIR solo valen 0 o π | `paths.a` usado como si `a[0]` fuera complejo | **D-01** |
| Las potencias parecen ~10–25 dB bajas y no cuadran con la distancia | Idem | **D-01** |
| Mover el slider «Ray Density» no cambia nada | `samples_per_src` nunca se pasa al solver | **D-02** |
| Activar/desactivar «Diffraction» no cambia nada | `scene.diffraction = X` es un atributo inerte | **D-03** |
| Los rayos dibujados no salen del router ni llegan al ESP32 | `vertices` no incluye Tx/Rx | **D-04** |
| Nunca se ve la línea directa Tx→Rx | El filtro «≥2 vértices no nulos» descarta el LOS | **D-04** |
| Todos los rayos tienen exactamente `-60.0 dB` | `power = 1e-6` hardcodeado | **D-04** |
| Un vértice aparece bajo el suelo (`Z<0`) o fuera de la sala | Padding tratado como coordenada real | **D-04** |
| `num_interactions` no coincide con los rebotes visibles | `len(coords)-2` sin Tx/Rx en la lista | **D-04** |

---

## 9. Checklist antes de cerrar un cambio en `simulation.py`

- [ ] ¿Reconstruyes la amplitud compleja como `a[0] + 1j*a[1]`?
- [ ] ¿Pasas `samples_per_src`, `diffraction`, `diffuse_reflection`,
      `specular_reflection` y `refraction` explícitamente al solver?
- [ ] ¿Usas `paths.valid` / `paths.interactions` en lugar de heurísticos sobre
      coordenadas?
- [ ] ¿Añades `TRANSMITTER["position"]` al principio y la posición del Rx al final de cada
      camino?
- [ ] ¿La potencia de cada camino viene de `|a|²` real y no de una constante?
- [ ] ¿`PathSolver` y `RadioMapSolver` reciben la misma configuración física?
- [ ] ¿Has ejecutado `python scripts/verify.py --level gpu` y hay **cero `xpass`**?
