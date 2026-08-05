#!/usr/bin/env python3
"""Environment diagnostics for MVP-Sionna-Wifi.

Prints a green/red table of everything the project needs, and - crucially - NAMES THE
CAUSE when the GPU is not available. Reporting "CPU" without saying why is useless: the
three possible causes (missing env vars, a native NVIDIA driver shadowing libcuda inside
WSL2, or no GPU at all) need completely different fixes.

Stdlib-only for the base checks, so it also runs under the Windows Python where neither
Sionna nor numpy is installed.

Usage:
    python scripts/env_check.py
    python scripts/env_check.py --json
    python scripts/env_check.py --quiet          # only failures

Exit code: 0 if nothing critical failed, 1 otherwise.

See docs/agent/ENVIRONMENT.md for the full failure-chain documentation.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Status constants. ASCII only: the Windows console is cp1252 by default and emojis
# raise UnicodeEncodeError (see AGENTS.md rule R3).
OK, WARN, FAIL, SKIP, INFO = "OK", "WARN", "FAIL", "SKIP", "INFO"

# Statuses that make the whole run fail
CRITICAL_STATUSES = {FAIL}


class Report:
    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.sections: list[str] = []

    def section(self, title: str) -> None:
        self.sections.append(title)
        self.rows.append({"section": title})

    def add(self, name: str, status: str, detail: str = "", critical: bool = False,
            fix: str = "") -> None:
        self.rows.append({
            "name": name, "status": status, "detail": detail,
            "critical": critical, "fix": fix,
        })

    @property
    def failures(self) -> list[dict]:
        return [r for r in self.rows
                if r.get("status") in CRITICAL_STATUSES and r.get("critical")]

    def render(self, quiet: bool = False) -> str:
        lines: list[str] = []
        width = 34
        for row in self.rows:
            if "section" in row:
                if not quiet:
                    lines.append("")
                    lines.append(f"--- {row['section']} " + "-" * max(0, 60 - len(row["section"])))
                continue
            if quiet and row["status"] not in (FAIL, WARN):
                continue
            mark = f"[{row['status']:^4}]"
            lines.append(f"{mark} {row['name']:<{width}} {row['detail']}")
            if row["fix"] and row["status"] in (FAIL, WARN):
                lines.append(f"       {'':<{width}} -> {row['fix']}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Platform
# ---------------------------------------------------------------------------

def _is_wsl() -> bool:
    if platform.system() != "Linux":
        return False
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except OSError:
        return False


def check_platform(rep: Report) -> None:
    rep.section("Plataforma")
    rep.add("sistema", INFO, f"{platform.system()} {platform.release()}")
    rep.add("python", INFO, f"{sys.version.split()[0]} ({sys.executable})")

    if _is_wsl():
        rep.add("entorno", OK, "WSL2 - el backend de simulacion puede correr aqui")
    elif platform.system() == "Linux":
        rep.add("entorno", OK, "Linux nativo")
    else:
        rep.add(
            "entorno", WARN,
            f"{platform.system()} - solo sirve para --level mock y para el frontend",
            fix="El backend necesita Linux/WSL2 (Sionna depende de TensorFlow con CUDA)",
        )

    conda = os.environ.get("CONDA_DEFAULT_ENV")
    if conda:
        rep.add("entorno conda", OK if conda == "sionna" else WARN, conda,
                fix="" if conda == "sionna" else "conda activate sionna")
    else:
        rep.add("entorno conda", WARN, "ninguno activo",
                fix="source ~/miniconda3/etc/profile.d/conda.sh && conda activate sionna")


# ---------------------------------------------------------------------------
# Python packages
# ---------------------------------------------------------------------------

PACKAGES = [
    # (import name, needed for level, critical for that level)
    ("numpy", "mock", True),
    ("fastapi", "sionna", True),
    ("uvicorn", "sionna", True),
    ("pytest", "mock", True),
    ("httpx", "sionna", False),
    ("sionna", "sionna", True),
    ("mitsuba", "sionna", True),
    ("drjit", "sionna", True),
    ("tensorflow", "sionna", False),
    ("torch", "smpl", False),
    ("smplx", "smpl", False),
    ("trimesh", "smpl", False),
]


def check_packages(rep: Report) -> dict[str, str | None]:
    rep.section("Paquetes de Python")
    found: dict[str, str | None] = {}
    for name, level, critical in PACKAGES:
        try:
            mod = __import__(name)
            version = getattr(mod, "__version__", "?")
            found[name] = version
            rep.add(name, OK, f"{version}  (nivel {level})")
        except Exception as exc:  # ImportError, but also broken installs
            found[name] = None
            detail = f"AUSENTE  (nivel {level})"
            if not isinstance(exc, ImportError):
                detail = f"ROTO: {type(exc).__name__}  (nivel {level})"
            rep.add(name, FAIL if critical else WARN, detail,
                    critical=critical, fix=f"pip install {name}")
    return found


# ---------------------------------------------------------------------------
# GPU chain - the part that must explain itself
# ---------------------------------------------------------------------------

WSL_LIB = Path("/usr/lib/wsl/lib")
NATIVE_LIBCUDA = Path("/usr/lib/x86_64-linux-gnu/libcuda.so")
OPTIX_REAL = WSL_LIB / "libnvoptix_real.so.1"


def check_gpu_chain(rep: Report, packages: dict[str, str | None]) -> str:
    """Diagnose the CUDA/OptiX chain layer by layer. Returns the active variant."""
    rep.section("Cadena de GPU (CUDA + OptiX)")

    if platform.system() != "Linux":
        rep.add("cadena de GPU", SKIP, "solo aplicable en Linux/WSL2")
        return "n/a"

    # --- Layer 1: passthrough ------------------------------------------------
    dxg = Path("/dev/dxg").exists()
    rep.add("/dev/dxg", OK if dxg else FAIL,
            "presente (passthrough de GPU a WSL2)" if dxg else "AUSENTE",
            fix="" if dxg else "Actualiza el driver NVIDIA de Windows y reinicia WSL")

    smi = shutil.which("nvidia-smi")
    gpu_name = ""
    if smi:
        try:
            out = subprocess.run(
                [smi, "--query-gpu=name,driver_version", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=30)
            gpu_name = out.stdout.strip().splitlines()[0] if out.stdout.strip() else ""
            rep.add("nvidia-smi", OK if gpu_name else WARN, gpu_name or "sin salida")
        except Exception as exc:
            rep.add("nvidia-smi", WARN, f"fallo: {type(exc).__name__}")
    else:
        rep.add("nvidia-smi", FAIL, "no encontrado en PATH",
                fix="Sin GPU visible no hay aceleracion; se usara CPU")

    # --- Layer 2: libcuda shadowing (defect D-26) ---------------------------
    if NATIVE_LIBCUDA.exists():
        target = os.path.realpath(NATIVE_LIBCUDA)
        rep.add(
            "libcuda nativa", WARN,
            f"presente: {Path(target).name}",
            fix="Driver Linux NATIVO dentro de WSL2 (D-26). Secuestra dlopen('libcuda.so') "
                "de drjit. Parche: LD_LIBRARY_PATH=/usr/lib/wsl/lib. Solucion: WP-00b",
        )
    else:
        rep.add("libcuda nativa", OK, "ausente (correcto en WSL2)")

    ld = os.environ.get("LD_LIBRARY_PATH", "")
    if str(WSL_LIB) in ld:
        rep.add("LD_LIBRARY_PATH", OK, "incluye /usr/lib/wsl/lib")
    else:
        rep.add(
            "LD_LIBRARY_PATH", WARN,
            f"[{ld}]" if ld else "vacia",
            fix="Necesaria si hay libcuda nativa. Si estas en shell NO interactiva, las "
                "variables de ~/.bashrc:135-137 no se aplican (D-25). Usa "
                "scripts/run_backend.sh o aplica WP-00",
        )

    # --- Layer 3: OptiX loader stub -----------------------------------------
    optix_env = os.environ.get("DRJIT_LIBOPTIX_PATH", "")
    if optix_env:
        exists = Path(optix_env).exists()
        rep.add("DRJIT_LIBOPTIX_PATH", OK if exists else FAIL,
                optix_env if exists else f"{optix_env} (NO EXISTE)",
                fix="" if exists else f"Deberia ser {OPTIX_REAL}")
    else:
        rep.add(
            "DRJIT_LIBOPTIX_PATH", WARN, "no definida",
            fix=f"El libnvoptix.so.1 de WSL es un stub que no exporta "
                f"optixQueryFunctionTable. Apunta a {OPTIX_REAL}",
        )

    # --- Layer 4/5: the real test -------------------------------------------
    if packages.get("mitsuba") is None:
        rep.add("variant de Mitsuba", SKIP, "mitsuba no instalado")
        return "none"

    variant, status, detail, fix = _probe_mitsuba()
    rep.add("variant de Mitsuba", status, detail, fix=fix)
    return variant


def _probe_mitsuba() -> tuple[str, str, str, str]:
    """Try CUDA+OptiX, then LLVM. Classify the failure precisely."""
    import mitsuba as mi  # noqa: PLC0415 - deliberately late

    empty = '<scene version="2.0.0"></scene>'
    try:
        mi.set_variant("cuda_ad_mono_polarized")
        mi.load_string(empty)
        return ("cuda_ad_mono_polarized", OK,
                "cuda_ad_mono_polarized - GPU + OptiX ACTIVO", "")
    except Exception as exc:
        msg = str(exc)
        low = msg.lower()

        if "cuinit" in low or "no cuda-capable device" in low:
            cause = ("CUDA no arranca: cuInit() falla. Causa tipica: la libcuda NATIVA "
                     "de /usr/lib/x86_64-linux-gnu tapa la de WSL (D-26). "
                     "Parche: export LD_LIBRARY_PATH=/usr/lib/wsl/lib. Ver ENVIRONMENT.md seccion5 capa 2")
        elif "optixqueryfunctiontable" in low or "could not initialize optix" in low:
            cause = (f"CUDA funciona pero OptiX no: el libnvoptix.so.1 de WSL es un stub. "
                     f"export DRJIT_LIBOPTIX_PATH={OPTIX_REAL}. Ver ENVIRONMENT.md seccion5 capa 3")
        else:
            cause = f"Fallo no clasificado: {msg.splitlines()[0][:140]}"

        try:
            mi.set_variant("llvm_ad_mono_polarized")
            return ("llvm_ad_mono_polarized", WARN,
                    "llvm_ad_mono_polarized - CPU (~5x mas lento)", cause)
        except Exception as exc2:
            return ("none", FAIL, f"ningun variant disponible: {exc2}", cause)


# ---------------------------------------------------------------------------
# Project assets
# ---------------------------------------------------------------------------

def check_assets(rep: Report) -> None:
    rep.section("Recursos del proyecto")

    scene = REPO_ROOT / "scenes" / "room_simple.xml"
    override = os.environ.get("WIFIVISION_SCENE_PATH")
    if override:
        p = Path(override)
        rep.add("escena (override)", OK if p.exists() else FAIL,
                f"{override}{'' if p.exists() else ' (NO EXISTE)'}")
    elif scene.exists():
        rep.add("scenes/room_simple.xml", OK, f"{scene.stat().st_size} bytes")
    else:
        rep.add(
            "scenes/room_simple.xml", FAIL, "AUSENTE",
            critical=False,
            fix="La escena NO esta en git (defecto D-05). Sin ella el backend cae a modo "
                "mock permanente. Copiala del directorio principal o define "
                "WIFIVISION_SCENE_PATH. Lo arregla WP-05",
        )

    smpl_dir = REPO_ROOT / "backend" / "models" / "smpl"
    pkls = sorted(smpl_dir.glob("*.pkl")) if smpl_dir.is_dir() else []
    if pkls:
        rep.add("modelos SMPL", OK, f"{len(pkls)} .pkl en backend/models/smpl/")
    else:
        rep.add(
            "modelos SMPL", WARN, "ausentes",
            fix="Descargalos de https://smpl.is.tue.mpg.de/ (licencia MPI-IS, no se "
                "redistribuyen). Sin ellos se desactiva el obstaculo humano",
        )

    nm = REPO_ROOT / "frontend" / "node_modules"
    rep.add("frontend/node_modules", OK if nm.is_dir() else WARN,
            "presente" if nm.is_dir() else "ausente",
            fix="" if nm.is_dir() else "cd frontend && npm install")

    node = shutil.which("node")
    if node:
        try:
            v = subprocess.run([node, "--version"], capture_output=True, text=True,
                               timeout=20).stdout.strip()
            rep.add("node", OK, v)
        except Exception:
            rep.add("node", WARN, "presente pero no responde")
    else:
        rep.add("node", WARN, "no encontrado", fix="Necesario solo para el frontend")


# ---------------------------------------------------------------------------
# Conda GPU hooks (installed by WP-00)
# ---------------------------------------------------------------------------

def check_conda_hooks(rep: Report) -> None:
    rep.section("Hooks de GPU en conda (WP-00)")
    prefix = os.environ.get("CONDA_PREFIX")
    if not prefix:
        rep.add("hooks de conda", SKIP, "sin CONDA_PREFIX")
        return
    hook = Path(prefix) / "etc" / "conda" / "activate.d" / "10-wifivision-gpu.sh"
    if hook.exists():
        rep.add("hooks de conda", OK, str(hook))
    else:
        rep.add(
            "hooks de conda", WARN, "no instalados",
            fix="Las variables de GPU dependen de ~/.bashrc, que NO se aplica en shells "
                "no interactivas (D-25). Instalalos con WP-00 "
                "(scripts/setup_conda_gpu_env.sh) o usa scripts/run_backend.sh",
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    # Diagnostics must never die of an encoding error. Output is kept ASCII-only on
    # purpose (the Windows console is cp1252 by default - AGENTS.md rule R3); this is the
    # belt and braces in case a non-ASCII character slips into a message later.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true", help="salida JSON legible por maquina")
    ap.add_argument("--quiet", action="store_true", help="solo fallos y avisos")
    args = ap.parse_args()

    rep = Report()
    check_platform(rep)
    packages = check_packages(rep)
    variant = check_gpu_chain(rep, packages)
    check_conda_hooks(rep)
    check_assets(rep)

    if args.json:
        print(json.dumps({
            "rows": [r for r in rep.rows if "section" not in r],
            "variant": variant,
            "failures": len(rep.failures),
        }, indent=2, ensure_ascii=False))
        return 1 if rep.failures else 0

    print("=" * 70)
    print("  MVP-Sionna-Wifi - diagnostico de entorno")
    print("=" * 70)
    print(rep.render(quiet=args.quiet))
    print()
    print("-" * 70)

    if variant.startswith("cuda"):
        backend = "GPU (CUDA + OptiX)"
    elif variant.startswith("llvm"):
        backend = "CPU (LLVM) - ~5x mas lento"
    elif variant in ("none", "n/a"):
        backend = "modo mock / no disponible"
    else:
        backend = variant

    print(f"  Backend de simulacion: {backend}")
    fails = rep.failures
    if fails:
        print(f"  Resultado: {len(fails)} fallo(s) critico(s)")
        for f in fails:
            print(f"    - {f['name']}: {f['detail']}")
    else:
        print("  Resultado: sin fallos criticos")
    print("  Detalle de cada capa: docs/agent/ENVIRONMENT.md")
    print("-" * 70)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
