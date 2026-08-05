#!/usr/bin/env python3
"""Verification orchestrator for MVP-Sionna-Wifi.

Runs every check that applies to the requested level and prints one summary table.
This is the single command an agent runs to know whether the project is healthy.

    python scripts/verify.py --level mock       # nothing required; Windows Python works
    python scripts/verify.py --level sionna     # needs the "sionna" conda env
    python scripts/verify.py --level gpu        # needs the GPU env vars too
    python scripts/verify.py --level hardware   # needs ESP32 nodes

Forces PYTHONUTF8=1 on every child process so the emoji-laden test output does not blow
up on the Windows cp1252 console (AGENTS.md rule R3).

XPASS IS A FAILURE. The invariant suite marks known-broken physics with
xfail(strict=True); an xpass means someone fixed a defect and left the marker behind.
See docs/agent/VERIFICATION.md.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

LEVELS = ["mock", "sionna", "gpu", "hardware"]

MARKER_EXPR = {
    "mock": "mock",
    "sionna": "mock or sionna",
    "gpu": "mock or sionna or gpu",
    "hardware": "mock or sionna or gpu or hardware",
}

PASS, FAIL, WARN, SKIP, XFAIL = "PASS", "FAIL", "WARN", "SKIP", "XFAIL"


class Step:
    def __init__(self, name: str, gating: bool = True) -> None:
        self.name = name
        self.gating = gating
        self.status = SKIP
        self.detail = ""
        self.seconds = 0.0

    def as_dict(self) -> dict:
        return {"name": self.name, "status": self.status, "detail": self.detail,
                "gating": self.gating, "seconds": round(self.seconds, 1)}


def _child_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _run(cmd: list[str], cwd: Path | None = None, timeout: int = 1800
         ) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd, cwd=str(cwd or REPO_ROOT), env=_child_env(),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout,
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except FileNotFoundError as exc:
        return 127, f"comando no encontrado: {exc}"
    except subprocess.TimeoutExpired:
        return 124, f"timeout tras {timeout}s"


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

def step_env_check(level: str, verbose: bool) -> Step:
    st = Step("env_check", gating=(level != "mock"))
    t0 = time.time()
    code, out = _run([sys.executable, "scripts/env_check.py"], timeout=300)
    st.seconds = time.time() - t0

    variant = "desconocido"
    m = re.search(r"Backend de simulacion:\s*(.+)", out)
    if m:
        variant = m.group(1).strip()
    st.detail = variant

    if verbose:
        print(out)

    if code != 0:
        st.status = FAIL if st.gating else WARN
        st.detail = f"{variant} - fallos criticos (ejecuta scripts/env_check.py)"
        return st

    if level == "gpu" and "GPU" not in variant:
        st.status = FAIL
        st.detail = (f"{variant} - el nivel gpu exige CUDA+OptiX. "
                     "Usa scripts/run_backend.sh o aplica WP-00")
        return st

    st.status = PASS
    return st


def step_pytest(level: str, verbose: bool) -> Step:
    st = Step(f"pytest -m \"{MARKER_EXPR[level]}\"")
    try:
        import pytest  # noqa: F401,PLC0415
    except ImportError:
        st.status = FAIL
        st.detail = "pytest no instalado - pip install pytest"
        return st

    t0 = time.time()
    code, out = _run([
        sys.executable, "-m", "pytest",
        "-m", MARKER_EXPR[level],
        "-q", "--no-header", "-rxX",
    ])
    st.seconds = time.time() - t0

    if verbose:
        print(out)

    counts = {k: 0 for k in ("passed", "failed", "xfailed", "xpassed", "skipped", "error")}
    for key in counts:
        m = re.search(rf"(\d+) {key}", out)
        if m:
            counts[key] = int(m.group(1))

    st.detail = (f"{counts['passed']} passed, {counts['failed']} failed, "
                 f"{counts['xfailed']} xfailed, {counts['xpassed']} xpassed, "
                 f"{counts['skipped']} skipped")

    if counts["xpassed"]:
        st.status = FAIL
        st.detail += "  <-- XPASS: un defecto se arreglo; quita la marca xfail (ver DEFECTS.md)"
    elif counts["failed"] or counts["error"] or code not in (0, 5):
        st.status = FAIL
        if code == 4:
            st.detail += "  <-- error de uso de pytest"
    elif counts["xfailed"]:
        st.status = XFAIL
        st.detail += "  (esperado: defectos P0 abiertos)"
    else:
        st.status = PASS
    return st


def step_frontend(verbose: bool) -> Step:
    st = Step("build del frontend", gating=False)
    fe = REPO_ROOT / "frontend"
    vite = fe / "node_modules" / "vite" / "bin" / "vite.js"

    if not vite.exists():
        st.status = SKIP
        st.detail = "node_modules ausente - cd frontend && npm install"
        return st
    if not shutil.which("node"):
        st.status = SKIP
        st.detail = "node no encontrado en PATH"
        return st

    outdir = Path(tempfile.mkdtemp(prefix="wifivision-vite-"))
    t0 = time.time()
    # Local binary on purpose: the user's PowerShell profile redirects npx to `pnpm dlx`,
    # which rejects the flags we need. See docs/agent/ENVIRONMENT.md section 8.
    code, out = _run(["node", str(vite), "build", "--outDir", str(outdir),
                      "--emptyOutDir"], cwd=fe, timeout=600)
    st.seconds = time.time() - t0

    if verbose:
        print(out)

    m = re.search(r"(\d+) modules transformed", out)
    st.detail = f"{m.group(1)} modulos" if m else "sin recuento de modulos"
    st.status = PASS if code == 0 else FAIL
    if code != 0:
        st.detail = out.strip().splitlines()[-1][:120] if out.strip() else "fallo del build"

    shutil.rmtree(outdir, ignore_errors=True)
    return st


def step_legacy_suite(verbose: bool) -> Step:
    """Informational only. Known to fail 3 tests (D-06); WP-04 absorbs it."""
    st = Step("suite legada (informativa)", gating=False)
    runner = REPO_ROOT / "tests" / "run_all.py"
    if not runner.exists():
        st.status = SKIP
        st.detail = "eliminada (WP-04 completado)"
        return st

    t0 = time.time()
    code, out = _run([sys.executable, "tests/run_all.py"], timeout=1800)
    st.seconds = time.time() - t0

    if verbose:
        print(out)

    m = re.search(r"Final:\s*(\d+) suites passed,\s*(\d+) failed", out)
    if m:
        st.detail = f"{m.group(1)} suites passed, {m.group(2)} failed"
        st.status = PASS if m.group(2) == "0" else WARN
        if m.group(2) != "0":
            st.detail += "  (esperado: D-06 - no bloquea)"
    else:
        st.status = WARN
        st.detail = "sin resumen legible (no bloquea)"
    return st


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    # Never die of an encoding error. Output is ASCII-only on purpose (the Windows console
    # is cp1252 by default - AGENTS.md rule R3); this is the belt and braces.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--level", choices=LEVELS, default="sionna")
    ap.add_argument("--verbose", "-v", action="store_true",
                    help="volcar la salida completa de cada paso")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-frontend", action="store_true")
    ap.add_argument("--no-legacy", action="store_true")
    args = ap.parse_args()

    steps: list[Step] = [step_env_check(args.level, args.verbose)]
    steps.append(step_pytest(args.level, args.verbose))
    if not args.no_frontend:
        steps.append(step_frontend(args.verbose))
    if not args.no_legacy and args.level != "mock":
        steps.append(step_legacy_suite(args.verbose))

    gating_failures = [s for s in steps if s.gating and s.status == FAIL]

    if args.json:
        print(json.dumps({
            "level": args.level,
            "steps": [s.as_dict() for s in steps],
            "ok": not gating_failures,
        }, indent=2, ensure_ascii=False))
        return 1 if gating_failures else 0

    print()
    print("=" * 78)
    print(f"  MVP-Sionna-Wifi - verificacion  (nivel: {args.level})")
    print("=" * 78)
    for s in steps:
        flag = "" if s.gating else " *"
        print(f"  [{s.status:^5}] {s.name:<32}{flag:<2} {s.detail}")
        if s.seconds >= 1:
            print(f"          {'':<32}   ({s.seconds:.1f}s)")
    print("-" * 78)
    print("  * = informativo, no bloquea")
    if gating_failures:
        print(f"  RESULTADO: FALLO - {len(gating_failures)} paso(s) bloqueante(s)")
        print("  Que hacer: docs/agent/VERIFICATION.md section 7")
    else:
        print("  RESULTADO: OK")
        if any(s.status == XFAIL for s in steps):
            print("  Hay xfail esperados: defectos P0 abiertos. Ver docs/DEFECTS.md")
    print("=" * 78)
    print()
    return 1 if gating_failures else 0


if __name__ == "__main__":
    sys.exit(main())
