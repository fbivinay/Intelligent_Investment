"""Black-Scholes prices and implied volatility, vectorised (no dividend; the rate is the caller's)."""
from __future__ import annotations

import numpy as np
from scipy.special import ndtr


def price(s, k, t, vol, r, cp):
    """cp = 1 call, -1 put. Arrays broadcast."""
    s, k, t, vol, cp = np.broadcast_arrays(*(np.asarray(x, dtype=float) for x in (s, k, t, vol, cp)))
    sq = vol * np.sqrt(t)
    with np.errstate(divide="ignore", invalid="ignore"):
        d1 = (np.log(s / k) + (r + 0.5 * vol * vol) * t) / sq
    d2 = d1 - sq
    disc = np.exp(-r * t)
    out = cp * (s * ndtr(cp * d1) - k * disc * ndtr(cp * d2))
    return np.where(sq > 0, out, np.maximum(cp * (s - k), 0.0))


def implied(p, s, k, t, r, cp, lo=0.01, hi=3.0, iters=60):
    """Volatility that prices each option at p, by bisection; NaN where p is missing or outside the no-arbitrage range."""
    p, s, k, t, cp = np.broadcast_arrays(*(np.asarray(x, dtype=float) for x in (p, s, k, t, cp)))
    a, b = np.full(p.shape, lo), np.full(p.shape, hi)
    ok = np.isfinite(p) & (p > price(s, k, t, lo, r, cp)) & (p < price(s, k, t, hi, r, cp))
    for _ in range(iters):
        m = (a + b) / 2
        up = price(s, k, t, m, r, cp) > p
        b = np.where(up, m, b)
        a = np.where(up, a, m)
    return np.where(ok, (a + b) / 2, np.nan)


if __name__ == "__main__":
    v = implied(price(22000, 22100, 3 / 365, 0.14, 0.065, 1), 22000, 22100, 3 / 365, 0.065, 1)
    assert abs(float(v) - 0.14) < 1e-6, v
    print("ok")
