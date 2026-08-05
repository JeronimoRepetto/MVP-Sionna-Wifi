"""Shared pytest fixtures for MVP-Sionna-Wifi.

Design notes
------------
* Session-scoped fixtures for anything expensive. Loading the Mitsuba scene and running
  the path solver dominate the runtime; doing it once per session keeps the suite usable.
* Sionna is imported lazily inside fixtures, never at module level. Importing
  ``scene_loader`` selects the Mitsuba variant as a side effect, and that must not happen
  during collection of ``mock``-level tests.
* Missing resources produce ``skip`` with an explicit reason, never a hard error. The scene
  is not in git (defect D-05) and the SMPL models cannot be redistributed (MPI-IS licence),
  so a fresh clone legitimately lacks both.

The legacy suites are excluded from collection until WP-04 migrates them: ``test_api.py``
raises ``RuntimeError`` at import time when ``httpx`` is missing (defect D-16), which would
abort collection for everything else. They still run via ``tests/run_all.py``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# Removed by WP-04, which migrates these files to pytest.
collect_ignore = [
    "test_config.py",
    "test_pose_library.py",
    "test_animation.py",
    "test_scene_loader.py",
    "test_simulation.py",
    "test_api.py",
]


# ---------------------------------------------------------------------------
# Paths and availability
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def scene_path() -> Path:
    """Resolve the Mitsuba scene, or skip with an actionable reason.

    Order: WIFIVISION_SCENE_PATH env var, then scenes/room_simple.xml.
    """
    override = os.environ.get("WIFIVISION_SCENE_PATH")
    if override:
        p = Path(override)
        if not p.exists():
            pytest.skip(f"WIFIVISION_SCENE_PATH apunta a un fichero inexistente: {p}")
        return p

    default = REPO_ROOT / "scenes" / "room_simple.xml"
    if not default.exists():
        pytest.skip(
            "falta scenes/room_simple.xml. La escena NO esta versionada (defecto D-05): "
            "copiala del directorio principal, define WIFIVISION_SCENE_PATH, o aplica WP-05"
        )
    return default


@pytest.fixture(scope="session")
def sionna_rt():
    """The sionna.rt module, or skip."""
    try:
        from sionna import rt  # noqa: PLC0415
    except ImportError:
        pytest.skip("sionna no instalado — conda activate sionna")
    return rt


@pytest.fixture(scope="session")
def mitsuba_variant() -> str:
    try:
        from scene_loader import MITSUBA_VARIANT  # noqa: PLC0415
    except ImportError:
        pytest.skip("scene_loader no importable")
    return MITSUBA_VARIANT


@pytest.fixture(scope="session")
def smpl_available() -> bool:
    smpl_dir = BACKEND / "models" / "smpl"
    return smpl_dir.is_dir() and any(smpl_dir.glob("*.pkl"))


# ---------------------------------------------------------------------------
# Scene, paths and simulation results
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def real_scene(scene_path, sionna_rt):
    """A real Sionna scene with 1 Tx and 8 Rx. Expensive: session-scoped."""
    from scene_loader import load_scene  # noqa: PLC0415
    scene = load_scene(scene_path=str(scene_path))
    if isinstance(scene, dict):
        pytest.skip("load_scene devolvio un mock: Sionna no esta operativo")
    return scene


@pytest.fixture(scope="session")
def solver_max_depth(config_module) -> int:
    """The depth the application actually ships with, not an arbitrary small number.

    This matters: some defects are depth-dependent. The out-of-scene padding vertex that
    INV-04 catches (observed at Z=-3.0) only appears at higher depths — at max_depth=3 the
    invariant passes and the bug hides. Invariants must be checked against the
    configuration that runs in production.
    """
    return int(config_module.RT_MAX_DEPTH)


@pytest.fixture(scope="session")
def real_paths(real_scene, sionna_rt, solver_max_depth):
    """Raw Paths object straight from the solver — the ground truth for the tests."""
    return sionna_rt.PathSolver()(scene=real_scene, max_depth=solver_max_depth)


@pytest.fixture(scope="session")
def truth_amplitudes(real_paths):
    """Correctly reconstructed complex amplitudes: a[0] + 1j*a[1].

    THIS is the reference. Comparing simulation.py's output against its own internal
    calculation would detect nothing — the current code is self-consistent and still wrong
    (defect D-01). See docs/agent/SIONNA_API_CONTRACT.md section 2.
    """
    import numpy as np  # noqa: PLC0415
    a = real_paths.a
    if not isinstance(a, tuple):
        return np.array(a)
    return np.array(a[0]) + 1j * np.array(a[1])


@pytest.fixture(scope="session")
def truth_tau(real_paths):
    import numpy as np  # noqa: PLC0415
    return np.array(real_paths.tau)


@pytest.fixture(scope="session")
def sim_result(real_scene, solver_max_depth):
    """Full run_simulation() output. Includes the coverage map, so it is slow."""
    from simulation import run_simulation  # noqa: PLC0415
    result = run_simulation(real_scene, max_depth=solver_max_depth)
    if result.get("fallback"):
        pytest.skip(f"run_simulation cayo a mock: {result.get('error')}")
    return result


@pytest.fixture(scope="session")
def mock_result():
    """Mock simulation output — always available, no Sionna needed."""
    from simulation import run_simulation  # noqa: PLC0415
    return run_simulation({"type": "mock"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def config_module():
    import config  # noqa: PLC0415
    return config


def per_receiver_truth_power(amplitudes, tau):
    """Total power per receiver in dB, computed from correctly reconstructed amplitudes.

    Indexing: amplitudes is (num_rx, rx_ant, num_tx, tx_ant, num_paths) and tau is
    (num_rx, num_tx, num_paths). Written out explicitly rather than relying on
    ``[rx, 0]`` + ``flatten()``, which only works by accident with a single Tx and a
    single antenna.
    """
    import numpy as np

    out = []
    num_rx = amplitudes.shape[0]
    for rx in range(num_rx):
        a_rx = amplitudes[rx, 0, 0, 0, :]
        tau_rx = tau[rx, 0, :] if tau.ndim == 3 else tau[rx, :]
        valid = tau_rx > 0
        total = float(np.sum(np.abs(a_rx[valid]) ** 2))
        out.append(10.0 * np.log10(total + 1e-30))
    return out
