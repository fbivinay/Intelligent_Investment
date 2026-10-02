"""Nifty futures as an overlay: the return of holding the near-month NIFTY future, rolled, per rupee of exposure, after charges and slippage.

The near contract is held until `roll` trading days before its expiry, then swapped at that day's close for the next one. A future's return is the
index's minus the carry (about the cash rate), so exposure through futures costs that carry and needs only margin. Charges: the engine's own on each
roll (both legs), slippage `slip` a side. Tax is not here: futures gains are business income (taxed at slab rates through engine.tax with Business).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd

from engine.charges import Order, order_charges
from engine.rules import Rules

ROOT = Path(__file__).resolve().parents[1]


def rolled(symbol="NIFTY", roll=3, slip=0.0002, rules: Rules | None = None) -> pd.Series:
    """Daily return of one rupee of exposure in the rolled near future, after roll costs (charged on the roll day)."""
    rules = rules or Rules.load(ROOT / "rules")
    df = pd.read_csv(ROOT / "data" / "processed" / "nse_index_futures_daily.csv", parse_dates=["date", "expiry"])
    df = df[df.symbol == symbol].assign(px=lambda x: x.close.where(x.close > 0, x.settle))     # a contract with no trade that day: its settlement price
    px = df.pivot_table(index="date", columns="expiry", values="px")
    days = px.index
    listed = df.groupby("date").expiry.apply(sorted)                       # the contracts each day really has (NSE re-dated some expiries)
    out = pd.Series(0.0, index=days)
    held = None
    for k, d in enumerate(days):
        live = listed[d]
        pos = days.searchsorted(live[0]) if live else len(days)
        near = live[0] if (pos - k) > roll or len(live) < 2 else live[1]   # trading days left to the near expiry
        if held is not None:
            prev = days[k - 1]
            out[d] = px.at[d, held] / px.at[prev, held] - 1 if held in live else 0.0
        if held != near:
            if held is not None:
                p = px.at[d, near]
                cost = sum(float(order_charges(rules, Order(d.date(), "fut_index", side, Decimal(1000), Decimal(repr(round(float(p), 2))))).total.value)
                           for side in ("buy", "sell")) / (1000 * p)
                out[d] -= 2 * slip + cost
            held = near
    return out


if __name__ == "__main__":
    r = rolled()
    yrs = (r.index[-1] - r.index[0]).days / 365.25
    print("rolled NIFTY future", r.index[0].date(), r.index[-1].date(), "growth a year", round((1 + r).prod() ** (1 / yrs) - 1, 4))
