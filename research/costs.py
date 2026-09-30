"""Trading costs for the fast simulator, worked out from the exact engine so the two cannot drift.

A charge is (nearly) linear in the order value, but brokerage can be a flat fee or the lower of a flat fee and a percentage, and every line is rounded to the paisa.
So for each regime (a run of days between two dates on which any charge rule changes) and each instrument class and side, the engine's own total is recorded at a
grid of order sizes (`SIZES`) and the simulator interpolates. Depository charges (one event per sale of ETF units) are added to ETF sells. The yearly demat fee and
the opening fee are fixed costs on their own days. Slippage is an assumption, labelled, and lives here.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import numpy as np

from engine.charges import Order, account_opening_fee, amc_fee, dp_charge, order_charges
from engine.rules import Rules
from engine.tax import fy_end, fy_of

SIZES = np.array([1e3, 1e4, 5e4, 1e5, 2.5e5, 5e5, 1e6, 2.5e6, 5e6, 1e7, 5e7, 1e8])
CLASSES = ("etf_equity", "etf_gold", "mf_debt")
SIDES = ("buy", "sell")
CHARGE_RULES = ("fyers.brokerage", "charges.stt", "charges.exchange_txn", "charges.sebi", "charges.ipft", "charges.clearing", "charges.stamp", "charges.gst",
                "fyers.dp", "charges.dp_depository")

# Slippage (assumed, labelled): a half-spread per instrument plus an impact that grows with the square root of the order's share of a normal day's traded value.
HALF_SPREAD = {"NIFTYBEES": 0.0003, "JUNIORBEES": 0.0008, "BANKBEES": 0.0006, "GOLDBEES": 0.0006, "CASH": 0.0}
IMPACT = 0.005
MAX_SLIPPAGE = 0.03


@dataclass(frozen=True)
class CostTable:
    values: np.ndarray        # R x 3 classes x 2 sides x len(SIZES): rupees, ETF sells include the depository charge
    dates: tuple              # the date each regime was evaluated on


def regimes(rules: Rules, days: list[date]):
    """(regime start dates, for each day the index of the regime it falls in). A regime starts on any date a charge rule row starts."""
    starts = sorted({r.valid_from for t in CHARGE_RULES for r in rules.tables[t].all_rows()})
    return starts, np.array([max(0, bisect_right(starts, d) - 1) for d in days])


def charge_table(rules: Rules, regime_dates) -> CostTable:
    vals = np.zeros((len(regime_dates), len(CLASSES), 2, len(SIZES)))
    price = Decimal(100)
    for r, on in enumerate(regime_dates):
        dp = float(dp_charge(rules, on).value)
        for c, cls in enumerate(CLASSES):
            for s, side in enumerate(SIDES):
                for k, v in enumerate(SIZES):
                    total = float(order_charges(rules, Order(on, cls, side, Decimal(repr(float(v))) / price, price)).total.value)
                    vals[r, c, s, k] = total + (dp if (side == "sell" and cls != "mf_debt") else 0.0)
    return CostTable(vals, tuple(regime_dates))


def charge_array(values: np.ndarray, reg: int, c: int, s: int, value: float) -> float:
    """Charges on an order of `value` rupees; linear between grid sizes, proportional to zero below the first and beyond the last."""
    if value <= 0:
        return 0.0
    row = values[reg, c, s]
    if value <= SIZES[0]:
        return float(row[0] * value / SIZES[0])
    if value >= SIZES[-1]:
        return float(row[-1] * value / SIZES[-1])
    return float(np.interp(value, SIZES, row))


def charge(table: CostTable, reg: int, cls: str, side: str, value: float) -> float:
    return charge_array(table.values, reg, CLASSES.index(cls), SIDES.index(side), value)


def fixed_costs(rules: Rules, days: list[date]) -> np.ndarray:
    """Rupees charged to the account on each day: the opening fee on the first day, the yearly demat fee on the last trading day of each full financial year."""
    out = np.zeros(len(days))
    out[0] += float(account_opening_fee(rules, days[0]).value)
    for fy in range(fy_of(days[0]), fy_of(days[-1]) + 1):
        end = fy_end(fy)
        if end > days[-1]:
            continue                                       # a financial year that has not ended: its fee is not due yet
        i = bisect_right(days, end) - 1
        out[i] += float(amc_fee(rules, days[i], days[0]).value)
    return out


def slippage_rate(asset: str, order_value: float, adv: float) -> float:
    """Fraction of the price lost on a fill: a half-spread plus impact. `adv` is the past average daily traded value; a missing or zero one means 'the whole
    day's trading', the worst case, never a division by zero."""
    if order_value <= 0 or asset == "CASH":
        return 0.0
    part = 1.0 if not (adv == adv and adv > 0) else min(order_value / adv, 1.0)
    return min(HALF_SPREAD[asset] + IMPACT * part ** 0.5, MAX_SLIPPAGE)
