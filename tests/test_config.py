"""
MVP-Sionna-WiFi: Configuration Tests
Validates all physical parameters, sensor positions, and room geometry.
"""

import sys
import os
import math

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from config import (
    ROOM_WIDTH, ROOM_DEPTH, ROOM_HEIGHT, WALL_THICKNESS,
    WIFI_FREQUENCY, WIFI_BANDWIDTH, NUM_SUBCARRIERS,
    TRANSMITTER, RECEIVERS, ANTENNA_PATTERN,
    RT_MAX_DEPTH, RT_NUM_SAMPLES,
    MATERIALS, COVERAGE_GRID_RESOLUTION,
)


def test_room_dimensions():
    """Room must match user-specified dimensions: 2.0 x 3.5 x 2.0 m."""
    assert ROOM_WIDTH == 2.0, f"Room width should be 2.0m, got {ROOM_WIDTH}"
    assert ROOM_DEPTH == 3.5, f"Room depth should be 3.5m, got {ROOM_DEPTH}"
    assert ROOM_HEIGHT == 2.0, f"Room height should be 2.0m, got {ROOM_HEIGHT}"
    print("  ✅ Room dimensions: 2.0 x 3.5 x 2.0 m")


def test_wall_thickness():
    """Wall thickness must be 12 cm (0.12 m)."""
    assert WALL_THICKNESS == 0.12, f"Wall thickness should be 0.12m, got {WALL_THICKNESS}"
    print("  ✅ Wall thickness: 0.12 m")


def test_wifi_parameters():
    """WiFi config must match project spec: 2.437 GHz, Ch6, HT40."""
    assert WIFI_FREQUENCY == 2.437e9, f"Frequency should be 2.437 GHz, got {WIFI_FREQUENCY}"
    assert WIFI_BANDWIDTH == 40e6, f"Bandwidth should be 40 MHz, got {WIFI_BANDWIDTH}"
    assert NUM_SUBCARRIERS == 114, f"Subcarriers should be 114, got {NUM_SUBCARRIERS}"
    print("  ✅ WiFi: 2.437 GHz, 40 MHz BW, 114 subcarriers")


def test_transmitter_position():
    """Transmitter must be inside the room and near the back wall."""
    pos = TRANSMITTER["position"]
    assert 0 <= pos[0] <= ROOM_WIDTH, f"Tx X={pos[0]} outside room [0, {ROOM_WIDTH}]"
    assert 0 <= pos[1] <= ROOM_DEPTH, f"Tx Y={pos[1]} outside room [0, {ROOM_DEPTH}]"
    assert 0 <= pos[2] <= ROOM_HEIGHT, f"Tx Z={pos[2]} outside room [0, {ROOM_HEIGHT}]"
    # Should be near back wall (high Y)
    assert pos[1] > ROOM_DEPTH * 0.8, f"Tx should be near back wall, Y={pos[1]}"
    print(f"  ✅ Transmitter: {pos} (inside room, near back wall)")


def test_receiver_count():
    """Must have exactly 8 receivers."""
    assert len(RECEIVERS) == 8, f"Should have 8 receivers, got {len(RECEIVERS)}"
    print(f"  ✅ Receiver count: {len(RECEIVERS)}")


def test_receiver_positions_inside_room():
    """All receivers must be inside the room boundaries."""
    for name, config in RECEIVERS.items():
        pos = config["position"]
        assert 0 <= pos[0] <= ROOM_WIDTH, f"{name} X={pos[0]} outside room"
        assert 0 <= pos[1] <= ROOM_DEPTH, f"{name} Y={pos[1]} outside room"
        assert 0 <= pos[2] <= ROOM_HEIGHT, f"{name} Z={pos[2]} outside room"
    print("  ✅ All 8 receivers inside room boundaries")


def test_receiver_two_levels():
    """Receivers should be split into 2 levels: 4 high + 4 low."""
    high = [n for n, c in RECEIVERS.items() if c["position"][2] > 1.0]
    low = [n for n, c in RECEIVERS.items() if c["position"][2] < 1.0]
    assert len(high) == 4, f"Should have 4 high receivers, got {len(high)}"
    assert len(low) == 4, f"Should have 4 low receivers, got {len(low)}"
    print(f"  ✅ Two levels: {len(high)} high, {len(low)} low")


def test_receiver_labels_exist():
    """Each receiver must have a descriptive label."""
    for name, config in RECEIVERS.items():
        assert "label" in config, f"{name} missing 'label'"
        assert len(config["label"]) > 0, f"{name} has empty label"
    print("  ✅ All receivers have labels")


def test_materials_itu_convention():
    """Material names must follow ITU naming (itu_ prefix)."""
    for surface, material in MATERIALS.items():
        assert material.startswith("itu_"), \
            f"Material '{material}' for '{surface}' must start with 'itu_'"
    print(f"  ✅ All materials follow ITU naming: {list(MATERIALS.values())}")


def test_ray_tracing_params_reasonable():
    """RT parameters must be within reasonable ranges."""
    assert 1 <= RT_MAX_DEPTH <= 20, f"Max depth {RT_MAX_DEPTH} out of range [1,20]"
    assert 10_000 <= RT_NUM_SAMPLES <= 10_000_000, \
        f"Num samples {RT_NUM_SAMPLES} out of range"
    assert 0.01 <= COVERAGE_GRID_RESOLUTION <= 0.5, \
        f"Grid resolution {COVERAGE_GRID_RESOLUTION} out of range"
    print(f"  ✅ RT params: depth={RT_MAX_DEPTH}, samples={RT_NUM_SAMPLES:,}")


def test_no_duplicate_positions():
    """No two sensors should occupy the exact same position."""
    all_positions = [tuple(TRANSMITTER["position"])]
    for name, config in RECEIVERS.items():
        pos = tuple(config["position"])
        assert pos not in all_positions, \
            f"{name} at {pos} duplicates another sensor"
        all_positions.append(pos)
    print("  ✅ No duplicate sensor positions")


# =============================================================================
# Runner
# =============================================================================
if __name__ == "__main__":
    tests = [
        test_room_dimensions,
        test_wall_thickness,
        test_wifi_parameters,
        test_transmitter_position,
        test_receiver_count,
        test_receiver_positions_inside_room,
        test_receiver_two_levels,
        test_receiver_labels_exist,
        test_materials_itu_convention,
        test_ray_tracing_params_reasonable,
        test_no_duplicate_positions,
    ]
    
    print("\n🧪 Config Tests")
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
    print("✅ All config tests passed!\n")
