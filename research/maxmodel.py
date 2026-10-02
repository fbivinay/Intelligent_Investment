"""The Max level: one account holding stock momentum (half), the gold ETF (a quarter) and the Nasdaq 100 ETF (a quarter).

    python -m research.maxmodel        # writes research/out/signal_max/: Max.csv (weights by date), panel.npz (its prices), manifest.json (hashes)

The momentum half is research/stockmom.py's rule with the market switch: each quarter the 30 best by the momentum-index score among the 500 most traded
stocks, in equal parts; while the Nifty ETF closes below its 200-day average (checked on the first trading day of each month) that half is in the liquid
fund. On every decision day the whole account goes back to half / quarter / quarter; in between the weights drift. No drawdown guard.
Choices made with hindsight, said wherever the level is shown: the gold and Nasdaq ETFs were picked knowing 2017-2026 was good for them, and the switch
and mix were picked after seeing this period. The stock data starts 2016-01, so the first pick is 2017-04-03.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from research import panel as P, stockmom as M, strategies as st
from research.kaggle.snapshot import sha256

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "out" / "signal_max"
FIXED = {"GOLDBEES": 0.25, "MON100": 0.25}
MOMENTUM = 0.5
TREND = 200


def _etf_prices(panel: P.Panel) -> P.Panel:
    """The gold and Nasdaq columns from the ETF panel (split-adjusted, the Nasdaq ETF's old ticker N100 joined): the stock file knows the Nasdaq ETF only under
    its ticker since 2021. A weekend session only the stock file has carries the ETF's last price."""
    etf = P.load_panel(end=str(panel.dates[-1]), assets=P.GROWTH)
    out = {k: getattr(panel, k).copy() for k in ("open", "high", "low", "close", "value", "vwap")}
    for a in FIXED:
        j, k = etf.assets.index(a), panel.assets.index(a)
        for name in out:
            src = pd.Series(getattr(etf, name)[:, j], index=etf.dates).reindex(panel.dates)
            out[name][:, k] = (src.fillna(0.0) if name == "value" else src.ffill()).to_numpy()
    return P.Panel(**{**{x: getattr(panel, x) for x in ("dates", "assets", "cash", "nifty", "vix", "pe", "pb")}, **out})


def build(out: Path = OUT) -> dict:
    f, idx, traded = M.wide()
    chosen = M.picks(idx, f["value"], traded, 30, 500, trend=TREND)
    syms = sorted({s for v in chosen.values() for s in v} - set(FIXED)) + list(FIXED)
    panel = _etf_prices(M.stock_panel(f, idx, syms))
    dates = pd.DatetimeIndex(panel.dates.astype("datetime64[ns]"))
    n = len(syms)
    col = {s: j for j, s in enumerate(syms)}
    target, reset = np.zeros((len(dates), n + 1)), np.zeros(len(dates), dtype=bool)
    target[:, n] = 1.0
    for d, picks in chosen.items():
        t = dates.get_loc(d)
        row = np.zeros(n + 1)
        for s, w in FIXED.items():
            row[col[s]] = w
        if picks:
            row[[col[s] for s in picks]] += MOMENTUM / len(picks)
        else:
            row[n] = MOMENTUM
        target[t:] = row
        reset[t] = True
    i0 = int(np.argmax(reset))                          # the account starts on the first decision day
    sub = P.from_day(panel, i0)
    w = st._drifting(sub, target[i0:], reset[i0:])
    out.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(w, columns=syms + ["cash"])
    df.insert(0, "date", [str(d) for d in sub.dates])
    df["multiplier"] = 1.0
    df["strategy"] = "Max|momentum 30 of 500 with the 200-day switch 50, GOLDBEES 25, MON100 25"
    df.to_csv(out / "Max.csv", index=False, float_format="%.8g", lineterminator="\n")
    np.savez_compressed(out / "panel.npz", dates=sub.dates.astype(str), assets=np.array(syms), open=sub.open, high=sub.high, low=sub.low, close=sub.close,
                        value=sub.value, vwap=sub.vwap, cash=sub.cash)
    manifest = {"files": {k: sha256(out / k) for k in ("Max.csv", "panel.npz")}, "assets": syms + ["cash"], "first_day": str(sub.dates[0]),
                "rule": "momentum 30 of the 500 most traded, quarterly, 200-day switch on the Nifty ETF, half; GOLDBEES a quarter; MON100 a quarter; reset on decision days"}
    (out / "manifest.json").write_bytes((json.dumps(manifest, indent=1, sort_keys=True) + "\n").encode("utf-8"))
    return manifest


def load_panel(out: Path = OUT) -> P.Panel:
    """The Max level's panel, after checking its hash."""
    files = json.loads((Path(out) / "manifest.json").read_text(encoding="utf-8"))["files"]
    if sha256(Path(out) / "panel.npz") != files["panel.npz"]:
        raise ValueError("panel.npz does not match its recorded hash")
    z = np.load(Path(out) / "panel.npz")
    nan = np.full(len(z["dates"]), np.nan)
    return P.Panel(dates=z["dates"].astype("datetime64[D]"), assets=[str(a) for a in z["assets"]], open=z["open"], high=z["high"], low=z["low"], close=z["close"],
                   value=z["value"], vwap=z["vwap"], cash=z["cash"], nifty=nan, vix=nan, pe=nan, pb=nan)


if __name__ == "__main__":
    m = build()
    print(len(m["assets"]), "assets from", m["first_day"], file=sys.stderr)
