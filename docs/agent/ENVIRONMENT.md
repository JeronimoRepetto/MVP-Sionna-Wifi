# Entorno de desarrollo — estado medido

> Este documento describe el entorno **tal como está**, no como debería estar. Los valores
> vienen de una inspección real de la máquina de desarrollo (2026-08-05). Si algo no
> coincide, ejecuta `python scripts/env_check.py` y actualiza este fichero.
>
> Para la guía de instalación desde cero, ver [`../INSTALL_WSL2_GPU.md`](../INSTALL_WSL2_GPU.md)
> — pero lee primero la §6 de este documento, porque uno de sus pasos es probablemente el
> origen de los problemas actuales.

---

## 1. Topología

```
Windows 11 (host)                    WSL2 Ubuntu-22.04
┌────────────────────────┐          ┌──────────────────────────────┐
│ frontend (Vite/Three)  │◄─:5173──►│  conda env "sionna"          │
│ Node v24.11.1          │          │  Python 3.10.20              │
│                        │◄─:8000──►│  backend FastAPI + Sionna RT │
│ ESP-IDF 5.5.3          │          │  Mitsuba 3.8 → CUDA/OptiX    │
│ (firmware ESP32)       │          └──────────────────────────────┘
└────────────────────────┘                      │
                                          RTX 5070 vía /dev/dxg
```

El backend **no puede correr en Windows**: Sionna depende de TensorFlow con CUDA, que no
tiene soporte GPU nativo en Windows desde finales de 2022. El frontend sí es indiferente.

---

## 2. Versiones verificadas

### WSL2 — conda env `sionna` (Python 3.10.20)

| Paquete | Versión |
|---|---|
| `sionna` / `sionna-rt` | 1.2.2 |
| `mitsuba` | 3.8.0 |
| `drjit` | 1.3.1 |
| `tensorflow` | 2.21.0 |
| `torch` | 2.10.0 |
| `smplx` | 0.1.28 |
| `trimesh` | 4.11.4 |
| `fastapi` | 0.135.1 |
| `uvicorn` | 0.42.0 |
| `numpy` | 2.2.6 |
| **`httpx`** | ❌ **AUSENTE** → `tests/test_api.py` no arranca (defecto D-16) |
| **`pytest`** | ❌ **AUSENTE** → la suite de invariantes no se puede ejecutar |

Faltan dos paquetes necesarios para el harness:

```bash
conda activate sionna && pip install pytest httpx
```

### Hardware / driver

| | |
|---|---|
| GPU | NVIDIA GeForce RTX 5070, 12 GB |
| KMD (kernel, Windows) | 610.47 |
| CUDA UMD | 13.3 |
| `nvidia-smi` en WSL | 610.43.02 (vía `/usr/lib/wsl/lib/nvidia-smi`) |
| Passthrough | `/dev/dxg` presente (correcto para WSL2) |
| `/dev/nvidia*` | **ausente** (correcto para WSL2 — ver §5) |

### Windows

| | |
|---|---|
| Node | v24.11.1 |
| `frontend/node_modules` | presente |
| Python de Windows | 3.13.12 — **sin** `fastapi`, `numpy`, `pytest`, `pyserial` |
| ESP-IDF | 5.5.3 en `C:\Espressif` — **roto**, ver §7 |

> El Python de Windows sirve solo para `scripts/verify.py --level mock`. Cualquier cosa que
> toque Sionna, SMPL o el firmware necesita WSL2 o el venv de ESP-IDF.

---

## 3. Las tres variables que habilitan la GPU

```bash
export LD_LIBRARY_PATH=/usr/lib/wsl/lib:$LD_LIBRARY_PATH
export LD_LIBRARY_PATH=/usr/local/cuda-12.6/lib64:$LD_LIBRARY_PATH
export DRJIT_LIBOPTIX_PATH=/usr/lib/wsl/lib/libnvoptix_real.so.1
```

Con ellas aplicadas, el arranque del backend dice:

```
🟢 Mitsuba backend: CUDA + OptiX mono-polarized (GPU)
  PathSolver max_depth=6: 0.687s   ← primera llamada, compila kernels
  segunda pasada:         0.027s   ← régimen estacionario
```

Sin ellas:

```
⚠️  OptiX not available (common in WSL2)
🟡 Mitsuba backend: LLVM mono-polarized (CPU)
  PathSolver max_depth=6: 0.13s por frame, 100 % de todos los núcleos
```

**~5× más lento y con carga térmica sostenida.** Y el fallback es silencioso: el programa
no falla, solo va lento y calienta.

---

## 4. ⚠️ La trampa del `.bashrc` (defecto D-25)

Las tres variables **ya existen** en `~/.bashrc`, líneas 135-137. Pero el `.bashrc` de
Ubuntu empieza así:

```bash
# If not running interactively, don't do anything
case $- in
    *i*) ;;
      *) return;;
esac
```

Las líneas 135-137 están **después** de ese guard. Consecuencia:

| Forma de lanzar | ¿Se aplican las variables? | Resultado |
|---|---|---|
| Terminal WSL interactiva → `python main.py` | ✅ sí | 🟢 GPU |
| `wsl -e bash -lc "python main.py"` | ❌ no | 🟡 CPU |
| Tarea de VS Code, script, cron, CI | ❌ no | 🟡 CPU |
| Un agente de IA ejecutando comandos | ❌ no | 🟡 CPU |

Esto es exactamente por qué existe **`scripts/run_backend.sh`**: exporta las tres
variables explícitamente, sin depender del `.bashrc`. Úsalo siempre.

`WP-00` mueve las variables a `$CONDA_PREFIX/etc/conda/activate.d/`, que sí se ejecuta en
shells no interactivas al activar el entorno, y elimina el problema de raíz.

---

## 5. Cadena de fallo de CUDA / OptiX, por capas

Cuando `env_check.py` reporta CPU, el fallo está en una de estas cinco capas. Diagnostica
en orden — cada una tiene su comando.

### Capa 1 — Passthrough de GPU a WSL2

```bash
ls -la /dev/dxg && nvidia-smi --query-gpu=name,driver_version --format=csv
```

Debe existir `/dev/dxg` y `nvidia-smi` debe listar la GPU. Si no: problema del driver de
Windows o de la configuración de WSL, no del proyecto.

> En WSL2 **no debe** existir `/dev/nvidia0`. Su presencia indica un driver Linux nativo
> instalado, que es un problema (capa 2).

### Capa 2 — `libcuda.so` secuestrado por un driver nativo (defecto D-26)

```bash
ldconfig -p | grep "libcuda\.so"
ls -la /usr/lib/x86_64-linux-gnu/libcuda.so*
```

Estado actual de la máquina:

```
libcuda.so.1 => /usr/lib/wsl/lib/libcuda.so.1              ← el correcto (stub de 188 KB)
libcuda.so.1 => /lib/x86_64-linux-gnu/libcuda.so.1         ← driver NATIVO
libcuda.so   => /lib/x86_64-linux-gnu/libcuda.so           ← ¡solo existe el nativo!
                → libcuda.so.580.173.02  (96 MB, del paquete libnvidia-compute-580)
```

**El mecanismo exacto del fallo**: `libdrjit-core.so` hace
`dlopen("libcuda.so")` — el nombre **sin versionar** (verificado con `strings`). Ese nombre
solo resuelve al driver nativo. El driver nativo busca `/dev/nvidia0`, que no existe en
WSL2, y devuelve:

```
jit_cuda_init(): the CUDA backend is not available because cuInit() failed.
  The specific error message produced by cuInit was
    "no CUDA-capable device is detected"
```

**Por qué PyTorch no se ve afectado**: PyTorch carga `libcuda.so.1` (versionado), que sí
resuelve primero al de WSL. De ahí la paradoja aparente de
`torch.cuda.is_available() == True` mientras Mitsuba falla.

Paquetes nativos instalados hoy (no deberían estar dentro de WSL2):

```
libnvidia-compute-495, -510, -535, -580      ← -580 es el que aporta el libcuda.so
nvidia-kernel-common-580
nvidia-cuda-toolkit 11.5.1                   ← también pone nvcc 11.5 en /usr/bin, tapando
                                               el 12.6 de /usr/local/cuda-12.6/bin
~/NVIDIA-Linux-x86_64-580.142.run            ← 398 MB, instalador de driver nativo
```

`LD_LIBRARY_PATH=/usr/lib/wsl/lib` es un **parche** que fuerza la resolución correcta.
`WP-00b` elimina la causa.

### Capa 3 — OptiX: el stub no exporta el símbolo

```bash
nm -D --defined-only /usr/lib/wsl/lib/libnvoptix.so.1      | grep optixQuery
nm -D --defined-only /usr/lib/wsl/lib/libnvoptix_real.so.1 | grep optixQuery
```

Resultado medido:

```
libnvoptix.so.1       → (vacío)          ← stub de 14 KB, solo símbolos dxcore_*
libnvoptix_real.so.1  → T optixQueryFunctionTable   ← el real, 105 MB
```

El driver moderno de WSL parte OptiX en tres piezas: un *loader* (`libnvoptix.so.1`,
14 KB), la biblioteca real (`libnvoptix_real.so.1`, 105 MB) y `nvoptix.bin` (60 MB).
`drjit` hace `dlopen("libnvoptix.so.1")` y busca `optixQueryFunctionTable`, que el loader
no expone. Síntoma exacto:

```
jit_optix_api_init(): could not find symbol optixQueryFunctionTable
RuntimeError: ... failed to instantiate scene plugin of type "scene": Could not initialize OptiX!
```

Solución: `DRJIT_LIBOPTIX_PATH=/usr/lib/wsl/lib/libnvoptix_real.so.1` apunta a drjit
directamente a la biblioteca real.

### Capa 4 — Orden de import de Mitsuba

Si las capas 1-3 están bien pero la escena falla al cargar, revisa que el variant se fije
**antes** de importar Sionna. Ver §7 de
[`SIONNA_API_CONTRACT.md`](SIONNA_API_CONTRACT.md).

### Capa 5 — Verificación de extremo a extremo

```bash
LD_LIBRARY_PATH=/usr/lib/wsl/lib \
DRJIT_LIBOPTIX_PATH=/usr/lib/wsl/lib/libnvoptix_real.so.1 \
python -c "
import mitsuba as mi
mi.set_variant('cuda_ad_mono_polarized')
mi.load_string('<scene version=\"2.0.0\"></scene>')
print('OptiX OK')"
```

---

## 6. Origen probable del problema

El paso 3 de [`INSTALL_WSL2_GPU.md`](../INSTALL_WSL2_GPU.md) dice:

```bash
sudo apt-get install -y cuda-toolkit
```

y avisa correctamente: *«Do NOT install a regular Linux NVIDIA driver inside WSL2»*. Pero
el metapaquete `cuda-toolkit` puede arrastrar `cuda-drivers` / `libnvidia-compute-*` según
la versión del repositorio, y además en esta máquina también está instalado el
`nvidia-cuda-toolkit` de Ubuntu (que sí depende de `libnvidia-compute`).

`libcuda.so.580.173.02` tiene fecha **29-jun-2026**, mientras las docs dicen «Tested with
Driver 591.59» y el host va hoy por 610.47. Eso encaja con una actualización de sistema en
esa fecha que introdujo el driver nativo y rompió lo que antes funcionaba.

`WP-00b` incluye el comando de limpieza. `WP-06` corrige la instrucción de la guía para que
no vuelva a pasar.

---

## 7. ESP-IDF roto — y por qué NO afecta a Sionna (defecto D-27)

Al abrir PowerShell aparece:

```
Activating ESP-IDF 5.5
* Checking python dependencies ... FAILED
The following Python requirements are not satisfied:
Requirement 'click<8.2,>=7.0' was not met. Installed version: 8.3.2
ERROR: Activation script failed
...
La expresión que sigue a '.' en un elemento de canalización produjo un objeto no válido.
En C:\Espressif\frameworks\esp-idf-v5.5.3\export.ps1: 27 Carácter: 3
+ . $idf_exports
```

**Qué rompe**: `idf.py`. Es decir, compilar y flashear el firmware de `wifi-csi-capture`.
Nada más.

**Qué NO rompe**: Sionna, Mitsuba, el backend, el frontend. Viven en WSL2/bash y no leen
el perfil de PowerShell.

**El perfil no se aborta.** El error de `.` (dot-sourcing) es no terminante: las líneas
posteriores de `Microsoft.PowerShell_profile.ps1` sí se ejecutan (comprobado: los wrappers
`npm`→`pnpm` de las líneas 20-33 funcionan). Así que la hipótesis «Sionna falla por el
error de PowerShell» queda descartada.

**Causa**: el venv de ESP-IDF (`C:\Espressif\python_env\idf5.5_py3.13_env`) tiene
`click 8.3.2`, y esp-idf 5.5.3 exige `click<8.2`.

**Arreglo** (WP-00c, requiere tu intervención):

```powershell
C:\Espressif\install.bat
```

o, más quirúrgico:

```powershell
C:\Espressif\python_env\idf5.5_py3.13_env\Scripts\python.exe -m pip install "click<8.2"
```

---

## 8. Nota sobre `npm` / `npx` en Windows

El perfil de PowerShell del usuario redirige `npm` y `npx` a `pnpm` como defensa de cadena
de suministro:

```
[npm->pnpm] Redirigido por defensa supply-chain
[npx->pnpm dlx] Redirigido por defensa supply-chain
```

Efecto práctico: `npx --no-install vite build` **falla** (`pnpm dlx` no acepta
`--install`). En scripts automatizados invoca el binario local directamente:

```bash
node ./node_modules/vite/bin/vite.js build
```

`scripts/verify.py` ya lo hace así.

---

## 9. Estados conocidos como roto — tabla de referencia rápida

| Síntoma | Causa | Comando de diagnóstico | Arreglo |
|---|---|---|---|
| `🟡 LLVM (CPU)` en vez de `🟢 CUDA + OptiX` | Variables no aplicadas (shell no interactiva) | `echo "[$LD_LIBRARY_PATH]"` → vacío | `scripts/run_backend.sh` · WP-00 |
| `cuInit() failed: no CUDA-capable device` | `libcuda.so` nativo secuestrado | `ldconfig -p \| grep libcuda\.so` | `LD_LIBRARY_PATH=/usr/lib/wsl/lib` · WP-00b |
| `could not find symbol optixQueryFunctionTable` | El `libnvoptix.so.1` de WSL es un stub | `nm -D … \| grep optixQuery` | `DRJIT_LIBOPTIX_PATH=…_real.so.1` |
| `⚠️ Sionna/Mitsuba not installed` → modo mock | Entorno conda no activado | `python -c "import sionna"` | `conda activate sionna` |
| `⚠️ Could not load scene` → modo mock | Falta `scenes/room_simple.xml` | `ls scenes/` | WP-05 |
| `UnicodeEncodeError: 'charmap'` al correr tests | Consola Windows en cp1252 + emojis | — | `PYTHONUTF8=1` o `scripts/verify.py` |
| `RuntimeError: … requires the httpx package` | Falta `httpx` | `pip show httpx` | `pip install httpx` |
| `🚨 Missing SMPL models` | Falta `backend/models/smpl/*.pkl` | `ls backend/models/smpl/` | Descargar de MPI-IS (no se distribuyen) |
| `idf.py` no existe / perfil falla | `click 8.3.2` vs `<8.2` | ver §7 | `C:\Espressif\install.bat` · WP-00c |
| `npx: Unknown option 'install'` | `npx`→`pnpm dlx` del perfil | — | `node ./node_modules/vite/bin/vite.js` |

---

## 10. Comandos de referencia

```bash
# Activar entorno
source ~/miniconda3/etc/profile.d/conda.sh && conda activate sionna

# Diagnóstico completo del entorno
python scripts/env_check.py

# Backend con GPU garantizada
bash scripts/run_backend.sh

# Solo comprobar el backend sin arrancar el servidor
bash scripts/run_backend.sh --check-only

# Verificación por niveles
python scripts/verify.py --level mock      # sirve el Python de Windows
python scripts/verify.py --level sionna    # necesita conda env
python scripts/verify.py --level gpu       # necesita las 3 variables
```

Desde Windows, para lanzar algo en el entorno correcto en una sola línea:

```bash
wsl -e bash -lc "source ~/miniconda3/etc/profile.d/conda.sh && conda activate sionna && cd /mnt/c/Users/jeron/Desktop/MVP-Sionna-Wifi && python scripts/env_check.py"
```
