# How It Works: MVP-Sionna-WiFi

This document details the inner workings of the MVP-Sionna-WiFi digital twin simulation. It is a simplified architectural overview of the systems driving the WiFi simulation and real-time 3D visualization.

## 1. Project Architecture
The project is split into a **Python Backend (FastAPI + Sionna)** and a **JavaScript Frontend (Vite + Three.js)**. 
They communicate in real-time using WebSockets, allowing the 3D visualization to subscribe to the heavy ray tracing calculations done by the backend.

### The Backend (FastAPI + Sionna)
The backend is responsible for physics simulation. It creates a digital replica of the physical environment and uses **NVIDIA Sionna** to fire thousands of electromagnetic rays and calculate how they bounce, refract, and diffract around the room.

- **`config.py`**: The single source of truth for the physical setup (room dimensions, sensor positions, antenna types).
- **`scene_loader.py`**: Translates `config.py` into a Sionna-compatible 3D scene. It places the walls, the Router (Tx), and the 8 ESP32 receivers (Rx).
  - *Crucial Detail*: The sensors are placed **outside** the room walls. The backend explicitly enables **refraction** in Sionna so rays can penetrate the walls and reach the sensors.
  - *Material Thickness*: All radio materials (brick, concrete, wood, etc.) have their `thickness` set programmatically from `config.py`, ensuring realistic signal attenuation through walls.
  - *Antenna Pattern*: A 1x1 `PlanarArray` with a `dipole` pattern is used, mimicking the real-world vertical polarization antennas.
- **`simulation.py`**: Executes the mathematical calculations (Shooting and Bouncing Rays). It computes paths, Channel Impulse Response (CIR), and the full 114-subcarrier Channel State Information (CSI).
- **`main.py`**: The FastAPI server exposes `/api/scene`, `/api/simulate`, `/api/coverage` and `/ws/simulation`.

### The Frontend (Vite + Three.js)
The frontend is responsible for rendering the calculated data into an interactive, visually stunning interface.

- **`scene3d.js`**: Recreates the room boundaries using Three.js lines and handles the camera orbit.
- **`sensors.js`**: Draws the Transmitters (Orange) and Receivers (Purple).
- **`rays.js`**: Visualizes the paths from the router to the ESP32s calculated by Sionna. It color-codes the rays based on their bounces.
- **`heatmap.js`**: Renders a **volumetric 3D heatmap** by stacking 10 semi-transparent planes at different heights (0.1m to 1.9m). Each layer maps signal strength using a Jet colormap. The heatmap extends 0.5m beyond the room walls to visualize signal penetration. A badge indicator shows whether the data comes from Sionna RT or mock calculations.
- **`csi_panel.js`**: **The Spectrogram Monitor**. It replicates tools like `wifi-csi-capture`. When an ESP32 is selected, it displays 4 real-time Canvas charts:
  - Subcarrier Amplitude (114 bars)
  - Subcarrier Phase (Unwrapped radians)
  - Amplitude Spectrogram (Historical waterfall heatmap)
  - RSSI trajectory

## 2. Why WSL2 & Ubuntu?
Wait, why doesn't this run natively on Windows?
NVIDIA Sionna relies heavily on **TensorFlow** to parallelize ray tracing on the GPU. As of late 2022, TensorFlow removed native GPU support for Windows. To leverage the RTX 5070 for real-time ray tracing, the backend **must** run inside a Linux environment with CUDA support. 
**WSL2 (Windows Subsystem for Linux)** is the recommended approach to seamlessly bridge the Windows frontend with a Linux/NVIDIA-accelerated backend.

## 3. The CSI Spectrogram Feature
The frontend features a real-time CSI panel that automatically pops up when an ESP32 receiver is clicked in the right sidebar. 
Because Sionna computes a "static" snapshot of the room per simulation, the frontend injects micro-turbulence (Gaussian noise) into the static CSI data. This "fakes" the dynamic nature of an empty room over time, causing the Spectrogram and Phase charts to scroll and animate just like they would during a live physical capture.

## 4. Performance: GPU vs CPU Mode

The project features an automatic backend fallback chain depending on your hardware:

1. **CUDA + OptiX (GPU)**: `~0.02s` per frame. Requires NVIDIA GPU and OptiX configuration in WSL2.
2. **LLVM (CPU)**: `~0.15s` per frame. Automatic fallback if OptiX fails. Uses 100% CPU.
3. **Mock Mode**: Instant. Synthetic data when dependencies are missing.

Sionna RT is designed for **NVIDIA GPUs with CUDA**. In your WSL2 terminal, check the startup logs:
```
🟢 Mitsuba backend: CUDA + OptiX mono-polarized (GPU)
```
If you see `🟡 Mitsuba backend: LLVM mono-polarized (CPU)` instead, Sionna is running in **CPU fallback mode**. It still produces correct results but:
- Each frame takes **~0.15–0.5s** instead of ~0.02s
- **CPU usage hits 100%** across all cores
- **System temperature may rise significantly** — monitor with `sensors` (Linux) or HWMonitor (Windows)

> **Tip**: Reduce `Max Reflections` (3–4) and `Ray Density` in the UI to lower CPU load.

## 5. Setup

See the [README](../README.md) for full installation instructions. Key steps:
1. WSL2 Ubuntu + Miniconda with Python 3.10–3.11
2. `pip install sionna tensorflow` inside the conda environment
3. Start backend: `python main.py` / Frontend: `npm run dev`

## 6. Roadmap: SMPL Human Body Integration
The next major evolution is introducing a parametric human body (SMPL-X model) into the scene:
- **Phase A**: Static human mesh injected into Sionna's scene, observable signal attenuation behind the body.
- **Phase B**: Animated walking trajectory that dynamically modifies CSI patterns in real-time, demonstrating WiFi-based human activity recognition capabilities.
