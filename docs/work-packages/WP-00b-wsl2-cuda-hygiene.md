# WP-00b — Higiene de CUDA en WSL2

| | |
|---|---|
| **Fase** | F0 · Entorno reproducible |
| **Estado** | `PENDIENTE` |
| **Defectos que cierra** | D-26 |
| **Invariantes que pone en verde** | — |
| **Depende de** | — (recomendado tras `WP-00`) |
| **Nivel de verificación** | `gpu` |
| **Requiere intervención del usuario** | **sí — `sudo`. Un agente NO debe ejecutar esto** |

> ⚠️ **Este paquete modifica el sistema, no el repositorio.** Un agente de IA puede
> preparar los comandos, explicar cada uno y verificar el resultado, pero **la ejecución la
> hace el usuario**. Desinstalar paquetes de driver es potencialmente disruptivo.
>
> `WP-00` ya deja la GPU funcionando con un parche. Este paquete elimina la **causa** para
> que el parche deje de ser necesario. Es deseable, no urgente.

## Objetivo

Eliminar los paquetes de driver NVIDIA **nativo de Linux** instalados dentro de WSL2. Su
presencia secuestra `libcuda.so` y es la razón por la que Sionna necesita el parche de
`LD_LIBRARY_PATH`. Sin ellos, CUDA funciona sin trucos.

## Contexto

Lee [`../agent/ENVIRONMENT.md §5 capa 2`](../agent/ENVIRONMENT.md).

Diagnóstico medido:

```
$ ldconfig -p | grep "libcuda\.so"
libcuda.so.1 => /usr/lib/wsl/lib/libcuda.so.1          ← correcto (stub 188 KB)
libcuda.so.1 => /lib/x86_64-linux-gnu/libcuda.so.1     ← driver NATIVO
libcuda.so   => /lib/x86_64-linux-gnu/libcuda.so       ← ¡solo existe el nativo!

$ ls -la /usr/lib/x86_64-linux-gnu/libcuda.so.580.173.02
-rw-r--r-- 96284520  Jun 29 07:30

$ dpkg -S /usr/lib/x86_64-linux-gnu/libcuda.so.580.173.02
libnvidia-compute-580:amd64

$ ls /dev/nvidia*
No such file or directory        ← correcto en WSL2: solo existe /dev/dxg
```

`libdrjit-core.so` hace `dlopen("libcuda.so")` — el nombre **sin versionar**, verificado con
`strings`. Ese nombre solo resuelve al driver nativo, que busca `/dev/nvidia0`, inexistente
en WSL2, y devuelve:

```
jit_cuda_init(): the CUDA backend is not available because cuInit() failed.
  "no CUDA-capable device is detected"
```

PyTorch no se ve afectado porque carga `libcuda.so.1` (versionado), que sí resuelve primero
al de WSL. De ahí la paradoja de `torch.cuda.is_available() == True` mientras Mitsuba falla.

**Origen probable**: el paso 3 de [`../INSTALL_WSL2_GPU.md`](../INSTALL_WSL2_GPU.md)
(`sudo apt-get install -y cuda-toolkit`), cuyo metapaquete puede arrastrar
`cuda-drivers`/`libnvidia-compute-*`. Además está instalado el `nvidia-cuda-toolkit` de
Ubuntu, que sí depende de `libnvidia-compute`. La fecha del fichero (29-jun-2026) encaja con
una actualización de sistema que rompió lo que antes funcionaba.

## Qué hay instalado que no debería

```
libnvidia-compute-495:amd64   510.108.03
libnvidia-compute-510:amd64   525.147.05
libnvidia-compute-535:amd64   535.309.01
libnvidia-compute-580:amd64   580.173.02   ← el que aporta el libcuda.so problemático
nvidia-kernel-common-580      580.173.02
nvidia-cuda-toolkit           11.5.1       ← además pone nvcc 11.5 en /usr/bin,
                                             tapando el 12.6 de /usr/local/cuda-12.6/bin
libnvidia-ml-dev              11.5.50
~/NVIDIA-Linux-x86_64-580.142.run   398 MB  ← instalador de driver nativo
```

## Pasos (los ejecuta el usuario)

**Antes de nada: snapshot.** `wsl --shutdown` y
`wsl --export Ubuntu-22.04 D:\backup-ubuntu.tar`. Si algo va mal, `wsl --import` restaura.

1. Ver qué se eliminaría, **sin eliminar nada**:

   ```bash
   sudo apt-get remove --dry-run libnvidia-compute-495 libnvidia-compute-510 \
        libnvidia-compute-535 libnvidia-compute-580 nvidia-kernel-common-580
   ```

   Revisar la lista. Si arrastra algo inesperado (sobre todo paquetes `cuda-*-12-6`),
   **parar** y reevaluar.

2. Eliminar los paquetes de driver nativo:

   ```bash
   sudo apt-get remove --purge libnvidia-compute-495 libnvidia-compute-510 \
        libnvidia-compute-535 libnvidia-compute-580 nvidia-kernel-common-580
   ```

3. Eliminar el toolkit de Ubuntu (el 11.5 que tapa el 12.6):

   ```bash
   sudo apt-get remove --purge nvidia-cuda-toolkit nvidia-cuda-toolkit-doc libnvidia-ml-dev
   ```

4. Reconstruir la caché del enlazador y confirmar:

   ```bash
   sudo ldconfig
   ldconfig -p | grep "libcuda\.so"
   # Esperado: SOLO entradas de /usr/lib/wsl/lib
   ```

5. Borrar el instalador nativo para que nadie lo ejecute por error:

   ```bash
   rm ~/NVIDIA-Linux-x86_64-580.142.run
   ```

6. Verificar `nvcc`:

   ```bash
   which -a nvcc
   # Esperado: /usr/local/cuda-12.6/bin/nvcc (o vacío si no está en PATH; NO /usr/bin/nvcc)
   ```

7. Si el paso 4 sale limpio, **quitar el parche**: comentar
   `LD_LIBRARY_PATH=/usr/lib/wsl/lib` en el hook de conda de `WP-00` y comprobar que la GPU
   sigue funcionando. `DRJIT_LIBOPTIX_PATH` **sigue siendo necesaria** — es un problema
   distinto (el stub de OptiX, capa 3) que este paquete no resuelve.

## Criterios de aceptación

```bash
# 1. Solo la libcuda de WSL
ldconfig -p | grep "libcuda\.so"
# Esperado: únicamente rutas /usr/lib/wsl/lib
```

```bash
# 2. CUDA arranca SIN el parche de LD_LIBRARY_PATH
env -u LD_LIBRARY_PATH DRJIT_LIBOPTIX_PATH=/usr/lib/wsl/lib/libnvoptix_real.so.1 \
  python -c "
import mitsuba as mi
mi.set_variant('cuda_ad_mono_polarized')
mi.load_string('<scene version=\"2.0.0\"></scene>')
print('CUDA + OptiX OK sin parche')"
```

```bash
# 3. PyTorch sigue viendo la GPU
python -c "import torch; print('torch.cuda:', torch.cuda.is_available())"
# Esperado: True
```

```bash
# 4. Nada se ha roto
python scripts/verify.py --level gpu
```

- [ ] Los cuatro comandos pasan
- [ ] `LD_LIBRARY_PATH=/usr/lib/wsl/lib` eliminado del hook de conda
- [ ] `ENVIRONMENT.md §5` y §6 actualizados
- [ ] `INSTALL_WSL2_GPU.md` paso 3 corregido: usar `cuda-toolkit-12-6` en lugar del
      metapaquete `cuda-toolkit`, y añadir una comprobación de que no ha entrado
      `libnvidia-compute-*`
- [ ] D-26 marcado `CERRADO`

## Fuera de alcance

- El stub de OptiX (capa 3). `DRJIT_LIBOPTIX_PATH` sigue siendo necesaria.
- Actualizar CUDA a 13.x para alinear con el UMD 13.3 del host. No hay evidencia de que
  haga falta: 12.6 funciona.
- Cualquier cambio en el repositorio salvo la corrección de las dos guías.

## Riesgos y trampas

| Riesgo | Mitigación |
|---|---|
| Quitar `libnvidia-compute-*` rompe otro software que dependa de él | Paso 1 (`--dry-run`) lo revela antes. Snapshot de WSL como red |
| `apt` arrastra paquetes `cuda-*-12-6` en la desinstalación | Parar en el paso 1 si aparecen; eliminar uno por uno en su lugar |
| Una futura actualización reintroduce el driver nativo | `env_check.py` detecta la libcuda nativa y avisa. Considerar `apt-mark hold` |
| Perder el entorno WSL entero | El `wsl --export` previo no es opcional |
