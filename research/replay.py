"""The replay check: every order the fast simulator placed, priced again by the exact engine (Decimal, the engine's own rounding), against the charges the simulator
took from its interpolated tables. Taxes need no replay: the simulator already hands each financial year's sales to engine.tax.investment_tax.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import numpy as np

from engine.charges import Order, dp_charge, order_charges
from engine.rules import Rules
from research.sim import ASSET_CLASS, Result


def exact_charges(rules: Rules, days: list[date], log: np.ndarray) -> np.ndarray:
    """The engine's charges for each order of the log, plus the depository charge on a sale of ETF units."""
    out = np.zeros(len(log))
    for k, (t, a, side, u, price, _) in enumerate(log):
        cls, on = ASSET_CLASS[int(a)], days[int(t)]
        ch = order_charges(rules, Order(on, cls, "sell" if side else "buy", Decimal(repr(float(u))), Decimal(repr(float(price))))).total.value
        out[k] = float(ch) + (float(dp_charge(rules, on).value) if side and cls != "mf_debt" else 0.0)
    return out


def check(r: Result, rules: Rules, days: list[date]) -> dict:
    """How far the simulator's charges are from the engine's: per order and in total, and the total as a share of the final wealth (the wealth gap, before compounding)."""
    exact = exact_charges(rules, days, r.order_log)
    taken = r.order_log[:, 5]
    gap = float(taken.sum() - exact.sum())
    return dict(orders=len(taken), sim_charges=float(taken.sum()), exact_charges=float(exact.sum()), total_gap=gap,
                max_order_gap=float(np.abs(taken - exact).max()) if len(taken) else 0.0, wealth_gap_share=gap / float(r.equity[-1]))
