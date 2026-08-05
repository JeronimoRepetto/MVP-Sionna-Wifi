# WP-13 — Calibración diferenciable de materiales

| | |
|---|---|
| **Fase** | F4 · Calibración del gemelo digital |
| **Estado** | `ESBOZO` — se detalla al activar F4 |
| **Defectos que cierra** | — |
| **Depende de** | `WP-12` (métricas y umbrales acordados) |
| **Nivel de verificación** | `gpu` (el gradiente sobre CPU será impracticable) |
| **Requiere intervención del usuario** | no |

## Objetivo

Ajustar la permitividad relativa y la conductividad de cada material para minimizar el error
entre CSI simulado y medido. Es lo que convierte una simulación en un **gemelo digital**: un
modelo cuyas predicciones son fiables porque se ha contrastado con la realidad.

## Alcance

Sionna RT es **diferenciable** — está construido sobre Mitsuba 3 con Dr.Jit y soporta modo
de diferenciación automática (`*_ad_*` en el nombre del variant). Este es exactamente el caso
de uso para el que existe.

**Parámetros a optimizar**: `εr` y `σ` de cada material presente en la escena. Valores
iniciales ya documentados en `wifi-csi-capture/tools/digital_twin_sionna.py::MATERIALS`:

| Material | εr | σ (S/m) |
|---|---|---|
| Tabique de yeso | 2,94 | 0,0386 |
| Hormigón | 5,31 | 0,0707 |
| Madera | 1,99 | 0,0047 |
| Barandilla metálica | 1,0 | 1e7 |
| Tejido humano | 39,2 | 1,8 |

Los de tejido humano vienen de un modelo Cole-Cole a 2,45 GHz (piel εr 38,1 / σ 1,46;
músculo 52,7 / 1,74; grasa 5,28 / 0,10; hueso 11,4 / 0,39). Son un buen punto de partida y
probablemente **no** deban optimizarse: son propiedades físicas conocidas, no parámetros
libres. Los de construcción sí: dependen del material real de la escalera, que se desconoce.

**Restricciones físicas obligatorias**: acotar la optimización a rangos plausibles según
ITU-R P.2040. Sin cotas, el optimizador encontrará valores que minimizan el error y no
corresponden a ningún material real — habría ajustado la física a los datos en lugar de
descubrirla.

**Validación**: el criterio es el error en los receptores *held-out* de `WP-12`, nunca el de
los usados para ajustar.

## Puerta de salida

```bash
python scripts/calibrate.py \
    --real data/sessions/<baseline_empty>/raw \
    --holdout ESP32_3,ESP32_7 \
    --out docs/contracts/materials_calibrated.json
# Esperado: métricas de WP-12 por debajo del umbral en los receptores held-out,
#           y valores finales de εr/σ dentro de los rangos de ITU-R P.2040
```

## Pendiente de detallar

- Optimizador y planificación de la tasa de aprendizaje.
- Si el gradiente atraviesa `RadioMapSolver` además de `PathSolver`.
- Coste computacional: cada paso implica una simulación completa. Con 0,027 s/frame en GPU es
  viable; medirlo antes de comprometerse a un número de iteraciones.
- Si además de materiales conviene ajustar posiciones de antena (dentro de la incertidumbre
  de medida) y patrones de radiación. Añade grados de libertad y riesgo de sobreajuste.
- Cómo se versionan los materiales calibrados y cómo se relacionan con `scene.json`.
