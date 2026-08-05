# WP-00c — Reparar ESP-IDF

| | |
|---|---|
| **Fase** | F0 · Entorno reproducible |
| **Estado** | `PENDIENTE` |
| **Defectos que cierra** | D-27 |
| **Invariantes que pone en verde** | — |
| **Depende de** | — |
| **Nivel de verificación** | `hardware` |
| **Requiere intervención del usuario** | **sí — modifica `C:\Espressif`, fuera del repo** |

> Este paquete desbloquea **toda la fase F3** (dataset real). Sin `idf.py` no se puede
> compilar ni flashear el firmware, así que no hay datos reales, y sin datos reales no hay
> calibración (F4) ni dataset sintético validado (F5).

## Objetivo

Devolver `idf.py` a un estado funcional. Hoy el venv de ESP-IDF tiene una versión de `click`
incompatible y el script de activación falla, dejando el toolchain inutilizable.

## Contexto

Al abrir PowerShell:

```
Activating ESP-IDF 5.5
Setting IDF_PATH to 'C:\Espressif\frameworks\esp-idf-v5.5.3'.
* Checking python version ... 3.13.12
* Checking python dependencies ... FAILED
error:  Command "...idf_tools.py check-python-dependencies" failed with error code 4294967295
The following Python requirements are not satisfied:
Requirement 'click<8.2,>=7.0' was not met. Installed version: 8.3.2
To install the missing packages, please run "install.bat"

ERROR: Activation script failed
...
La expresión que sigue a '.' en un elemento de canalización produjo un objeto no válido.
En C:\Espressif\frameworks\esp-idf-v5.5.3\export.ps1: 27 Carácter: 3
+ . $idf_exports
```

### Dos aclaraciones importantes

**1. Esto NO afecta a Sionna.** El backend de simulación corre en WSL2/bash y no lee el
perfil de PowerShell. La hipótesis «Sionna falla por el error de PowerShell» está
descartada.

**2. El perfil de PowerShell NO se aborta.** El fallo del dot-sourcing es no terminante: las
líneas posteriores de `Microsoft.PowerShell_profile.ps1` sí se ejecutan — verificado, porque
los wrappers `npm`→`pnpm` de las líneas 20-33 funcionan y emiten su mensaje.

**Causa**: `C:\Espressif\python_env\idf5.5_py3.13_env` tiene `click 8.3.2`; esp-idf 5.5.3
exige `click<8.2`. Alguna instalación posterior (`pip install` de otra herramienta en ese
venv, o una actualización) lo subió.

Contexto completo en [`../agent/ENVIRONMENT.md §7`](../agent/ENVIRONMENT.md).

## Pasos (los ejecuta el usuario)

### Opción A — reinstalación completa (recomendada)

```powershell
C:\Espressif\install.bat
```

Recrea el venv respetando `C:\Espressif\espidf.constraints.v5.5.txt`. Es la vía soportada
por Espressif y arregla también cualquier otra dependencia desalineada. Tarda unos minutos.

### Opción B — quirúrgica

```powershell
C:\Espressif\python_env\idf5.5_py3.13_env\Scripts\python.exe -m pip install "click<8.2"
```

Más rápida, pero solo arregla `click`. Si hay más dependencias fuera de rango, el siguiente
`check-python-dependencies` volverá a fallar por otra razón.

### Verificar

```powershell
. C:\Espressif\frameworks\esp-idf-v5.5.3\export.ps1
idf.py --version
```

### Prevención

Considerar añadir al perfil de PowerShell un guard para que un fallo de ESP-IDF no
contamine cada nueva terminal:

```powershell
if (Test-Path 'C:\Espressif\frameworks\esp-idf-v5.5.3\export.ps1') {
    try   { . 'C:\Espressif\frameworks\esp-idf-v5.5.3\export.ps1' }
    catch { Write-Host "ESP-IDF no disponible (ver WP-00c)" -ForegroundColor DarkYellow }
}
```

O simplemente sacarlo del perfil y activarlo a demanda con una función `idf`. Activar
ESP-IDF en **cada** terminal cuesta ~600 ms y solo se necesita para trabajar con el
firmware.

> Decisión del usuario: el perfil de PowerShell es suyo. Este paquete propone, no impone.

## Criterios de aceptación

```powershell
# 1. Se activa sin errores
. C:\Espressif\frameworks\esp-idf-v5.5.3\export.ps1
# Esperado: "* Checking python dependencies ... OK" y ningún ERROR
```

```powershell
# 2. idf.py responde
idf.py --version
# Esperado: v5.5.3
```

```powershell
# 3. El firmware compila
cd C:\Users\jeron\Desktop\wifi-csi-capture
idf.py set-target esp32s3
idf.py build
# Esperado: "Project build complete" y csi_capture.bin generado
```

```powershell
# 4. Una terminal nueva arranca limpia
# Esperado: ningún bloque rojo al abrir PowerShell
```

- [ ] Los cuatro criterios pasan
- [ ] `ENVIRONMENT.md §7` actualizado con la solución aplicada
- [ ] D-27 marcado `CERRADO`

## Fuera de alcance

- Flashear los nodos y capturar datos → `WP-09` / `WP-10`.
- Los defectos del firmware (D-23, D-28…D-33) → `WP-09`.
- Cualquier cambio en el repositorio salvo la actualización de `ENVIRONMENT.md`.

## Riesgos y trampas

| Riesgo | Mitigación |
|---|---|
| `install.bat` tarda y descarga toolchains | Normal. Necesita red y varios GB de disco |
| Python 3.13 en el venv puede estar fuera de la matriz soportada por esp-idf 5.5 | Si `install.bat` protesta por la versión de Python, recrear el venv con 3.11 usando `install.bat` tras ajustar `IDF_PYTHON` |
| Otra herramienta vuelve a subir `click` en ese venv | No instalar nada ajeno en `idf5.5_py3.13_env`. Usar un venv aparte para scripts propios |
| `set-target esp32s3` regenera `sdkconfig` | `sdkconfig` está gitignorado y `sdkconfig.defaults` aporta los valores correctos. Reconfigurar SSID/password/MAC con `idf.py menuconfig` tras regenerarlo |
