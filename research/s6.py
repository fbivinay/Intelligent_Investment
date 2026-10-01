"""The deep model S6 as candidates for the ledger and the selector: the out-of-sample weights the Kaggle kernel wrote (research/out/s6), checked against the kernel's
own hashes and against the dates they were computed for.

Before the first April cut no model exists, and the untrained model holds equal weights (its head starts at zero), so that is S6's weight there. A selector may pick S6
only once it has three years of its own out-of-sample record.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from research.dl import configs as C
from research.kaggle import run as K
from research.kaggle.snapshot import sha256
from research.strategies import Trial

OUT = Path(__file__).resolve().parent / "out" / "s6"
OUT_FROZEN = Path(__file__).resolve().parent / "out" / "s6_frozen"
RECORD_YEARS = 3
NEVER = "9999-12-31"
BAND = 0.05


def load(out=OUT) -> tuple[dict, np.ndarray]:
    """{configuration name: T x 5 weights} and the dates they belong to, after checking every file against its recorded hash."""
    out = Path(out)
    names = [c["name"] for c in C.committed()]
    K.verify_output(out, [f"weights_{n}.npy" for n in names])
    if sha256(out / "dates.npy") != json.loads((out / "input_manifest.json").read_text(encoding="utf-8"))["files"]["d_dates.npy"]:
        raise ValueError("dates.npy is not the dates file the kernel read")
    return {n: np.load(out / f"weights_{n}.npy").astype(float) for n in names}, np.load(out / "dates.npy").astype("datetime64[D]")


def _prepared(w: np.ndarray) -> tuple[np.ndarray, int]:
    """The weights with the equal-weight prior before the first day a model existed, renormalised (they were stored as float32)."""
    known = np.isfinite(w).all(axis=1)
    first = int(np.argmax(known))
    if not known[first:].all():
        raise ValueError("weights are missing on a day after the first model existed")
    w = w.copy()
    w[:first] = 0.2
    return w / w.sum(axis=1, keepdims=True), first


def eligible_from(dates: np.ndarray, first: int) -> str:
    """The first April cut at least RECORD_YEARS years after the first day with model weights."""
    from research.selector import cut_days
    later = cut_days(dates, str(dates[first] + np.timedelta64(round(365.25 * RECORD_YEARS), "D")))
    return str(dates[later[0]]) if later else NEVER


def _trial(name: str, w: np.ndarray, dates: np.ndarray, params: dict) -> Trial:
    prepared = {}

    def fn(p):
        n = len(p.dates)
        if n > len(dates) or not np.array_equal(p.dates.astype("datetime64[D]"), dates[:n]):
            raise ValueError("the S6 weights were computed for other dates than this panel's")
        if not prepared:
            prepared["w"] = _prepared(w)[0]
        return prepared["w"][:n]
    first = int(np.argmax(np.isfinite(w).all(axis=1)))
    return Trial(f"S6|{name}|band={BAND:g}", "S6", params, fn, BAND, None, eligible_from(dates, first))


def trials(out=OUT) -> list[Trial]:
    """One trial per committed configuration."""
    weights, dates = load(out)
    return [_trial(c["name"], weights[c["name"]], dates, {k: c[k] for k in ("arch", "seq_len", "cost")}) for c in C.committed()]


def ensemble(out=OUT) -> Trial:
    """The mean of every committed configuration's weights: the deep model as one candidate with nothing left to choose."""
    weights, dates = load(out)
    return _trial(f"mean of {len(weights)} configurations", np.mean(list(weights.values()), axis=0), dates, {"configs": len(weights), "seeds": len(C.SEEDS)})


def ensemble_combined(design=OUT, frozen=OUT_FROZEN) -> Trial:
    """The deep model through the frozen years: the design run's weights for every design day (the record is never rewritten) and the frozen run's for the days after,
    from models retrained each April on the data before it."""
    dw, ddates = load(design)
    fw, fdates = load(frozen)
    n = len(ddates)
    if len(fdates) < n or not np.array_equal(fdates[:n], ddates):
        raise ValueError("the frozen run's calendar does not extend the design run's")
    combined = {}
    for name, w in fw.items():
        if not np.isfinite(w[n:]).all():
            raise ValueError(f"weights are missing on new days in the frozen run of {name}")
        c = w.copy()
        c[:n] = dw[name]
        combined[name] = c
    return _trial(f"mean of {len(combined)} configurations", np.mean(list(combined.values()), axis=0), fdates, {"configs": len(combined), "seeds": len(C.SEEDS)})
