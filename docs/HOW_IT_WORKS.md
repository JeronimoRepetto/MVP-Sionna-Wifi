# How It Works: MVP-Sionna-WiFi

This document details the inner workings of the MVP-Sionna-WiFi digital twin simulation. It is a simplified architectural overview of the systems driving the WiFi simulation and real-time 3D visualization.

## 1. Project Architecture
The project is split into a **Python Backend (FastAPI + Sionna)** and a **JavaScript Frontend (Vite + Three.js)**. 
They communicate in real-time using WebSockets, allowing the 3D visualization to subscribe to the heavy ray tracing calculations done by the backend.

### The Backend (FastAPI + Sionna)
The backend is responsible for physics simulation. It creates a digital replica of the physical environment and uses **NVIDIA Sionna** to fire thousands of electromagnetic rays and calculate how they bounce, refract, and diffract around the room.

- **`config.py`**: The single source of truth for the physical setup (room dimensions, sensor positions, antenna types).
- **`scene_loader.py`**: Translates `config.py` into a Sionna-compatible 3D scene. It places the walls (Concrete), the Router (Tx), and the 8 ESP32 receivers (Rx).
  - *Crucial Detail*: The sensors are placed **outside** the concrete room walls. The backend explicitly enables **refraction** in Sionna so rays can penetrate the 12cm walls and reach the sensors.
  - *Antenna Pattern*: A 1x1 `PlanarArray` with a `dipole` pattern is used, mimicking the real-world vertical polarization antennas.
- **`simulation.py`**: Executes the mathematical calculations (Shooting and Bouncing Rays). It computes paths, Channel Impulse Response (CIR), and the full 114-subcarrier Channel State Information (CSI).
- **`main.py`**: The FastAPI server exposes `/api/simulate` and `/ws`.

### The Frontend (Vite + Three.js)
The frontend is responsible for rendering the calculated data into an interactive, visually stunning interface.

- **`scene3d.js`**: Recreates the room boundaries using Three.js lines and handles the camera orbit.
- **`sensors.js`**: Draws the Transmitters (Orange) and Receivers (Purple).
- **`rays.js`**: Visualizes the paths from the router to the ESP32s calculated by Sionna. It color-codes the rays based on their bounces.
- **`heatmap.js`**: Renders the 2D signal strength coverage map across the room floor.
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

## 4. Next Steps
To run this project with full Sionna capabilities:
1. Ensure Docker Desktop or a default Ubuntu WSL2 distro is installed and configured (`wsl --set-default Ubuntu`).
2. Run `pip install tensorflow==2.15.0 nvidia-sionna` inside the WSL environment.
3. Start the backend with `python main.py` and the frontend with `npm run dev`.
