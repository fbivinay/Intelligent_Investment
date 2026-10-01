"""The product for a user: an account that follows the signal artifact of one risk level from the start day to the end day, its orders decided by the fast
simulator and booked exactly by calc.replay.

The account has no drawdown governor of its own: it follows the reference account's governed weights (sub-project 3 spec), so its own drawdown can exceed the cap.
The smallest order is Rs 5,000 or 0.5% of the amount, whichever is smaller, so small accounts still follow the weights.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import numpy as np

from calc import replay as R
from calc.options import PRODUCT_START
from engine.charges import amc_fee
from engine.rules import Rules
from engine.tax import TaxProfile
from research import artifact as A, causal, panel as P, sim

ROOT = Path(__file__).resolve().parents[1]
DATA_END = date(2026, 9, 30)
MIN_AMOUNT = Decimal(10000)
LEVELS = tuple(A.LEVELS)


@lru_cache(maxsize=1)
def rules() -> Rules:
    return Rules.load(ROOT / "rules")


@lru_cache(maxsize=1)
def full_panel() -> P.Panel:
    return P.load_panel(end=DATA_END.isoformat())


@lru_cache(maxsize=None)
def _signal(level: str):
    return A.load(level)


@dataclass
class ProductRun:
    level: str
    booked: R.Booked
    dates: list[str]            # the trading days of the account
    weights: np.ndarray         # the artifact's weights it followed
    strategy: list[str]         # the strategy the product held each day
    equity: list[float]         # the fast simulator's daily marks at the close (after tax paid), for the chart
    drawdown: list[float]
    sim_final: float
    gap: float                  # exact books (still holding) less the fast simulator's, the yearly fee of the year in progress allowed for
    growth_sold: float
    growth_held: float
    worst_fall: float


def run(level: str, amount: Decimal, start: date, end: date, profile: TaxProfile, slippage: bool = True) -> ProductRun:
    if level not in LEVELS:
        raise KeyError(f"unknown risk level {level!r}; the levels are {LEVELS}")
    if start < PRODUCT_START:
        raise ValueError(f"the model's history starts {PRODUCT_START.isoformat()} (its first yearly pick); choose a start on or after it")
    if end <= start:
        raise ValueError("the end date must be after the start date")
    if end > DATA_END:
        raise ValueError(f"the data ends {DATA_END.isoformat()}")
    if amount < MIN_AMOUNT:
        raise ValueError(f"the model needs at least Rs {MIN_AMOUNT:,} to hold its mix of ETFs")
    panel, rl = full_panel(), rules()
    sig_dates, sig_w, sig_strategy = _signal(level)
    i0 = int(np.searchsorted(panel.dates, np.datetime64(start)))
    i1 = int(np.searchsorted(panel.dates, np.datetime64(end), side="right")) - 1
    if i1 - i0 < 2:
        raise ValueError("the period holds fewer than three trading days")
    window = causal.truncate(P.from_day(panel, i0), i1 - i0 + 1)
    s0 = int(np.searchsorted(sig_dates, panel.dates[i0]))
    if sig_dates[s0] != panel.dates[i0]:
        raise ValueError("the signal and the price data do not share a calendar")
    w = sig_w[s0:s0 + len(window.dates)]
    cfg = sim.SimConfig(capital=float(amount), governor=False, harvest=True, slippage=slippage, profile=profile, min_trade=min(5000.0, float(amount) * 0.005))
    r = sim.simulate(window, w, rl, cfg)
    booked = R.book(rl, window, r.order_log, amount, profile)
    days = [date.fromisoformat(str(d)) for d in window.dates]
    last_fee = float(amc_fee(rl, days[-1], days[0]).value)                     # the books charge the year in progress; the simulator does not
    years = (days[-1] - days[0]).days / 365.25
    grow = lambda v: (float(v) / float(amount)) ** (1 / years) - 1 if v > 0 else -1.0
    return ProductRun(level, booked, [d.isoformat() for d in days], w, sig_strategy[s0:s0 + len(days)], [float(x) for x in r.equity], [float(x) for x in r.drawdown],
                      float(r.equity[-1] - r.pending_tax), float(booked.held.value) - (float(r.equity[-1] - r.pending_tax) - last_fee),
                      grow(booked.sold.value), grow(booked.held.value), float(r.drawdown.max()))
