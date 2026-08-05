# WP-12 — Métricas real vs simulado

| | |
|---|---|
| **Fase** | F4 · Calibración del gemelo digital |
| **Estado** | `ESBOZO` — se detalla al activar F4 |
| **Defectos que cierra** | — |
| **Depende de** | `WP-01`…`WP-03` (física correcta), `WP-08` (tensor común), `WP-11` (datos con QA) |
| **Nivel de verificación** | `sionna` + datos reales |
| **Requiere intervención del usuario** | **sí — fijar los umbrales de aceptación** |

## Objetivo

Cuantificar cuánto se parece la simulación a la realidad. Sin una métrica acordada, «el
gemelo digital funciona» es una opinión. `WP-13` optimiza contra estas métricas, así que
definirlas bien es lo que determina qué se optimiza.

## Alcance

Métricas por receptor, sobre el tensor común de `WP-08`:

| Métrica | Qué captura | Notas |
|---|---|---|
| RMSE de amplitud por subportadora | Forma del desvanecimiento en frecuencia | Tras la normalización N7 (el real no tiene escala absoluta) |
| Correlación de Pearson sobre subportadoras | Si el **patrón** coincide, aunque la escala no | Más robusta que el RMSE frente a errores de ganancia |
| Diferencia de delay spread | Si la habitación «resuena» igual | Métrica agregada, muy sensible a la geometría |
| Diferencia de RSSI medio | Pérdida de camino global | Sensible a los materiales |
| Distancia entre perfiles de fase | Estructura del multicamino | Tras la normalización N8 (offset CFO/SFO) |

Reglas metodológicas que hay que fijar aquí:

1. **Sobre qué frames se compara.** El real tiene miles de frames por sesión; el simulado es
   estático por configuración. Comparar el promedio de la sesión `baseline_empty` contra una
   simulación de sala vacía es el punto de partida natural.
2. **Receptores *held-out*.** Reservar al menos 2 de los 8 para validación. Ajustar 5
   materiales contra 8 receptores sobreajusta con facilidad.
3. **Cuál es la métrica de decisión.** Recomendación: correlación de patrón por encima de un
   umbral **y** diferencia de RSSI por debajo de otro. El RMSE de amplitud a secas premia
   acertar la escala y no la física.

## Puerta de salida

```bash
python scripts/calibration_report.py \
    --real data/sessions/<baseline_empty>/raw \
    --sim-config docs/contracts/scene.json
# Esperado: tabla por receptor con las 5 métricas + agregado, y una figura por receptor
#           superponiendo el CSI real y el simulado
```

Los umbrales concretos son la decisión pendiente del usuario. Sin datos reales no se pueden
fijar de forma honesta.

## Pendiente de detallar

- Umbrales de aceptación por métrica.
- Elección de receptores *held-out*.
- Si se compara promedio de sesión o distribución completa.
- Cómo tratar la ausencia de ruido en el simulado: comparar contra el real crudo penaliza al
  simulador injustamente. Puede necesitar `WP-15` (modelo de ruido) antes de que las métricas
  sean del todo justas — evaluar al activar la fase.
