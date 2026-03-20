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
    """Set physical thickness for all wall/surface materials."""
    configured = 0
    
    # Method 1: Try scene-level radio_materials (Sionna 0.16+)
    try:
        for mat_name, mat in scene.radio_materials.items():
            mat.thickness = WALL_THICKNESS
            print(f"   Material '{mat_name}': thickness={WALL_THICKNESS}m")
            configured += 1
    except AttributeError:
        pass
    
    # Method 2: Try object-level radio_materials
    if configured == 0:
        try:
            for obj_name, obj in scene.objects.items():
                if hasattr(obj, 'radio_materials'):
                    for mat_name, mat in obj.radio_materials.items():
                        mat.thickness = WALL_THICKNESS
                        print(f"   Material '{mat_name}' on '{obj_name}': "
                              f"thickness={WALL_THICKNESS}m")
                        configured += 1
                elif hasattr(obj, 'radio_material'):
                    mat = obj.radio_material
                    if mat is not None:
                        mat.thickness = WALL_THICKNESS
                        print(f"   Material on '{obj_name}': thickness={WALL_THICKNESS}m")
                        configured += 1
        except Exception as e:
            print(f"   ⚠️ Could not configure material thickness: {e}")
    
    if configured == 0:
        print("   ⚠️ No radio materials found to configure thickness. "
              "Sionna will use default ITU material properties.")


def _add_transmitter(scene):
    """Add the WiFi router as a transmitter."""
    tx_pos = TRANSMITTER["position"]
    tx_orient = TRANSMITTER.get("orientation", [0, 0, 0])
    
    # In Sionna 0.19+, antenna arrays are set on the scene level
    # scene.tx_array and scene.rx_array are shared by all Tx/Rx
    try:
        scene.tx_array = rt.PlanarArray(
            num_rows=1, num_cols=1,
            vertical_spacing=0.5, horizontal_spacing=0.5,
            pattern="dipole", polarization="V"
        )
    except Exception as e:
        print(f"   ⚠️ Could not set tx_array: {e}")
    
    # Add transmitter to scene
    tx = rt.Transmitter(
        name=TRANSMITTER["name"],
        position=tx_pos,
        orientation=tx_orient
    )
    scene.add(tx)


def _add_receivers(scene):
    """Add all 8 ESP32-S3 receivers."""
    # In Sionna 0.19+, antenna arrays are set on the scene level
    try:
        scene.rx_array = rt.PlanarArray(
            num_rows=1, num_cols=1,
            vertical_spacing=0.5, horizontal_spacing=0.5,
            pattern="dipole", polarization="V"
        )
    except Exception as e:
        print(f"   ⚠️ Could not set rx_array: {e}")
    
    for rx_name, rx_config in RECEIVERS.items():
        rx = rt.Receiver(
            name=rx_name,
            position=rx_config["position"],
            orientation=[0, 0, 0]
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
        "sionna_active": HAS_SIONNA,
    }


if __name__ == "__main__":
    scene = load_scene()
    info = get_scene_info(scene)
    import json
    print("\nScene Info:")
    print(json.dumps(info, indent=2))
