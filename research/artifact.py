"""The signal artifact the calculator replays: per risk level, the weights of one reference account after its drawdown governor, by date.

The frozen run wrote the product's target weights (research/out/frozen/signal_<level>.csv). The reference account (Rs 10 lakh from the first April pick, the governor
at the level's cap, W1 harvesting, the research tax profile) follows them, and at each close the governor scales the risky weights it decides. Those scaled weights,
the rest in the fund, are what a user's account follows: the weights depend on the date only (sub-project 3 spec, section 2), and a user's own drawdown can exceed the cap.

    python -m research.artifact      # writes research/out/signal/<level>.csv and manifest.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from engine.rules import Rules
from research import baseline as B, panel as P, sim
from research.kaggle.snapshot import sha256

ROOT = Path(__file__).resolve().parents[1]
FROZEN = Path(__file__).resolve().parent / "out" / "frozen"
SIGNAL = Path(__file__).resolve().parent / "out" / "signal"
LEVELS = B.RISKS
SIGNAL_SIX = Path(__file__).resolve().parent / "out" / "signal_growth"     # the six-ETF model's signal (research/growth.py signal)
LEVELS_SIX = (*B.RISKS, "Growth")                    # the first three: the selector with the drawdown governor; Growth: GROWTH_MIX, no governor
GROWTH_MIX = [1 / 6] * 6 + [0.0]                     # the six ETFs in equal parts, no cash, back to equal each April
COLUMNS = ["NIFTYBEES", "JUNIORBEES", "BANKBEES", "GOLDBEES", "cash"]
EXECUTION = {"harvest": True}


def effective(target: np.ndarray, mult: np.ndarray) -> np.ndarray:
    """Risky weights times the governor's multiplier; what they give up goes to the fund."""
    if (mult < 0).any() or (mult > 1).any():
        raise ValueError("a governor multiplier is between 0 and 1")
    risky = target[:, :-1] * mult[:, None]
    return np.column_stack([risky, 1.0 - risky.sum(axis=1)])


def _read_verified(path: Path, files: dict) -> pd.DataFrame:
    if sha256(path) != files.get(path.name):
        raise ValueError(f"{path.name} does not match its recorded hash")
    return pd.read_csv(path)


def build(panel: P.Panel, rules: Rules, frozen: Path = FROZEN, out: Path = SIGNAL) -> dict:
    """Run the reference account of each level on its frozen target weights and write the governed weights."""
    src = json.loads((Path(frozen) / "manifest.json").read_text(encoding="utf-8"))["files"]
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    files = {}
    for level, cap in LEVELS.items():
        sig = _read_verified(Path(frozen) / f"signal_{level}.csv", src)
        i0 = int(np.searchsorted(panel.dates, np.datetime64(sig.date.iloc[0])))
        if len(panel.dates) - i0 != len(sig) or [str(d) for d in panel.dates[i0:]] != sig.date.tolist():
            raise ValueError(f"the {level} signal's dates are not the panel's dates from {sig.date.iloc[0]}")
        target = sig[COLUMNS].to_numpy(dtype=float)
        ref = sim.simulate(P.from_day(panel, i0), target, rules, sim.SimConfig(cap=cap, **EXECUTION))
        df = pd.DataFrame(effective(target, ref.multiplier), columns=COLUMNS)
        df.insert(0, "date", sig.date)
        df["multiplier"] = ref.multiplier
        df["strategy"] = sig.strategy
        df.to_csv(out / f"{level}.csv", index=False, float_format="%.10g", lineterminator="\n")
        files[f"{level}.csv"] = sha256(out / f"{level}.csv")
    manifest = {"files": files, "source": src, "execution": EXECUTION}
    (out / "manifest.json").write_bytes((json.dumps(manifest, indent=1, sort_keys=True) + "\n").encode("utf-8"))
    return manifest


def load(level: str, out: Path = SIGNAL) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Dates, T x (n + 1) weights (the ETFs, then cash) and the strategy held, of one level's artifact, after checking its hash."""
    files = json.loads((Path(out) / "manifest.json").read_text(encoding="utf-8"))["files"]
    df = _read_verified(Path(out) / f"{level}.csv", files)
    cols = [c for c in df.columns if c not in ("date", "multiplier", "strategy")]
    return df.date.to_numpy(dtype="datetime64[D]"), df[cols].to_numpy(dtype=float), df.strategy.tolist()


if __name__ == "__main__":
    from research import frozen
    m = build(P.load_panel(end=frozen.FROZEN_END), Rules.load(ROOT / "rules"))
    print(json.dumps(m["files"], indent=1))
