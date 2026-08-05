# WP-17 — Clasificación de actividad

| | |
|---|---|
| **Fase** | F6 · Modelos |
| **Estado** | `ESBOZO` — se detalla al activar F6 |
| **Defectos que cierra** | — |
| **Depende de** | `WP-16` (presencia como paso previo), `WP-11` (datos con QA) |
| **Nivel de verificación** | `hardware` |
| **Requiere intervención del usuario** | **sí — definir el conjunto de clases** |

## Objetivo

Distinguir qué está haciendo la persona, no solo si está. Segunda puerta de F6.

## Alcance

**Clases mínimas**, alineadas con los escenarios que `record_session.py` ya define:

| Clase | Escenario de captura |
|---|---|
| vacío | `baseline_empty` |
| quieto | `stairs_still` |
| caminando | `stairs_walk` |

Ampliaciones posibles (decisión del usuario): subir vs bajar escaleras, sentarse, caída. La
detección de caídas es la aplicación con más valor práctico de todo el proyecto y merece
considerarse explícitamente al fijar las clases — condiciona qué se captura en `WP-10`.

**Entrada**: ventanas temporales de CSI multinodo. La dimensión temporal es lo que distingue
este paquete de `WP-16`: quieto y caminando pueden tener perturbación media similar y
dinámica completamente distinta.

**Características de partida**, todas ya disponibles o triviales de derivar:

- `CV = std/mean` por nodo y frame — ya lo calcula `csi_panel.js` y lo usa el visualizador.
  Invariante a escalado, robusto frente al AGC.
- Diferencia temporal de amplitud (perturbación por movimiento).
- Espectrograma por nodo — el visualizador ya lo construye.
- Delay spread por frame.
- Puntuación de consenso espacial de `WP-16`.

**Modelos**: empezar simple (bosque aleatorio o gradient boosting sobre características
agregadas por ventana) antes de pasar a redes temporales. Con un dataset pequeño, un modelo
simple con buenas características suele ganar, y además es interpretable.

## Puerta de salida

```bash
python scripts/eval_activity.py --sessions data/sessions/ --holdout <sesiones-no-vistas>
# Esperado: exactitud > 0,85 y matriz de confusión sin ninguna clase colapsada
```

La matriz de confusión es parte del criterio: una exactitud del 85 % que se logra ignorando
la clase minoritaria no vale.

## Pendiente de detallar

- Conjunto de clases definitivo (decisión del usuario, condiciona `WP-10`).
- Longitud de ventana y solapamiento. Determina la latencia de decisión.
- Si se entrena con sintético (F5) o solo con real. Para actividad, el real probablemente
  baste; el sintético es más crítico para pose.
- Estrategia frente al desbalance de clases.
