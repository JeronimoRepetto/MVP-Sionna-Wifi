# Roadmap — Wi-Fi Vision 3D

> Del estado actual hasta el objetivo final: **estimar la pose humana en 3D usando solo
> señales Wi-Fi, sin cámaras**.
>
> Ocho fases (F0…F7). Cada una tiene una **puerta de salida verificable por comando**: no
> se avanza a la siguiente sin haberla superado. Las fases intermedias son hitos con valor
> propio — puedes parar en cualquiera sin perder el trabajo hecho.

---

## Mapa de un vistazo

```
F0  Entorno reproducible                    ← días
     │  GPU estable en shells no interactivas, ESP-IDF operativo
     ▼
F1  Física correcta  ★ EL CUELLO DE BOTELLA ← 1-2 semanas
     │  Los números de la simulación pasan a ser válidos
     ▼
F2  El puente                               ← 1-2 semanas
     │  Una única geometría y un único formato de CSI para ambos repos
     ▼
F3  Dataset real  ──────────┐               ← semanas (depende de hardware)
     │  Captura con QA      │
     ▼                      │
F4  Calibración  ◄──────────┘               ← 2-4 semanas
     │  El gemelo digital reproduce la realidad medida
     ▼
F5  Dataset sintético a escala              ← 2-4 semanas
     │  Miles de muestras etiquetadas por GPU
     ▼
F6  Modelos: presencia → actividad → pose   ← meses
     │  Tres puertas independientes
     ▼
F7  Validación y publicación
```

**Dependencia crítica**: F4 necesita F1 **y** F3. Sin F1 calibrarías el simulador contra su
propio bug; sin F3 no hay verdad de referencia. F1 se puede hacer hoy; F3 depende de
hardware y de reparar ESP-IDF.

---

## F0 · Entorno reproducible

**Objetivo**: que el proyecto se comporte igual lanzado a mano, por un script, por CI o por
un agente de IA. Hoy no: la GPU solo funciona en terminales interactivas.

| WP | Título | Defectos | Requiere |
|---|---|---|---|
| [`WP-00`](work-packages/WP-00-environment-gpu-env-vars.md) | Variables de GPU fuera del `.bashrc` | D-25 | — |
| [`WP-00b`](work-packages/WP-00b-wsl2-cuda-hygiene.md) | Higiene de CUDA en WSL2 | D-26 | `sudo` del usuario |
| [`WP-00c`](work-packages/WP-00c-esp-idf-repair.md) | Reparar ESP-IDF | D-27 | admin del usuario |

**Puerta de salida**

```bash
# En shell NO interactiva → debe reportar GPU
wsl -e bash -lc "cd /mnt/c/.../MVP-Sionna-Wifi && bash scripts/run_backend.sh --check-only"
# Esperado: 🟢 Mitsuba backend: CUDA + OptiX mono-polarized (GPU)

# ESP-IDF operativo
idf.py --version          # sin errores
cd wifi-csi-capture && idf.py build     # compila
```

`WP-00b` y `WP-00c` requieren privilegios y son responsabilidad del usuario. `WP-00` no
depende de ellos: el lanzador funciona con el parche de `LD_LIBRARY_PATH`.

---

## F1 · Física correcta ★

**Objetivo**: que los números que produce la simulación sean físicamente válidos. **Es la
fase más importante del roadmap.** Todo lo posterior —comparación con datos reales,
calibración, generación de datasets, entrenamiento— se construye sobre estos números. Con
la física mal, cada fase siguiente amplifica el error.

| WP | Título | Defectos | Invariantes que pone en verde |
|---|---|---|---|
| [`WP-01`](work-packages/WP-01-complex-path-amplitudes.md) | Amplitudes complejas desde `paths.a` | D-01, D-38 | INV-05, INV-06, INV-07 |
| [`WP-02`](work-packages/WP-02-solver-parameters.md) | Parámetros de física al solver | D-02, D-03, D-37 | INV-10, INV-11 |
| [`WP-03`](work-packages/WP-03-path-extraction.md) | Reconstruir `_extract_paths` | D-04 | INV-01…INV-04 |
| [`WP-04`](work-packages/WP-04-pytest-migration.md) | Migrar la suite a pytest | D-06, D-16 | INV-13 |
| [`WP-05`](work-packages/WP-05-scene-reproducibility.md) | Reproducibilidad de la escena | D-05, D-07, D-08 | INV-09 |
| [`WP-06`](work-packages/WP-06-repo-hygiene.md) | Higiene de repo y documentación | D-09…D-22 | — |

**Orden recomendado**: WP-01 → WP-02 → WP-03 → WP-04, y WP-05/WP-06 en paralelo (no tocan
física).

**Puerta de salida**

```bash
python scripts/verify.py --level gpu
# Esperado: 13 passed, 0 xfailed, 0 xpassed, 0 failed

python tests/diag_compare.py
# Esperado: "✅ CONFIRMED: Human mesh affects simulation!" con Δ físicamente coherente
```

Y una comprobación que ningún test automatiza: abrir el navegador y confirmar que los rayos
**salen del router y llegan a los ESP32**, que se ve la línea directa, y que los colores por
potencia varían entre caminos en lugar de ser todos iguales.

---

## F2 · El puente

**Objetivo**: que los dos repos hablen de la misma habitación y del mismo formato de datos.
Hoy no lo hacen y esto invalida cualquier comparación.

| Aspecto | `MVP-Sionna-Wifi` | `wifi-csi-capture` |
|---|---|---|
| Geometría | sala 2,0 × 3,5 × 2,0 m | escalera 3,0 × 4,0 × 2,8 m |
| Tx | `[1.0, 3.62, 1.0]` | `[1.5, 2.0, 1.5]` |
| Rx altos / bajos | Z = 1,9 / 0,1 m, **fuera** de las paredes | Z = 2,5 / 0,15 m |

| WP | Título | Defectos |
|---|---|---|
| [`WP-07`](work-packages/WP-07-canonical-scene.md) | Geometría canónica compartida | D-24 |
| [`WP-08`](work-packages/WP-08-csi-normalizer.md) | Normalizador de CSI real ↔ simulado | D-24 |

Contratos: [`contracts/SCENE_GEOMETRY.md`](contracts/SCENE_GEOMETRY.md) ·
[`contracts/CSI_DATA_CONTRACT.md`](contracts/CSI_DATA_CONTRACT.md)

**Puerta de salida**

```bash
python scripts/compare_real_vs_sim.py --real data/sessions/<X>/raw --sim-frames 100
# Esperado: ambos tensores con shape idéntico [frames, 8, 114] complejo,
#           mismo orden de receptores, y un informe de diferencias por receptor
```

**Decisión pendiente del usuario**: qué escena es la canónica. Recomendación: medir la
escalera real y adoptarla, porque es donde se captarán los datos y el simulador debe
imitar la realidad, no al revés.

---

## F3 · Dataset real

**Objetivo**: horas de CSI real, etiquetado, con control de calidad y trazabilidad.

`wifi-csi-capture` ya tiene casi todo lo necesario: firmware, captura multinodo con barrier
de sincronización, `t0_host_us` como ancla absoluta, manifest JSON y filtrado por MAC. Lo
que falta es **ejecutarlo** y añadir el control de calidad.

| WP | Título | Defectos |
|---|---|---|
| `WP-09` | Reparar el toolchain y flashear los nodos | D-23, D-28…D-31, D-33 |
| `WP-10` | Ejecutar el protocolo de captura | D-32 |
| `WP-11` | QA automático de sesión | — |

**Bloqueado por**: `WP-00c` (ESP-IDF) y por la disponibilidad de hardware.

**Puerta de salida**

```bash
python tools/session_qa.py data/sessions/
# Esperado por sesión: Hz ≥ 45, drops = 0, MAC 100 % esperada,
#                      drift < 35 ms, manifest completo
```

Criterio de volumen: definirlo al activar la fase, en función de cuántos nodos haya
realmente disponibles. Escenarios mínimos: `baseline_empty`, `stairs_walk`, `stairs_still`.

---

## F4 · Calibración del gemelo digital

**Objetivo**: que la simulación reproduzca las mediciones reales. Es lo que convierte el
simulador en un gemelo *digital* en lugar de una animación bonita.

Sionna RT es **diferenciable**: se puede optimizar la permitividad y la conductividad de
cada material por descenso de gradiente para minimizar el error contra las medidas. Es
exactamente el caso de uso para el que existe.

| WP | Título |
|---|---|
| `WP-12` | Métricas real vs simulado (RMSE de amplitud, correlación, delay spread, RSSI) |
| `WP-13` | Optimización diferenciable de propiedades de materiales |

Valores de partida ya documentados en `wifi-csi-capture/tools/digital_twin_sionna.py`
(`MATERIALS`): drywall εr 2,94 / σ 0,0386; hormigón 5,31 / 0,0707; madera 1,99 / 0,0047;
tejido humano 39,2 / 1,8 (modelo Cole-Cole a 2,45 GHz). Reutilizarlos como inicialización.

**Puerta de salida**

```bash
python scripts/calibrate.py --holdout ESP32_3,ESP32_7
# Esperado: RMSE de amplitud por debajo del umbral acordado en los receptores excluidos
#           del ajuste (held-out), no solo en los usados para optimizar
```

El *held-out* es esencial: ajustar 5 materiales contra 8 receptores sobreajusta con
facilidad.

---

## F5 · Dataset sintético a escala

**Objetivo**: generar miles de muestras etiquetadas por GPU. Aquí está el verdadero valor
del gemelo digital: en simulación sabes exactamente dónde está cada articulación, algo que
con datos reales exigiría un sistema de captura de movimiento.

| WP | Título |
|---|---|
| `WP-14` | Runner headless en batch (sin frontend, paralelizado en GPU) |
| `WP-15` | Variabilidad realista y modelo de ruido del ESP32-S3 |

`WP-15` debe emular las imperfecciones del hardware, ya especificadas en
`digital_twin_sionna.py::esp32s3_emulation`: cuantización `int8`,
`first_word_invalid`, suelo de ruido −90 dBm, ganancia de antena 2 dBi, deriva de reloj
20 ppm, ruido de fase σ 0,15 rad. Más variabilidad de sujeto (`betas` de SMPL),
trayectorias y poses.

Requiere resolver D-35 (recarga de escena por frame) para que el throughput sea razonable.

**Puerta de salida**

```bash
python scripts/generate_dataset.py --hours 10 --out data/synthetic/
python scripts/dataset_stats.py --compare data/synthetic/ data/sessions/
# Esperado: distribuciones de amplitud, fase y delay spread estadísticamente
#           compatibles con el real según las métricas de F4
```

---

## F6 · Modelos

**Objetivo**: pose 3D. Tres puertas independientes, de menor a mayor dificultad. Cada una
es un resultado con valor propio.

| WP | Nivel | Entrada | Salida | Baseline de referencia |
|---|---|---|---|---|
| `WP-16` | **Presencia** | CSI multinodo | binario | `spatial_filter.py::SpatialZoneFilter`, que ya funciona |
| `WP-17` | **Actividad** | ventanas temporales de CSI | multiclase (vacío / de pie / caminando) | — |
| `WP-18` | **Pose 3D** | CSI multinodo | articulaciones SMPL | — |

Estrategia sim-to-real para `WP-18`: preentrenar con el dataset sintético de F5, afinar con
el real de F3. Es el enfoque estándar cuando etiquetar datos reales es caro, y es la razón
de ser de las fases F4-F5.

**Puertas de salida**

```
WP-16: F1 > 0,95 en detección de presencia, en sesiones no vistas
WP-17: matriz de confusión con exactitud > 0,85 en las 3 clases
WP-18: error medio por articulación por debajo del umbral acordado
```

Los umbrales de `WP-18` se fijan al activar la fase, con la literatura del momento como
referencia. Cerrar `WP-16` y `WP-17` ya constituye un resultado publicable.

---

## F7 · Validación y publicación

| WP | Título |
|---|---|
| `WP-19` | Reproducibilidad end-to-end, CI, model card y auditoría de licencias |

Incluye: CI en GitHub Actions limitado a `--level mock` (los runners no tienen GPU),
resolver definitivamente la licencia de SMPL (D-19), model card del modelo entrenado, y
verificar que un tercero puede reproducir todo desde cero siguiendo únicamente
[`../AGENTS.md`](../AGENTS.md).

**Puerta de salida**: una persona ajena al proyecto clona, sigue `AGENTS.md` y llega a un
`scripts/verify.py --level gpu` verde sin preguntar nada.

---

## Riesgos

| Riesgo | Fase | Impacto | Mitigación |
|---|---|---|---|
| Calibrar contra la física mal | F4 | Todo el gemelo digital queda inválido | **F1 es requisito duro de F4.** No se salta |
| Hardware insuficiente (< 8 nodos) | F3 | Menos diversidad espacial | El protocolo por rondas de `record_session.py` ya permite 2 nodos en 4 rondas |
| Brecha sim-to-real irreducible | F6 | El modelo sintético no transfiere | Puertas de F4 y F5 la miden antes de entrenar; afinado con datos reales |
| Licencia de SMPL bloquea publicación | F7 | No se puede liberar el dataset ni las mallas | Resolver D-19 **ya**, no al final |
| Deriva de reloj entre nodos | F3, F6 | Desalineación temporal | Ya resuelto: barrier + `t0_host_us` + join de ±20 ms. Presupuesto de error documentado en `ADVANCED.md` |
| La API de Sionna vuelve a cambiar | todas | Rotura silenciosa como la de 0.x→1.x | [`agent/SIONNA_API_CONTRACT.md`](agent/SIONNA_API_CONTRACT.md) + invariantes que fallan si algo cambia |
| Termia en CPU | F1, F5 | Throttling, sesiones largas inviables | F0 garantiza GPU; 0,027 s/frame frente a 0,13 s |

---

## Estado actual

| Fase | Estado |
|---|---|
| **F0** | 🟠 Parcial — GPU funciona pero es frágil; ESP-IDF roto |
| **F1** | 🔴 Sin empezar — 4 defectos P0 de física abiertos |
| **F2** | 🔴 Sin empezar — las dos escenas divergen |
| **F3** | ⚪ Bloqueada por F0 (ESP-IDF) y hardware |
| **F4** | ⚪ Bloqueada por F1 y F3 |
| **F5** | ⚪ Bloqueada por F4 |
| **F6** | ⚪ Bloqueada por F5 |
| **F7** | ⚪ — |

**Siguiente acción**: `WP-01`. Es un cambio de dos líneas con el mayor impacto de todo el
roadmap.
