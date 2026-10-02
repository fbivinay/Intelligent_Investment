"""Minute option price paths for one day, from research.intraday.prep's table.

Each strike's volatility moves with the India VIX through the day (iv_open x VIX now / VIX at 09:15) and is bent linearly in time so that it lands on the
volatility of the exchange's close: both ends match the exchange's own prices, the path between is a model (labelled). Options are priced on the Nifty minute
path with research.intraday.pricing.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.intraday import pricing as BS
from research.intraday.prep import BARS, R, STEP


def _t_left(day, expiry) -> np.ndarray:
    """Years from each bar's minute to 15:30 on the expiry day."""
    start = (expiry.astype("datetime64[m]") + np.timedelta64(15 * 60 + 30, "m")) - (day.astype("datetime64[m]") + np.timedelta64(9 * 60 + 15, "m"))
    mins = start.astype(float) - np.arange(BARS)
    return np.maximum(mins, 1.0) / (365.25 * 24 * 60)


def vols(T: dict, i: int, slot: int) -> np.ndarray:
    """BARS x strikes volatility path (NaN where a strike has no open or close volatility)."""
    v0, v1 = T["iv"][i, slot, 0], T["iv"][i, slot, 1]
    vx = T["vix"][i]
    ratio = vx / vx[0]
    bend = v1 / (v0 * ratio[-1])
    w = np.linspace(0.0, 1.0, BARS)[:, None]
    return v0[None, :] * ratio[:, None] * (1 + w * (bend[None, :] - 1))


def option_paths(T: dict, i: int, slot: int = 0):
    """(strikes, call path BARS x K, put path BARS x K)."""
    strikes = T["atm"][i] + T["offs"] * int(T.get("step", STEP))
    s = T["spot"][i][:, None]
    t = _t_left(T["days"][i], T["expiry"][i, slot])[:, None]
    v = vols(T, i, slot)
    return strikes, BS.price(s, strikes[None, :], t, v, R, 1), BS.price(s, strikes[None, :], t, v, R, -1)


def check(T: dict, n_strikes: int = 3) -> pd.DataFrame:
    """Model against the exchange: for the strikes nearest the money, the modelled day high and low against the real ones (nearest expiry)."""
    mid = len(T["offs"]) // 2
    rows = []
    for i in range(len(T["days"])):
        if not np.isfinite(T["iv"][i, 0, :, mid]).all():
            continue
        k, ce, pe = option_paths(T, i)
        for j in range(mid - n_strikes, mid + n_strikes + 1):
            for t, path in enumerate((ce, pe)):
                hi, lo = T["hl"][i, 0, 0, t, j], T["hl"][i, 0, 1, t, j]
                if np.isfinite(path[:, j]).all() and np.isfinite(hi) and lo > 0:
                    rows.append(dict(day=T["days"][i], off=int(T["offs"][j]), kind="CE" if t == 0 else "PE", real_hi=hi, model_hi=path[:, j].max(),
                                     real_lo=lo, model_lo=path[:, j].min()))
    return pd.DataFrame(rows)
