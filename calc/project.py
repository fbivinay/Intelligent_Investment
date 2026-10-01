"""Projection, an ESTIMATE: resample an option's own past daily returns into many futures and tax the value at the horizon on today's rules.

Stationary block bootstrap (blocks of about a month, so calm and stormy spells stay together), 2,000 paths. The value at the horizon is taxed as one sale on
2026-09-30's rules (rules assumed unchanged), split by the holding's tax classes, through engine.tax.investment_tax at a grid of values and interpolated. The past
fifteen years were a strong run for Indian equity; resampling them can flatter the future. Charges of the final sale are left out.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import numpy as np

from calc.product import rules
from engine.tax import CGEvent, Carry, TaxProfile, fy_of, investment_tax
from engine.trace import const

PATHS = 2000
BLOCK = 21
SALE_DAY = date(2026, 9, 30)               # today's rules: those in force on the data's last day
NEW_BUCKETS = date(2023, 4, 1)             # a purchase today falls in the post-2023 buckets
LABEL = "ESTIMATE: past returns resampled, rules assumed unchanged; not a forecast or a promise"


def bootstrap(returns: np.ndarray, days: int, paths: int = PATHS, seed: int = 0, checkpoints: int = 1, block: int = BLOCK) -> np.ndarray:
    """paths x (checkpoints + 1) growth multiples at equally spaced days from 0 to `days`."""
    r = np.log1p(np.asarray(returns, dtype=float))
    n, rng = len(r), np.random.default_rng(seed)
    marks = np.linspace(0, days, checkpoints + 1).round().astype(int)
    out = np.ones((paths, checkpoints + 1))
    for lo in range(0, paths, 500):
        k = min(500, paths - lo)
        restart = rng.random((k, days)) < 1.0 / block
        restart[:, 0] = True
        start = rng.integers(0, n, (k, days))
        t = np.arange(days)
        began = np.maximum.accumulate(np.where(restart, t, 0), axis=1)
        idx = (np.take_along_axis(start, began, axis=1) + t - began) % n
        cum = np.concatenate([np.zeros((k, 1)), np.cumsum(r[idx], axis=1)], axis=1)
        out[lo:lo + k] = np.exp(cum[:, marks])
    return out


def tax_curve(amount: Decimal, split: dict, years: float, profile: TaxProfile, grid: int = 40, top: float = 20.0):
    """A function of the value multiple at the horizon: the tax of selling it all then, split by tax class, on today's rules."""
    acq = max(SALE_DAY - timedelta(days=round(365.25 * years)), NEW_BUCKETS)
    ms = np.unique(np.r_[1.0, np.geomspace(1.0001, top, grid)])
    taxes = []
    for m in ms:
        events = [CGEvent(f"{cls} at the horizon", SALE_DAY, cls, acq, const("Value at the horizon", Decimal(repr(float(float(amount) * m * w)))), const("Sale costs", Decimal(0)),
                          const("Cost", Decimal(repr(float(float(amount) * w))))) for cls, w in split.items() if w > 0]
        taxes.append(float(investment_tax(rules(), fy_of(SALE_DAY), profile, events, Carry()).extra.value))
    ms, taxes = np.r_[0.0, ms], np.r_[0.0, taxes]

    def curve(m):
        m = np.asarray(m, dtype=float)
        inside = np.interp(m, ms, taxes)
        beyond = taxes[-1] + (m - ms[-1]) * (taxes[-1] - taxes[-2]) / (ms[-1] - ms[-2])        # past the grid: the last slope
        return np.where(m <= 1.0, 0.0, np.where(m > ms[-1], beyond, inside))
    return curve


def project(returns: np.ndarray, amount: Decimal, split: dict, years: int, profile: TaxProfile, seed: int = 0) -> dict:
    if not 1 <= years <= 20:
        raise ValueError("the projection horizon is 1 to 20 years")
    paths = bootstrap(returns, days=252 * years, seed=seed, checkpoints=years)
    a = float(amount)
    final = a * paths[:, -1]
    after = final - tax_curve(amount, split, years, profile)(paths[:, -1])
    q = lambda x, p: float(np.percentile(x, p))
    fan = [{"year": y, "p10": q(a * paths[:, y], 10), "p50": q(a * paths[:, y], 50), "p90": q(a * paths[:, y], 90)} for y in range(years + 1)]
    return {"label": LABEL, "years": years, "paths": len(paths), "p10": q(final, 10), "p50": q(final, 50), "p90": q(final, 90),
            "after_tax": {"p10": q(after, 10), "p50": q(after, 50), "p90": q(after, 90)}, "chance_of_loss": float((after < a - 1e-6).mean()), "fan": fan}
