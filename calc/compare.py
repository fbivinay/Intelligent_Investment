"""The alternatives: each bought on the start day and held, through the engine's traced buy-and-hold, with the same amount, dates and tax profile; or, for a
monthly plan, bought with each payment through the engine's monthly buy-and-hold.

ETFs at the start day's close in whole units, in a demat account (opening, yearly and depository fees); funds at the start day's NAV in units to three decimals,
held with the fund house (no demat fees). Both endings: everything sold on the last day, or still holding (`held=False` skips the second: the website's
lean answers show only the sale).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import numpy as np

from calc import paths
from calc.options import Option, history
from calc.product import rules
from engine.scenario import Result, buy_and_hold, buy_monthly
from engine.tax import TaxProfile


@dataclass
class OptionRun:
    option: Option
    sold: Result
    held: Result | None          # None when the run was asked for the sale only
    plan: str
    units: Decimal
    buy_price: Decimal
    dates: list[str]
    values: list[float]          # daily value of the holding (units at the day's price plus the cash left over), for the chart
    growth_sold: float           # a year: plain growth for one payment, the plan's XIRR for monthly payments
    growth_held: float | None
    worst_fall: float
    paid: list[float] = None     # rupees paid in on each of the days (the first day's included)


def run_option(o: Option, amount: Decimal, start: date, end: date, profile: TaxProfile, monthly: bool = False, held: bool = True) -> OptionRun:
    """`monthly`: `amount` is paid on each day of paths.schedule(start, end) instead of once. `held`: also work out the ending that keeps the holding."""
    bars, dividends, plan = history(o, start)
    fund = o.kind == "fund"
    kw = dict(instrument=o.id, instrument_class=o.instrument_class, bars=bars, dividends=dividends, profile=profile,
              unit_step=Decimal("0.001") if fund else Decimal(1), demat=not fund)
    if monthly:
        last = max((b.on for b in bars if b.on <= end), default=start)       # a payment due after the last price day cannot buy
        return _monthly(o, plan, kw, [(d, amount) for d in paths.schedule(start, last)], end, held)
    sold = buy_and_hold(rules(), sell_at_end=True, amount=amount, start=start, end=end, **kw)
    kept = buy_and_hold(rules(), sell_at_end=False, amount=amount, start=start, end=end, **kw) if held else None
    span = [b for b in bars if sold.bought_on <= b.on <= sold.ended_on]
    buy_price = span[0].close
    left = amount - sold.waterfall["buy_charges"].value - sold.units * buy_price
    values = [float(sold.units * b.close + left) for b in span]
    peak, worst = values[0], 0.0
    for v in values:
        peak = max(peak, v)
        worst = max(worst, 1 - v / peak)
    years = (span[-1].on - span[0].on).days / 365.25
    grow = lambda v: (float(v) / float(amount)) ** (1 / years) - 1 if v > 0 and years > 0 else -1.0
    return OptionRun(o, sold, kept, plan, sold.units, buy_price, [b.on.isoformat() for b in span], values, grow(sold.net.value),
                     grow(kept.net.value) if kept else None, worst, [float(amount)] + [0.0] * (len(span) - 1))


def _monthly(o: Option, plan: str, kw: dict, payments: list[tuple[date, Decimal]], end: date, held: bool = True) -> OptionRun:
    sold = buy_monthly(rules(), payments=payments, end=end, sell_at_end=True, **kw)
    kept = buy_monthly(rules(), payments=payments, end=end, sell_at_end=False, **kw) if held else None
    span = [b for b in kw["bars"] if sold.buys[0][0] <= b.on <= sold.ended_on]
    days = [b.on for b in span]
    units, cash, paid = np.zeros(len(span)), np.zeros(len(span)), np.zeros(len(span))
    for on, amt, q, spent in sold.buys:                    # from its day on: the units it bought, and the money it left as cash
        i = days.index(on)
        units[i:] += float(q)
        cash[i:] += float(amt - spent)
        paid[i] += float(amt)
    values = units * np.array([float(b.close) for b in span]) + cash
    flows = lambda net: [(on, -float(amt)) for on, amt, _, _ in sold.buys] + [(sold.ended_on, float(net))]      # noqa: E731
    return OptionRun(o, sold, kept, plan, sold.units, span[0].close, [d.isoformat() for d in days], [float(v) for v in values],
                     paths.xirr(flows(sold.net.value)), paths.xirr(flows(kept.net.value)) if kept else None,
                     float(paths.drawdown(paths.growth_index(values, paid)).max()), [float(x) for x in paid])
