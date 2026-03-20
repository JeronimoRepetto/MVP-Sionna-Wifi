# MVP-Sionna-WiFi

> Simplified WiFi propagation simulation using NVIDIA Sionna RT, Mitsuba 3, and Blender.

A virtual test room with **8 ESP32-S3 receivers** and **1 WiFi router** — built as a learning project to explore ray-tracing-based RF simulation before tackling the full [WiFi Vision 3D](https://github.com/JeronimoRepetto/wifi-csi-capture) research pipeline.

![Status](https://img.shields.io/badge/status-in_development-yellow)
![Sionna](https://img.shields.io/badge/Sionna_RT-v1.0+-76B900?logo=nvidia)
![Blender](https://img.shields.io/badge/Blender-3.6%2B-E8751A?logo=blender)
![Three.js](https://img.shields.io/badge/Three.js-r160+-black?logo=three.js)

## Overview

This project creates a **100% virtual** simulation environment:

1. **Blender** → Model a concrete room with ITU-standard materials
2. **Mitsuba 3** → Export scene geometry as XML
3. **Sionna RT** → Run differentiable ray tracing (SBR algorithm) at 2.437 GHz
4. **Three.js** → Visualize the room, sensors, ray paths, and signal coverage in real time

No physical hardware required. No SMPL body model (yet).

## Room Configuration

| Parameter | Value |
|-----------|-------|
| Room dimensions | 2.0 × 3.5 × 2.0 m |
| Wall thickness | 0.12 m (concrete) |
| Wall material | `itu_concrete` (ITU-R P.2040) |
| WiFi frequency | 2.437 GHz (Channel 6) |
| Bandwidth | 40 MHz (HT40, 802.11n) |
| Subcarriers | 114 (108 data) |
| Transmitter | 1 × Router (center back wall, Z=1.8m) |
| Receivers | 8 × ESP32-S3 (4 high + 4 low corners) |

### Sensor Layout

```
        2.0 m
   ┌─────────────┐
   │ ESP1    ESP2 │  ← Z = 1.8m (high)
   │              │
   │              │  3.5 m
   │              │
   │ ESP3  R ESP4 │  ← R = Router
   └─────────────┘

   + mirrored at Z = 0.15m (ESP5–ESP8)
```

## Architecture

```
Blender Script ──XML──► Mitsuba 3 ──► Sionna RT ──► FastAPI ──WS──► Three.js
(generate_room.py)      (parser)      (ray trace)    (backend)       (frontend)
```

## Project Structure

```
MVP-Sionna-Wifi/
├── blender/
│   ├── generate_room.py      # Procedural room generation (run in Blender)
│   └── export_scene.py       # Export to Mitsuba XML
├── scenes/                   # Exported XML scenes
├── backend/
│   ├── config.py             # Physical parameters & sensor positions
│   ├── scene_loader.py       # Load XML into Sionna RT
│   ├── simulation.py         # Ray tracing engine (SBR)
│   ├── main.py               # FastAPI server
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── main.js           # Entry point
│   │   ├── scene3d.js        # Three.js room renderer
│   │   ├── rays.js           # Ray path visualization
│   │   ├── sensors.js        # Tx/Rx markers
│   │   ├── heatmap.js        # Coverage overlay
│   │   ├── controls.js       # UI panel
│   │   └── websocket.js      # WS client
│   ├── index.html
│   ├── style.css
│   └── package.json
└── README.md
```

## Requirements

- **Python** 3.9+
- **NVIDIA GPU** with CUDA (tested on RTX 5070, 12GB VRAM)
- **Blender** 3.6+ (for room modeling)
- **Node.js** 18+ (for frontend)

### Python Dependencies

```
sionna>=1.0
mitsuba>=3.0
tensorflow>=2.12
numpy
fastapi
uvicorn
websockets
```

## Setup & Installation (Windows / WSL2)

NVIDIA Sionna requires a Linux environment to utilize hardware GPU acceleration via TensorFlow. On Windows, you MUST use WSL2 (Ubuntu).

### 1. Prepare WSL2 (Ubuntu) Environment
First, ensure you have an Ubuntu distribution installed in WSL2:
```bash
wsl --install -d Ubuntu-22.04
```
*Note: After installing, open the "Ubuntu 22.04" app from your Windows Start Menu to set up your UNIX username and password.*

### 2. Install Python 3.10 and Sionna in WSL2
Sionna is officially supported on Python 3.10. Open your **Ubuntu terminal** and run:
```bash
# Install Miniconda
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh -b
~/miniconda3/bin/conda init bash
source ~/.bashrc

# Accept Conda Terms of Service
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r

# Create Python environment
conda create -n sionna python=3.10 -y
conda activate sionna

# Install CUDA toolkit (if not already installed via Windows drivers)
sudo apt update
sudo apt install -y nvidia-cuda-toolkit
```

### 3. Install Backend Dependencies
Navigate to your project folder from *inside* the Ubuntu terminal (e.g., `/mnt/c/Users/YourUser/Desktop/MVP-Sionna-Wifi`):
```bash
cd /mnt/c/Users/jeron/Desktop/MVP-Sionna-Wifi/backend
pip install -r requirements.txt
pip install sionna tensorflow
```

### 4. Running the Project

**Start Backend (from Ubuntu WSL Terminal)**
```bash
conda activate sionna
cd /mnt/c/Users/jeron/Desktop/MVP-Sionna-Wifi/backend
python main.py
```
*(If you see `🟢 Sionna RT: Active` in the web UI, it is using your GPU!)*

**Start Frontend (from Windows PowerShell)**
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

## Roadmap

| Version | Description |
|:-------:|-------------|
| **v0.1** | ← Current: Room + Sionna RT + Visualization |
| v0.2 | Add SMPL body model as obstacle |
| v0.3 | Animated human movement + dynamic CSI |
| v0.4 | Compare simulated vs real CSI (ESP32) |
| v0.5 | Full pose estimation pipeline integration |

## Related Projects

- [WiFi Vision 3D (wifi-csi-capture)](https://github.com/JeronimoRepetto/wifi-csi-capture) — The main research project
- [NVIDIA Sionna](https://github.com/NVlabs/sionna) — Open-source library for communication systems
- [Mitsuba-Blender](https://github.com/mitsuba-renderer/mitsuba-blender) — Blender integration for Mitsuba 3

## License

MIT
