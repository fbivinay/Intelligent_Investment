"""Build the dataset a Kaggle kernel reads: the research panel (design period only) and its causal features, as arrays, with the hash of every file.

    python -m research.kaggle.build        # writes artifacts/kaggle/snapshot (git-ignored)
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np

from research import features as F, panel as P
from research.kaggle import snapshot as SN

ROOT = Path(__file__).resolve().parents[2]
SNAP = ROOT / "artifacts" / "kaggle" / "snapshot"
PANEL_ARRAYS = ("open", "high", "low", "close", "value", "vwap", "cash", "nifty", "vix", "pe", "pb")


def build_snapshot(panel: P.Panel, out: Path, code: dict | None = None, design_end: str = P.DESIGN_END, extra_arrays: dict | None = None) -> dict:
    """The panel's arrays (dates as days since 1970), its features as f_<name>, any extra arrays, and the code files, in one flat folder."""
    arrays = {"dates": panel.dates.astype("datetime64[D]").astype("int64")}
    arrays.update({name: getattr(panel, name) for name in PANEL_ARRAYS})
    arrays.update({f"f_{k}": v for k, v in F.build(panel).items()})
    arrays.update(extra_arrays or {})
    code = {"snapshot.py": Path(SN.__file__), **(code or {})}
    return SN.write_snapshot(out, arrays, code, {"design_end": design_end, "assets": list(panel.assets), "days": len(panel.dates), "first_day": str(panel.dates[0]),
                                                 "last_day": str(panel.dates[-1])}, dates_key="dates")


if __name__ == "__main__":
    m = build_snapshot(P.load_panel(end=P.DESIGN_END), SNAP)
    print(f"{len(m['files'])} files in {SNAP}")
