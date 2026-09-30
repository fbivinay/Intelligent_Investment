"""Causal features from a Panel: each row t uses only rows up to t. `assert_causal` (research/causal.py) proves it for every one of them.

Per asset (T x 4): ret{1,5,21,63,252}, vol{21,63}, dd252, dist50, dist200, vspike. Market level (T): vix, vixchg5, pe_pct, pb_pct, gold_vs_equity63,
cash_yield63. NaN where the history is too short (and P/E, P/B, VIX before they exist).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.panel import Panel

RET_LAGS = (1, 5, 21, 63, 252)
VOL_WINDOWS = (21, 63)
MIN_PCT_HISTORY = 250


def _pct_rank(x: np.ndarray, min_obs: int = MIN_PCT_HISTORY) -> np.ndarray:
    """Share of the values seen so far (from the first finite one) that are not above today's, once min_obs of them exist."""
    out = np.full(len(x), np.nan)
    finite = np.flatnonzero(np.isfinite(x))
    if not len(finite):
        return out
    start = finite[0]
    for t in range(start + min_obs - 1, len(x)):
        h = x[start:t + 1]
        h = h[np.isfinite(h)]
        if len(h) >= min_obs and np.isfinite(x[t]):
            out[t] = (h <= x[t]).mean()
    return out


def build(p: Panel) -> dict[str, np.ndarray]:
    close = pd.DataFrame(p.close)
    f: dict[str, np.ndarray] = {}
    for k in RET_LAGS:
        f[f"ret{k}"] = (close / close.shift(k) - 1).to_numpy()
    lr = np.log(close).diff()
    for k in VOL_WINDOWS:
        f[f"vol{k}"] = (lr.rolling(k, min_periods=k).std(ddof=1) * np.sqrt(252)).to_numpy()
    f["dd252"] = (close / close.rolling(252, min_periods=252).max() - 1).to_numpy()
    for k in (50, 200):
        f[f"dist{k}"] = (close / close.rolling(k, min_periods=k).mean() - 1).to_numpy()
    v = pd.DataFrame(p.value)
    f["vspike"] = (v / v.rolling(63, min_periods=63).mean()).to_numpy()
    vix = pd.Series(p.vix)
    f["vix"] = vix.to_numpy()
    f["vixchg5"] = (vix / vix.shift(5) - 1).to_numpy()
    f["pe_pct"] = _pct_rank(p.pe)
    f["pb_pct"] = _pct_rank(p.pb)
    f["gold_vs_equity63"] = f["ret63"][:, 3] - f["ret63"][:, 0]
    cash = pd.Series(p.cash)
    f["cash_yield63"] = ((cash / cash.shift(63)) ** (252 / 63) - 1).to_numpy()
    return f
