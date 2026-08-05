"""Physics invariants — the safety net of this project.

Each test enforces one property that EVERY simulation result must satisfy, whatever the
parameters, the compute backend or the scene contents. They exist because this project's
most dangerous failure mode is producing plausible-but-wrong numbers without raising a
single exception.

Tests blocked by a known defect are marked ``xfail(strict=True)``. That is deliberate:
when the defect is fixed the test turns into an XPASS, which FAILS the suite and forces
whoever fixed it to remove the marker and close the defect. A silent xfail that quietly
becomes correct is how stale test suites are born.

Reference: docs/agent/PHYSICS_INVARIANTS.md
Defects:   docs/DEFECTS.md
"""

from __future__ import annotations

import numpy as np
import pytest

from conftest import per_receiver_truth_power

pytestmark = pytest.mark.sionna


# ---------------------------------------------------------------------------
# INV-01 — every path runs from the Tx to its Rx
# ---------------------------------------------------------------------------

@pytest.mark.xfail(
    reason="D-04: paths.vertices holds only interaction points; _extract_paths never "
           "prepends the Tx nor appends the Rx. Fixed by WP-03",
    strict=True,
)
def test_inv01_paths_connect_tx_to_rx(sim_result, config_module):
    tx = np.array(config_module.TRANSMITTER["position"], dtype=float)
    tol = 0.01  # 1 cm: float32 rounding only; a real error would be decimetres

    checked = 0
    for rx_data in sim_result["paths"]:
        rx = np.array(config_module.RECEIVERS[rx_data["receiver"]]["position"], dtype=float)
        for path in rx_data["paths"]:
            verts = np.array(path["vertices"], dtype=float)
            assert verts.shape[0] >= 2, f"{rx_data['receiver']}: camino con < 2 vertices"
            assert np.linalg.norm(verts[0] - tx) < tol, (
                f"{rx_data['receiver']}: el camino empieza en {verts[0]}, Tx esta en {tx}")
            assert np.linalg.norm(verts[-1] - rx) < tol, (
                f"{rx_data['receiver']}: el camino acaba en {verts[-1]}, Rx esta en {rx}")
            checked += 1

    assert checked > 0, "ningun camino que comprobar"


# ---------------------------------------------------------------------------
# INV-02 — the LOS path exists and dominates
# ---------------------------------------------------------------------------

@pytest.mark.xfail(
    reason="D-04: the LOS path has zero interactions, so the 'at least 2 non-zero "
           "vertices' filter discards it every time. D-01 also breaks the powers. "
           "Fixed by WP-03",
    strict=True,
)
def test_inv02_los_exists_and_dominates(sim_result):
    for rx_data in sim_result["paths"]:
        name = rx_data["receiver"]
        los = [p for p in rx_data["paths"] if p["num_interactions"] == 0]
        assert los, f"{name}: no hay camino LOS (0 interacciones)"

        reflected = [p for p in rx_data["paths"] if p["num_interactions"] > 0]
        if reflected:
            strongest_reflected = max(p["power_db"] for p in reflected)
            assert los[0]["power_db"] >= strongest_reflected, (
                f"{name}: LOS {los[0]['power_db']:.2f} dB es mas debil que "
                f"el mejor reflejado {strongest_reflected:.2f} dB")


# ---------------------------------------------------------------------------
# INV-03 — powers are negative and decrease with the number of bounces
# ---------------------------------------------------------------------------

@pytest.mark.xfail(
    reason="D-04: power is hardcoded to 1e-6, so every path reports exactly -60.0 dB. "
           "Fixed by WP-03",
    strict=True,
)
def test_inv03_powers_negative_and_decreasing(sim_result):
    for rx_data in sim_result["paths"]:
        name = rx_data["receiver"]
        paths = rx_data["paths"]
        if not paths:
            continue

        for p in paths:
            assert p["power_db"] < 0, f"{name}: potencia {p['power_db']} dB no es negativa"

        # Group by bounce count and compare group means. Per-path monotonicity would be
        # physically wrong: geometry, not bounce count alone, decides an individual path.
        by_bounces: dict[int, list[float]] = {}
        for p in paths:
            by_bounces.setdefault(p["num_interactions"], []).append(p["power_db"])

        means = {k: float(np.mean(v)) for k, v in sorted(by_bounces.items())}
        if len(means) >= 2:
            keys = sorted(means)
            for lo, hi in zip(keys, keys[1:]):
                assert means[hi] <= means[lo] + 1e-9, (
                    f"{name}: media con {hi} rebotes ({means[hi]:.2f} dB) supera "
                    f"la de {lo} rebotes ({means[lo]:.2f} dB)")

        # Constant powers across every path mean the value is not being computed.
        distinct = {round(p["power_db"], 3) for p in paths}
        if len(paths) > 1:
            assert len(distinct) > 1, (
                f"{name}: los {len(paths)} caminos tienen potencia identica "
                f"({distinct.pop()} dB) — la potencia no se esta calculando")


# ---------------------------------------------------------------------------
# INV-04 — path geometry is physical
# ---------------------------------------------------------------------------

@pytest.mark.xfail(
    reason="D-04: Sionna's padding is not zero (a vertex at Z=-3.0 was observed) and the "
           "'!= 0' filter lets it through as a real coordinate. Fixed by WP-03",
    strict=True,
)
def test_inv04_geometry_is_physical(sim_result, config_module, solver_max_depth):
    # The Tx and the 8 Rx sit outside the walls by design (+-0.12 m), so the box needs a
    # margin. 0.5 m is generous and still catches a vertex 3 m below the floor.
    margin = 0.5
    lo = np.array([-margin, -margin, -margin])
    hi = np.array([config_module.ROOM_WIDTH + margin,
                   config_module.ROOM_DEPTH + margin,
                   config_module.ROOM_HEIGHT + margin])

    for rx_data in sim_result["paths"]:
        name = rx_data["receiver"]
        for path in rx_data["paths"]:
            verts = np.array(path["vertices"], dtype=float)
            outside = np.any((verts < lo) | (verts > hi), axis=1)
            assert not outside.any(), (
                f"{name}: vertice fuera de la escena: {verts[outside][0]}")

            n_int = path["num_interactions"]
            assert 0 <= n_int <= solver_max_depth, (
                f"{name}: num_interactions={n_int} fuera de [0, {solver_max_depth}]")
            assert n_int == len(verts) - 2, (
                f"{name}: num_interactions={n_int} pero el camino tiene "
                f"{len(verts)} vertices (esperado {n_int + 2}: Tx + {n_int} + Rx)")


# ---------------------------------------------------------------------------
# INV-05 — CIR phases carry information
# ---------------------------------------------------------------------------

@pytest.mark.xfail(
    reason="D-01: paths.a is (real, imag) and only a[0] is used, so np.angle() of a real "
           "number can only return 0 or pi. Fixed by WP-01",
    strict=True,
)
def test_inv05_cir_phases_carry_information(sim_result):
    all_phases = []
    for cir in sim_result["cir"]:
        all_phases.extend(cir["phases_rad"])

    assert all_phases, "no hay fases en el CIR"
    ph = np.asarray(all_phases, dtype=float)

    assert np.all(ph >= -np.pi - 1e-6) and np.all(ph <= np.pi + 1e-6), (
        f"fases fuera de [-pi, pi]: min={ph.min():.4f} max={ph.max():.4f}")

    # Collapsed to {0, pi} means the imaginary part was discarded.
    near_zero = np.isclose(ph, 0.0, atol=1e-6)
    near_pi = np.isclose(np.abs(ph), np.pi, atol=1e-6)
    collapsed = np.all(near_zero | near_pi)
    assert not collapsed, (
        f"las {ph.size} fases estan colapsadas en {{0, pi}}: se ha descartado "
        "la parte imaginaria de paths.a")

    # And they should actually spread out, not just avoid the two exact values.
    occupied = np.unique(np.digitize(ph, np.linspace(-np.pi, np.pi, 9)))
    assert occupied.size >= 3, (
        f"las fases solo ocupan {occupied.size} de 8 sectores del circulo")


# ---------------------------------------------------------------------------
# INV-06 — reported total power matches the amplitudes
# ---------------------------------------------------------------------------

@pytest.mark.xfail(
    reason="D-01: total_power_db is computed from the real part alone, understating the "
           "magnitude by up to 26 dB. Fixed by WP-01",
    strict=True,
)
def test_inv06_total_power_matches_amplitudes(sim_result, truth_amplitudes, truth_tau):
    truth = per_receiver_truth_power(truth_amplitudes, truth_tau)
    reported = [c["total_power_db"] for c in sim_result["cir"]]

    assert len(truth) == len(reported), (
        f"{len(truth)} receptores en paths.a vs {len(reported)} en el CIR")

    for i, (t, r) in enumerate(zip(truth, reported)):
        assert abs(t - r) < 0.1, (
            f"{sim_result['cir'][i]['receiver']}: total_power_db={r:.3f} dB pero "
            f"10*log10(sum|a|^2)={t:.3f} dB  (delta={r - t:+.3f} dB)")


# ---------------------------------------------------------------------------
# INV-07 — the CSI is consistent with the CIR
# ---------------------------------------------------------------------------

@pytest.mark.xfail(
    reason="D-01: H(f) is built from real-valued coefficients, so the subcarrier "
           "interference pattern is wrong. Fixed by WP-01",
    strict=True,
)
def test_inv07_csi_consistent_with_cir(sim_result, truth_amplitudes, truth_tau):
    truth = per_receiver_truth_power(truth_amplitudes, truth_tau)

    # 3 dB tolerance on purpose: with only 114 subcarriers and delays in the nanosecond
    # range, the multipath cross terms do not fully average out. Loose enough to avoid
    # false positives, tight enough to catch a structural error.
    tol_db = 3.0

    for i, csi in enumerate(sim_result["csi"]):
        amp_db = np.asarray(csi["amplitude_db"], dtype=float)
        mean_power_db = 10.0 * np.log10(np.mean(10.0 ** (amp_db / 10.0)) + 1e-30)
        assert abs(mean_power_db - truth[i]) < tol_db, (
            f"{csi['receiver']}: mean|H(f)|^2={mean_power_db:.2f} dB vs "
            f"sum|a|^2={truth[i]:.2f} dB  (delta={mean_power_db - truth[i]:+.2f} dB)")


# ---------------------------------------------------------------------------
# INV-08 — ESP32-S3 CSI format  (passes today)
# ---------------------------------------------------------------------------

def test_inv08_csi_format(sim_result, config_module):
    """Format contract with wifi-csi-capture. See docs/contracts/CSI_DATA_CONTRACT.md."""
    n = config_module.NUM_SUBCARRIERS
    assert n == 114, f"NUM_SUBCARRIERS deberia ser 114 (HT40), es {n}"

    expected = list(range(-57, 57))
    for csi in sim_result["csi"]:
        name = csi["receiver"]
        assert csi["subcarrier_indices"] == expected, f"{name}: indices inesperados"
        assert len(csi["amplitude_db"]) == n, f"{name}: amplitude_db != {n}"
        assert len(csi["phase_rad"]) == n, f"{name}: phase_rad != {n}"
        assert np.all(np.isfinite(csi["amplitude_db"])), f"{name}: amplitud no finita"
        assert np.all(np.isfinite(csi["phase_rad"])), f"{name}: fase no finita"


# ---------------------------------------------------------------------------
# INV-09 — a human body perturbs the channel
# ---------------------------------------------------------------------------

def test_inv09_human_perturbs_channel(real_scene, scene_path, smpl_available, tmp_path,
                                      solver_max_depth):
    """A body is ~60% water: at 2.4 GHz it absorbs and reflects heavily.

    Same criterion as tests/diag_compare.py, which already implements this comparison.
    """
    if not smpl_available:
        pytest.skip("faltan backend/models/smpl/*.pkl (licencia MPI-IS, no redistribuibles)")

    from scene_loader import load_scene  # noqa: PLC0415
    from simulation import run_simulation  # noqa: PLC0415
    try:
        from smpl_manager import SMPLManager  # noqa: PLC0415
    except ImportError as exc:
        pytest.skip(f"smpl_manager no importable: {exc}")

    obj = tmp_path / "human.obj"
    SMPLManager().save_obj(str(obj), transl=[1.0, 1.0, 1.8], for_sionna=True)

    without = run_simulation(load_scene(scene_path=str(scene_path)),
                             max_depth=solver_max_depth)
    with_human = run_simulation(
        load_scene(scene_path=str(scene_path), human_mesh_path=str(obj)),
        max_depth=solver_max_depth)

    deltas = [abs(a["total_power_db"] - b["total_power_db"])
              for a, b in zip(without["cir"], with_human["cir"])]

    assert deltas, "sin datos de CIR que comparar"
    assert max(deltas) > 0.5, (
        f"la malla humana no afecta a la simulacion: delta maximo {max(deltas):.4f} dB. "
        "Revisa que la malla se inyecte en el XML y que el material se asigne")


# ---------------------------------------------------------------------------
# INV-10 / INV-11 — the parameters actually reach the solver
# ---------------------------------------------------------------------------

def _capture_solver_kwargs(monkeypatch, sionna_rt, scene, **sim_kwargs) -> dict:
    """Run run_simulation() and return the kwargs PathSolver actually received.

    Behavioural comparison (different sample counts -> different results) would be flaky
    on a six-rectangle scene where the solver can legitimately find the same paths either
    way. Inspecting the call is deterministic.
    """
    import simulation as sim_mod  # noqa: PLC0415

    captured: dict = {}
    original = sionna_rt.PathSolver.__call__

    def spy(self, *args, **kwargs):
        captured.update(kwargs)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(sionna_rt.PathSolver, "__call__", spy)
    # Skip the radio map: 10 slices per call and irrelevant to what we are checking.
    monkeypatch.setattr(sim_mod, "_compute_coverage", lambda *a, **k: {"slices": []})

    sim_mod.run_simulation(scene, **sim_kwargs)
    return captured


@pytest.mark.xfail(
    reason="D-02: samples_per_src is never forwarded, so the UI's Ray Density slider "
           "does nothing. Fixed by WP-02",
    strict=True,
)
def test_inv10_num_samples_reaches_solver(monkeypatch, sionna_rt, real_scene):
    captured = _capture_solver_kwargs(
        monkeypatch, sionna_rt, real_scene, max_depth=2, num_samples=12345)

    assert "samples_per_src" in captured, (
        f"samples_per_src no llega al solver; recibidos: {sorted(captured)}")
    assert captured["samples_per_src"] == 12345, (
        f"samples_per_src={captured['samples_per_src']}, esperado 12345")


@pytest.mark.xfail(
    reason="D-03: the code writes scene.diffraction / scene.scattering, attributes that "
           "do not exist on Scene, so the flags never reach the solver. PathSolver's "
           "default for diffraction is False, so diffraction is always OFF. Fixed by WP-02",
    strict=True,
)
def test_inv11_physics_switches_reach_solver(monkeypatch, sionna_rt, real_scene):
    captured = _capture_solver_kwargs(
        monkeypatch, sionna_rt, real_scene, max_depth=2, diffraction=True)

    for key in ("diffraction", "diffuse_reflection", "specular_reflection", "refraction"):
        assert key in captured, (
            f"{key} no llega al solver; recibidos: {sorted(captured)}")

    assert captured["diffraction"] is True, (
        f"diffraction={captured['diffraction']}, se pidio True")


# ---------------------------------------------------------------------------
# INV-12 — the coverage map is finite  (passes today)
# ---------------------------------------------------------------------------

def test_inv12_coverage_is_finite(sim_result):
    """NaN or +-inf poison the min_db/max_db the frontend uses to normalise colours,
    turning the whole heatmap a single flat colour with no error message."""
    cov = sim_result.get("coverage")
    assert cov, "el resultado no trae mapa de cobertura"

    slices = cov.get("slices")
    assert slices, "la cobertura no trae rebanadas"

    for sl in slices:
        data = np.asarray(sl["data"], dtype=float)
        assert data.size > 0, f"rebanada vacia a h={sl['height']}"
        bad = ~np.isfinite(data)
        assert not bad.any(), (
            f"h={sl['height']}: {bad.sum()} celdas no finitas de {data.size}")

    assert np.isfinite(cov["min_db"]) and np.isfinite(cov["max_db"])
    assert cov["min_db"] <= cov["max_db"]


# ---------------------------------------------------------------------------
# INV-13 — GPU and CPU agree
# ---------------------------------------------------------------------------

@pytest.mark.gpu
@pytest.mark.skip(
    reason="Mitsuba fija el variant una sola vez por proceso y no se puede cambiar en "
           "caliente de forma fiable. Requiere lanzar dos subprocesos y comparar sus "
           "salidas. Lo implementa WP-04"
)
def test_inv13_gpu_matches_cpu():
    """Physical results must not depend on the compute backend.

    Implementation sketch for WP-04: run a small script in two subprocesses, forcing
    cuda_ad_mono_polarized and llvm_ad_mono_polarized via an environment variable that
    scene_loader honours, with a fixed seed, and compare total_power_db per receiver
    within 0.5 dB (the two backends reduce in different orders).
    """
