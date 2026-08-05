# Contrato — datos de CSI

> Formato del CSI **real** (ESP32-S3) y del CSI **simulado** (Sionna RT), y el tensor común
> al que ambos deben normalizarse para poder compararse.
>
> Lo implementa [`WP-08`](../work-packages/WP-08-csi-normalizer.md).

---

## 1. Origen 1 — CSI real del ESP32-S3

### Línea del puerto serie

El firmware (`wifi-csi-capture/main/csi_capture_main.c:169-183`) emite una línea por frame:

```
CSI_DATA,<timestamp_us>,<mac>,<rssi>,<rate>,<sig_mode>,<mcs>,<cwb>,<smoothing>,
  <not_sounding>,<aggregation>,<stbc>,<fec>,<sgi>,<channel>,<secondary_ch>,
  <rx_seq>,<len>,<first_word_invalid>,<imag0>,<real0>,<imag1>,<real1>,...
```

**18 campos de cabecera**, seguidos de los valores de CSI.

| # | Campo | Tipo | Notas |
|---|---|---|---|
| 1 | `timestamp_us` | int64 | `esp_timer_get_time()`. **Relativo al arranque del nodo**, no epoch |
| 2 | `mac` | str | MAC origen del frame. Clave para el filtrado (ver §1.3) |
| 3 | `rssi` | int8 | dBm |
| 4 | `rate` | uint | Índice de tasa del driver |
| 5 | `sig_mode` | uint | 0 = non-HT, 1 = HT. **Debe ser 1** para HT40 |
| 6 | `mcs` | uint | Modulation and coding scheme |
| 7 | `cwb` | uint | Channel bandwidth: 0 = 20 MHz, 1 = 40 MHz |
| 8-14 | `smoothing`, `not_sounding`, `aggregation`, `stbc`, `fec`, `sgi` | uint | Flags de la capa física |
| 15 | `channel` | uint | Canal primario |
| 16 | `secondary_ch` | uint | Canal secundario (HT40) |
| 17 | `rx_seq` | uint | Número de secuencia. Sirve para detectar frames perdidos |
| 18 | `len` | uint | Bytes de CSI emitidos (tras el recorte) |
| 19 | `first_word_invalid` | uint | Si 1, los 4 primeros bytes se descartan en origen |
| 20+ | `imag0, real0, imag1, real1, …` | int8 | **228 valores** = 114 subportadoras × 2 |

### ⚠️ Tres detalles fáciles de equivocar

1. **El orden es `(imag, real)`, no `(real, imag)`.** El parser canónico
   (`tools/analyze_csi.py:75-79`) lo hace así:
   ```python
   imag = csi_vals[2 * i]
   real = csi_vals[2 * i + 1]
   amp[i]   = np.sqrt(real ** 2 + imag ** 2)
   phase[i] = np.arctan2(imag, real)
   ```
2. **Los valores son `int8`** (−128…127). Amplitud y fase son relativas, sin unidades
   físicas absolutas. Para comparar con la simulación hace falta normalizar (ver §3).
3. **`first_word_invalid`** hace que el firmware empiece en el índice 4. El número de
   valores por línea **varía**: comprueba `len`, no asumas 228.

### CSV producido por el host

`capture_csi.py` / `record_session.py` escriben:

```
# Wi-Fi Vision 3D - CSI Capture
# Node ID: 1
# Position ID: 1
# Port: COM3
# Scenario: baseline_empty
# Start: 2026-03-14T16:22:24.123456
# Duration: 300s
# t0_host_us: 1773504144123456
timestamp_us,mac,rssi,rate,sig_mode,...,first_word_invalid,csi_data
1234567,d8:47:32:2e:4c:f9,-42,11,1,...,0,-3 12 -5 8 ...
```

- Las líneas `#` son metadatos `clave: valor`.
- La cabecera CSV repite los 18 campos y añade `csi_data`, con los int8 **separados por
  espacios** en una sola celda.
- **`t0_host_us`** es el ancla crítica: epoch Unix en microsegundos en el instante en que el
  `threading.Barrier` liberó todos los hilos de captura. Permite reconstruir una línea de
  tiempo absoluta común:

  ```
  t_abs_us = t0_host_us + timestamp_us
  ```

  Sin él, los timestamps de distintos nodos no son comparables (cada ESP32 cuenta desde su
  propio arranque). Ficheros antiguos no lo tienen y
  `spatial_filter.align_nodes_by_timestamp` cae a emparejamiento por índice.

### Filtrado por MAC

Sin filtro, el callback captura frames de **cualquier** emisor Wi-Fi en el rango (routers
vecinos, móviles, IoT). Datos con MAC mezclada contaminan el dataset: distintos
transmisores producen perfiles de amplitud/fase distintos que el modelo aprendería como
características del entorno.

Configuración: `CSI_FILTER_TARGET_MAC` + `CSI_TARGET_MAC` (BSSID del router) en
`idf.py menuconfig`. `record_session.py --expected-mac` valida a posteriori.

**Para datos de entrenamiento, el filtro es obligatorio.**

### Rendimiento medido

| Métrica | Valor |
|---|---|
| Tasa CSI interna | 100 Hz (ping ICMP cada 10 ms) |
| Throughput serie | 50-93 Hz (limitado por UART a 921600 baudios) |
| Subportadoras | 114 (HT40) |
| Drops de cola | 0 (buffer de 32 slots) |
| Tamaño de CSV | ~5-8 MB por minuto y nodo |

---

## 2. Origen 2 — CSI simulado por Sionna RT

`backend/simulation.py::_compute_csi` produce por receptor:

```json
{
  "receiver": "ESP32_1",
  "subcarrier_indices": [-57, -56, ..., 55, 56],
  "amplitude_db": [...114 valores...],
  "phase_rad": [...114 valores...],
  "mean_amplitude_db": -93.83
}
```

Calculado como la respuesta en frecuencia del canal:

```
H(f) = Σᵢ aᵢ · e^{-j2πf·τᵢ}
```

con `aᵢ` la amplitud compleja del camino *i* y `τᵢ` su retardo.

⚠️ **Hoy este cálculo es incorrecto** (defecto D-01): `aᵢ` se toma como la parte real de
`paths.a` en lugar de reconstruir el complejo. Amplitudes con hasta 26 dB de error y fases
colapsadas a `{0, π}`. **No compares nada con el simulado hasta cerrar `WP-01`.**

### Diferencias estructurales frente al real

| Aspecto | Real (ESP32) | Simulado (Sionna) |
|---|---|---|
| Escala | `int8` relativo, sin unidades | dB absolutos respecto a la potencia transmitida |
| Ruido | Térmico + AGC + ruido de fase + deriva de reloj | Ninguno |
| Cuantización | 8 bits | float32 |
| Cadencia | ~50-93 Hz irregular | Una muestra por invocación |
| Tiempo | `t_abs_us` con deriva por nodo | Determinista, sin deriva |
| Fase | Con offset aleatorio por frame (CFO/SFO) | Absoluta y coherente |
| `first_word_invalid` | Puede recortar los primeros valores | No aplica |

Estas diferencias son el objeto de `WP-15` (F5): añadir al simulado el modelo de ruido del
ESP32-S3 para que sea estadísticamente comparable.

---

## 3. Tensor común

Objetivo de `WP-08`: una función que lleve cualquiera de los dos orígenes a la misma
estructura.

```python
CsiTensor = np.ndarray   # shape (n_frames, n_rx, 114), dtype complex64

# Metadatos que acompañan al tensor
{
  "source": "real" | "sim",
  "receiver_ids": ["ESP32_1", ..., "ESP32_8"],   # orden fijo, del contrato de escena
  "subcarrier_indices": [-57, ..., 56],           # orden fijo
  "t_abs_us": np.ndarray,                         # (n_frames,) — solo si source == "real"
  "scenario": str,
  "scene_contract_version": "1.0"
}
```

### Reglas de normalización

| # | Regla |
|---|---|
| N1 | El orden de receptores lo fija `receivers[]` de `scene.json`. Nunca el orden de ficheros en disco |
| N2 | El orden de subportadoras es `-57…56` ascendente. Si un origen usa otro, se reordena |
| N3 | **Real** → `H = real + 1j*imag` a partir de los pares `int8`, respetando el orden `(imag, real)` |
| N4 | **Simulado** → `H = 10^(amplitude_db/20) · e^{j·phase_rad}` |
| N5 | Los frames reales se alinean entre nodos con `spatial_filter.align_nodes_by_timestamp` (ventana ±20 ms) **antes** de apilarlos. No emparejar por índice |
| N6 | Frames con `sig_mode != 1` o menos de 114 subportadoras se descartan y se cuentan en un informe |
| N7 | Para comparar magnitudes, normalizar cada frame por su media sobre subportadoras. El real no tiene escala absoluta |
| N8 | Para comparar fases, quitar el offset común por frame (la mediana) — el real tiene offset aleatorio por CFO/SFO |

N7 y N8 son lo que hace la comparación posible. Sin ellas se compararía una magnitud
absoluta contra una relativa.

### Firma propuesta

```python
def load_real_csi(session_dir: Path, scene: dict) -> tuple[CsiTensor, dict]:
    """CSV de una sesión → tensor común. Usa analyze_csi.load_csi_file y
    spatial_filter.align_nodes_by_timestamp. NO reimplementar el parser."""

def load_sim_csi(results: list[dict], scene: dict) -> tuple[CsiTensor, dict]:
    """Lista de resultados de run_simulation() → tensor común."""

def compare(real: CsiTensor, sim: CsiTensor) -> dict:
    """RMSE de amplitud, correlación y delay spread por receptor.
    Aplica las normalizaciones N7 y N8."""
```

**Reutiliza `analyze_csi.load_csi_file`.** Es el parser canónico, está probado y maneja
frames de longitud variable, metadatos y ficheros vacíos. Escribir otro parser es garantía
de divergencia.

---

## 4. Criterios de aceptación de `WP-08`

```bash
# 1. Ida y vuelta sobre datos reales
python scripts/csi_normalize.py --real data/sessions/<X>/raw --report
# Esperado: shape (N, 8, 114) complex64, N > 0, informe de frames descartados

# 2. Ida y vuelta sobre datos simulados
python scripts/csi_normalize.py --sim --frames 10 --report
# Esperado: shape (10, 8, 114) complex64

# 3. Ambos comparables
python scripts/compare_real_vs_sim.py --real data/sessions/<X>/raw --sim-frames 100
# Esperado: shapes idénticos salvo la dimensión de frames; mismo orden de receptores;
#           RMSE y correlación por receptor

# 4. El orden de receptores sale del contrato
# Esperado: receiver_ids == [r["id"] for r in scene["receivers"]] en ambos orígenes
```
