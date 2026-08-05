# WP-18 — Estimación de pose 3D

| | |
|---|---|
| **Fase** | F6 · Modelos |
| **Estado** | `ESBOZO` — se detalla al activar F6 |
| **Defectos que cierra** | — |
| **Depende de** | `WP-15` (dataset sintético validado), `WP-17` (actividad), `WP-11` (datos reales) |
| **Nivel de verificación** | `gpu` + datos reales |
| **Requiere intervención del usuario** | **sí — fijar los umbrales de error** |

## Objetivo

**El objetivo final del proyecto**: estimar la pose humana en 3D —las articulaciones del
modelo SMPL— a partir únicamente de CSI de Wi-Fi, sin cámaras.

## Alcance

**Entrada**: ventanas de CSI multinodo, tensor `[frames, 8, 114]` complejo del contrato de
`WP-08`.

**Salida**: articulaciones SMPL. Dos formulaciones posibles:

| Formulación | Salida | Ventaja |
|---|---|---|
| Regresión de parámetros | `body_pose` (69) + `global_orient` (3) + `transl` (3) | Compacta; garantiza poses anatómicamente válidas por construcción |
| Regresión de posiciones | coordenadas 3D de 24 articulaciones | Más directa de evaluar; puede producir poses imposibles |

La primera es preferible: SMPL ya restringe el espacio de salida a cuerpos humanos plausibles,
que es precisamente el prior que se necesita cuando la señal de entrada es tan indirecta.

### Estrategia sim-to-real

Es la razón de ser de F4 y F5:

1. **Preentrenar** con el dataset sintético de F5, donde el ground truth de pose es exacto y
   gratuito por construcción.
2. **Afinar** con el dataset real de F3.

El problema con datos reales puros es el etiquetado: obtener pose real de referencia exigiría
un sistema de captura de movimiento, que es justo lo que el proyecto quiere evitar. Por eso el
gemelo digital calibrado no es un adorno: es lo que hace viable el ground truth.

### Riesgo principal

**La brecha sim-to-real.** Si el CSI sintético no captura la física y el ruido reales, el
modelo no transferirá. Mitigaciones ya previstas en el roadmap:

- `WP-13` calibra los materiales contra medidas reales.
- `WP-15` añade el ruido del ESP32-S3 (cuantización int8, AGC, ruido de fase, deriva).
- `WP-12` da la métrica para saber si la brecha se está cerrando **antes** de entrenar.

Si tras F4 y F5 la brecha sigue siendo grande, hay que resolverlo ahí, no aquí. Entrenar
sobre un sintético no validado es tiempo perdido.

## Puerta de salida

```bash
python scripts/eval_pose.py --model <checkpoint> --real data/sessions/ --holdout <sujetos-no-vistos>
# Esperado: error medio por articulación por debajo del umbral acordado,
#           en sujetos no vistos durante el entrenamiento
```

Los umbrales se fijan al activar la fase, con la literatura del momento como referencia. La
partición **por sujeto** (no por sesión) es lo que mide generalización real: un modelo que
memoriza la firma RF de una persona concreta no sirve.

## Pendiente de detallar

- Arquitectura. La entrada es un tensor complejo multinodo con estructura temporal; el diseño
  se decidirá con la literatura vigente al activar la fase.
- Cómo tratar la parte compleja: magnitud y fase por separado, o representación compleja
  nativa.
- Métrica: MPJPE, MPJPE alineado por Procrustes, o error de parámetros SMPL.
- Cuántos sujetos hacen falta para una partición honesta. Con uno solo no se puede medir
  generalización entre personas.
- Ground truth de pose real para el afinado: sin captura de movimiento, puede que solo se
  pueda afinar contra actividad (`WP-17`) en lugar de pose exacta. **Esta es la incógnita
  metodológica más grande del proyecto** y conviene pensarla antes de llegar aquí.
