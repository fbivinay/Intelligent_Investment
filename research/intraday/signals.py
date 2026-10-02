"""Entry signals of the Fyers automations, on the Nifty minute path: for each day the first bar a signal fires between 09:30 and 14:30 and its direction
(+1 up, -1 down), or -1 when it does not fire. Indicators use only bars up to the signal (5-minute candles are complete when used: the signal bar is the
minute after the candle closes). The day before's close comes from the previous row.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FIRST, LAST = 15, 315           # 09:30 and 14:30


def _first(cond: np.ndarray, direction: np.ndarray, lo: int = FIRST, hi: int = LAST):
    """cond, direction: D x bars (minute bars). First bar in [lo, hi] where cond holds."""
    c = cond.copy()
    c[:, :lo] = False
    c[:, hi + 1:] = False
    any_ = c.any(axis=1)
    bar = np.where(any_, c.argmax(axis=1), -1)
    d = np.where(any_, direction[np.arange(len(bar)), np.clip(bar, 0, None)], 0)
    return bar + np.where(any_, 1, 0), d.astype(int)          # act on the next minute


def _candles(spot: np.ndarray, n: int) -> np.ndarray:
    """D x (375 / n) closes of n-minute candles."""
    return spot[:, n - 1::n]


def _on_minutes(x: np.ndarray, n: int) -> np.ndarray:
    """A candle-level D x C array spread back to minutes (value known from the candle's last minute)."""
    out = np.repeat(x, n, axis=1)
    out = np.concatenate([np.full((x.shape[0], n - 1), np.nan), out], axis=1)[:, :x.shape[1] * n]
    return out


def _ema(x, span):
    return pd.DataFrame(x).T.ewm(span=span, adjust=False).mean().T.to_numpy()


def _rsi(x, n=14):
    d = np.diff(x, axis=1, prepend=x[:, :1])
    up = pd.DataFrame(np.maximum(d, 0)).T.ewm(alpha=1 / n, adjust=False).mean().T.to_numpy()
    dn = pd.DataFrame(np.maximum(-d, 0)).T.ewm(alpha=1 / n, adjust=False).mean().T.to_numpy()
    return 100 - 100 / (1 + up / np.maximum(dn, 1e-9))


def _cross(a, b):
    """+1 where a crosses above b, -1 below, 0 else."""
    prev = np.sign(np.roll(a - b, 1, axis=1))
    now = np.sign(a - b)
    prev[:, 0] = now[:, 0]
    return np.where((prev <= 0) & (now > 0), 1, np.where((prev >= 0) & (now < 0), -1, 0))


def build(T: dict) -> dict:
    spot, vix = T["spot"], T["vix"]
    prev_close = np.r_[np.nan, spot[:-1, -1]]
    out = {}
    c5 = _candles(spot, 5)
    m = lambda x: _on_minutes(x, 5)                                       # noqa: E731
    # trend: EMA 9 / 21 cross, SMA 20 cross, MACD cross, linear regression slope fast/slow
    x = _cross(_ema(c5, 9), _ema(c5, 21))
    out["ema9_21"] = _first(m(x) != 0, np.nan_to_num(m(x)).astype(int))
    sma = pd.DataFrame(c5).T.rolling(20).mean().T.to_numpy()
    x = _cross(c5, sma)
    out["sma20_cross"] = _first(m(x) != 0, np.nan_to_num(m(x)).astype(int))
    macd = _ema(c5, 12) - _ema(c5, 26)
    x = _cross(macd, _ema(macd, 9))
    out["macd"] = _first(m(x) != 0, np.nan_to_num(m(x)).astype(int))
    t = np.arange(c5.shape[1])

    def slope(n):
        s = pd.DataFrame(c5).T.rolling(n).apply(lambda y: np.polyfit(np.arange(len(y)), y, 1)[0], raw=True).T.to_numpy()
        return s
    x = _cross(slope(5), slope(15))
    out["linreg_slope"] = _first(m(x) != 0, np.nan_to_num(m(x)).astype(int))
    # reversal: RSI 70/30 (sell the overbought), Bollinger close outside (fade), stochastic %K/%D from extremes
    r = _rsi(c5)
    cond = (r > 70) | (r < 30)
    out["rsi_reversal"] = _first(m(cond.astype(float)) > 0, m(np.where(r > 70, -1, 1).astype(float)).astype(int))
    out["rsi_momentum"] = _first(m(cond.astype(float)) > 0, m(np.where(r > 70, 1, -1).astype(float)).astype(int))
    mean = pd.DataFrame(c5).T.rolling(20).mean().T.to_numpy()
    sd = pd.DataFrame(c5).T.rolling(20).std().T.to_numpy()
    up, dn = c5 > mean + 2 * sd, c5 < mean - 2 * sd
    out["bb_fade"] = _first(m((up | dn).astype(float)) > 0, m(np.where(up, -1, 1).astype(float)).astype(int))
    out["bb_breakout"] = _first(m((up | dn).astype(float)) > 0, m(np.where(up, 1, -1).astype(float)).astype(int))
    hi14 = pd.DataFrame(c5).T.rolling(14).max().T.to_numpy()
    lo14 = pd.DataFrame(c5).T.rolling(14).min().T.to_numpy()
    k = 100 * (c5 - lo14) / np.maximum(hi14 - lo14, 1e-9)
    dline = pd.DataFrame(k).T.rolling(3).mean().T.to_numpy()
    x = _cross(k, dline)
    cond = ((x > 0) & (k < 20)) | ((x < 0) & (k > 80))
    out["stochastic"] = _first(m(cond.astype(float)) > 0, m(x.astype(float)).astype(int))
    # momentum: 1-minute momentum (ROC 14) beyond a level, ROC with ATR spike
    roc = (spot / np.roll(spot, 14, axis=1) - 1) * 100
    roc[:, :14] = 0
    out["momentum_1m"] = _first(np.abs(roc) > 0.25, np.sign(roc).astype(int))
    tr = pd.DataFrame(np.abs(np.diff(c5, axis=1, prepend=c5[:, :1]))).T
    atr = tr.rolling(14).mean().T.to_numpy()
    spike = tr.T.to_numpy() > 2 * atr
    roc5 = np.diff(c5, axis=1, prepend=c5[:, :1])
    out["atr_roc"] = _first(m(spike.astype(float)) > 0, m(np.sign(roc5)).astype(int))
    # opening range 09:15-09:30 breakout, its reversal, day high / low break after 11:00, last hour rejection
    hi, lo = spot[:, :15].max(axis=1)[:, None], spot[:, :15].min(axis=1)[:, None]
    brk_up, brk_dn = spot > hi, spot < lo
    out["orb"] = _first(brk_up | brk_dn, np.where(brk_up, 1, -1))
    out["orb_reversal"] = _first(brk_up | brk_dn, np.where(brk_up, -1, 1))
    run_hi = np.maximum.accumulate(spot, axis=1)
    run_lo = np.minimum.accumulate(spot, axis=1)
    nh = spot >= np.roll(run_hi, 1, axis=1)
    nl = spot <= np.roll(run_lo, 1, axis=1)
    out["day_high_low_break"] = _first(nh | nl, np.where(nh, 1, -1), lo=105)
    out["last_hour_rejection"] = _first(nh | nl, np.where(nh, -1, 1), lo=315, hi=355)
    # gap at the open (the day before's close): follow, or fade
    gap = (spot[:, 0] / prev_close - 1) * 100
    has = np.abs(gap) > 0.5
    bar = np.where(has, 1, -1)
    out["gap_follow"] = (bar, np.sign(gap).astype(int))
    out["gap_fade"] = (bar, -np.sign(gap).astype(int))
    # volatility: VIX up or down more than 5% on the day before's close by 09:20
    vprev = np.r_[np.nan, vix[:-1, -1]]
    vchg = (vix[:, 5] / vprev - 1) * 100
    out["vix_spike"] = (np.where(np.abs(vchg) > 5, 6, -1), np.ones(len(vchg), dtype=int))
    # every day at 09:20 with the direction of the first five minutes (for the direction-based condors and spreads)
    out["open_direction"] = (np.full(len(spot), 6), np.where(spot[:, 5] >= spot[:, 0], 1, -1))
    return out
