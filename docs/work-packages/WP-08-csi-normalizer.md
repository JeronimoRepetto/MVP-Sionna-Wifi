# WP-08 — Normalizador de CSI real ↔ simulado

| | |
|---|---|
| **Fase** | F2 · El puente |
| **Estado** | `PENDIENTE` |
| **Defectos que cierra** | D-24 (resto) |
| **Invariantes que pone en verde** | — |
| **Depende de** | `WP-01` (el CSI simulado debe ser correcto), `WP-07` (misma geometría) |
| **Nivel de verificación** | `sionna` + datos reales de `wifi-csi-capture` |
| **Requiere intervención del usuario** | no (pero necesita al menos una sesión capturada) |

## Objetivo

Una función que convierta cualquiera de los dos orígenes de CSI —CSV del ESP32-S3 o
resultados de Sionna— al **mismo tensor**, para poder compararlos campo a campo. Es la pieza
que hace posible F4 (calibración) y, más adelante, entrenar un modelo indistintamente con
datos reales o sintéticos.

## Contexto

**Lectura obligatoria**:
[`../contracts/CSI_DATA_CONTRACT.md`](../contracts/CSI_DATA_CONTRACT.md), que ya especifica
ambos formatos, el tensor común y las ocho reglas de normalización N1-N8.

Las tres trampas que el contrato documenta y que hay que respetar:

1. El orden en el CSV real es **`(imag, real)`**, no `(real, imag)`.
2. Los valores reales son `int8` **sin escala física absoluta**; el simulado está en dB
   absolutos. Comparar magnitudes exige normalizar por frame (regla N7).
3. La fase real lleva un **offset aleatorio por frame** (CFO/SFO) que hay que eliminar antes
   de comparar (regla N8).

⚠️ **Requisito previo duro**: `WP-01` debe estar cerrado. El CSI simulado tiene hoy hasta
26 dB de error y fases sin información (D-01). Comparar contra datos reales antes de
arreglarlo produciría un error de calibración achacado a los materiales.

## Ficheros a tocar

| Fichero | Qué cambia |
|---|---|
| `scripts/csi_normalize.py` | **Nuevo**. `load_real_csi`, `load_sim_csi`, `compare` |
| `scripts/compare_real_vs_sim.py` | **Nuevo**. CLI que genera el informe por receptor |
| `tests/test_csi_contract.py` | **Nuevo**. Tests del normalizador con datos sintéticos |
| `../wifi-csi-capture/tools/digital_twin_sionna.py` | Eliminar su lógica de simulación con API 0.x y delegar en el backend del MVP (cierra D-24) |
| `docs/contracts/CSI_DATA_CONTRACT.md` | Documentar la implementación real y cualquier desviación |

## Pasos

1. Implementar las tres funciones con las firmas del contrato (`CSI_DATA_CONTRACT.md §3`).

2. **Reutilizar `analyze_csi.load_csi_file`** de `wifi-csi-capture` para parsear el CSV. Es
   el parser canónico: maneja frames de longitud variable, metadatos `#`, ficheros vacíos y
   el orden `(imag, real)`. Escribir otro parser garantiza divergencia.

   > `load_csi_file` devuelve amplitud y fase por separado, no el complejo. Reconstruir:
   > `H = amplitude * exp(1j * phase)`. Comprobar si la fase que devuelve viene ya
   > desenvuelta (`np.unwrap` en `analyze_csi.py:82`) — para reconstruir el complejo hace
   > falta la fase **envuelta**. Si no está disponible, extender `load_csi_file` para que
   > devuelva también el complejo crudo, en lugar de reimplementar el parseo.

3. **Reutilizar `spatial_filter.align_nodes_by_timestamp`** para alinear los nodos antes de
   apilarlos (regla N5). Usa `t_abs_us = t0_host_us + timestamp_us` con ventana de ±20 ms.
   Emparejar por índice es incorrecto: los nodos arrancan desfasados y derivan.

4. El orden de receptores lo fija `scene.json` (regla N1), nunca el orden de ficheros en
   disco. Un `sorted(glob(...))` daría un orden aparentemente estable y silenciosamente
   distinto entre sesiones.

5. Implementar las normalizaciones N7 (magnitud por frame) y N8 (offset de fase por frame)
   como funciones separadas y **testeables por su cuenta**. Son la parte con más sutileza y
   donde se concentrará la incertidumbre de F4.

6. Informe de frames descartados: cuántos y por qué (`sig_mode != 1`, menos de 114
   subportadoras, sin pareja temporal). Un descarte silencioso del 40 % de los frames
   invalidaría las conclusiones sin que nadie se enterase.

7. `compare()` devuelve por receptor: RMSE de amplitud, correlación de Pearson sobre
   subportadoras, diferencia de delay spread y diferencia de RSSI.

8. Tests con datos **sintéticos** construidos a mano: un CSV mínimo con valores conocidos y
   un resultado de simulación conocido, para verificar el ida y vuelta sin depender de tener
   capturas reales.

9. Portar `digital_twin_sionna.py`: eliminar `simulate_csi()` con API 0.x y hacer que importe
   el backend del MVP. Conservar `MATERIALS` y `esp32s3_emulation`, que son datos valiosos
   para F4 y F5.

## Criterios de aceptación

Los cuatro criterios están en
[`../contracts/CSI_DATA_CONTRACT.md §4`](../contracts/CSI_DATA_CONTRACT.md). Resumen:

```bash
python scripts/csi_normalize.py --real data/sessions/<X>/raw --report
# Esperado: shape (N, 8, 114) complex64, N > 0, informe de descartes

python scripts/csi_normalize.py --sim --frames 10 --report
# Esperado: shape (10, 8, 114) complex64

python scripts/compare_real_vs_sim.py --real data/sessions/<X>/raw --sim-frames 100
# Esperado: RMSE y correlación por receptor, mismo orden de receptores en ambos lados
```

Más:

```bash
# Tests del normalizador sin necesidad de datos reales
python -m pytest tests/test_csi_contract.py -v
# Esperado: todos passed, incluidos los de N7 y N8 por separado
```

```bash
# digital_twin_sionna.py ya no usa la API 0.x
cd ../wifi-csi-capture && grep -n "compute_paths\|paths.cfr\|Scene()" tools/digital_twin_sionna.py
# Esperado: sin resultados
```

- [ ] Todos los criterios pasan
- [ ] El informe de descartes indica el porcentaje de frames usados
- [ ] D-24 marcado `CERRADO`
- [ ] `CSI_DATA_CONTRACT.md` actualizado con la implementación real

## Fuera de alcance

- Métricas de calibración y su interpretación → `WP-12`.
- Optimizar propiedades de materiales → `WP-13`.
- Modelar el ruido del ESP32-S3 en el simulado → `WP-15`.
- Capturar los datos → `WP-10`.

## Riesgos y trampas

| Riesgo | Mitigación |
|---|---|
| Comparar antes de cerrar `WP-01` | Requisito previo duro. El script debe **rechazar** ejecutarse si detecta fases colapsadas en `{0, π}` en el CSI simulado, con un mensaje que apunte a `WP-01` |
| `load_csi_file` solo devuelve la fase desenvuelta y no se puede reconstruir el complejo | Extender `load_csi_file` (es del otro repo, pero es el sitio correcto). No duplicar el parser |
| N7/N8 mal implementadas sesgan toda la calibración | Tests unitarios propios con señales sintéticas de offset conocido |
| Sin datos reales todavía | Los tests con datos sintéticos permiten desarrollar y verificar el normalizador antes de F3. Solo el criterio con `data/sessions/` queda pendiente |
| Descarte silencioso de frames | El informe es obligatorio, no opcional |
