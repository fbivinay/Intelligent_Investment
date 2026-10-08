"""The product for a user: an account that follows the signal artifact of one risk level from the start day to the end day, its orders decided by the fast
simulator and booked exactly by calc.replay. Two models: "six" (six ETFs: the four plus the Midcap 100 and Nasdaq 100 ETFs, four levels) and "four" (the
four-ETF model of the frozen test, three levels).

The account has no drawdown governor of its own: it follows the reference account's governed weights (sub-project 3 spec), so its own drawdown can exceed the cap.
The smallest order is Rs 5,000 or 0.5% of the amount, whichever is smaller, so small accounts still follow the weights.
"""
from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import numpy as np

from calc import paths, replay as R
from calc.options import MAX_START, PRODUCT_START
from engine.charges import amc_fee
from engine.rules import Rules
from engine.tax import TaxProfile
from research import artifact as A, causal, maxmodel as X, panel as P, sim

ROOT = Path(__file__).resolve().parents[1]
DATA_END = date(2026, 9, 30)
MIN_AMOUNT = Decimal(10000)
MIN_PAYMENT = Decimal(1000)        # a monthly plan's smallest payment
MODELS = {"six": (P.GROWTH, A.SIGNAL_SIX, (*A.LEVELS_SIX, "Max", "LSTM")), "four": (P.ASSETS, A.SIGNAL, tuple(A.LEVELS))}     # assets, signal folder, levels
LSTM_SIGNAL = ROOT / "research" / "out" / "signal_lstm"          # the LSTM strategy's weights (research/lstm_result.py signal)
BAND = {"LSTM": 0.05}                                             # the trade band a level was tested with (the simulator's default otherwise)
LEVELS = MODELS["six"][2]


@lru_cache(maxsize=1)
def rules() -> Rules:
    return Rules.load(ROOT / "rules")


def start_of(level: str) -> date:
    """The level's first day: Max holds stocks, whose data starts later; the LSTM's first weights are from its first April cut, the same day."""
    return MAX_START if level in ("Max", "LSTM") else PRODUCT_START


@lru_cache(maxsize=None)
def full_panel(model: str = "six", level: str = "") -> P.Panel:
    if level == "Max":
        return X.load_panel()                      # its own panel: the stocks it ever held, the gold and Nasdaq ETFs
    return P.load_panel(end=DATA_END.isoformat(), assets=MODELS[model][0])


@lru_cache(maxsize=None)
def _signal(level: str, model: str = "six"):
    return A.load(level, X.OUT if level == "Max" else LSTM_SIGNAL if level == "LSTM" else MODELS[model][1])


@dataclass
class ProductRun:
    level: str
    booked: R.Booked
    names: tuple                # the ETFs and the liquid fund, in the order of the weights
    dates: list[str]            # the trading days of the account
    weights: np.ndarray         # the artifact's weights it followed
    strategy: list[str]         # the strategy the product held each day
    equity: list[float]         # the fast simulator's daily marks at the close (after tax paid), for the chart
    pretax: list[float]         # the same marks with the tax paid added back: the returns a projection resamples
    drawdown: list[float]
    units: np.ndarray           # T x (n + 1) units held after each day's fills (the fast simulator's), for the Fyers preview
    prices: np.ndarray          # T x (n + 1) closing prices (the fund: its total-return index), to value those units
    sim_final: float
    gap: float                  # exact books (still holding) less the fast simulator's, the yearly fee of the year in progress allowed for
    growth_sold: float          # a year: plain growth for one payment, the plan's XIRR for monthly payments
    growth_held: float
    worst_fall: float           # before tax, payments left out (calc.paths.growth_index)
    paid: list[float] = None    # rupees paid in on each day (the first day's included)
    invested: Decimal = Decimal(0)


def run(level: str, amount: Decimal, start: date, end: date, profile: TaxProfile, slippage: bool = True, model: str = "six", monthly: bool = False) -> ProductRun:
    """`monthly`: `amount` is paid on each day of calc.paths.schedule (the first trading day on or after it) instead of once."""
    if model not in MODELS:
        raise KeyError(f"unknown model {model!r}; the models are {tuple(MODELS)}")
    if level not in MODELS[model][2]:
        raise KeyError(f"unknown risk level {level!r}; the levels are {MODELS[model][2]}")
    if start < start_of(level):
        raise ValueError(f"the {level} level's history starts {start_of(level).isoformat()} (its first pick); choose a start on or after it")
    if end <= start:
        raise ValueError("the end date must be after the start date")
    if end > DATA_END:
        raise ValueError(f"the data ends {DATA_END.isoformat()}")
    if monthly and amount < MIN_PAYMENT:
        raise ValueError(f"a monthly plan needs at least Rs {MIN_PAYMENT:,} a month")
    if not monthly and amount < MIN_AMOUNT:
        raise ValueError(f"the model needs at least Rs {MIN_AMOUNT:,} to hold its mix of ETFs")
    panel, rl = full_panel(model, "Max" if level == "Max" else ""), rules()
    sig_dates, sig_w, sig_strategy = _signal(level, model)
    i0 = int(np.searchsorted(panel.dates, np.datetime64(start)))
    i1 = int(np.searchsorted(panel.dates, np.datetime64(end), side="right")) - 1
    if i1 - i0 < 2:
        raise ValueError("the period holds fewer than three trading days")
    window = causal.truncate(P.from_day(panel, i0), i1 - i0 + 1)
    s0 = int(np.searchsorted(sig_dates, panel.dates[i0]))
    if sig_dates[s0] != panel.dates[i0]:
        raise ValueError("the signal and the price data do not share a calendar")
    w = sig_w[s0:s0 + len(window.dates)]
    days = [date.fromisoformat(str(d)) for d in window.dates]
    paid = np.zeros(len(days))
    for d in (paths.schedule(start, days[-1]) if monthly else [start]):
        paid[bisect_left(days, d)] += float(amount)                           # the first trading day on or after the payment's date
    invested = amount * int(np.count_nonzero(paid))
    cfg = sim.SimConfig(capital=paid[0], governor=False, harvest=True, slippage=slippage, profile=profile, min_trade=min(5000.0, float(amount) * 0.005),
                        max_orders=200_000, band=BAND.get(level, sim.SimConfig.band))
    r = sim.simulate(window, w, rl, cfg, deposits=np.r_[0.0, paid[1:]])
    booked = R.book(rl, window, r.order_log, invested, profile)
    last_fee = float(amc_fee(rl, days[-1], days[0]).value)                     # the books charge the year in progress; the simulator does not
    pretax = r.equity + np.cumsum(r.tax_paid)
    if monthly:
        flows = lambda v: [(days[t], -paid[t]) for t in np.nonzero(paid)[0]] + [(days[-1], float(v))]      # noqa: E731
        grow = lambda v: paths.xirr(flows(v))                                                             # noqa: E731
        worst = float(paths.drawdown(paths.growth_index(pretax, paid)).max())
    else:
        years = (days[-1] - days[0]).days / 365.25
        grow = lambda v: (float(v) / float(amount)) ** (1 / years) - 1 if v > 0 else -1.0                   # noqa: E731
        worst = float(r.drawdown.max())
    return ProductRun(level, booked, R.names_of(window), [d.isoformat() for d in days], w, sig_strategy[s0:s0 + len(days)], [float(x) for x in r.equity],
                      [float(x) for x in pretax], [float(x) for x in r.drawdown], r.units, np.column_stack([window.close, window.cash]),
                      float(r.equity[-1] - r.pending_tax), float(booked.held.value) - (float(r.equity[-1] - r.pending_tax) - last_fee),
                      grow(booked.sold.value), grow(booked.held.value), worst, [float(x) for x in paid], invested)
