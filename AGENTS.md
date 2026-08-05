# AGENTS.md — Instrucciones para agentes de IA

> Punto de entrada único. Si eres un agente (Claude Code, Cursor, Codex, Copilot
> Workspace, …) y vas a trabajar en este repositorio, **lee este fichero completo antes
> de tocar nada**. Es corto a propósito.

---

## 1. Qué es esto

`MVP-Sionna-Wifi` es un **gemelo digital 3D** de una sala con 1 router Wi-Fi (Tx) y 8
ESP32-S3 (Rx). Simula la propagación de radio a 2,437 GHz con **NVIDIA Sionna RT**
(ray tracing sobre Mitsuba 3), inyecta un cuerpo humano **SMPL** de 6.890 vértices como
obstáculo RF, y lo visualiza en tiempo real con **Three.js**.

Forma parte del programa de investigación **Wi-Fi Vision 3D**, cuyo objetivo final es
estimar la pose humana en 3D usando solo señales Wi-Fi, sin cámaras. El repo hermano
[`wifi-csi-capture`](https://github.com/JeronimoRepetto/wifi-csi-capture) captura CSI
**real** del hardware; este repo genera el equivalente **simulado**. Los dos deben
converger — ver [`docs/contracts/`](docs/contracts/).

Este repositorio es el **canónico** para documentación, roadmap y contratos compartidos
entre ambos repos.

---

## 2. Reglas duras

Violar cualquiera de estas causa daño real. No hay excepciones sin instrucción explícita
del usuario.

| # | Regla |
|---|---|
| R1 | **Nunca** escribas, muevas ni commitees nada en `backend/models/smpl/`. Son ficheros bajo licencia [MPI-IS](https://smpl.is.tue.mpg.de/) que no pueden redistribuirse. Lo mismo aplica a cualquier malla derivada de ellos. |
| R2 | **Nunca** ejecutes `blender/generate_room.py` sin haber leído [`WP-05`](docs/work-packages/WP-05-scene-reproducibility.md). Sobrescribe `scenes/room_simple.xml`, que es la escena **en uso** y **no está en git**. Perderías la única copia. |
| R3 | **Nunca** corras los tests con el Python de Windows sin `PYTHONUTF8=1`. Los emojis de los tests provocan `UnicodeEncodeError` en cp1252. Usa `scripts/verify.py`, que ya lo hace. |
| R4 | **Nunca** commitees datos: `data/`, `output/`, `build/`, `sdkconfig`, `*.csv`, `*.pkl`, `*.npz`. |
| R5 | Antes de modificar `backend/simulation.py` o `backend/scene_loader.py`, **lee [`docs/agent/SIONNA_API_CONTRACT.md`](docs/agent/SIONNA_API_CONTRACT.md)**. La API de Sionna RT 1.x rompió con la 0.x de formas que no dan error, solo resultados incorrectos. Este repo ya cayó en cuatro de esas trampas. |
| R6 | No inventes parámetros físicos. `backend/config.py` es la única fuente de verdad. |
| R7 | Si un cambio hace que un test pase de `xfail` a `xpass`, **quita la marca `xfail`** y cierra el defecto en [`docs/DEFECTS.md`](docs/DEFECTS.md). La suite está configurada con `strict=True` precisamente para forzarlo. |

---

## 3. Arranque

El backend **solo funciona en Linux/WSL2** (Sionna necesita CUDA vía Linux). El frontend
corre en Windows o Linux indistintamente.

```bash
# 1. Activar el entorno (WSL2)
source ~/miniconda3/etc/profile.d/conda.sh && conda activate sionna

# 2. Comprobar que el entorno está sano — SIEMPRE lo primero
python scripts/env_check.py

# 3. Verificar el estado del proyecto
python scripts/verify.py --level sionna

# 4. Arrancar el backend (usa este lanzador, NO `python main.py` directamente)
bash scripts/run_backend.sh
```

**Por qué `run_backend.sh` y no `python backend/main.py`**: las tres variables de entorno
que habilitan la GPU viven en `~/.bashrc`, después del guard de no-interactividad de
Ubuntu. En cualquier shell no interactiva no se aplican y Sionna cae a CPU **en silencio**
(~5× más lento). El lanzador las exporta explícitamente. Detalle completo en
[`docs/agent/ENVIRONMENT.md`](docs/agent/ENVIRONMENT.md).

Frontend:

```bash
cd frontend && npm run dev     # http://localhost:5173
```

> Nota: el perfil de PowerShell del usuario redirige `npm`/`npx` a `pnpm`. En scripts
> automatizados usa `node ./node_modules/vite/bin/vite.js` para evitar sorpresas.

---

## 4. Flujo de trabajo

1. **Elige un paquete de trabajo** en [`docs/work-packages/`](docs/work-packages/).
   El orden lo marca [`docs/ROADMAP.md`](docs/ROADMAP.md); respeta las dependencias
   declaradas en la cabecera de cada ficha.
2. **Lee los documentos que la ficha referencia** antes de escribir código.
3. **Implementa** cumpliendo los criterios de aceptación de la ficha. Cada criterio es un
   comando con salida esperada — no son descripciones vagas.
4. **Verifica**: `python scripts/verify.py --level gpu` (o el nivel que indique la ficha).
5. **Cierra los defectos** que la ficha lista en [`docs/DEFECTS.md`](docs/DEFECTS.md):
   cambia el estado a `CERRADO` y añade el commit.
6. **Sincroniza la documentación** si tu cambio la deja obsoleta. Documentación que miente
   es peor que no tener documentación — este repo ya tuvo tres casos.

### Definición de «hecho»

- [ ] `scripts/verify.py` verde en el nivel que exige la ficha.
- [ ] Cero `xpass` (si algo pasó a verde, la marca `xfail` está quitada).
- [ ] Defectos afectados marcados en `docs/DEFECTS.md`.
- [ ] Documentación afectada actualizada.
- [ ] `git status` no muestra ficheros que las reglas R1/R4 prohíben.

---

## 5. Índice de documentación

### Para agentes — leer según necesidad

| Documento | Cuándo leerlo |
|---|---|
| [`docs/agent/SIONNA_API_CONTRACT.md`](docs/agent/SIONNA_API_CONTRACT.md) | **Obligatorio** antes de tocar `simulation.py` o `scene_loader.py` |
| [`docs/agent/ENVIRONMENT.md`](docs/agent/ENVIRONMENT.md) | Cuando algo del entorno falla, o cuando `env_check.py` sale en rojo |
| [`docs/agent/PHYSICS_INVARIANTS.md`](docs/agent/PHYSICS_INVARIANTS.md) | Antes de cambiar cualquier cálculo de física, y al escribir tests |
| [`docs/agent/CONVENTIONS.md`](docs/agent/CONVENTIONS.md) | Antes del primer commit; contiene los 3 sistemas de coordenadas |
| [`docs/agent/VERIFICATION.md`](docs/agent/VERIFICATION.md) | Para entender los niveles de verificación y qué hacer si algo sale rojo |

### Estado y plan

| Documento | Contenido |
|---|---|
| [`docs/DEFECTS.md`](docs/DEFECTS.md) | Registro de defectos con ID estable. Empieza aquí para saber qué está roto |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Fases F0→F7 hasta pose 3D, con puertas de salida verificables |
| [`docs/work-packages/`](docs/work-packages/) | Una ficha ejecutable por paquete de trabajo |
| [`docs/GLOSSARY.md`](docs/GLOSSARY.md) | CSI, CIR, CFR, SBR, HT40, SMPL, betas, delay spread… |

### Contratos compartidos con `wifi-csi-capture`

| Documento | Contenido |
|---|---|
| [`docs/contracts/SCENE_GEOMETRY.md`](docs/contracts/SCENE_GEOMETRY.md) | Geometría canónica. **Hoy los dos repos usan escenas distintas** |
| [`docs/contracts/CSI_DATA_CONTRACT.md`](docs/contracts/CSI_DATA_CONTRACT.md) | Formato del CSI real y del simulado, para que sean comparables |

### Documentación de usuario (no de agente)

`README.md`, [`docs/HOW_IT_WORKS.md`](docs/HOW_IT_WORKS.md),
[`docs/INSTALL_WSL2_GPU.md`](docs/INSTALL_WSL2_GPU.md). Contienen afirmaciones
desactualizadas registradas como defectos — **no las uses como fuente de verdad técnica**
hasta que WP-06 las sincronice.

---

## 6. Mapa del código

```
backend/
  config.py         Fuente de verdad: geometría, RF, posiciones Tx/Rx, parámetros de RT
  scene_loader.py   Selecciona el variant de Mitsuba ANTES de importar Sionna (crítico,
                    no reordenar), carga el XML, añade Tx + 8 Rx, inyecta la malla humana
  simulation.py     PathSolver + RadioMapSolver → paths / CIR / CSI / coverage.
                    ⚠️ Aquí viven los 4 defectos P0 de física
  smpl_manager.py   smplx + trimesh → malla de 6.890 vértices, con swap Y↔Z para Mitsuba
  pose_library.py   Keyframes de marcha y trayectoria. Referencia correcta de coordenadas
  main.py           FastAPI: /api/scene, /api/simulate, /api/coverage, /ws/simulation
frontend/src/
  main.js           Orquestador: Three.js + WebSocket + controles
  scene3d.js  sensors.js  rays.js  heatmap.js  human.js  csi_panel.js  controls.js
  websocket.js      Cliente WS con reconexión automática
blender/
  generate_room.py  Generador de sala. ⚠️ Ver R2 antes de ejecutarlo
scenes/
  room_simple.xml   Escena Mitsuba en uso. ⚠️ NO está en git (defecto D-05)
tests/               Suite legada (scripts sueltos) + suite nueva de invariantes (pytest)
scripts/             env_check.py, verify.py, run_backend.sh
```

---

## 7. Estado actual en una tabla

| Área | Estado |
|---|---|
| Infraestructura, frontend, pipeline SMPL | ✅ Funcionan |
| Sionna RT ejecutándose (GPU y CPU) | ✅ Funciona (0,027 s/frame en GPU) |
| **Corrección física de los resultados** | 🔴 **Incorrecta** — ver D-01…D-04 |
| Reproducibilidad desde un clon limpio | 🔴 Falta la escena en git — D-05 |
| Tests | 🟠 Los que pasan solo ejercitan el mock — D-06 |
| Puente con datos reales | ⚪ No empezado — F2 del roadmap |

**Lo importante**: el proyecto *parece* funcionar. La UI es convincente, el badge dice
«Sionna RT: Active» y los gráficos se mueven. Pero los números que muestra no son
físicamente válidos. Si tu tarea es comparar con datos reales, **arregla F1 primero** o
calibrarás el simulador contra su propio bug.
