# Sionna RT + OptiX GPU Setup on Windows (WSL2)

Complete guide to set up **Sionna RT** with **NVIDIA OptiX GPU ray tracing** on Windows using WSL2.

> **Tested with**: RTX 5070 (Blackwell), Windows 11, WSL2 Ubuntu 22.04, CUDA 13.1, Driver 591.59

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [WSL2 Setup](#2-wsl2-setup)
3. [CUDA Toolkit in WSL2](#3-cuda-toolkit-in-wsl2)
4. [Conda Environment](#4-conda-environment)
5. [Install Sionna & Dependencies](#5-install-sionna--dependencies)
6. [Enable OptiX in WSL2](#6-enable-optix-in-wsl2-gpu-acceleration)
7. [Run the Backend](#7-run-the-backend)
8. [Verify GPU Usage](#8-verify-gpu-usage)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Prerequisites

### On Windows

- **Windows 11** (or Windows 10 build 19041+)
- **NVIDIA GPU** with ray tracing support (RTX 20xx or newer)
- **Latest NVIDIA Windows driver** — download from [nvidia.com/drivers](https://www.nvidia.com/download/index.aspx)
- **WSL2 enabled** — see [Microsoft docs](https://learn.microsoft.com/en-us/windows/wsl/install)

### Verify your GPU

Open PowerShell and run:

```powershell
nvidia-smi
```

Note your **Driver Version** (e.g. `591.59`) and **CUDA Version** (e.g. `13.1`).

---

## 2. WSL2 Setup

### Install Ubuntu

```powershell
wsl --install -d Ubuntu-22.04
```

### Verify WSL2 is running

```powershell
wsl -l -v
```

You should see `Ubuntu-22.04` with `VERSION 2`.

### Verify GPU is visible from WSL

```bash
nvidia-smi
```

You should see your GPU listed. If not, update your Windows NVIDIA driver.

---

## 3. CUDA Toolkit in WSL2

> **Important**: Do NOT install a regular Linux NVIDIA driver inside WSL2. WSL2 uses the Windows driver. Only install the CUDA toolkit.

```bash
# Add NVIDIA package repository (WSL-Ubuntu specific)
wget https://developer.download.nvidia.com/compute/cuda/repos/wsl-ubuntu/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt-get update

# Install CUDA toolkit (without the driver)
sudo apt-get install -y cuda-toolkit
```

### Verify CUDA

```bash
nvcc --version
```

---

## 4. Conda Environment

### Install Miniconda (if not already installed)

```bash
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh
# Follow the prompts, then restart your shell
```

### Create the Sionna environment

```bash
conda create -n sionna python=3.11 -y
conda activate sionna
```

---

## 5. Install Sionna & Dependencies

```bash
pip install sionna-rt
pip install tensorflow[and-cuda]
pip install fastapi uvicorn websockets numpy
```

### Verify Sionna is installed

```bash
python -c "import sionna; print('Sionna version:', sionna.__version__)"
python -c "import mitsuba; print('Mitsuba version:', mitsuba.__version__)"
```

### Verify TensorFlow sees the GPU

```bash
python -c "import tensorflow as tf; print('GPUs:', tf.config.list_physical_devices('GPU'))"
```

You should see at least one GPU device listed.

---

## 6. Enable OptiX in WSL2 (GPU Acceleration)

> **Why is this needed?** OptiX is not officially supported in WSL2. The WSL driver ships a tiny stub `libnvoptix.so.1` (~10KB) instead of the real library (~100MB). We need to extract the real library from a Linux NVIDIA driver and make it available to WSL2.

### Step 6.1 — Download a compatible Linux driver

1. Go to [nvidia.com/drivers](https://www.nvidia.com/download/index.aspx)
2. Select:
   - **Product**: Your GPU (e.g. GeForce RTX 5070)
   - **Operating System**: **Linux 64-bit**
   - **Download Type**: Recommended/Certified
3. Download the latest `.run` file

### Step 6.2 — Extract the driver in WSL2 (do NOT install it)

```bash
# Copy the downloaded file to WSL
cp /mnt/c/Users/<YOUR_USERNAME>/Downloads/NVIDIA-Linux-x86_64-*.run ~/

# Extract without installing
cd ~
bash NVIDIA-Linux-x86_64-*.run -x --target driver

# Verify the OptiX libraries were extracted
ls driver/libnvoptix.so.* driver/nvoptix.bin
```

You should see files like `libnvoptix.so.580.142` and `nvoptix.bin`.

### Step 6.3 — Copy libraries to a Windows-accessible path

From **inside WSL**, copy the files to your Windows Desktop (or any shared location):

```bash
cp ~/driver/libnvoptix.so.* /mnt/c/Users/<YOUR_USERNAME>/Desktop/
cp ~/driver/libnvidia-ptxjitcompiler.so.* /mnt/c/Users/<YOUR_USERNAME>/Desktop/
cp ~/driver/libnvidia-rtcore.so.* /mnt/c/Users/<YOUR_USERNAME>/Desktop/
cp ~/driver/libnvidia-gpucomp.so.* /mnt/c/Users/<YOUR_USERNAME>/Desktop/
cp ~/driver/nvoptix.bin /mnt/c/Users/<YOUR_USERNAME>/Desktop/
```

### Step 6.4 — Copy to WSL system directory from Windows

> **Note**: The original `libnvoptix.so.1` in `lxss\lib` is protected by TrustedInstaller and cannot be overwritten, even as admin. We use a different filename and point DrJit to it.

Open **PowerShell as Administrator** on Windows:

```powershell
Copy-Item "C:\Users\<YOUR_USERNAME>\Desktop\libnvoptix.so.*" "C:\Windows\System32\lxss\lib\libnvoptix_real.so.1" -Force
Copy-Item "C:\Users\<YOUR_USERNAME>\Desktop\libnvidia-ptxjitcompiler.so.*" "C:\Windows\System32\lxss\lib\libnvidia-ptxjitcompiler.so.1" -Force
Copy-Item "C:\Users\<YOUR_USERNAME>\Desktop\libnvidia-rtcore.so.*" "C:\Windows\System32\lxss\lib\" -Force
Copy-Item "C:\Users\<YOUR_USERNAME>\Desktop\libnvidia-gpucomp.so.*" "C:\Windows\System32\lxss\lib\" -Force
Copy-Item "C:\Users\<YOUR_USERNAME>\Desktop\nvoptix.bin" "C:\Windows\System32\lxss\lib\" -Force
```

### Step 6.5 — Configure the environment variable

Tell DrJit where to find the real OptiX library. In WSL, run:

```bash
echo 'export DRJIT_LIBOPTIX_PATH=/usr/lib/wsl/lib/libnvoptix_real.so.1' >> ~/.bashrc
source ~/.bashrc
```

### Step 6.6 — Restart WSL

From **PowerShell** on Windows:

```powershell
wsl --shutdown
```

Then open WSL again. The env variable will be set automatically.

---

## 7. Run the Backend

```bash
cd /mnt/c/Users/<YOUR_USERNAME>/Desktop/MVP-Sionna-Wifi/backend
conda activate sionna
python main.py
```

### Expected output (GPU mode)

```
🟢 Mitsuba backend: CUDA + OptiX mono-polarized (GPU)
...
✅ Scene loaded: .../scenes/room_simple.xml
   Backend: CUDA+OptiX (GPU)
   Frequency: 2.437 GHz
   Objects: 6
...
⏱️  Simulation completed in 0.02s
```

---

## 8. Verify GPU Usage

### Check simulation times

| Backend | First Run | Subsequent Runs |
|---------|-----------|-----------------|
| Mock (no Sionna) | instant | instant |
| LLVM (CPU) | ~0.25s | ~0.14s |
| **CUDA+OptiX (GPU)** | **~0.4s** | **~0.02s** ⚡ |

### Check the API response

```bash
curl http://localhost:8000/api/scene | python -m json.tool
```

Look for `"backend": "cuda_optix"` in the response.

### Monitor GPU utilization

In a separate terminal:

```bash
watch -n 1 nvidia-smi
```

You should see GPU memory usage increase during simulation.

---

## 9. Troubleshooting

### `optixQueryFunctionTable not found`

OptiX libraries are not properly installed. Follow [Step 6](#6-enable-optix-in-wsl2-gpu-acceleration) again.

### `LLVM mono-polarized (CPU)` instead of GPU

The `DRJIT_LIBOPTIX_PATH` env variable is not set. Verify:

```bash
echo $DRJIT_LIBOPTIX_PATH
# Should print: /usr/lib/wsl/lib/libnvoptix_real.so.1
```

If empty, re-run Step 6.5.

### `Sionna/Mitsuba not installed`

Your conda environment is not activated:

```bash
conda activate sionna
```

### `dr.while_loop() encountered an exception`

This is a known DrJit bug with the `rgb` Mitsuba variants. The project automatically uses `mono_polarized` variant to avoid this. If you see this error, ensure you're running the latest version of `scene_loader.py`.

### Simulation falls back to mock

Check the full traceback in the terminal logs. Common causes:
- Scene XML file not found — verify `scenes/room_simple.xml` exists
- Memory issue — reduce `max_depth` or `num_samples` in the frontend

### Permission denied when copying to `lxss\lib`

The stub `libnvoptix.so.1` is owned by TrustedInstaller. Use a different filename (e.g. `libnvoptix_real.so.1`) and set `DRJIT_LIBOPTIX_PATH` to point to it.

---

## Architecture Notes

### Why `mono_polarized` variant?

Sionna RT uses Mitsuba 3 for ray tracing. Mitsuba offers several rendering variants:

- `cuda_ad_rgb` — GPU, full color (3-channel) — **has a known DrJit bug with PathSolver**
- `cuda_ad_mono_polarized` — GPU, mono with polarization — **stable, used by this project**
- `llvm_ad_mono_polarized` — CPU fallback — **stable but slower**

The project automatically selects the best available variant at startup.

### Automatic fallback chain

```
1. Try CUDA + OptiX (GPU)     → cuda_ad_mono_polarized
2. Fall back to LLVM (CPU)    → llvm_ad_mono_polarized
3. Fall back to mock mode     → synthetic data for frontend dev
```

This ensures the backend always starts, regardless of GPU availability.

---

## 10. SMPL Human Integration (Optional)

If you want to visualize how the human body (blockage/diffraction) affects the WiFi signal, you need to install the **SMPL** neural network models.
*Due to Max Planck Institute (MPI-IS) licensing restrictions, these mathematical files (.pkl) are not included in the repository.*

### Step 1: Python Dependencies
Make sure you are in WSL2 and have the conda environment activated (`conda activate sionna`).
```bash
pip install smplx torch trimesh

# Chumpy is required by smplx but has an outdated setup.py that breaks with modern pip.
# You must install it using the --no-build-isolation flag:
pip install --no-build-isolation chumpy
```

### Step 2: Download the Original SMPL Model
1. Go to the official SMPL website: [https://smpl.is.tue.mpg.de/](https://smpl.is.tue.mpg.de/)
2. Register (create an account) and log in.
3. Go to **Downloads**.
4. Download the basic model (usually a ZIP file containing `.pkl` files).
5. Extract the ZIP file.

### Step 3: Place and Rename Files
At the root of this project, create the following directory structure:
```bash
mkdir -p backend/models/smpl
```

Copy the two extracted files (`basicmodel_m_lbs_10_207_0_v1.0.0.pkl` and `basicModel_f_lbs_10_207_0_v1.0.0.pkl`) into that folder.

**IMPORTANT**: The `smplx` library (used in the backend) expects a neutral file if no gender is specified. You must rename one of them or use the neutral version if provided. The easiest way is to rename the female or male average file like this:
```bash
cd backend/models/smpl
cp basicModel_f_lbs_10_207_0_v1.0.0.pkl SMPL_NEUTRAL.pkl
```

Upon restarting the FastAPI server and running a simulation, the web interface will allow you to insert or animate humans.
