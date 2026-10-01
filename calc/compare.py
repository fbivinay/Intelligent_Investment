"""The alternatives: each bought on the start day and held, through the engine's traced buy-and-hold, with the same amount, dates and tax profile.

ETFs at the start day's close in whole units, in a demat account (opening, yearly and depository fees); funds at the start day's NAV in units to three decimals,
held with the fund house (no demat fees). Both endings: everything sold on the last day, or still holding.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from calc.options import Option, history
from calc.product import rules
from engine.scenario import Result, buy_and_hold
from engine.tax import TaxProfile


@dataclass
class OptionRun:
    option: Option
    sold: Result
    held: Result
    plan: str
    units: Decimal
    buy_price: Decimal
    dates: list[str]
    values: list[float]          # daily value of the holding (units at the day's price plus the cash left over), for the chart
    growth_sold: float
    growth_held: float
    worst_fall: float


def run_option(o: Option, amount: Decimal, start: date, end: date, profile: TaxProfile) -> OptionRun:
    bars, dividends, plan = history(o, start)
    fund = o.kind == "fund"
    kw = dict(instrument=o.id, instrument_class=o.instrument_class, bars=bars, dividends=dividends, amount=amount, start=start, end=end, profile=profile,
              unit_step=Decimal("0.001") if fund else Decimal(1), demat=not fund)
    sold, held = buy_and_hold(rules(), sell_at_end=True, **kw), buy_and_hold(rules(), sell_at_end=False, **kw)
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
    return OptionRun(o, sold, held, plan, sold.units, buy_price, [b.on.isoformat() for b in span], values, grow(sold.net.value), grow(held.net.value), worst)
