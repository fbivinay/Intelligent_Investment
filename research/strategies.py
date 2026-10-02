"""Baseline strategies S0 to S5. Each factory returns `fn(panel) -> weights`: T x (n + 1) target weights over the panel's n ETFs (NIFTYBEES first) and the cash leg.

Row t is what is wanted after the close of day t (the simulator fills it on day t + 1). Weights are long only and sum to 1; what is not in an ETF is in the cash
leg. Row t uses only data up to day t; `causal.assert_causal` proves it in the tests.

Two kinds. S0, S2, S4 and S5 give a fresh target every day from their signal, and the simulator's no-trade band decides when a move is worth trading. S1 and S3
are calendar strategies: they set a target on their rebalance days and let the weights drift with the prices in between, so "yearly", "never" and "monthly"
mean what they say and nothing is traded on the other days.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Callable

import numpy as np
import pandas as pd

RISK_CAPS = (0.10, 0.20, 0.30)              # maximum drawdown for Conservative, Balanced, Aggressive
SHARES = np.linspace(0.0, 1.0, 21)          # S0 tries Nifty shares in steps of 5%
VOL_DAYS = 63                               # volatility window of the inverse-volatility weights
MIN_VOL = 0.01                              # floor under a measured volatility: a flat price never gets an infinite weight
MONTHS = {"month": None, "quarter": (1, 4, 7, 10)}


def _vol(close: np.ndarray, n: int) -> np.ndarray:
    """Annualised volatility of the daily log changes over the last n days; NaN until n of them exist."""
    lr = np.log(pd.DataFrame(close)).diff()
    return (lr.rolling(n, min_periods=n).std(ddof=1) * np.sqrt(252)).to_numpy()


def _with_cash(risky: np.ndarray) -> np.ndarray:
    """T x (n + 1) weights from the T x n weights on the ETFs: what is not in them is in the cash leg."""
    return np.column_stack([risky, 1.0 - risky.sum(axis=1)])


def _first_days(dates: np.ndarray, months: tuple | None = None) -> np.ndarray:
    """True on the first trading day of each month (of the listed calendar months, if given); day 0 counts as a first day. Known from the dates so far."""
    m = dates.astype("datetime64[M]")
    new = np.r_[True, m[1:] != m[:-1]]
    return new if months is None else new & np.isin(m.astype(int) % 12 + 1, months)


def _drifting(p, target: np.ndarray, reset: np.ndarray) -> np.ndarray:
    """Weights equal to `target[t]` on the days flagged in `reset` and drifting with the prices in between, as if nothing were traded. Before the first
    flagged day they drift from `target[0]`."""
    level = np.column_stack([p.close, p.cash])
    start = np.maximum.accumulate(np.where(reset, np.arange(len(level)), 0))
    x = target[start] * level / level[start]
    return x / x.sum(axis=1, keepdims=True)


def s0_plain(cap: float, min_days: int = 252) -> Callable:
    """Same-risk plain holding: the largest Nifty share (steps of 5%, the rest in the cash leg, rebalanced daily) whose drawdown over all the history so far stayed
    within `cap`. The feasible shares can only shrink as history grows, so the share only falls. Cash until `min_days` of history exist."""
    def fn(p):
        nifty = np.r_[0.0, p.close[1:, 0] / p.close[:-1, 0] - 1]
        cash = np.r_[0.0, p.cash[1:] / p.cash[:-1] - 1]
        path = np.cumprod(1 + SHARES[:, None] * nifty + (1 - SHARES[:, None]) * cash, axis=1)
        worst = np.maximum.accumulate(1 - path / np.maximum.accumulate(path, axis=1), axis=1)
        share = np.where(worst <= cap + 1e-12, SHARES[:, None], 0.0).max(axis=0)
        share[:min_days - 1] = 0.0
        return _with_cash(np.column_stack([share, np.zeros((len(share), p.close.shape[1] - 1))]))
    return fn


def s1_grid(steps: int, n: int = 4) -> list[list[float]]:
    """Every mix of the n ETFs and cash in steps of 1/steps that sums to 1."""
    return [[k / steps for k in (*c, steps - sum(c))] for c in product(range(steps + 1), repeat=n) if sum(c) <= steps]


def s1_static(weights, rebalance: str = "band") -> Callable:
    """A fixed mix. `rebalance`: "band" holds the target every day (the simulator trades back when it is off by its band), "year" goes back to it on the first
    trading day of each financial year, "never" buys it on day 0 and lets it drift."""
    w = np.asarray(weights, dtype=float)
    if w.ndim != 1 or len(w) < 2 or (w < 0).any() or abs(w.sum() - 1) > 1e-9:
        raise ValueError("a mix is non-negative weights, one per ETF and the cash leg last, that sum to 1")
    if rebalance not in ("band", "year", "never"):
        raise ValueError(f"rebalance must be band, year or never, not {rebalance!r}")

    def fn(p):
        if len(w) != p.close.shape[1] + 1:
            raise ValueError(f"a mix for this panel has {p.close.shape[1] + 1} weights, not {len(w)}")
        target = np.tile(w, (len(p.dates), 1))
        if rebalance == "band":
            return target
        return _drifting(p, target, _first_days(p.dates, (4,)) if rebalance == "year" else np.zeros(len(p.dates), dtype=bool))
    return fn


def s2_trend(length: int, weighting: str = "equal") -> Callable:
    """Hold an ETF while its close is above its `length` day average, else its slot stays in cash. "equal": a quarter of the money per ETF in trend.
    "invvol": the ETFs in trend share all the money in inverse proportion to their volatility (cash when none is in trend or no volatility is known yet)."""
    if weighting not in ("equal", "invvol"):
        raise ValueError(f"weighting must be equal or invvol, not {weighting!r}")

    def fn(p):
        close = pd.DataFrame(p.close)
        up = (close > close.rolling(length, min_periods=length).mean()).to_numpy()
        if weighting == "equal":
            return _with_cash(up / up.shape[1])
        inv = 1.0 / np.maximum(_vol(p.close, VOL_DAYS), MIN_VOL)              # NaN while the volatility is unknown
        raw = np.where(up & np.isfinite(inv), inv, 0.0)
        total = raw.sum(axis=1, keepdims=True)
        return _with_cash(np.divide(raw, total, out=np.zeros_like(raw), where=total > 0))
    return fn


def s3_momentum(lookback: int, k: int, every: str = "month") -> Callable:
    """On the first trading day of each month (or quarter) put 1/k of the money in each of the k ETFs with the best return over the last `lookback` days,
    skipping any whose return is not above zero (their slots stay in cash); hold until the next rebalance day."""
    if every not in MONTHS:
        raise ValueError(f"every must be month or quarter, not {every!r}")
    if k < 1:
        raise ValueError("k is at least 1")

    def fn(p):
        past = p.close / np.vstack([np.full((lookback, p.close.shape[1]), np.nan), p.close[:-lookback]])[:len(p.close)] - 1   # NaN until `lookback` days exist
        reset = _first_days(p.dates, MONTHS[every])
        n = p.close.shape[1]
        if k > n:
            raise ValueError(f"k is at most the number of ETFs ({n})")
        target = np.zeros((len(p.dates), n + 1))
        target[:, n] = 1.0
        for t in np.flatnonzero(reset):
            r = np.where(np.isfinite(past[t]), past[t], -np.inf)
            chosen = [i for i in np.argsort(-r, kind="stable")[:k] if r[i] > 0]
            target[t, chosen] = 1.0 / k
            target[t, n] = 1.0 - len(chosen) / k
        return _drifting(p, target, reset)
    return fn


def s4_voltarget(target: float, lookback: int) -> Callable:
    """Volatility targeting of the Nifty ETF: its share is target / realised volatility over `lookback` days, at most 1 (no leverage); the rest is cash.
    Cash until the volatility is known."""
    if target <= 0:
        raise ValueError("the volatility target is above zero")

    def fn(p):
        vol = _vol(p.close[:, :1], lookback)[:, 0]
        share = np.where(np.isfinite(vol), np.minimum(1.0, target / np.maximum(vol, MIN_VOL)), 0.0)
        return _with_cash(np.column_stack([share, np.zeros((len(share), p.close.shape[1] - 1))]))
    return fn


def s5_marketdd(start: float, end: float) -> Callable:
    """Drawdown-aware exposure: the Nifty ETF's share is 1 while it is less than `start` below its highest close of the last year, falling in a straight line
    to 0 at `end` below it; the rest is cash."""
    if not 0 <= start < end <= 1:
        raise ValueError("drawdown points need 0 <= start < end <= 1")

    def fn(p):
        close = pd.Series(p.close[:, 0])
        dd = (1 - close / close.rolling(252, min_periods=1).max()).to_numpy()
        share = np.clip((end - dd) / (end - start), 0.0, 1.0)
        return _with_cash(np.column_stack([share, np.zeros((len(share), p.close.shape[1] - 1))]))
    return fn


@dataclass(frozen=True)
class Trial:
    id: str
    family: str
    params: dict
    fn: Callable
    band: float = 0.01                 # the simulator's no-trade band for this trial, as a share of wealth
    cap: float | None = None           # S0 only: the risk level it belongs to
    eligible_from: str | None = None   # a selector may pick it only at cuts on or after this date (a model needs a record of its own first)


def _fmt(v) -> str:
    return "/".join(f"{x:g}" for x in v) if isinstance(v, (list, tuple)) else (f"{v:g}" if isinstance(v, float) else str(v))


def trials(s1_steps: int = 10, n: int = 4) -> list[Trial]:
    """The committed list, every parameter set of S0 to S5 (spec section 3). Each one is a trial for the ledger and the deflated Sharpe ratio."""
    out: list[Trial] = []

    def add(family, factory, params, band=0.01, cap=None):
        """The strategy is built from `params`, so the parameters on the trial are the ones it runs with."""
        out.append(Trial(f"{family}|{','.join(f'{k}={_fmt(v)}' for k, v in params.items())}|band={band:g}", family, params, factory(**params), band, cap))

    for cap in RISK_CAPS:
        add("S0", s0_plain, {"cap": cap}, cap=cap)
    for w, rebalance in product(s1_grid(s1_steps, n), ("year", "never")):
        add("S1", s1_static, {"weights": w, "rebalance": rebalance})
    for (length, weighting), band in product(product((50, 100, 200), ("equal", "invvol")), (0.01, 0.05)):
        add("S2", s2_trend, {"length": length, "weighting": weighting}, band)
    for (lookback, k), every in product(product((63, 126, 252), (1, 2, 3)), ("month", "quarter")):
        add("S3", s3_momentum, {"lookback": lookback, "k": k, "every": every})
    for (target, lookback), band in product(product((0.06, 0.09, 0.12, 0.15, 0.18), (20, 60)), (0.01, 0.05)):
        add("S4", s4_voltarget, {"target": target, "lookback": lookback}, band)
    for (start, end), band in product(product((0.05, 0.10, 0.15), (0.25, 0.35)), (0.01, 0.05)):
        add("S5", s5_marketdd, {"start": start, "end": end}, band)
    return out


def ensembles(n: int = 4, s1_steps: int = 10) -> list[Trial]:
    """One candidate per family with no parameter left to choose. E1: the equal-weight mix of the four ETFs and cash, rebalanced yearly (the 1/N portfolio, the average of the
    symmetric S1 grid). E2 to E5: the average of the weights of every committed parameter set of S2 to S5 (those with the 5% simulator band where a family has both bands)."""
    every = trials(s1_steps, n)
    eq = [1.0 / (n + 1)] * (n + 1)
    out = [Trial("E1|equal-weight,rebalance=year|band=0.01", "E1", {"weights": eq, "rebalance": "year"}, s1_static(eq, "year"))]
    for k, src in enumerate(("S2", "S3", "S4", "S5"), start=2):
        band = 0.01 if src == "S3" else 0.05
        members = [t.fn for t in every if t.family == src and t.band == band]
        out.append(Trial(f"E{k}|mean of {len(members)} {src}|band={band:g}", f"E{k}", {"of": src, "members": len(members)},
                         lambda p, members=members: np.mean([m(p) for m in members], axis=0), band))
    return out
