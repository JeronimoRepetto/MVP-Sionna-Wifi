"""
MVP-Sionna-WiFi: Ray Tracing Simulation Engine
Runs Sionna RT's SBR (Shooting and Bouncing Rays) algorithm and extracts
propagation paths, CIR, CSI, and coverage maps.
"""

import numpy as np
import json
import time

try:
    import sionna
    from sionna import rt
    import tensorflow as tf
    HAS_SIONNA = True
except ImportError:
    HAS_SIONNA = False

from config import (
    RT_MAX_DEPTH, RT_NUM_SAMPLES, RT_DIFFRACTION, RT_SCATTERING,
    RECEIVERS, TRANSMITTER, WIFI_FREQUENCY, NUM_SUBCARRIERS,
    ROOM_WIDTH, ROOM_DEPTH, ROOM_HEIGHT,
    COVERAGE_GRID_RESOLUTION, COVERAGE_HEIGHT
)


def run_simulation(scene, max_depth=6, num_samples=20000, 
                   diffraction=True, scattering=False,
                   refraction=True, specular_reflection=True,
                   coverage_height=None):
    """
    Run the full ray tracing simulation.
    
    Args:
        scene: Sionna RT scene or mock dict
        max_depth: Override max reflections
        num_samples: Override ray count
        diffraction: Override diffraction toggle
        scattering: Override scattering toggle
        refraction: Override refraction toggle
        specular_reflection: Override specular reflection toggle
        coverage_height: Override height for the 2D coverage map
        
    Returns:
        dict with paths, CIR, CSI, and coverage data serialized for frontend
    """
    max_depth = max_depth or RT_MAX_DEPTH
    num_samples = num_samples or RT_NUM_SAMPLES
    diffraction = diffraction if diffraction is not None else RT_DIFFRACTION
    scattering = scattering if scattering is not None else RT_SCATTERING
    coverage_height = coverage_height if coverage_height is not None else COVERAGE_HEIGHT
    
    if not HAS_SIONNA or (isinstance(scene, dict) and scene.get("type") == "mock"):
        return _mock_simulation(max_depth, num_samples, coverage_height)
    
    return _run_sionna_simulation(scene, max_depth, num_samples, 
                                      diffraction, scattering, 
                                      refraction, specular_reflection,
                                      coverage_height)


def _run_sionna_simulation(scene, max_depth, num_samples, diffraction, scattering,
                           refraction, specular_reflection, coverage_height):
    """Run actual Sionna RT ray tracing."""
    print(f"\n{'='*60}")
    print(f"Running Sionna RT Simulation")
    print(f"  Max depth: {max_depth}")
    print(f"  Num samples: {num_samples:,}")
    print(f"  Diffraction: {diffraction}")
    print(f"  Scattering: {scattering}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    # Configure solver
    solver = rt.SolverPaths(scene)
    solver.max_depth = max_depth
    solver.num_samples = num_samples
    solver.diffraction = diffraction
    solver.scattering = scattering
    
    # Compute paths
    paths = solver()
    
    elapsed = time.time() - start_time
    print(f"  ⏱️  Simulation completed in {elapsed:.2f}s")
    
    # Extract results for each receiver
    results = {
        "simulation_time": elapsed,
        "parameters": {
            "max_depth": max_depth,
            "num_samples": num_samples,
            "diffraction": diffraction,
            "scattering": scattering,
        },
        "paths": _extract_paths(paths),
        "cir": _compute_cir(paths),
        "csi": _compute_csi(paths),
    }
    
    # Compute coverage map
    results["coverage"] = _compute_coverage(scene, max_depth, coverage_height)
    
    return results


def _extract_paths(paths):
    """Extract ray path coordinates for visualization."""
    path_data = []
    
    # paths.vertices: [batch, tx, rx, path, vertex, 3]
    vertices = paths.vertices.numpy()
    powers = paths.a.numpy()  # Complex amplitudes
    
    for rx_idx, rx_name in enumerate(RECEIVERS.keys()):
        rx_paths = []
        for path_idx in range(vertices.shape[3]):
            # Get vertices for this path
            path_vertices = vertices[0, 0, rx_idx, path_idx]
            # Filter out zero-padded vertices
            valid = np.any(path_vertices != 0, axis=-1)
            if np.sum(valid) < 2:
                continue
            
            coords = path_vertices[valid].tolist()
            power = float(np.abs(powers[0, 0, rx_idx, path_idx]) ** 2)
            
            rx_paths.append({
                "vertices": coords,
                "power_linear": power,
                "power_db": float(10 * np.log10(power + 1e-30)),
                "num_interactions": len(coords) - 2,  # Exclude Tx and Rx
            })
        
        path_data.append({
            "receiver": rx_name,
            "num_paths": len(rx_paths),
            "paths": rx_paths[:50],  # Limit to top 50 paths for frontend
        })
    
    return path_data


def _compute_cir(paths):
    """Compute Channel Impulse Response for each Tx→Rx link."""
    cir_data = []
    
    delays = paths.tau.numpy()      # [batch, tx, rx, path]
    amplitudes = paths.a.numpy()    # Complex amplitudes
    
    for rx_idx, rx_name in enumerate(RECEIVERS.keys()):
        tau = delays[0, 0, rx_idx]
        a = amplitudes[0, 0, rx_idx]
        
        # Filter valid paths (non-zero delay)
        valid = tau > 0
        tau_valid = tau[valid]
        a_valid = a[valid]
        
        # Sort by delay
        sort_idx = np.argsort(tau_valid)
        tau_sorted = tau_valid[sort_idx]
        a_sorted = a_valid[sort_idx]
        
        cir_data.append({
            "receiver": rx_name,
            "delays_ns": (tau_sorted * 1e9).tolist(),  # Convert to nanoseconds
            "amplitudes_db": (20 * np.log10(np.abs(a_sorted) + 1e-30)).tolist(),
            "phases_rad": np.angle(a_sorted).tolist(),
            "delay_spread_ns": float(
                np.sqrt(np.sum(np.abs(a_sorted)**2 * tau_sorted**2) / 
                       np.sum(np.abs(a_sorted)**2 + 1e-30)) * 1e9
            ) if len(a_sorted) > 0 else 0.0,
            "total_power_db": float(
                10 * np.log10(np.sum(np.abs(a_sorted)**2) + 1e-30)
            ),
        })
    
    return cir_data


def _compute_csi(paths):
    """Compute Channel State Information (CSI) - amplitude and phase per subcarrier."""
    csi_data = []
    
    delays = paths.tau.numpy()
    amplitudes = paths.a.numpy()
    
    # Subcarrier frequencies for HT40 (40 MHz, 114 subcarriers)
    subcarrier_spacing = 312.5e3  # Hz (OFDM spacing for 802.11n)
    subcarrier_indices = np.arange(-57, 57)  # 114 subcarriers centered at 0
    subcarrier_freqs = subcarrier_indices * subcarrier_spacing
    
    for rx_idx, rx_name in enumerate(RECEIVERS.keys()):
        tau = delays[0, 0, rx_idx]
        a = amplitudes[0, 0, rx_idx]
        
        valid = tau > 0
        tau_valid = tau[valid]
        a_valid = a[valid]
        
        # Compute H(f) = Σ a_i * exp(-j2π f τ_i) for each subcarrier
        H = np.zeros(len(subcarrier_freqs), dtype=complex)
        for i in range(len(tau_valid)):
            H += a_valid[i] * np.exp(-1j * 2 * np.pi * subcarrier_freqs * tau_valid[i])
        
        csi_data.append({
            "receiver": rx_name,
            "subcarrier_indices": subcarrier_indices.tolist(),
            "amplitude_db": (20 * np.log10(np.abs(H) + 1e-30)).tolist(),
            "phase_rad": np.angle(H).tolist(),
            "mean_amplitude_db": float(20 * np.log10(np.mean(np.abs(H)) + 1e-30)),
        })
    
    return csi_data


def _compute_coverage(scene, max_depth, _):
    """Compute a volumetric 3D coverage map by stacking 2D slices."""
    heights = np.linspace(0.1, 1.9, 10)
    slices = []
    
    cm_width = ROOM_WIDTH + 1.0
    cm_depth = ROOM_DEPTH + 1.0
    
    for h in heights:
        cm = rt.CoverageMap(
            scene=scene,
            max_depth=max_depth,
            cm_cell_size=[COVERAGE_GRID_RESOLUTION, COVERAGE_GRID_RESOLUTION],
            cm_center=[ROOM_WIDTH / 2, ROOM_DEPTH / 2, float(h)],
            cm_orientation=[0, 0, 0],
            cm_size=[cm_width, cm_depth],
            num_samples=100_000,
        )
        
        coverage_data = cm().numpy()[0]
        coverage_db = 10 * np.log10(coverage_data + 1e-30)
        
        slices.append({
            "height": float(h),
            "data": coverage_db.tolist()
        })
        
    all_data = [s["data"] for s in slices]
    
    return {
        "slices": slices,
        "min_db": float(np.min(all_data)),
        "max_db": float(np.max(all_data)),
        "resolution": COVERAGE_GRID_RESOLUTION,
        "grid_size": list(np.array(all_data[0]).shape),
        "physical_size": [cm_width, cm_depth]
    }


# =============================================================================
# Mock simulation for frontend development without GPU
# =============================================================================
def _mock_simulation(max_depth, num_samples, coverage_height):
    """Generate realistic-looking mock data for frontend development."""
    np.random.seed(42)
    
    tx_pos = np.array(TRANSMITTER["position"])
    
    results = {
        "simulation_time": 0.5,
        "parameters": {
            "max_depth": max_depth,
            "num_samples": num_samples,
            "diffraction": RT_DIFFRACTION,
            "scattering": RT_SCATTERING,
        },
        "paths": [],
        "cir": [],
        "csi": [],
        "coverage": _mock_coverage(coverage_height),
    }
    
    for rx_name, rx_config in RECEIVERS.items():
        rx_pos = np.array(rx_config["position"])
        distance = np.linalg.norm(tx_pos - rx_pos)
        
        # Generate mock paths
        mock_paths = _generate_mock_paths(tx_pos, rx_pos, max_depth)
        results["paths"].append({
            "receiver": rx_name,
            "num_paths": len(mock_paths),
            "paths": mock_paths,
        })
        
        # Generate mock CIR
        num_taps = np.random.randint(5, 15)
        delays = np.sort(np.random.exponential(distance / 3e8, num_taps)) * 1e9
        delays[0] = distance / 3e8 * 1e9  # LOS delay
        amplitudes = -20 * np.log10(distance + 1) - np.arange(num_taps) * 3 + np.random.randn(num_taps) * 2
        phases = np.random.uniform(-np.pi, np.pi, num_taps)
        
        results["cir"].append({
            "receiver": rx_name,
            "delays_ns": delays.tolist(),
            "amplitudes_db": amplitudes.tolist(),
            "phases_rad": phases.tolist(),
            "delay_spread_ns": float(np.std(delays)),
            "total_power_db": float(amplitudes[0]),
        })
        
        # Generate mock CSI
        subcarrier_indices = list(range(-57, 57))
        base_amplitude = -30 - 20 * np.log10(distance + 0.1)
        amp_variation = np.sin(np.linspace(0, 4 * np.pi, 114)) * 5
        noise = np.random.randn(114) * 1.5
        amplitude_db = (base_amplitude + amp_variation + noise).tolist()
        phase_rad = np.unwrap(np.cumsum(np.random.randn(114) * 0.3)).tolist()
        
        results["csi"].append({
            "receiver": rx_name,
            "subcarrier_indices": subcarrier_indices,
            "amplitude_db": amplitude_db,
            "phase_rad": phase_rad,
            "mean_amplitude_db": float(np.mean(amplitude_db)),
        })
    
    return results


def _generate_mock_paths(tx_pos, rx_pos, max_depth):
    """Generate realistic mock ray paths with reflections."""
    paths = []
    
    # Direct path (LOS)
    distance = np.linalg.norm(tx_pos - rx_pos)
    paths.append({
        "vertices": [tx_pos.tolist(), rx_pos.tolist()],
        "power_linear": float(1.0 / (4 * np.pi * distance) ** 2),
        "power_db": float(-20 * np.log10(4 * np.pi * distance)),
        "num_interactions": 0,
    })
    
    # Single-bounce reflections off each wall
    wall_planes = [
        ("x", 0), ("x", ROOM_WIDTH),      # Left, Right walls
        ("y", 0), ("y", ROOM_DEPTH),       # Front, Back walls
        ("z", 0), ("z", ROOM_HEIGHT),      # Floor, Ceiling
    ]
    
    for axis, pos in wall_planes:
        # Compute mirror image of transmitter
        mirror_tx = tx_pos.copy()
        axis_idx = {"x": 0, "y": 1, "z": 2}[axis]
        mirror_tx[axis_idx] = 2 * pos - mirror_tx[axis_idx]
        
        # Reflection point on wall
        t = (pos - tx_pos[axis_idx]) / (rx_pos[axis_idx] - tx_pos[axis_idx] + 1e-10)
        if 0 < t < 1:
            reflection_pt = tx_pos + t * (rx_pos - tx_pos)
            reflection_pt[axis_idx] = pos
            
            # Clamp reflection point within room
            reflection_pt[0] = np.clip(reflection_pt[0], 0, ROOM_WIDTH)
            reflection_pt[1] = np.clip(reflection_pt[1], 0, ROOM_DEPTH)
            reflection_pt[2] = np.clip(reflection_pt[2], 0, ROOM_HEIGHT)
            
            total_dist = (np.linalg.norm(tx_pos - reflection_pt) + 
                         np.linalg.norm(reflection_pt - rx_pos))
            
            # Concrete reflection coefficient ~0.5-0.7 for 2.4 GHz
            refl_loss = 0.6
            power = refl_loss / (4 * np.pi * total_dist) ** 2
            
            paths.append({
                "vertices": [tx_pos.tolist(), reflection_pt.tolist(), rx_pos.tolist()],
                "power_linear": float(power),
                "power_db": float(10 * np.log10(power + 1e-30)),
                "num_interactions": 1,
            })
    
    # A few double-bounce paths
    for _ in range(3):
        # Random combination of two walls
        wall1 = wall_planes[np.random.randint(len(wall_planes))]
        wall2 = wall_planes[np.random.randint(len(wall_planes))]
        
        pt1 = np.array([
            np.random.uniform(0, ROOM_WIDTH),
            np.random.uniform(0, ROOM_DEPTH),
            np.random.uniform(0, ROOM_HEIGHT)
        ])
        pt2 = np.array([
            np.random.uniform(0, ROOM_WIDTH),
            np.random.uniform(0, ROOM_DEPTH),
            np.random.uniform(0, ROOM_HEIGHT)
        ])
        
        axis1_idx = {"x": 0, "y": 1, "z": 2}[wall1[0]]
        axis2_idx = {"x": 0, "y": 1, "z": 2}[wall2[0]]
        pt1[axis1_idx] = wall1[1]
        pt2[axis2_idx] = wall2[1]
        
        total_dist = (np.linalg.norm(tx_pos - pt1) + 
                     np.linalg.norm(pt1 - pt2) + 
                     np.linalg.norm(pt2 - rx_pos))
        power = 0.36 / (4 * np.pi * total_dist) ** 2
        
        paths.append({
            "vertices": [tx_pos.tolist(), pt1.tolist(), pt2.tolist(), rx_pos.tolist()],
            "power_linear": float(power),
            "power_db": float(10 * np.log10(power + 1e-30)),
            "num_interactions": 2,
        })
    
    return paths


def _mock_coverage(_):
    """Generate a realistic mock 3D coverage map."""
    tx_pos = np.array(TRANSMITTER["position"])
    
    cm_width = ROOM_WIDTH + 1.0
    cm_depth = ROOM_DEPTH + 1.0
    
    nx = int(cm_width / COVERAGE_GRID_RESOLUTION)
    ny = int(cm_depth / COVERAGE_GRID_RESOLUTION)
    
    heights = np.linspace(0.1, 1.9, 10)
    slices = []
    
    for h in heights:
        coverage = np.zeros((nx, ny))
        for i in range(nx):
            for j in range(ny):
                # Offset the calculation coordinates to match the expanded grid center
                x = (i + 0.5) * COVERAGE_GRID_RESOLUTION - 0.5 
                y = (j + 0.5) * COVERAGE_GRID_RESOLUTION - 0.5
                
                dist = np.sqrt((x - tx_pos[0])**2 + (y - tx_pos[1])**2 + (h - tx_pos[2])**2)
                fspl = -20 * np.log10(4 * np.pi * dist * WIFI_FREQUENCY / 3e8 + 1e-10)
                fading = 2 * np.sin(2 * np.pi * x * 3) * np.sin(2 * np.pi * y * 2) * np.sin(2 * np.pi * h * 4)
                coverage[i, j] = fspl + fading + np.random.randn() * 1
                
        slices.append({
            "height": float(h),
            "data": coverage.tolist()
        })
        
    all_data = [s["data"] for s in slices]
    
    return {
        "slices": slices,
        "min_db": float(np.min(all_data)),
        "max_db": float(np.max(all_data)),
        "resolution": COVERAGE_GRID_RESOLUTION,
        "grid_size": [nx, ny],
        "physical_size": [cm_width, cm_depth]
    }


if __name__ == "__main__":
    from scene_loader import load_scene
    scene = load_scene()
    results = run_simulation(scene)
    print(f"\n✅ Simulation complete:")
    print(f"   Time: {results['simulation_time']:.2f}s")
    print(f"   Receivers: {len(results['paths'])}")
    for p in results['paths']:
        print(f"   {p['receiver']}: {p['num_paths']} paths")
