"""What the calculator can show: the product at each risk level and ten alternatives, with their price or NAV history from the committed data files.

ETFs: the exchange close and high, split-adjusted (units on today's unit size), and their dividends. Funds: the NAV on today's unit size (data/nav_units.csv applied),
the direct plan from its first day in 2013, the regular plan for an earlier start (a holding cannot switch plans without a sale).
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from engine.scenario import Bar

DATA = Path(__file__).resolve().parents[1] / "data"


@dataclass(frozen=True)
class Option:
    id: str
    name: str
    kind: str                 # product | etf | fund
    instrument_class: str     # the engine's class for charges and tax ("" for the product: it holds several)
    symbol: str = ""          # ETF symbol in the exchange file
    regular: str = ""         # fund: the regular plan's scheme code
    direct: str = ""          # fund: the direct plan's scheme code
    direct_from: date | None = None
    note: str = ""


PRODUCT_START = date(2013, 4, 1)
MAX_START = date(2017, 4, 3)       # the Max level holds stocks: the stock data starts 2016-01, its first pick needs a year of it
OPTIONS = [
    Option("PRODUCT_Conservative", "Model: Conservative (10% cap)", "product", ""),
    Option("PRODUCT_Balanced", "Model: Balanced (20% cap)", "product", ""),
    Option("PRODUCT_Aggressive", "Model: Aggressive (30% cap)", "product", ""),
    Option("PRODUCT_Growth", "Model: Growth (six ETFs in equal parts, no fall guard)", "product", ""),
    Option("PRODUCT_Max", "Model: Max (stock momentum half with a market switch, gold ETF and Nasdaq 100 ETF a quarter each)", "product", "",
           note="from 2017-04-03; the gold and Nasdaq ETFs and the mix were chosen after seeing 2017-2026"),
    Option("NIFTYBEES", "Nifty 50 ETF (Nifty BeES)", "etf", "etf_equity", symbol="NIFTYBEES"),
    Option("JUNIORBEES", "Nifty Next 50 ETF (Junior BeES)", "etf", "etf_equity", symbol="JUNIORBEES"),
    Option("BANKBEES", "Nifty Bank ETF (Bank BeES)", "etf", "etf_equity", symbol="BANKBEES"),
    Option("GOLDBEES", "Gold ETF (Gold BeES)", "etf", "etf_gold", symbol="GOLDBEES"),
    Option("MOM100", "Nifty Midcap 100 ETF (Motilal Oswal)", "etf", "etf_equity", symbol="MOM100", note="before 2016 its NAV stands in for the price"),
    Option("MON100", "Nasdaq 100 ETF (Motilal Oswal)", "etf", "etf_gold", symbol="MON100",
           note="taxed as a non-equity ETF, like gold; traded above its NAV since 2022; before 2016 its NAV stands in for the price"),
    Option("NIFTY50_INDEX_FUND", "HDFC Nifty 50 index fund", "fund", "mf_equity", regular="101525", direct="119063", direct_from=date(2013, 1, 1)),
    Option("NEXT50_INDEX_FUND", "ICICI Prudential Nifty Next 50 index fund", "fund", "mf_equity", regular="112957", direct="120684", direct_from=date(2013, 1, 2)),
    Option("ARBITRAGE_FUND", "SBI Arbitrage fund", "fund", "mf_equity", regular="104457", direct="119574", direct_from=date(2013, 1, 14),
           note="taxed as an equity-oriented fund"),
    Option("LIQUID_FUND", "Nippon India Liquid fund", "fund", "mf_debt", regular="100851", direct="118701", direct_from=date(2013, 1, 1),
           note="bought after 2023-03-31, its gains are taxed at your slab rate"),
]
_BY_ID = {o.id: o for o in OPTIONS}


def get(option_id: str) -> Option:
    if option_id not in _BY_ID:
        raise KeyError(f"unknown option {option_id!r}; the options are {sorted(_BY_ID)}")
    return _BY_ID[option_id]


def _rows(name: str):
    with (DATA / name).open(newline="") as f:
        yield from csv.DictReader(f)


@lru_cache(maxsize=None)
def _etf(symbol: str) -> tuple[Bar, ...]:
    return tuple(Bar(date.fromisoformat(r["date"]), Decimal(r["adj_high"]), Decimal(r["adj_close"]))
                 for r in _rows("processed/etf_daily_adjusted.csv") if r["symbol"] == symbol)


@lru_cache(maxsize=None)
def _dividends(symbol: str) -> dict:
    path = DATA / "processed" / f"{symbol}_dividends.csv"
    return {date.fromisoformat(r["ex_date"]): Decimal(r["per_unit"]) for r in _rows(f"processed/{symbol}_dividends.csv")} if path.exists() else {}


@lru_cache(maxsize=None)
def _nav(code: str) -> tuple[Bar, ...]:
    out = [(date.fromisoformat(r["date"]), Decimal(r["adj_nav"])) for r in _rows("processed/amfi_nav_adjusted.csv") if r["code"] == code]
    return tuple(Bar(d, v, v) for d, v in sorted(out))


def first_day(o: Option, on: date | None = None) -> date:
    """The first day the option can be bought (for a fund, of the plan a start on `on` would use)."""
    if o.kind == "product":
        return MAX_START if o.id == "PRODUCT_Max" else PRODUCT_START
    if o.kind == "etf":
        return _etf(o.symbol)[0].on
    return _nav(_plan(o, on or date.min)[0])[0].on


def _plan(o: Option, start: date) -> tuple[str, str]:
    return (o.direct, "direct plan") if start >= o.direct_from else (o.regular, "regular plan (the direct plan starts " + o.direct_from.isoformat() + ")")


def history(o: Option, start: date) -> tuple[list[Bar], dict, str]:
    """Price or NAV bars from `start` on, the dividends, and which plan or market they come from."""
    if o.kind == "product":
        raise ValueError("the product has no single price history: it is replayed from its signal")
    if o.kind == "etf":
        bars, divs, plan = _etf(o.symbol), _dividends(o.symbol), "exchange"
    else:
        code, plan = _plan(o, start)
        bars, divs = _nav(code), {}
    if not bars or start < bars[0].on:
        raise ValueError(f"{o.name} can be bought from {bars[0].on.isoformat() if bars else 'no date'}; the start {start.isoformat()} is earlier")
    return [b for b in bars if b.on >= start], divs, plan
