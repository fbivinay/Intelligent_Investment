"""The LSTM strategy's record: the out-of-sample weights the Kaggle kernel wrote (research/out/lstm), checked against their hashes, run through the exact
simulator with every charge and tax on Rs 10 lakh from the first April cut (2017-04-03, the Max level's first day) to 2026-09-30.

    python -m research.lstm_result          # v1: writes research/out/lstm/result.json
    python -m research.lstm_result v2       # v2: writes research/out/lstm_v2/result.json

Trades follow the weights only when a holding is more than 5% of the money away from its target (the band the earlier deep model used), so a small daily
change in the network's output does not become an order. Taxed with the research profile (new regime, Rs 12 lakh other income), as the Max level's
saved answer is; the growth figure is after selling everything on the last day.
"""
from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

import numpy as np

from engine.rules import Rules
from research import baseline as B, lstm as L, oos, panel as P, sim
from research.kaggle import lstm as KL, run as K
from research.kaggle.snapshot import sha256

ROOT = Path(__file__).resolve().parents[1]
OUT = KL.out_dir("v1")
END = KL.END
BAND = 0.05
CAPITAL = 1_000_000.0


def load(out: Path = OUT, name: str = "chosen") -> tuple[np.ndarray, np.ndarray]:
    """The weights (T x 7) and their dates, after checking every file against the hashes the kernel and the snapshot recorded."""
    K.verify_output(out, [f"weights_{c['name']}.npy" for c in L.CONFIGS] + ["weights_chosen.npy", "run.json"])
    if sha256(out / "dates.npy") != json.loads((out / "input_manifest.json").read_text(encoding="utf-8"))["files"]["d_dates.npy"]:
        raise ValueError("dates.npy is not the dates file the kernel read")
    return np.load(out / f"weights_{name}.npy").astype(float), np.load(out / "dates.npy").astype("datetime64[D]")


def subpanel(p: P.Panel, assets: list[str]) -> P.Panel:
    """The panel cut to some of its ETFs (same days)."""
    cols = [p.assets.index(a) for a in assets]
    return dataclasses.replace(p, assets=list(assets), **{k: getattr(p, k)[:, cols] for k in ("open", "high", "low", "close", "value", "vwap")})


def record(w: np.ndarray, dates: np.ndarray, assets: list[str] = P.GROWTH) -> tuple[dict, sim.Result, P.Panel]:
    """Simulate the weights from the first day a network made them; returns the ledger figures, the run and the panel window."""
    panel = subpanel(P.load_panel(end=END, assets=P.GROWTH), assets)
    if not np.array_equal(panel.dates.astype("datetime64[D]"), dates):
        raise ValueError("the weights were computed for other dates than this panel's")
    i0 = int(np.argmax(np.isfinite(w).all(axis=1)))
    win = P.from_day(panel, i0)
    ww = w[i0:] / w[i0:].sum(axis=1, keepdims=True)                         # stored as float32: renormalise
    rules = Rules.load(ROOT / "rules")
    r = sim.simulate(win, ww, rules, sim.SimConfig(capital=CAPITAL, cap=1.0, band=BAND, **{**oos.EXECUTION, "governor": False}))
    return B.measure(win, r, B.fixed_total(win, rules), CAPITAL), r, win


def main(version: str = "v1") -> dict:
    out = KL.out_dir(version)
    w, dates = load(out)
    m, r, win = record(w, dates, KL.VERSIONS[version])
    run = json.loads((out / "run.json").read_text(encoding="utf-8"))
    keep = np.unique(np.r_[np.arange(0, len(win.dates), 5), len(win.dates) - 1])
    mix = {a: round(float(x), 4) for a, x in zip([*win.assets, "LIQUID_FUND"], w[np.isfinite(w).all(axis=1)].mean(axis=0))}
    res = {"version": version, "from": str(win.dates[0]), "to": str(win.dates[-1]), "capital": CAPITAL, "final": float(r.liquidation_equity), "cagr": m["cagr_liquidated"],
           "worst_fall": m["max_dd"], "orders": m["orders"], "tax": m["tax"], "charges": m["charges"], "turnover": m["turnover"], "average_mix": mix,
           "choice": [{"from": str(dates[c["cut"]]), "chosen": c["chosen"]} for c in run["choice"]], "gpu": run.get("gpu"),
           "series": {"dates": [str(win.dates[i]) for i in keep], "values": [round(float(r.equity[i]), 2) for i in keep]}}
    (out / "result.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


if __name__ == "__main__":
    res = main(*sys.argv[1:2])
    print(json.dumps({k: v for k, v in res.items() if k != "series"}, indent=1), file=sys.stderr)
