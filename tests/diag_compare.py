"""
Diagnostic script: Compare Sionna simulation WITH vs WITHOUT human mesh.
Verifies that the SMPL model actually affects ray tracing results.

Run from WSL:
  cd /mnt/c/Users/jeron/Desktop/MVP-Sionna-Wifi/backend
  python /tmp/compare_with_without_human.py
"""
import sys, os

# Add backend to path
_backend = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'backend')
sys.path.insert(0, _backend)
os.chdir(_backend)

import numpy as np

# ----- 1. Generate a human mesh at a specific position -----
print("=" * 60)
print("STEP 1: Generate SMPL mesh")
print("=" * 60)

try:
    from smpl_manager import SMPLManager
    smpl = SMPLManager()
    
    # Place human at center of room (Y-up SMPL coords, for_sionna swaps to Z-up)
    smpl.save_obj(
        "output/diag_human.obj",
        transl=[1.0, 1.0, 1.8],  # SMPL Y-up: x=1.0, height=1.0, depth=1.8
        for_sionna=True,
    )
    print("  ✅ Human mesh generated at position [1.0, 1.0, 1.8] (SMPL Y-up)")
    human_obj = os.path.abspath("output/diag_human.obj")
except Exception as e:
    print(f"  ❌ Failed to generate SMPL mesh: {e}")
    sys.exit(1)

# ----- 2. Run simulation WITHOUT human -----
print("\n" + "=" * 60)
print("STEP 2: Simulation WITHOUT human")
print("=" * 60)

from scene_loader import load_scene, get_scene_info
from simulation import run_simulation

scene_no_human = load_scene()
print(f"  Objects in scene: {list(scene_no_human.objects.keys())}")

result_no_human = run_simulation(scene_no_human, max_depth=6, num_samples=1_000_000)

# ----- 3. Run simulation WITH human -----
print("\n" + "=" * 60)
print("STEP 3: Simulation WITH human")
print("=" * 60)

scene_with_human = load_scene(human_mesh_path=human_obj)
objects = list(scene_with_human.objects.keys())
print(f"  Objects in scene: {objects}")
has_human = any("human" in o.lower() or "smpl" in o.lower() for o in objects)
print(f"  Human object found: {has_human}")

result_with_human = run_simulation(scene_with_human, max_depth=6, num_samples=1_000_000)

# ----- 4. Compare results -----
print("\n" + "=" * 60)
print("STEP 4: COMPARISON")
print("=" * 60)

# Compare CIR
print("\n--- CIR (Channel Impulse Response) ---")
for rx_no, rx_with in zip(result_no_human['cir'], result_with_human['cir']):
    name = rx_no['receiver']
    power_no = rx_no['total_power_db']
    power_with = rx_with['total_power_db']
    diff = power_with - power_no
    
    ds_no = rx_no['delay_spread_ns']
    ds_with = rx_with['delay_spread_ns']
    
    marker = "⚡" if abs(diff) > 0.5 else "≈"
    print(f"  {name:14s}  Power: {power_no:+.2f} → {power_with:+.2f} dB  (Δ = {diff:+.3f} dB) {marker}")
    print(f"  {'':14s}  Delay spread: {ds_no:.3f} → {ds_with:.3f} ns")

# Compare CSI
print("\n--- CSI (Channel State Information) ---")
for rx_no, rx_with in zip(result_no_human['csi'], result_with_human['csi']):
    name = rx_no['receiver']
    mean_no = rx_no['mean_amplitude_db']
    mean_with = rx_with['mean_amplitude_db']
    diff = mean_with - mean_no
    
    # Compute correlation between CSI amplitude vectors
    amp_no = np.array(rx_no['amplitude_db'])
    amp_with = np.array(rx_with['amplitude_db'])
    if len(amp_no) == len(amp_with) and len(amp_no) > 0:
        corr = np.corrcoef(amp_no, amp_with)[0, 1]
    else:
        corr = 0.0
    
    marker = "⚡" if abs(diff) > 0.5 else "≈"
    print(f"  {name:14s}  Mean CSI: {mean_no:+.2f} → {mean_with:+.2f} dB  (Δ = {diff:+.3f}) {marker}  corr={corr:.4f}")

# Compare coverage
print("\n--- Coverage Map ---")
cov_no = result_no_human['coverage']
cov_with = result_with_human['coverage']
for s_no, s_with in zip(cov_no['slices'], cov_with['slices']):
    data_no = np.array(s_no['data'])
    data_with = np.array(s_with['data'])
    mean_diff = np.mean(data_with - data_no)
    max_diff = np.max(np.abs(data_with - data_no))
    h = s_no['height']
    marker = "⚡" if max_diff > 1.0 else "≈"
    print(f"  h={h:.1f}m  mean Δ={mean_diff:+.3f} dB  max |Δ|={max_diff:.3f} dB  {marker}")

# ----- Summary -----
print("\n" + "=" * 60)
cir_diffs = [abs(r1['total_power_db'] - r2['total_power_db']) 
             for r1, r2 in zip(result_no_human['cir'], result_with_human['cir'])]
max_cir_diff = max(cir_diffs) if cir_diffs else 0

csi_diffs = [abs(r1['mean_amplitude_db'] - r2['mean_amplitude_db']) 
             for r1, r2 in zip(result_no_human['csi'], result_with_human['csi'])]
max_csi_diff = max(csi_diffs) if csi_diffs else 0

if max_cir_diff < 0.01 and max_csi_diff < 0.01:
    print("❌ PROBLEM: Results are IDENTICAL. The human mesh is NOT affecting ray tracing.")
    print("   Possible causes:")
    print("   1. Mesh not loaded into scene correctly")
    print("   2. Material not assigned properly")
    print("   3. Mesh too small / too far from receivers")
elif max_cir_diff < 0.5 and max_csi_diff < 0.5:
    print("⚠️  MARGINAL: Very small differences detected.")
    print(f"   Max CIR Δ: {max_cir_diff:.4f} dB")
    print(f"   Max CSI Δ: {max_csi_diff:.4f} dB")
    print("   The human mesh may be present but causing minimal interaction.")
else:
    print(f"✅ CONFIRMED: Human mesh affects simulation!")
    print(f"   Max CIR Δ: {max_cir_diff:.4f} dB")
    print(f"   Max CSI Δ: {max_csi_diff:.4f} dB")
print("=" * 60)

# Cleanup
try:
    os.remove(human_obj)
except:
    pass
