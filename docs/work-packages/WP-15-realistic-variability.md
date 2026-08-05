# WP-15 — Variabilidad realista y modelo de ruido del ESP32-S3

| | |
|---|---|
| **Fase** | F5 · Dataset sintético a escala |
| **Estado** | `ESBOZO` — se detalla al activar F5 |
| **Defectos que cierra** | — |
| **Depende de** | `WP-14` (runner en batch), `WP-12` (métricas para medir el parecido) |
| **Nivel de verificación** | `gpu` |
| **Requiere intervención del usuario** | no |

## Objetivo

Que las muestras sintéticas se parezcan a las reales lo suficiente como para que un modelo
entrenado con ellas funcione sobre datos reales. Un CSI simulado perfecto y sin ruido es
*demasiado* limpio: el modelo aprendería a depender de una precisión que el hardware nunca
entrega.

## Alcance

### Modelo de ruido del ESP32-S3

Ya especificado en `wifi-csi-capture/tools/digital_twin_sionna.py::esp32s3_emulation`:

| Efecto | Valor documentado | Por qué importa |
|---|---|---|
| Cuantización | `int8` (−128…127) | El real solo tiene 8 bits por componente |
| `first_word_invalid` | `True` | Recorta los primeros valores de forma intermitente |
| Suelo de ruido | −90 dBm | Limita la dinámica útil |
| Ganancia de antena | 2,0 dBi | Desplaza la escala |
| Deriva de reloj | 20 ppm | Desalineación temporal entre nodos |
| Ruido de fase | σ = 0,15 rad | Difumina la información de fase |

Y de la revisión del hardware, dos efectos más que hay que añadir:

- **AGC**: saltos de amplitud no relacionados con el entorno. `ADVANCED.md` los describe como
  «sudden baseline shifts». Sin modelarlos, el modelo aprendería a confiar en una estabilidad
  de amplitud que no existe.
- **CFO/SFO**: offset de fase aleatorio por frame. Es la razón de la regla N8 de
  [`../contracts/CSI_DATA_CONTRACT.md`](../contracts/CSI_DATA_CONTRACT.md).

### Variabilidad de escena y sujeto

| Dimensión | Rango | Fuente |
|---|---|---|
| Forma corporal | 10 `betas` de SMPL | `SMPLManager.generate_mesh(betas=)` ya lo soporta |
| Trayectoria | más allá del rectángulo actual | `generate_rectangular_trajectory` es un buen punto de partida, no el único caso |
| Poses | más allá de los 7 keyframes de marcha | `WALK_CYCLE_POSES` cubre un ciclo de paso; hacen falta de pie, sentado, girando |
| Orientación | 0-360° | ya soportado vía `global_orient` |
| Escenario | vacío, 1 persona, (¿2 personas?) | multipersona multiplicaría la complejidad; decidir si entra |

## Puerta de salida

```bash
python scripts/dataset_stats.py --compare data/synthetic/ data/sessions/
# Esperado: distribuciones de amplitud, fase, delay spread y CV estadísticamente
#           compatibles según las métricas de WP-12
```

El criterio real: un modelo entrenado solo con sintético debe obtener un rendimiento no
trivial sobre datos reales **antes** de cualquier afinado. Si al transferir cae a nivel de
azar, la brecha sim-to-real sigue abierta y este paquete no ha terminado.

## Pendiente de detallar

- Orden de aplicación de los efectos de ruido (importa: cuantizar antes o después de añadir
  ruido de fase da resultados distintos).
- Si el AGC se modela como proceso aleatorio o se reproduce a partir de trazas reales.
- Multipersona: sí o no.
- Cuánta variabilidad es suficiente. Demasiada hace la tarea artificialmente difícil;
  demasiada poca no generaliza.
