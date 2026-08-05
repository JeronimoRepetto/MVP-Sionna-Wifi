# WP-00 — Variables de GPU fuera del `.bashrc`

| | |
|---|---|
| **Fase** | F0 · Entorno reproducible |
| **Estado** | `PENDIENTE` |
| **Defectos que cierra** | D-25 |
| **Invariantes que pone en verde** | — |
| **Depende de** | — |
| **Nivel de verificación** | `gpu` |
| **Requiere intervención del usuario** | no |

## Objetivo

Hacer que Sionna use la GPU **siempre**, no solo en terminales interactivas. Hoy las tres
variables que habilitan CUDA+OptiX viven en `~/.bashrc` después del guard de
no-interactividad de Ubuntu, así que cualquier script, tarea de VS Code, CI o agente de IA
ejecuta la simulación en CPU sin recibir ningún aviso: 5× más lento y con el 100 % de la CPU
ocupada.

## Contexto

Lee [`../agent/ENVIRONMENT.md §3-§5`](../agent/ENVIRONMENT.md) antes de empezar. Resumen de
lo medido:

```bash
# En shell no interactiva:
echo "[$LD_LIBRARY_PATH]"        →  []          # vacío
→ 🟡 Mitsuba backend: LLVM mono-polarized (CPU)   ·  0,13 s/frame

# Con las tres variables aplicadas a mano:
→ 🟢 Mitsuba backend: CUDA + OptiX mono-polarized (GPU)  ·  0,027 s/frame
```

Las variables necesarias y su motivo exacto:

| Variable | Motivo |
|---|---|
| `LD_LIBRARY_PATH=/usr/lib/wsl/lib` | Evita que `dlopen("libcuda.so")` de `libdrjit-core.so` resuelva al driver Linux nativo instalado en WSL2 (D-26) |
| `LD_LIBRARY_PATH+=/usr/local/cuda-12.6/lib64` | Runtime de CUDA 12.6 |
| `DRJIT_LIBOPTIX_PATH=/usr/lib/wsl/lib/libnvoptix_real.so.1` | El `libnvoptix.so.1` de WSL es un stub de 14 KB que no exporta `optixQueryFunctionTable`; el real son 105 MB |

`scripts/run_backend.sh` ya exporta las tres. Este paquete extiende esa solución al entorno
conda, para que valga también para pytest, scripts sueltos y cualquier invocación.

## Ficheros a tocar

| Fichero | Qué cambia |
|---|---|
| `$CONDA_PREFIX/etc/conda/activate.d/10-wifivision-gpu.sh` | **Nuevo**, fuera del repo. Exporta las tres variables al activar el entorno |
| `$CONDA_PREFIX/etc/conda/deactivate.d/10-wifivision-gpu.sh` | **Nuevo**, fuera del repo. Restaura los valores previos |
| `scripts/setup_conda_gpu_env.sh` | **Nuevo**. Instala los dos scripts anteriores de forma idempotente |
| `scripts/env_check.py` | Detectar y reportar si los hooks de conda están instalados |
| `../agent/ENVIRONMENT.md` | Documentar la solución definitiva y marcar el parche como histórico |

**NO tocar**: `~/.bashrc`. Las líneas 135-137 pueden quedarse; son inofensivas y siguen
sirviendo en sesiones interactivas. Modificar el `.bashrc` del usuario es un efecto lateral
fuera del repo que no aporta nada aquí.

## Pasos

1. Escribir `scripts/setup_conda_gpu_env.sh`. Debe:
   - Fallar con mensaje claro si `$CONDA_PREFIX` no está definido.
   - Crear `etc/conda/activate.d/` y `etc/conda/deactivate.d/` si no existen.
   - Escribir los hooks de forma **idempotente** (reejecutarlo no debe duplicar entradas
     en `LD_LIBRARY_PATH`).
   - Comprobar que `/usr/lib/wsl/lib/libnvoptix_real.so.1` existe antes de referenciarlo, y
     avisar si no (podría cambiar de nombre en un driver futuro).
2. El hook de activación guarda los valores previos en
   `_WIFIVISION_OLD_LD_LIBRARY_PATH` / `_WIFIVISION_OLD_DRJIT_LIBOPTIX_PATH` y los
   antepone; el de desactivación los restaura y limpia las variables auxiliares.
3. Ejecutarlo una vez en el entorno `sionna`.
4. Extender `scripts/env_check.py` con una fila `conda gpu hooks` que informe de si están
   instalados y de qué variables están activas.
5. Actualizar `ENVIRONMENT.md §3-§4`: la solución canónica pasa a ser el hook de conda;
   `run_backend.sh` sigue siendo el lanzador recomendado (funciona incluso sin el hook).

## Criterios de aceptación

```bash
# 1. GPU en shell NO interactiva, sin exportar nada a mano
wsl -e bash -lc "source ~/miniconda3/etc/profile.d/conda.sh && conda activate sionna && cd /mnt/c/Users/jeron/Desktop/MVP-Sionna-Wifi && python scripts/env_check.py"
# Esperado: backend = cuda_ad_mono_polarized (GPU + OptiX)
```

```bash
# 2. Los tests también van por GPU
wsl -e bash -lc "source ~/miniconda3/etc/profile.d/conda.sh && conda activate sionna && cd /mnt/c/Users/jeron/Desktop/MVP-Sionna-Wifi && python scripts/verify.py --level gpu"
# Esperado: env_check PASS con backend cuda_*
```

```bash
# 3. Idempotencia: dos ejecuciones no duplican rutas
bash scripts/setup_conda_gpu_env.sh && bash scripts/setup_conda_gpu_env.sh
conda deactivate && conda activate sionna
python -c "import os,collections; p=os.environ['LD_LIBRARY_PATH'].split(':'); d=[k for k,v in collections.Counter(p).items() if v>1]; assert not d, d; print('sin duplicados')"
```

```bash
# 4. Desactivar restaura el entorno
conda deactivate
python -c "import os; assert 'DRJIT_LIBOPTIX_PATH' not in os.environ; print('limpio')"
```

- [ ] Los cuatro comandos anteriores pasan
- [ ] `ENVIRONMENT.md` actualizado
- [ ] D-25 marcado `CERRADO` en [`../DEFECTS.md`](../DEFECTS.md)

## Fuera de alcance

- Eliminar el driver nativo de WSL2 que hace necesario `LD_LIBRARY_PATH` → `WP-00b`
  (requiere `sudo`).
- Reparar ESP-IDF → `WP-00c`.
- Cualquier cambio en `backend/`.

## Riesgos y trampas

| Riesgo | Mitigación |
|---|---|
| `libnvoptix_real.so.1` cambia de nombre en un driver futuro | El script comprueba su existencia y avisa; `env_check.py` lo reporta |
| Anteponer `/usr/lib/wsl/lib` rompe otra biblioteca | No observado. Si pasa, poner la ruta al final y confiar solo en `DRJIT_LIBOPTIX_PATH` |
| El hook se pierde al recrear el entorno conda | `setup_conda_gpu_env.sh` es idempotente y está documentado en `ENVIRONMENT.md` |
| Alguien «arregla» el `.bashrc` moviendo las líneas antes del guard | Rompería sesiones no interactivas de formas raras. El comentario del hook explica por qué está donde está |
