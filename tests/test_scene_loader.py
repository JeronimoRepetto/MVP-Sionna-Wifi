"""
MVP-Sionna-WiFi: Scene Loader Tests
Validates scene loading, mock mode, and scene info serialization.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from scene_loader import load_scene, get_scene_info
from config import RECEIVERS, TRANSMITTER, ROOM_WIDTH, ROOM_DEPTH, ROOM_HEIGHT


def test_load_scene_returns_object():
    """load_scene() must return a valid scene (mock or real)."""
    scene = load_scene()
    assert scene is not None, "load_scene() returned None"
    print(f"  ✅ Scene loaded (type: {type(scene).__name__})")


def test_mock_scene_has_correct_structure():
    """Mock scene must contain room, transmitter, receivers, materials."""
    scene = load_scene()
    if isinstance(scene, dict) and scene.get("type") == "mock":
        assert "room" in scene, "Mock scene missing 'room'"
        assert "transmitter" in scene, "Mock scene missing 'transmitter'"
        assert "receivers" in scene, "Mock scene missing 'receivers'"
        assert "materials" in scene, "Mock scene missing 'materials'"
        assert scene["room"]["width"] == ROOM_WIDTH
        assert scene["room"]["depth"] == ROOM_DEPTH
        assert scene["room"]["height"] == ROOM_HEIGHT
        print("  ✅ Mock scene has correct structure and dimensions")
    else:
        print("  ⏭️  Skipped (Sionna is installed, testing real scene)")


def test_get_scene_info_structure():
    """get_scene_info must return properly structured data for the frontend."""
    scene = load_scene()
    info = get_scene_info(scene)
    
    # Top-level keys
    required_keys = ["room", "transmitter", "receivers", 
                     "frequency_ghz", "bandwidth_mhz", "num_subcarriers"]
    for key in required_keys:
        assert key in info, f"Missing key '{key}' in scene info"
    
    # Room info
    assert info["room"]["width"] == ROOM_WIDTH
    assert info["room"]["depth"] == ROOM_DEPTH
    assert info["room"]["height"] == ROOM_HEIGHT
    
    # Transmitter
    assert "name" in info["transmitter"]
    assert "position" in info["transmitter"]
    assert len(info["transmitter"]["position"]) == 3
    
    # Receivers
    assert len(info["receivers"]) == 8
    for rx in info["receivers"]:
        assert "name" in rx
        assert "position" in rx
        assert "label" in rx
        assert len(rx["position"]) == 3
    
    print("  ✅ Scene info has correct structure for frontend")


def test_scene_info_serializable():
    """Scene info must be JSON-serializable (for API response)."""
    import json
    scene = load_scene()
    info = get_scene_info(scene)
    
    try:
        json_str = json.dumps(info)
        parsed = json.loads(json_str)
        assert parsed == info
    except (TypeError, ValueError) as e:
        raise AssertionError(f"Scene info is not JSON-serializable: {e}")
    
    print(f"  ✅ Scene info is JSON-serializable ({len(json_str)} bytes)")


def test_receiver_names_match_config():
    """Receiver names in scene_info must match config.py."""
    scene = load_scene()
    info = get_scene_info(scene)
    
    info_names = {rx["name"] for rx in info["receivers"]}
    config_names = set(RECEIVERS.keys())
    
    assert info_names == config_names, \
        f"Name mismatch: info={info_names}, config={config_names}"
    print("  ✅ Receiver names match between config and scene_info")


def test_frequency_in_valid_range():
    """Frequency must be in the 2.4 GHz WiFi band."""
    scene = load_scene()
    info = get_scene_info(scene)
    
    freq = info["frequency_ghz"]
    assert 2.4 <= freq <= 2.5, f"Frequency {freq} GHz outside 2.4 GHz band"
    print(f"  ✅ Frequency {freq} GHz is in 2.4 GHz band")


# =============================================================================
# Runner
# =============================================================================
if __name__ == "__main__":
    tests = [
        test_load_scene_returns_object,
        test_mock_scene_has_correct_structure,
        test_get_scene_info_structure,
        test_scene_info_serializable,
        test_receiver_names_match_config,
        test_frequency_in_valid_range,
    ]
    
    print("\n🧪 Scene Loader Tests")
    print("=" * 50)
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  ❌ {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  💥 {test.__name__}: {type(e).__name__}: {e}")
            failed += 1
    
    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    if failed > 0:
        sys.exit(1)
    print("✅ All scene loader tests passed!\n")
