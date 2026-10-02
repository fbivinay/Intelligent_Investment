"""Every Fyers-style intraday strategy as a grid of settings, judged out of sample at a 5% worst fall.

    python -m research.intraday.grid [workers]      # writes research/out/intraday/grid[_SYMBOL].csv (also what the Kaggle kernel runs); INTRADAY_SYMBOL=BANKNIFTY for the Bank Nifty

Each setting trades the whole period once. Its size is fitted on the training years (2016-01 to 2021-12) so that their worst fall is 5%; that size then runs on
the test years (2022-01 to 2026-05), which played no part in any choice. Both windows start fresh with Rs 10 lakh in the liquid fund. Families (the Fyers
cards they stand for): theta (sold straddles, strangles, iron condors and butterflies, with leg stops, VIX filters, expiry-day or not), long volatility (bought
straddles and strangles on a VIX spike, a gap or a range break), directional option buying and spreads and futures on 19 signals (EMA, SMA, MACD, linear
regression, RSI, Bollinger, stochastic, momentum, ATR/ROC, opening range, day high/low, last hour, gaps, VIX).
"""
from __future__ import annotations

import os
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

from research.intraday import engine as E, signals as S

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "research" / "out" / "intraday"
SPLIT = np.datetime64("2022-01-01")
TARGET = 0.05

STRUCT_SELL = {"straddle": ((0, 0, -1), (1, 0, -1)), "strangle2": ((0, 2, -1), (1, -2, -1)), "strangle3": ((0, 3, -1), (1, -3, -1)),
               "condor1_5": ((0, 1, -1), (1, -1, -1), (0, 5, 1), (1, -5, 1)), "condor2_7": ((0, 2, -1), (1, -2, -1), (0, 7, 1), (1, -7, 1)),
               "butterfly4": ((0, 0, -1), (1, 0, -1), (0, 4, 1), (1, -4, 1)), "butterfly6": ((0, 0, -1), (1, 0, -1), (0, 6, 1), (1, -6, 1))}
STRUCT_LONGVOL = {"long_straddle": ((0, 0, 1), (1, 0, 1)), "long_strangle2": ((0, 2, 1), (1, -2, 1))}
STRUCT_DIR = {"buy_atm": ((0, 0, 1),), "buy_otm1": ((0, 1, 1),), "debit_spread": ((0, 0, 1), (0, 2, -1)), "credit_spread": ((1, 0, -1), (1, -3, 1))}


def specs() -> list[E.Spec]:
    out = []
    for name, legs in STRUCT_SELL.items():
        for entry in (5, 15, 105):
            for leg_sl in (None, 0.25, 0.4, 0.5):
                for tgt, sl in ((None, None), (0.5, 1.0)):
                    for days in ("all", "expiry", "nonexpiry", "dte2"):
                        for vix in (None, (-3.0, 3.0)):
                            out.append(E.Spec(f"theta|{name}|entry={entry}|legsl={leg_sl}|tgt={tgt}|sl={sl}|days={days}|vix={vix}", "theta", legs, entry=entry,
                                              leg_sl=leg_sl, tgt=tgt, sl=sl, days=days, vix=vix))
    for name, legs in STRUCT_LONGVOL.items():
        for sig in ("vix_spike", "gap_follow", "orb", None):
            for tgt, sl in ((0.3, 0.3), (0.6, 0.4), (None, None)):
                for days in ("all", "expiry"):
                    out.append(E.Spec(f"longvol|{name}|signal={sig}|tgt={tgt}|sl={sl}|days={days}", "longvol", legs, entry=300 if sig is None else 5,
                                      tgt=tgt, sl=sl, days=days, signal=sig))
    sigs = ["ema9_21", "sma20_cross", "macd", "linreg_slope", "rsi_reversal", "rsi_momentum", "bb_fade", "bb_breakout", "stochastic", "momentum_1m",
            "atr_roc", "orb", "orb_reversal", "day_high_low_break", "last_hour_rejection", "gap_follow", "gap_fade", "vix_spike", "open_direction"]
    for sig in sigs:
        for name, legs in STRUCT_DIR.items():
            for tgt, sl in ((0.2, 0.2), (0.5, 0.3), (None, None)):
                for days in ("all", "nonexpiry"):
                    out.append(E.Spec(f"dir|{name}|signal={sig}|tgt={tgt}|sl={sl}|days={days}", "directional", legs, tgt=tgt, sl=sl, days=days, signal=sig))
        for tgt, sl in ((0.5, 0.3), (1.0, 0.5), (None, None)):
            out.append(E.Spec(f"dir|futures|signal={sig}|tgt={tgt}|sl={sl}", "futures", (), tgt=tgt, sl=sl, signal=sig, futures=True))
    return out


_D = _SIG = None
SYMBOL = os.environ.get("INTRADAY_SYMBOL", "NIFTY")


def _init():
    global _D, _SIG
    _D = E.load(SYMBOL)
    _SIG = S.build(_D.T)


def _fit(tr, lo, hi):
    """The size whose worst fall over days lo..hi is TARGET (a few fixed-point steps), and that run's stats."""
    scale = 1.0
    for _ in range(6):
        st = E.stats(E.account(_D, tr, scale=scale, lo=lo, hi=hi).equity)
        if st["worst_fall"] <= 0 or not np.isfinite(st["worst_fall"]):
            break
        scale *= min(TARGET / st["worst_fall"], 10.0) if st["worst_fall"] < 1 else 0.05
        if abs(st["worst_fall"] - TARGET) < 0.002:
            break
    return scale, E.stats(E.account(_D, tr, scale=scale, lo=lo, hi=hi).equity)


def evaluate(spec: E.Spec) -> dict:
    tr = E.trades(_D, spec, _SIG)
    split = int(np.searchsorted(_D.T["days"], SPLIT))
    row = dict(name=spec.name, family=spec.family, trades=len(tr), train_trades=int((tr.i < split).sum()) if len(tr) else 0)
    if row["train_trades"] < 50:
        return row
    scale, a = _fit(tr, 0, split)
    b = E.stats(E.account(_D, tr, scale=scale, lo=split, hi=len(_D.lot)).equity)
    win = (tr.points > 0).mean()
    return {**row, "scale": scale, "train_cagr": a["cagr"], "train_fall": a["worst_fall"], "test_cagr": b["cagr"], "test_fall": b["worst_fall"], "win_rate": win,
            "points_per_trade": tr.points.mean()}


def main(workers: int | None = None, out: Path = OUT) -> pd.DataFrame:
    out.mkdir(parents=True, exist_ok=True)
    sp = specs()
    workers = workers or os.cpu_count()
    with Pool(workers, initializer=_init) as pool:
        rows = []
        for k, r in enumerate(pool.imap_unordered(evaluate, sp, chunksize=4)):
            rows.append(r)
            if k % 50 == 0:
                print(f"{k}/{len(sp)}", file=sys.stderr, flush=True)
    df = pd.DataFrame(rows).sort_values("train_cagr", ascending=False)
    df.to_csv(out / ("grid.csv" if SYMBOL == "NIFTY" else f"grid_{SYMBOL}.csv"), index=False)
    return df


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
