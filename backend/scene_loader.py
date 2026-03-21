"""
MVP-Sionna-WiFi: Scene Loader
Loads the Mitsuba XML scene into Sionna RT and configures
transmitters, receivers, antennas, and material properties.
"""

import os
import numpy as np

# =============================================================================
# Mitsuba Variant Selection (BEFORE importing Sionna)
# =============================================================================
# Sionna registers custom Mitsuba plugins (itu-radio-material, etc.) at import
# time. These registrations are tied to the active variant, so we MUST choose
# the correct variant BEFORE importing Sionna.
#
# Problem in WSL2: mi.set_variant('cuda_ad_rgb') succeeds (CUDA works),
# but OptiX is NOT available, so rt.load_scene() fails later.
# Fix: test OptiX with a trivial scene load BEFORE importing Sionna.
# =============================================================================

MITSUBA_VARIANT = "none"
HAS_SIONNA = False

try:
    import mitsuba as mi
    
    def _test_optix():
        """Test if OptiX works by loading a trivial Mitsuba scene."""
        try:
            mi.set_variant('cuda_ad_mono_polarized')
            # This minimal load_string will trigger OptiX init if needed
            mi.load_string('<scene version="2.0.0"></scene>')
            return True
        except Exception as e:
            error_msg = str(e).lower()
            if "optix" in error_msg:
                return False
            # Non-OptiX error — CUDA might still work for other things,
            # but scene loading will fail, so fall back
            return False
    
    # Try CUDA+OptiX first
    if _test_optix():
        MITSUBA_VARIANT = "cuda_ad_mono_polarized"
        print("🟢 Mitsuba backend: CUDA + OptiX mono-polarized (GPU)")
    else:
        print("⚠️  OptiX not available (common in WSL2)")
        mi.set_variant('llvm_ad_mono_polarized')
        MITSUBA_VARIANT = "llvm_ad_mono_polarized"
        print("🟡 Mitsuba backend: LLVM mono-polarized (CPU)")
    
    # NOW import Sionna with the correct variant already active
    import sionna
    from sionna import rt
    HAS_SIONNA = True

except ImportError:
    print("⚠️  Sionna/Mitsuba not installed. Running in mock mode.")

from config import (
    WIFI_FREQUENCY, TRANSMITTER, RECEIVERS, ANTENNA_PATTERN,
    WALL_THICKNESS, MATERIALS
)

# Path to the exported XML scene
SCENE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'scenes', 'room_simple.xml'
)


def load_scene(scene_path=None, human_mesh_path=None):
    """
    Load the Mitsuba XML scene into Sionna RT.
    
    Args:
        scene_path: Path to .xml file. Defaults to scenes/room_simple.xml
        human_mesh_path: Optional path to an .obj file for a human obstacle
        
    Returns:
        scene: Sionna RT Scene object (or mock dict if Sionna not available)
    """
    if scene_path is None:
        scene_path = SCENE_PATH
    
    if not HAS_SIONNA:
        return _create_mock_scene()
        
    actual_scene_path = scene_path
    temp_path = None
    
    # Inject human mesh into XML
    if human_mesh_path and os.path.exists(human_mesh_path):
        import xml.etree.ElementTree as ET
        import tempfile
        try:
            tree = ET.parse(scene_path)
            root = tree.getroot()
            
            # Para que Mitsuba no falle por 'unresolved reference', inyectamos una definición
            # básica de 'itu_wet_ground' (material cercano biológicamente por su alta permitividad (agua)).
            # Sionna reemplazará las propiedades visuales por sus propiedades de Radio ITU reales.
            wet_mat = ET.Element("bsdf", type="twosided", id="itu_wet_ground")
            wet_diffuse = ET.SubElement(wet_mat, "bsdf", type="diffuse")
            ET.SubElement(wet_diffuse, "rgb", name="reflectance", value="0.2, 0.4, 0.8")
            root.insert(0, wet_mat)
            
            human_shape = ET.Element("shape", type="obj", id="Human_SMPL_Sionna")
            ET.SubElement(human_shape, "string", name="filename", value=human_mesh_path)
            ET.SubElement(human_shape, "ref", id="itu_wet_ground", name="bsdf")
            
            root.append(human_shape)
            temp_fd, temp_path = tempfile.mkstemp(suffix='.xml')
            with os.fdopen(temp_fd, 'wb') as f:
                tree.write(f)
            
            actual_scene_path = temp_path
            print(f"✅ Injected human mesh '{human_mesh_path}' into temporary XML.")
        except Exception as e:
            print(f"❌ Failed to inject human mesh: {e}")
    
    # Load scene — variant was already validated at import time
    scene = rt.load_scene(actual_scene_path, merge_shapes=False)
    
    # Cleanup temporary XML
    if temp_path and os.path.exists(temp_path):
        try:
            os.remove(temp_path)
        except:
            pass
    
    # Set operating frequency
    scene.frequency = WIFI_FREQUENCY
    
    # Configure material thicknesses
    _configure_materials(scene)
    
    # Add transmitter and receivers
    _add_transmitter(scene)
    _add_receivers(scene)
    
    variant_label = "CUDA+OptiX (GPU)" if "cuda" in MITSUBA_VARIANT else "LLVM (CPU)"
    print(f"✅ Scene loaded: {scene_path}")
    print(f"   Backend: {variant_label}")
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
    
    try:
        scene.tx_array = rt.PlanarArray(
            num_rows=1, num_cols=1,
            vertical_spacing=0.5, horizontal_spacing=0.5,
            pattern="dipole", polarization="V"
        )
    except Exception as e:
        print(f"   ⚠️ Could not set tx_array: {e}")
    
    tx = rt.Transmitter(
        name=TRANSMITTER["name"],
        position=tx_pos,
        orientation=tx_orient
    )
    scene.add(tx)


def _add_receivers(scene):
    """Add all 8 ESP32-S3 receivers."""
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
        dict with room geometry, sensor positions, materials, backend info
    """
    from config import ROOM_WIDTH, ROOM_DEPTH, ROOM_HEIGHT
    
    receivers_list = []
    for name, config in RECEIVERS.items():
        receivers_list.append({
            "name": name,
            "position": config["position"],
            "label": config["label"],
        })
    
    is_mock = isinstance(scene, dict) and scene.get("type") == "mock"
    if is_mock:
        backend = "mock"
    elif "cuda" in MITSUBA_VARIANT:
        backend = "cuda_optix"
    else:
        backend = "llvm_cpu"
    
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
        "sionna_active": HAS_SIONNA and not is_mock,
        "backend": backend,
        "mitsuba_variant": MITSUBA_VARIANT,
    }


if __name__ == "__main__":
    scene = load_scene()
    info = get_scene_info(scene)
    import json
    print("\nScene Info:")
    print(json.dumps(info, indent=2))
