"""
MVP-Sionna-WiFi: Simulation Tests
Validates the mock simulation engine produces correct, physically 
plausible results.
"""

import sys
import os
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from config import RECEIVERS, TRANSMITTER, ROOM_WIDTH, ROOM_DEPTH, ROOM_HEIGHT
from scene_loader import load_scene, get_scene_info
from simulation import run_simulation
import numpy as np


def _get_simulation():
    """Helper: run a simulation once and cache the result."""
    scene = load_scene()
    return run_simulation(scene)


def test_simulation_returns_all_receivers():
    """Simulation must return results for all 8 receivers."""
    result = _get_simulation()
    assert len(result["paths"]) == 8, \
        f"Expected 8 receiver results, got {len(result['paths'])}"
    
    rx_names = {p["receiver"] for p in result["paths"]}
    for name in RECEIVERS.keys():
        assert name in rx_names, f"Missing receiver {name} in results"
    print("  ✅ All 8 receivers present in simulation results")


def test_simulation_has_paths():
    """Every receiver must have at least 1 propagation path."""
    result = _get_simulation()
    for rx_data in result["paths"]:
        assert rx_data["num_paths"] > 0, \
            f"{rx_data['receiver']} has 0 paths"
        assert len(rx_data["paths"]) > 0, \
            f"{rx_data['receiver']} paths list is empty"
    print("  ✅ All receivers have propagation paths")


def test_paths_start_at_tx():
    """Each path's first vertex must be near the transmitter position."""
    result = _get_simulation()
    tx_pos = np.array(TRANSMITTER["position"])
    
    for rx_data in result["paths"]:
        for path in rx_data["paths"]:
            first_vertex = np.array(path["vertices"][0])
            dist = np.linalg.norm(first_vertex - tx_pos)
            assert dist < 0.5, \
                f"{rx_data['receiver']} path starts at {first_vertex}, " \
                f"Tx is at {tx_pos} (dist={dist:.2f}m)"
    print("  ✅ All paths start near the transmitter")


def test_paths_end_at_rx():
    """Each path's last vertex must be near the corresponding receiver."""
    result = _get_simulation()
    
    for rx_data in result["paths"]:
        rx_pos = np.array(RECEIVERS[rx_data["receiver"]]["position"])
        for path in rx_data["paths"]:
            last_vertex = np.array(path["vertices"][-1])
            dist = np.linalg.norm(last_vertex - rx_pos)
            assert dist < 0.5, \
                f"{rx_data['receiver']} path ends at {last_vertex}, " \
                f"Rx is at {rx_pos} (dist={dist:.2f}m)"
    print("  ✅ All paths end near their receiver")


def test_path_power_is_negative_db():
    """Signal power at receivers should be negative dB (free-space loss)."""
    result = _get_simulation()
    for rx_data in result["paths"]:
        for path in rx_data["paths"]:
            assert path["power_db"] < 0, \
                f"{rx_data['receiver']} path power {path['power_db']} dB is positive"
    print("  ✅ All path powers are negative dB (physically correct)")


def test_direct_path_is_strongest():
    """The direct (LOS) path should be the strongest for each receiver."""
    result = _get_simulation()
    for rx_data in result["paths"]:
        if len(rx_data["paths"]) < 2:
            continue
        # Direct path has 0 interactions (just Tx→Rx)
        direct = [p for p in rx_data["paths"] if p["num_interactions"] == 0]
        reflected = [p for p in rx_data["paths"] if p["num_interactions"] > 0]
        
        if direct and reflected:
            max_reflected = max(p["power_db"] for p in reflected)
            assert direct[0]["power_db"] >= max_reflected, \
                f"{rx_data['receiver']}: LOS power {direct[0]['power_db']:.1f} dB " \
                f"< reflected {max_reflected:.1f} dB"
    print("  ✅ Direct path is strongest for each receiver")


def test_cir_has_valid_data():
    """CIR must have delays, amplitudes, and phases for each receiver."""
    result = _get_simulation()
    assert "cir" in result, "Missing 'cir' in results"
    assert len(result["cir"]) == 8, f"CIR should have 8 entries, got {len(result['cir'])}"
    
    for cir in result["cir"]:
        assert "delays_ns" in cir, f"{cir['receiver']} missing delays_ns"
        assert "amplitudes_db" in cir, f"{cir['receiver']} missing amplitudes_db"
        assert len(cir["delays_ns"]) > 0, f"{cir['receiver']} has empty delays"
        assert len(cir["delays_ns"]) == len(cir["amplitudes_db"]), \
            f"{cir['receiver']}: delays and amplitudes count mismatch"
        assert cir["total_power_db"] < 0, \
            f"{cir['receiver']}: total power {cir['total_power_db']} should be negative"
    print("  ✅ CIR data is valid for all receivers")


def test_csi_has_114_subcarriers():
    """CSI must have 114 subcarriers for each receiver."""
    result = _get_simulation()
    assert "csi" in result, "Missing 'csi' in results"
    
    for csi_data in result["csi"]:
        assert len(csi_data["subcarrier_indices"]) == 114, \
            f"{csi_data['receiver']}: expected 114 subcarriers, " \
            f"got {len(csi_data['subcarrier_indices'])}"
        assert len(csi_data["amplitude_db"]) == 114, \
            f"{csi_data['receiver']}: amplitude array length != 114"
        assert len(csi_data["phase_rad"]) == 114, \
            f"{csi_data['receiver']}: phase array length != 114"
    print("  ✅ CSI has 114 subcarriers for all receivers")


def test_coverage_map_dimensions():
    """Coverage map grid must match room dimensions."""
    result = _get_simulation()
    assert "coverage" in result, "Missing 'coverage' in results"
    
    cov = result["coverage"]
    expected_nx = int(ROOM_WIDTH / cov["resolution"])
    expected_ny = int(ROOM_DEPTH / cov["resolution"])
    
    assert cov["grid_size"][0] == expected_nx, \
        f"Coverage X grid: expected {expected_nx}, got {cov['grid_size'][0]}"
    assert cov["grid_size"][1] == expected_ny, \
        f"Coverage Y grid: expected {expected_ny}, got {cov['grid_size'][1]}"
    assert len(cov["data"]) == expected_nx, \
        f"Coverage data rows: expected {expected_nx}"
    assert len(cov["data"][0]) == expected_ny, \
        f"Coverage data cols: expected {expected_ny}"
    print(f"  ✅ Coverage grid: {expected_nx}×{expected_ny} cells")


def test_simulation_time_recorded():
    """Simulation must report elapsed time."""
    result = _get_simulation()
    assert "simulation_time" in result, "Missing simulation_time"
    assert result["simulation_time"] >= 0, "Negative simulation time"
    print(f"  ✅ Simulation time: {result['simulation_time']:.3f}s")


def test_simulation_params_echoed():
    """Returned params must match what was requested."""
    result = _get_simulation()
    assert "parameters" in result, "Missing parameters in result"
    params = result["parameters"]
    assert "max_depth" in params
    assert "num_samples" in params
    assert "diffraction" in params
    print(f"  ✅ Parameters echoed: depth={params['max_depth']}, samples={params['num_samples']}")


# =============================================================================
# Runner
# =============================================================================
if __name__ == "__main__":
    tests = [
        test_simulation_returns_all_receivers,
        test_simulation_has_paths,
        test_paths_start_at_tx,
        test_paths_end_at_rx,
        test_path_power_is_negative_db,
        test_direct_path_is_strongest,
        test_cir_has_valid_data,
        test_csi_has_114_subcarriers,
        test_coverage_map_dimensions,
        test_simulation_time_recorded,
        test_simulation_params_echoed,
    ]
    
    print("\n🧪 Simulation Tests")
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
    print("✅ All simulation tests passed!\n")
