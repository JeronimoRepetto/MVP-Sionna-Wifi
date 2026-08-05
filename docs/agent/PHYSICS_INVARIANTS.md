# Invariantes físicos

> Propiedades que **todo** resultado de simulación debe cumplir, independientemente de los
> parámetros, del backend (GPU/CPU) o de si hay un humano en la escena. Son la red de
> seguridad contra el fallo más peligroso de este proyecto: producir números plausibles
> pero incorrectos, sin lanzar ninguna excepción.
>
> Implementación: [`../../tests/test_physics_invariants.py`](../../tests/test_physics_invariants.py)
> Ejecución: `python scripts/verify.py --level sionna`

## Cómo leer el estado

| Estado | Significado |
|---|---|
| ✅ verde | Se cumple hoy. Si se rompe, has introducido una regresión |
| ❌ `xfail` | **Sabemos que falla**, por el defecto indicado. Marcado `strict=True`: cuando lo arregles, el test pasará a `xpass` y **romperá la suite**, obligándote a quitar la marca |
| ⏭ skip | No se puede evaluar en este entorno (faltan modelos SMPL, hace falta doble proceso…) |

---

## Tabla de invariantes

| ID | Invariante | Estado | Bloqueado por | Lo arregla |
|---|---|---|---|---|
| INV-01 | Todo camino empieza en el Tx (±1 cm) y acaba en su Rx (±1 cm) | ❌ `xfail` | D-04 | WP-03 |
| INV-02 | Si hay línea de vista, el camino LOS existe y es el más fuerte | ❌ `xfail` | D-04, D-01 | WP-03 |
| INV-03 | Toda potencia de camino es < 0 dB, y decrece al aumentar los rebotes | ❌ `xfail` | D-04 | WP-03 |
| INV-04 | La geometría de todo camino es física: vértices dentro de la escena y `num_interactions` coherente | ❌ `xfail` | D-04 | WP-03 |
| INV-05 | Las fases del CIR se distribuyen en `[-π, π)`, **no** solo en `{0, π}` | ❌ `xfail` | D-01 | WP-01 |
| INV-06 | `total_power_db` == `10·log10(Σ\|a\|²)` calculado desde `a[0]+j·a[1]`, ±0,1 dB | ❌ `xfail` | D-01 | WP-01 |
| INV-07 | `mean(\|H(f)\|²)` es coherente con la potencia total del CIR (±3 dB) | ❌ `xfail` | D-01 | WP-01 |
| INV-08 | El CSI tiene exactamente 114 subportadoras con índices −57…56 | ✅ | — | — |
| INV-09 | Con humano en la escena, Δ > 0,5 dB en al menos un receptor | ⏭ skip | modelos SMPL ausentes | WP-05 |
| INV-10 | `samples_per_src` llega al solver | ❌ `xfail` | D-02 | WP-02 |
| INV-11 | `diffraction` y `diffuse_reflection` llegan al solver | ❌ `xfail` | D-03 | WP-02 |
| INV-12 | El mapa de cobertura es finito en todas las celdas (sin `NaN`/`±inf`) | ✅ | — | — |
| INV-13 | GPU y CPU coinciden dentro de tolerancia para la misma semilla | ⏭ skip | requiere doble proceso | WP-04 |

**Recuento esperado hoy**: 2 pasan, 9 `xfail`, 2 skip, **0 `xpass`**.
Si `verify.py` reporta cualquier `xpass`, algo se arregló y hay una marca que quitar.

---

## Detalle y justificación

### INV-01 · Los caminos conectan Tx con Rx

Un camino de propagación es, por definición, la trayectoria de la energía **desde** el
transmisor **hasta** el receptor. Si el primer vértice no es el Tx o el último no es el Rx,
lo que estás dibujando no es un camino.

**Por qué falla hoy**: `paths.vertices` de Sionna contiene únicamente los puntos de
interacción con la geometría; el código no añade los extremos. Medido:

```
camino 0 de ESP32_1: [0.962, 3.500, 0.901] → [0.614, 2.406, 0.000] → [-0.000, 0.477, 1.589]
Tx = [1.000, 3.620, 1.000]     Rx = [-0.120, 0.100, 1.900]
```

**Tolerancia**: 1 cm. Los vértices vienen en float32 y hay redondeo, pero un error real de
posición sería de decímetros o metros.

### INV-02 · El LOS existe y domina

En una sala de 2×3,5×2 m a 2,437 GHz, con el Tx a 12 cm detrás de la pared, el camino
directo (atravesando la pared por refracción) siempre existe y siempre transporta más
energía que cualquier camino con rebotes, porque cada reflexión en hormigón pierde ~4–6 dB
y cada metro extra añade pérdida de espacio libre.

**Por qué falla hoy**: el LOS tiene cero interacciones, así que el filtro
`if np.sum(valid) < 2: continue` lo descarta antes de llegar a la lista. Nunca se dibuja.

**Cuidado al implementarlo**: con 8 receptores fuera de las paredes, la «línea de vista»
atraviesa hormigón. Sigue siendo el camino de menor pérdida, pero el test debe comparar
contra los caminos con rebotes del **mismo** receptor, no entre receptores.

### INV-03 · Potencias negativas y decrecientes

Toda potencia normalizada respecto a la transmitida es una pérdida: `< 0 dB`. Y con más
rebotes hay más pérdida — no de forma estrictamente monótona camino a camino (la geometría
manda), pero sí en promedio por número de interacciones.

**Por qué falla hoy**: `_extract_paths` asigna `power = 1e-6` a todos los caminos, así que
todos salen exactamente a `-60,0 dB`. La parte «< 0 dB» pasa por accidente; la parte
«decreciente» no.

**Formulación del test**: comparar la **media** de potencia agrupada por
`num_interactions`. Grupos con más interacciones deben tener media menor. Evita exigir
monotonía camino a camino, que sería físicamente incorrecto.

### INV-04 · La geometría de los caminos es física

Dos condiciones:

1. **Ningún vértice fuera de la escena.** Todos los puntos deben caer dentro de la caja de
   la sala con un margen de 0,5 m (el Tx y los 8 Rx están fuera de las paredes por diseño,
   a ±0,12 m).
2. **`num_interactions` coherente**: igual a `len(vertices) - 2` (la lista incluye Tx y Rx)
   y acotado por `max_depth`.

**Por qué falla hoy**: el relleno de Sionna no es cero, y el filtro `!= 0` lo deja pasar
como coordenada real. Se observó un vértice en `[1.0, 3.62, -3.0]`, tres metros por debajo
del suelo. Y `len(coords)-2` asume que la lista incluye Tx y Rx, que no los incluye.

> Se formula así, y no como comparación directa contra `paths.interactions`, porque la
> semántica exacta de ese array (¿codifica el tipo de interacción? ¿cómo?) todavía no está
> medida. El paso 0 de [`../work-packages/WP-03-path-extraction.md`](../work-packages/WP-03-path-extraction.md)
> la mide; cuando esté documentada, este invariante puede endurecerse.

### INV-05 · Las fases contienen información

La fase de cada componente multicamino es lo que crea el patrón de interferencia entre
subportadoras. Es **la** magnitud de la que depende toda la detección de movimiento por
CSI: el cuerpo humano desplaza fases mucho antes de cambiar amplitudes de forma apreciable.

**Por qué falla hoy**: `np.angle()` sobre un número real solo puede devolver `0` (positivo)
o `π` (negativo). Al usar únicamente `a[0]`, las fases pierden toda su información.

**Formulación del test**: comprobar que las fases del CIR no están todas en `{0, π}` con
tolerancia `1e-6`, y que su histograma cubre más de 2 celdas.

### INV-06 · La potencia total cuadra con las amplitudes

Coherencia interna: la potencia total reportada debe ser exactamente la suma de las
potencias de las componentes.

```
total_power_db == 10·log10( Σᵢ |aᵢ|² )     con  aᵢ = a[0]ᵢ + j·a[1]ᵢ
```

**Clave del test**: la verdad de referencia se calcula **en el test**, reconstruyendo la
amplitud compleja correctamente desde `paths.a`. Comparar el valor reportado contra sí
mismo no detectaría nada — hoy `simulation.py` es internamente consistente y aun así
incorrecto.

**Tolerancia**: 0,1 dB (solo redondeo float32).

### INV-07 · El CSI cuadra con el CIR

El CSI es la transformada del CIR. Por Parseval, promediando sobre subportadoras los
términos cruzados se cancelan y queda:

```
mean(|H(f)|²) ≈ Σᵢ |aᵢ|²
```

**Tolerancia**: 3 dB. Es holgada a propósito — con solo 114 subportadoras y retardos muy
próximos (la sala mide metros, los retardos son de nanosegundos) los términos cruzados no
se cancelan del todo. Un error de 3 dB detecta un bug estructural sin dar falsos positivos.

Igual que INV-06, la referencia se calcula en el test desde `paths.a` bien reconstruido.

### INV-08 · Formato de CSI del ESP32-S3 ✅

114 subportadoras, índices `-57…56`, espaciado 312,5 kHz (HT40, 40 MHz). Es el formato que
produce el hardware real y la condición mínima para que el CSI simulado sea comparable —
ver [`../contracts/CSI_DATA_CONTRACT.md`](../contracts/CSI_DATA_CONTRACT.md).

Pasa hoy. Es un invariante de *formato*, no de física: protege el contrato con
`wifi-csi-capture`.

### INV-09 · El humano perturba el canal

Un cuerpo humano es ~60 % agua; a 2,4 GHz tiene permitividad relativa ≈ 39 y conductividad
≈ 1,8 S/m. Absorbe y refleja de forma masiva. Si insertar 6.890 vértices de tejido en el
camino no cambia nada medible, la malla no está llegando al motor de ray tracing.

**Umbral**: Δ > 0,5 dB en `total_power_db` de al menos un receptor. Es el mismo criterio
que usa [`../../tests/diag_compare.py`](../../tests/diag_compare.py), que ya implementa
esta comparación con/sin humano — reutilízalo en lugar de duplicar la lógica.

**Por qué hace skip**: requiere `backend/models/smpl/*.pkl`, que no se distribuyen
(licencia MPI-IS). El test detecta su ausencia y hace skip con motivo explícito.

### INV-10 · `samples_per_src` llega al solver

El slider «Ray Density» de la UI (100 K – 2 M) debe tener efecto. Si no llega al solver, el
usuario cree estar controlando la precisión y no controla nada.

**Formulación del test**: en lugar de comparar resultados con distintos valores de muestras
—que en una escena de 6 rectángulos pueden coincidir legítimamente, haciendo el test
inestable— se hace *monkeypatch* de `rt.PathSolver.__call__` y se comprueba que
`samples_per_src` aparece entre los argumentos recibidos. Determinista y sin falsos
negativos.

Es un invariante de *cableado*, no de física. Se declara aquí porque su ausencia produce
exactamente el mismo síntoma que un bug de física: un control que no hace nada.

### INV-11 · Los conmutadores de física llegan al solver

Igual que INV-10, para `diffraction`, `diffuse_reflection`, `specular_reflection` y
`refraction`.

**Recuerda**: el defecto por omisión de `diffraction` en Sionna 1.x es `False`. No pasarlo
significa tenerlo apagado, mientras la UI muestra el conmutador activado.

`WP-02` debería añadir además una comprobación de comportamiento (que `diffraction=True`
produzca un resultado distinto de `False` en una geometría con aristas), pero el
invariante mínimo es el cableado.

### INV-12 · El mapa de cobertura es finito ✅

`NaN` o `±inf` en el mapa de cobertura envenenan el `min_db`/`max_db` que el frontend usa
para normalizar los colores, y el heatmap entero se vuelve de un solo color sin ningún
mensaje de error.

Pasa hoy gracias al `+ 1e-30` antes del logaritmo. El invariante existe para que nadie lo
quite «porque no hace nada».

### INV-13 · GPU y CPU concuerdan

Los resultados físicos no pueden depender del backend de cómputo. Con la misma `seed`, GPU
y CPU deben coincidir dentro de la tolerancia de float32.

**Por qué hace skip**: el variant de Mitsuba se fija una sola vez por proceso y no se puede
cambiar de forma fiable en caliente. El test necesita lanzar dos subprocesos y comparar sus
salidas. Se implementa en `WP-04`.

---

## Cómo añadir un invariante nuevo

1. Dale un ID `INV-NN` y añádelo a la tabla de arriba con su justificación **física**, no
   solo el aserto.
2. Impleméntalo en `tests/test_physics_invariants.py` con el marker de nivel adecuado
   (`mock`, `sionna`, `gpu`, `hardware`).
3. Si falla por un defecto conocido, márcalo
   `@pytest.mark.xfail(reason="D-NN: …", strict=True)` y registra el defecto en
   [`../DEFECTS.md`](../DEFECTS.md).
4. Justifica la tolerancia. Una tolerancia sin justificar es un test que nadie se atreverá
   a tocar.
5. Actualiza el recuento esperado de esta página.
