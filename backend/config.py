"""
MVP-Sionna-WiFi: Physical Configuration Parameters
All dimensions, positions, and RF parameters for the simulation.
"""

# =============================================================================
# Room Geometry
# =============================================================================
ROOM_WIDTH = 2.0      # X-axis (meters)
ROOM_DEPTH = 3.5      # Y-axis (meters)
ROOM_HEIGHT = 2.0     # Z-axis (meters)
WALL_THICKNESS = 0.12  # meters (12 cm concrete)

# =============================================================================
# WiFi / RF Parameters
# =============================================================================
WIFI_FREQUENCY = 2.437e9    # Hz — Channel 6 (2.4 GHz band)
WIFI_BANDWIDTH = 40e6       # Hz — HT40 (802.11n)
NUM_SUBCARRIERS = 114       # OFDM subcarriers (HT40)
NUM_DATA_SUBCARRIERS = 108  # Data subcarriers (excluding pilots/null)

# =============================================================================
# Transmitter (Router / Illuminator)
# =============================================================================
TRANSMITTER = {
    "name": "Router",
    "position": [1.0, 3.62, 1.0],  # Centrado en X=1.0, y Z=1.0, por fuera de la pared trasera (Y=3.5+0.12)
    "orientation": [0, 0, 0]     # Orientación estándar
}

# =============================================================================
# Receivers (8x ESP32-S3 in volumetric cage)
# =============================================================================
# Layout: 4 high corners (Z=1.8m) + 4 low corners (Z=0.15m)
# Creates 8 Tx→Rx links for cross-# Receivers (8x ESP32-S3) - FUERA de las paredes de 3.5m x 2m (X < 0 y X > 2.0)
RECEIVERS = {
    # Esquinas Superiores - Z = 1.9m
    "ESP32_1": {"position": [-0.12, 0.1, 1.9], "label": "Front-Left High (Outside)"},
    "ESP32_2": {"position": [ 2.12, 0.1, 1.9], "label": "Front-Right High (Outside)"},
    "ESP32_3": {"position": [-0.12, 3.4, 1.9], "label": "Back-Left High (Outside)"},
    "ESP32_4": {"position": [ 2.12, 3.4, 1.9], "label": "Back-Right High (Outside)"},
    
    # Esquinas Inferiores - Z = 0.1m
    "ESP32_5": {"position": [-0.12, 0.1, 0.1], "label": "Front-Left Low (Outside)"},
    "ESP32_6": {"position": [ 2.12, 0.1, 0.1], "label": "Front-Right Low (Outside)"},
    "ESP32_7": {"position": [-0.12, 3.4, 0.1], "label": "Back-Left Low (Outside)"},
    "ESP32_8": {"position": [ 2.12, 3.4, 0.1], "label": "Back-Right Low (Outside)"},
}

# Antena base (omnidireccional dipole, polarización vertical)
ANTENNA_PATTERN = "dipole"  # Isotropic (omnidirectional)
# Each ESP32-S3 uses 1 antenna — the multi-static array compensates

# =============================================================================
# Ray Tracing Parameters (Sionna SBR)
# =============================================================================
RT_MAX_DEPTH = 6          # Máximo número de rebotes (depth) exigente para capturar multipath
RT_NUM_SAMPLES = 20000  # Precisión moderada para tiempo real
RT_DIFFRACTION = True     # Difracción en los bordes habilitada
RT_SCATTERING = False     # Scattering apagado para conservar performance
RT_REFRACTION = True   # Refracción habilitada (para penetrar las paredes)
RT_SPECULAR = True     # Reflexión especular habilitada

# =============================================================================
# Materials (ITU-R P.2040)
# =============================================================================
MATERIALS = {
    "walls": "itu_brick",
    "floor": "itu_concrete",
    "ceiling": "itu_concrete",
}

# =============================================================================
# Visualization
# =============================================================================
COVERAGE_GRID_RESOLUTION = 0.05  # meters (5 cm grid for coverage map)
COVERAGE_HEIGHT = 1.0           # Default height for 2D coverage slice

# =============================================================================
# Server
# =============================================================================
API_HOST = "0.0.0.0"
API_PORT = 8000
