"""The numbers a model sees: the causal features arranged as a matrix, normalised with statistics from before the cut, cut into windows that end on each day, and the
return each day's weights go on to earn (the simulator's timing: filled at the VWAP of the next day, held to the VWAP of the day after).
"""
from __future__ import annotations

import numpy as np

PER_ASSET = ("ret1", "ret5", "ret21", "ret63", "ret252", "vol21", "vol63", "dd252", "dist50", "dist200", "vspike")
MARKET = ("vix", "vixchg5", "pe_pct", "pb_pct", "gold_vs_equity63", "cash_yield63")
MAY_BE_MISSING = ("vix", "vixchg5", "pe_pct", "pb_pct")
ASSETS = ("NIFTYBEES", "JUNIORBEES", "BANKBEES", "GOLDBEES")


def feature_matrix(feats: dict) -> tuple[np.ndarray, list[str]]:
    """T x F raw features: each per-asset feature for the four ETFs in turn, then the market ones, then a 0/1 flag for each market feature that can be missing."""
    cols, names = [], []
    for k in PER_ASSET:
        for j, a in enumerate(ASSETS):
            cols.append(feats[k][:, j])
            names.append(f"{k}:{a}")
    for k in MARKET:
        cols.append(feats[k])
        names.append(k)
    for k in MAY_BE_MISSING:
        cols.append(np.isnan(feats[k]).astype(float))
        names.append(f"{k}:missing")
    return np.column_stack(cols), names


def first_valid(X: np.ndarray, names: list[str]) -> int:
    """The first day on which every feature that is always present (not VIX, P/E, P/B or a flag) is known."""
    core = [i for i, n in enumerate(names) if not n.startswith(("vix", "pe_pct", "pb_pct")) and not n.endswith(":missing")]
    return int(np.flatnonzero(np.isfinite(X[:, core]).all(axis=1))[0])


def fit_norm(X: np.ndarray, start: int, upto: int) -> tuple[np.ndarray, np.ndarray]:
    """Mean and deviation of each column over rows start..upto-1, ignoring missing values; a column with none or no spread gets mean 0 or deviation 1."""
    with np.errstate(all="ignore"):
        mu, sd = np.nanmean(X[start:upto], axis=0), np.nanstd(X[start:upto], axis=0, ddof=1)
    return np.where(np.isfinite(mu), mu, 0.0), np.where(np.isfinite(sd) & (sd > 0), sd, 1.0)


def normalise(X: np.ndarray, mu: np.ndarray, sd: np.ndarray, clip: float = 5.0) -> np.ndarray:
    """Standardise, clip to `clip` deviations, and turn missing values into zero (the mean)."""
    Z = np.clip((X - mu) / sd, -clip, clip)
    return np.where(np.isnan(Z), 0.0, Z)


def sequences(Z: np.ndarray, days: np.ndarray, length: int) -> np.ndarray:
    """(N, length, F): for each day in `days`, the `length` rows of Z that end on it."""
    days = np.asarray(days)
    if (days - length + 1 < 0).any():
        raise ValueError(f"a sequence of {length} days would start before the first row")
    return Z[days[:, None] + np.arange(-length + 1, 1)]


def labels(vwap: np.ndarray, cash: np.ndarray) -> np.ndarray:
    """T x 5 (four ETFs and the cash leg): row t is the return from the fill price on day t+1 to the one on day t+2, what weights decided after the close of t earn. The last two
    rows have none."""
    px = np.column_stack([vwap, cash])
    R = np.full(px.shape, np.nan)
    R[:-2] = px[2:] / px[1:-1] - 1
    return R
