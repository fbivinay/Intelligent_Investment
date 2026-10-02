"""Copy what the calculator's serverless function needs into site/api/_lib before a deploy: the code (calc, engine, the parts of research it imports), the rule
tables, the data files it reads, and the signal artifact. numba is replaced by a stand-in whose njit leaves functions as plain Python: the exact engine, not the
day loop, sets the speed, and there is then no compiler to start on a cold request.

    python -m tools.bundle_site
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "site" / "api" / "_lib"
CODE = ["calc", "engine", "research/__init__.py", "research/artifact.py", "research/baseline.py", "research/causal.py", "research/costs.py", "research/panel.py",
        "research/sim.py", "research/strategies.py", "research/maxmodel.py", "research/stockmom.py", "research/kaggle/__init__.py", "research/kaggle/snapshot.py"]
DATA = ["rules", "data/processed/etf_daily_adjusted.csv", "data/processed/amfi_nav_adjusted.csv", "data/processed/nse_index_daily.csv",
        "data/processed/NIFTYBEES_dividends.csv", "research/out/signal", "research/out/signal_growth", "research/out/signal_max"]
NUMBA = '''"""Stand-in for numba in the serverless bundle: njit returns the function unchanged (plain Python, same results, no compiler)."""
STAND_IN = True


def njit(*args, **kwargs):
    if len(args) == 1 and callable(args[0]) and not kwargs:
        return args[0]
    return lambda f: f
'''
SKIP = shutil.ignore_patterns("__pycache__", "*.pyc")


def bundle(lib: Path = LIB) -> Path:
    if lib.exists():
        shutil.rmtree(lib)
    for rel in CODE + DATA:
        src, dst = ROOT / rel, lib / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, ignore=SKIP)
        else:
            shutil.copyfile(src, dst)
    (lib / "numba").mkdir()
    (lib / "numba" / "__init__.py").write_text(NUMBA, encoding="utf-8")
    return lib


if __name__ == "__main__":
    out = bundle(Path(sys.argv[1]) if len(sys.argv) > 1 else LIB)
    print(f"bundled into {out}: {sum(1 for _ in out.rglob('*') if _.is_file())} files")
