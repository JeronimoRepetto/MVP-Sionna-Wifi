# WP-16 — Detección de presencia

| | |
|---|---|
| **Fase** | F6 · Modelos |
| **Estado** | `ESBOZO` — se detalla al activar F6 |
| **Defectos que cierra** | — |
| **Depende de** | `WP-11` (datos reales con QA). No necesita F4 ni F5 |
| **Nivel de verificación** | `hardware` (datos reales) |
| **Requiere intervención del usuario** | no |

## Objetivo

Detectar si hay una persona dentro de la zona objetivo. Es la primera puerta de F6 y **la más
cercana**: se puede abordar en cuanto haya datos reales, sin esperar a la calibración ni al
dataset sintético.

## Alcance

**El baseline ya existe y funciona**: `wifi-csi-capture/tools/spatial_filter.py` implementa
un filtro de consenso espacial completo:

1. Resta del baseline por subportadora (sesión `baseline_empty`).
2. Activación por nodo: RMS del residuo por encima de `activation_sigma` × σ del baseline.
3. Consenso espacial ponderado: declara evento solo si suficientes enlaces se perturban a la
   vez, con pesos según cuánto de la trayectoria Tx→Rx pasa por la zona
   (`compute_zone_weights` estima esa fracción por muestreo del segmento).

Tiene además 20+ tests en `tests/test_all.py`, incluidos casos de persona dentro, persona
fuera y una sola perturbación en pasillo.

**Este paquete consiste en**:

1. Evaluar el baseline sobre datos reales y medir su F1 de verdad. Puede que ya baste.
2. Solo si no basta: un clasificador aprendido (regresión logística o gradient boosting sobre
   estadísticos por nodo) para comparar contra él.
3. Ajustar `activation_sigma` y `consensus_threshold` con datos reales en lugar de los valores
   por defecto (3,0 y 0,5).

Empezar por el método existente es lo correcto: un umbral bien calibrado que se puede explicar
vale más que una red neuronal opaca, sobre todo cuando el propio filtro ya distingue actividad
interior de movimiento en pasillos adyacentes.

## Puerta de salida

```bash
python scripts/eval_presence.py --sessions data/sessions/ --holdout <sesiones-no-vistas>
# Esperado: F1 > 0,95 sobre sesiones no usadas para ajustar umbrales
```

## Pendiente de detallar

- Cómo se etiqueta el ground truth de presencia (depende de la decisión de etiquetado de
  `WP-10`).
- Partición de sesiones: por sesión, por sujeto o por día. Por sesión es lo mínimo; por sujeto
  mide generalización real.
- Si el objetivo incluye latencia de detección (cuántos frames se necesitan para decidir).
