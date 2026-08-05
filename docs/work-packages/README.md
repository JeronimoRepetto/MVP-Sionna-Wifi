# Paquetes de trabajo

Índice de todas las fichas. Cada una es una unidad de trabajo con criterios de aceptación
verificables **por comando**. El orden y las dependencias los marca
[`../ROADMAP.md`](../ROADMAP.md).

Plantilla para fichas nuevas: [`_TEMPLATE.md`](_TEMPLATE.md).

## Estados

| Estado | Significado |
|---|---|
| `PENDIENTE` | Listo para ejecutar |
| `ESBOZO` | Objetivo y puerta de salida definidos; se detalla al activar su fase |
| `EN CURSO` | Alguien está trabajando en él |
| `HECHO` | Completado y verificado |
| `BLOQUEADO` | Espera una dependencia o una decisión del usuario |

---

## F0 · Entorno reproducible

| WP | Título | Estado | Defectos | Usuario |
|---|---|---|---|---|
| [WP-00](WP-00-environment-gpu-env-vars.md) | Variables de GPU fuera del `.bashrc` | `PENDIENTE` | D-25 | no |
| [WP-00b](WP-00b-wsl2-cuda-hygiene.md) | Higiene de CUDA en WSL2 | `PENDIENTE` | D-26 | **sí** (`sudo`) |
| [WP-00c](WP-00c-esp-idf-repair.md) | Reparar ESP-IDF | `PENDIENTE` | D-27 | **sí** (admin) |

## F1 · Física correcta ★

| WP | Título | Estado | Defectos | Usuario |
|---|---|---|---|---|
| [WP-01](WP-01-complex-path-amplitudes.md) | Amplitudes complejas desde `paths.a` | `PENDIENTE` | D-01, D-38 | no |
| [WP-02](WP-02-solver-parameters.md) | Parámetros de física al solver | `PENDIENTE` | D-02, D-03, D-37 | no |
| [WP-03](WP-03-path-extraction.md) | Reconstruir `_extract_paths` | `PENDIENTE` | D-04 | no |
| [WP-04](WP-04-pytest-migration.md) | Migrar la suite a pytest | `PENDIENTE` | D-06, D-16 | no |
| [WP-05](WP-05-scene-reproducibility.md) | Reproducibilidad de la escena | `PENDIENTE` | D-05, D-07, D-08 | **sí** (decisión) |
| [WP-06](WP-06-repo-hygiene.md) | Higiene de repo y documentación | `PENDIENTE` | D-09…D-22 | **sí** (licencia) |

**Empieza por [WP-01](WP-01-complex-path-amplitudes.md)**: es un cambio de dos líneas con el
mayor impacto de todo el roadmap.

## F2 · El puente

| WP | Título | Estado | Defectos | Usuario |
|---|---|---|---|---|
| [WP-07](WP-07-canonical-scene.md) | Geometría canónica compartida | `PENDIENTE` | D-24 | **sí** (medir) |
| [WP-08](WP-08-csi-normalizer.md) | Normalizador de CSI real ↔ simulado | `PENDIENTE` | D-24 | no |

## F3 · Dataset real

| WP | Título | Estado | Defectos | Usuario |
|---|---|---|---|---|
| [WP-09](WP-09-firmware-and-nodes.md) | Reparar el firmware y flashear los nodos | `ESBOZO` | D-23, D-28…D-31, D-33 | **sí** (hardware) |
| [WP-10](WP-10-capture-protocol.md) | Ejecutar el protocolo de captura | `ESBOZO` | D-32 | **sí** (presencial) |
| [WP-11](WP-11-session-qa.md) | QA automático de sesión | `ESBOZO` | — | no |

## F4 · Calibración del gemelo digital

| WP | Título | Estado | Usuario |
|---|---|---|---|
| [WP-12](WP-12-calibration-metrics.md) | Métricas real vs simulado | `ESBOZO` | **sí** (umbrales) |
| [WP-13](WP-13-differentiable-calibration.md) | Calibración diferenciable de materiales | `ESBOZO` | no |

## F5 · Dataset sintético a escala

| WP | Título | Estado | Defectos |
|---|---|---|---|
| [WP-14](WP-14-headless-batch-runner.md) | Runner headless en batch | `ESBOZO` | D-35 |
| [WP-15](WP-15-realistic-variability.md) | Variabilidad realista y modelo de ruido | `ESBOZO` | — |

## F6 · Modelos

| WP | Título | Estado | Usuario |
|---|---|---|---|
| [WP-16](WP-16-presence-detection.md) | Detección de presencia | `ESBOZO` | no |
| [WP-17](WP-17-activity-classification.md) | Clasificación de actividad | `ESBOZO` | **sí** (clases) |
| [WP-18](WP-18-pose-estimation.md) | Estimación de pose 3D | `ESBOZO` | **sí** (umbrales) |

## F7 · Validación y publicación

| WP | Título | Estado | Defectos | Usuario |
|---|---|---|---|---|
| [WP-19](WP-19-reproducibility-and-release.md) | Reproducibilidad, CI y publicación | `ESBOZO` | D-19, D-36 | **sí** (licencias) |

---

## Decisiones pendientes del usuario

Reunidas aquí para que no se pierdan dentro de las fichas:

| # | Decisión | Ficha | Por qué importa |
|---|---|---|---|
| 1 | Licencia de `frontend/public/human.obj` (malla derivada de SMPL, versionada) | WP-06 | **Bloquea publicar el repo.** Resolverlo ya, no en F7 |
| 2 | Qué hacer con `blender/generate_room.py` (retirar / hacer real / proteger) | WP-05 | Hoy puede destruir la única copia de la escena |
| 3 | Materiales: alinear la doc con el código, o el código con la doc | WP-05 | Cambiar a `itu_brick` altera todos los resultados |
| 4 | Escena canónica y medidas reales de la escalera | WP-07 | Sin medidas reales, F4 no puede dar resultados válidos |
| 5 | Ejecutar `WP-00b` (purgar el driver nativo de WSL2) | WP-00b | Requiere `sudo`. Opcional: `WP-00` ya deja la GPU funcionando |
| 6 | Reparar ESP-IDF | WP-00c | **Bloquea toda la fase F3** |
| 7 | Número de nodos ESP32-S3 disponibles | WP-09 | Condiciona el protocolo de captura y la diversidad espacial |
| 8 | Método de etiquetado del ground truth | WP-10 | Condiciona qué modelos son entrenables en F6 |
| 9 | Conjunto de clases de actividad (¿incluye caídas?) | WP-17 | Condiciona qué se captura en WP-10 |
| 10 | Umbrales de aceptación de calibración y de pose | WP-12, WP-18 | Definen qué significa «funciona» |
