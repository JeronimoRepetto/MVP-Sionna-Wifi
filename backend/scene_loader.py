"""
MVP-Sionna-WiFi: Scene Loader
Loads the Mitsuba XML scene into Sionna RT and configures
transmitters, receivers, antennas, and material properties.
"""

import os
import numpy as np

try:
    import sionna
    from sionna import rt
    HAS_SIONNA = True
except ImportError:
    HAS_SIONNA = False
    print("⚠️  Sionna not installed. Running in mock mode for development.")

from config import (
    WIFI_FREQUENCY, TRANSMITTER, RECEIVERS, ANTENNA_PATTERN,
    WALL_THICKNESS, MATERIALS
)

# Path to the exported XML scene
SCENE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'scenes', 'room_simple.xml'
)


def load_scene(scene_path=None):
    """
    Load the Mitsuba XML scene into Sionna RT.
    
    Args:
        scene_path: Path to .xml file. Defaults to scenes/room_simple.xml
        
    Returns:
        scene: Sionna RT Scene object (or mock dict if Sionna not available)
    """
    if scene_path is None:
        scene_path = SCENE_PATH
    
    if not HAS_SIONNA:
        return _create_mock_scene()
    
    # Load scene with merge_shapes=False to keep individual wall meshes
    scene = rt.load_scene(scene_path, merge_shapes=False)
    
    # Set operating frequency
    scene.frequency = WIFI_FREQUENCY
    
    # Configure material thicknesses
    _configure_materials(scene)
    
    # Add transmitter and receivers
    _add_transmitter(scene)
    _add_receivers(scene)
    
    print(f"✅ Scene loaded: {scene_path}")
    print(f"   Frequency: {WIFI_FREQUENCY / 1e9:.3f} GHz")
    print(f"   Objects: {len(scene.objects)}")
    print(f"   Tx: {TRANSMITTER['name']} at {TRANSMITTER['position']}")
    print(f"   Rx: {len(RECEIVERS)} receivers")
    
    return scene


def _configure_materials(scene):
    """Set physical thickness for concrete walls."""
    for obj_name, obj in scene.objects.items():
        # All surfaces in our simple room are concrete
        for mat_name, mat in obj.radio_materials.items():
            if "concrete" in mat_name.lower():
                mat.thickness = WALL_THICKNESS
                print(f"   Material '{mat_name}' on '{obj_name}': "
                      f"thickness={WALL_THICKNESS}m")


def _add_transmitter(scene):
    """Add the WiFi router as a transmitter with isotropic antenna."""
    tx_pos = TRANSMITTER["position"]
    tx_orient = TRANSMITTER.get("orientation", [0, 0, 0])
    
    # Create antenna
    if ANTENNA_PATTERN == "iso":
        antenna = rt.Antenna("iso", "V")  # Isotropic, vertical polarization
    else:
        antenna = rt.Antenna("iso", "V")
    
    # Create antenna array (single antenna)
    tx_array = rt.AntennaArray(antenna, positions=[[0, 0, 0]])
    
    # Add transmitter to scene
    tx = rt.Transmitter(
        name=TRANSMITTER["name"],
        position=tx_pos,
        orientation=tx_orient,
        antenna=tx_array
    )
    scene.add(tx)


def _add_receivers(scene):
    """Add all 8 ESP32-S3 receivers with isotropic antennas."""
    # Create shared antenna
    if ANTENNA_PATTERN == "iso":
        antenna = rt.Antenna("iso", "V")
    else:
        antenna = rt.Antenna("iso", "V")
    
    rx_array = rt.AntennaArray(antenna, positions=[[0, 0, 0]])
    
    for rx_name, rx_config in RECEIVERS.items():
        rx = rt.Receiver(
            name=rx_name,
            position=rx_config["position"],
            orientation=[0, 0, 0],
            antenna=rx_array
        )
        scene.add(rx)


def _create_mock_scene():
    """
    Create a mock scene dictionary for frontend development when 
    Sionna is not installed.
    """
    from config import ROOM_WIDTH, ROOM_DEPTH, ROOM_HEIGHT
    
    return {
        "type": "mock",
        "frequency": WIFI_FREQUENCY,
        "room": {
            "width": ROOM_WIDTH,
            "depth": ROOM_DEPTH,
            "height": ROOM_HEIGHT,
            "wall_thickness": WALL_THICKNESS,
        },
        "transmitter": TRANSMITTER,
        "receivers": RECEIVERS,
        "materials": MATERIALS,
    }


def get_scene_info(scene):
    """
    Extract scene metadata for the frontend API.
    
    Returns:
        dict with room geometry, sensor positions, materials
    """
    from config import ROOM_WIDTH, ROOM_DEPTH, ROOM_HEIGHT
    
    # Build receiver list for frontend
    receivers_list = []
    for name, config in RECEIVERS.items():
        receivers_list.append({
            "name": name,
            "position": config["position"],
            "label": config["label"],
        })
    
    return {
        "room": {
            "width": ROOM_WIDTH,
            "depth": ROOM_DEPTH,
            "height": ROOM_HEIGHT,
            "wall_thickness": WALL_THICKNESS,
        },
        "transmitter": {
            "name": TRANSMITTER["name"],
            "position": TRANSMITTER["position"],
        },
        "receivers": receivers_list,
        "frequency_ghz": WIFI_FREQUENCY / 1e9,
        "bandwidth_mhz": 40,
        "num_subcarriers": 114,
    }


if __name__ == "__main__":
    scene = load_scene()
    info = get_scene_info(scene)
    import json
    print("\nScene Info:")
    print(json.dumps(info, indent=2))
