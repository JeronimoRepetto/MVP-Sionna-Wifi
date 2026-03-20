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
    "name": "Router_Tx",
    "position": [1.0, 3.4, 1.8],  # Center of back wall, high
    "orientation": [0.0, 0.0, 0.0],  # Pointing into the room
}

# =============================================================================
# Receivers (8x ESP32-S3 in volumetric cage)
# =============================================================================
# Layout: 4 high corners (Z=1.8m) + 4 low corners (Z=0.15m)
# Creates 8 Tx→Rx links for cross-coverage
RECEIVERS = {
    # --- High level (near ceiling) ---
    "ESP32_1": {
        "position": [0.1, 0.1, 1.8],
        "label": "Front-Left High",
    },
    "ESP32_2": {
        "position": [1.9, 0.1, 1.8],
        "label": "Front-Right High",
    },
    "ESP32_3": {
        "position": [0.1, 3.4, 1.8],
        "label": "Back-Left High",
    },
    "ESP32_4": {
        "position": [1.9, 3.4, 1.8],
        "label": "Back-Right High",
    },
    # --- Low level (near floor) ---
    "ESP32_5": {
        "position": [0.1, 0.1, 0.15],
        "label": "Front-Left Low",
    },
    "ESP32_6": {
        "position": [1.9, 0.1, 0.15],
        "label": "Front-Right Low",
    },
    "ESP32_7": {
        "position": [0.1, 3.4, 0.15],
        "label": "Back-Left Low",
    },
    "ESP32_8": {
        "position": [1.9, 3.4, 0.15],
        "label": "Back-Right Low",
    },
}

# =============================================================================
# Antenna Configuration
# =============================================================================
ANTENNA_PATTERN = "iso"  # Isotropic (omnidirectional)
# Each ESP32-S3 uses 1 antenna — the multi-static array compensates

# =============================================================================
# Ray Tracing Parameters (Sionna SBR)
# =============================================================================
RT_MAX_DEPTH = 6          # Max number of reflections
RT_NUM_SAMPLES = 1_000_000  # Number of rays to shoot
RT_DIFFRACTION = True     # Enable edge diffraction
RT_SCATTERING = False     # Disable scattering for simplicity

# =============================================================================
# Materials (ITU-R P.2040)
# =============================================================================
MATERIALS = {
    "walls": "itu_concrete",
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
