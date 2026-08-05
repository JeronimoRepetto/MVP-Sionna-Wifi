#!/usr/bin/env bash
# Canonical launcher for the MVP-Sionna-Wifi backend.
#
# WHY THIS EXISTS
# ---------------
# The three environment variables that enable CUDA + OptiX live in ~/.bashrc lines
# 135-137, which sit AFTER Ubuntu's non-interactive guard:
#
#     case $- in *i*) ;; *) return;; esac
#
# So in any non-interactive shell -- a script, a VS Code task, CI, or an AI agent running
# commands -- those lines never execute and Sionna silently falls back to CPU: 0.13 s per
# frame at 100% CPU instead of 0.027 s on GPU. The fallback prints a warning but does not
# fail, so it is easy to miss for a long time.
#
# This launcher exports them explicitly. Use it instead of `python backend/main.py`.
#
# WP-00 installs the same variables as a conda activate.d hook, which fixes the problem at
# the root. This script keeps working either way.
#
# Usage:
#     bash scripts/run_backend.sh                # start uvicorn
#     bash scripts/run_backend.sh --check-only   # print the active variant and exit
#
# See docs/agent/ENVIRONMENT.md sections 3-5.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WSL_LIB="/usr/lib/wsl/lib"
CUDA_LIB="/usr/local/cuda-12.6/lib64"
OPTIX_REAL="${WSL_LIB}/libnvoptix_real.so.1"

CHECK_ONLY=0
for arg in "$@"; do
    case "$arg" in
        --check-only) CHECK_ONLY=1 ;;
        -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
        *) echo "Argumento desconocido: $arg" >&2; exit 2 ;;
    esac
done

# --- GPU environment ---------------------------------------------------------
# Prepend, never overwrite: the caller may legitimately have other paths set.

if [ -d "$WSL_LIB" ]; then
    # Must come first: drjit dlopen()s the UNVERSIONED "libcuda.so", which otherwise
    # resolves to the native Linux driver installed inside WSL2 (defect D-26). The native
    # driver looks for /dev/nvidia0, which does not exist here, and cuInit() fails with
    # "no CUDA-capable device is detected".
    export LD_LIBRARY_PATH="${WSL_LIB}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
else
    echo "AVISO: ${WSL_LIB} no existe. ¿No estas en WSL2? Se usara CPU." >&2
fi

if [ -d "$CUDA_LIB" ]; then
    export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:+${LD_LIBRARY_PATH}:}${CUDA_LIB}"
fi

if [ -f "$OPTIX_REAL" ]; then
    # /usr/lib/wsl/lib/libnvoptix.so.1 is a 14 KB loader stub that does NOT export
    # optixQueryFunctionTable (verified with nm -D). The real 105 MB library is
    # libnvoptix_real.so.1. Point drjit straight at it.
    export DRJIT_LIBOPTIX_PATH="$OPTIX_REAL"
else
    echo "AVISO: ${OPTIX_REAL} no encontrado. OptiX no arrancara; se usara CPU." >&2
    echo "       Comprueba el nombre con: ls -la ${WSL_LIB}/libnvoptix*" >&2
fi

# --- Sanity checks -----------------------------------------------------------

if ! python -c "import sionna" >/dev/null 2>&1; then
    echo "ERROR: sionna no esta importable. ¿Has activado el entorno?" >&2
    echo "  source ~/miniconda3/etc/profile.d/conda.sh && conda activate sionna" >&2
    exit 1
fi

if [ ! -f "${REPO_ROOT}/scenes/room_simple.xml" ] && [ -z "${WIFIVISION_SCENE_PATH:-}" ]; then
    echo "AVISO: falta scenes/room_simple.xml (defecto D-05)." >&2
    echo "       El backend arrancara en MODO MOCK. Ver WP-05." >&2
fi

# --- Check-only mode ---------------------------------------------------------

if [ "$CHECK_ONLY" -eq 1 ]; then
    cd "${REPO_ROOT}/backend"
    # Reports the active variant. Loading the scene is best-effort: the point of
    # --check-only is the GPU, and the scene may legitimately be missing (defect D-05).
    python - <<'PY'
import os
import sys

from scene_loader import MITSUBA_VARIANT, load_scene

is_gpu = "cuda" in MITSUBA_VARIANT
label = "GPU (CUDA + OptiX)" if is_gpu else "CPU (LLVM)"
print()
print(f"  variant : {MITSUBA_VARIANT}")
print(f"  backend : {label}")

scene_override = os.environ.get("WIFIVISION_SCENE_PATH")
try:
    scene = load_scene(scene_path=scene_override) if scene_override else load_scene()
    print(f"  escena  : {len(scene.objects)} objetos")
except Exception as exc:
    print(f"  escena  : NO CARGADA ({type(exc).__name__})")
    print("            Falta scenes/room_simple.xml (defecto D-05) o define")
    print("            WIFIVISION_SCENE_PATH. El backend caeria a modo mock.")
print()
sys.exit(0 if is_gpu else 3)
PY
    exit $?
fi

# --- Start the server --------------------------------------------------------

cd "${REPO_ROOT}/backend"
echo "Arrancando backend desde ${REPO_ROOT}/backend"
echo "  LD_LIBRARY_PATH      = ${LD_LIBRARY_PATH:-<vacia>}"
echo "  DRJIT_LIBOPTIX_PATH  = ${DRJIT_LIBOPTIX_PATH:-<vacia>}"
exec python main.py
