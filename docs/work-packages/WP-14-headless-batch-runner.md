# WP-14 — Runner headless en batch

| | |
|---|---|
| **Fase** | F5 · Dataset sintético a escala |
| **Estado** | `ESBOZO` — se detalla al activar F5 |
| **Defectos que cierra** | D-35 |
| **Depende de** | `WP-13` (gemelo calibrado) |
| **Nivel de verificación** | `gpu` |
| **Requiere intervención del usuario** | no |

## Objetivo

Generar miles de muestras de CSI etiquetadas sin frontend, sin WebSocket y sin intervención.
Aquí está el valor real del gemelo digital: en simulación se conoce la posición exacta de
cada articulación, algo que con datos reales exigiría un sistema de captura de movimiento.

## Alcance

**Rendimiento** — el bloqueo principal es D-35: `handle_sim_walk` llama a
`load_scene(human_mesh_path=…)` en **cada frame**, lo que reparsea el XML, reconstruye la
escena de Mitsuba y vuelve a dar de alta 1 Tx + 8 Rx. Para generar decenas de miles de
muestras hay que actualizar solo los vértices de la malla humana mediante la API de Mitsuba,
manteniendo el resto de la escena viva.

**Arquitectura**: un script que recibe una especificación de barrido (trayectorias, poses,
`betas`, escenarios) y escribe muestras en un formato eficiente (`.npz` o similar), con
etiquetas: posición del pelvis, articulaciones SMPL, orientación, escenario, y los parámetros
de simulación usados.

**Reutilizar** en lugar de reescribir:

| Símbolo | Fichero | Para qué |
|---|---|---|
| `generate_walk_sequence` | `backend/pose_library.py` | Secuencias de marcha con ambos sistemas de coordenadas |
| `generate_rectangular_trajectory` | `backend/pose_library.py` | Trayectorias |
| `SMPLManager.save_obj(for_sionna=True)` | `backend/smpl_manager.py` | Malla con la permutación Y↔Z correcta |
| `run_simulation` | `backend/simulation.py` | Punto de entrada de simulación |

**Trazabilidad**: cada muestra debe registrar la versión de `scene.json`, el hash de los
materiales calibrados y la semilla. Un dataset sintético sin la procedencia de su generador
no es reproducible.

## Puerta de salida

```bash
python scripts/generate_dataset.py --spec configs/sweep_walk.yaml --out data/synthetic/
# Esperado: N muestras con etiquetas completas, throughput registrado,
#           metadatos de procedencia en cada fichero
```

Objetivo de throughput a fijar al activar la fase. Referencia: 0,027 s por simulación en GPU
sin recarga de escena — el techo teórico es alto; la recarga actual lo destruye.

## Pendiente de detallar

- Formato de almacenamiento y esquema de etiquetas (debe alinearse con lo que consuma `WP-18`).
- Paralelismo: procesos concurrentes vs *batching* dentro de una única escena de Mitsuba.
- Tamaño objetivo del dataset.
- Si la generación puede correr desatendida durante horas sin problemas térmicos (en GPU
  debería; en CPU está descartado).
