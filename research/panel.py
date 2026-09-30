"""The research panel: one aligned daily table for the strategy work, built from the processed data files.

Rows are the trading days every ETF has a row for; columns are arrays (T x 4 for the ETFs, T for the rest). Prices are split-adjusted (data/adjust.py), so units
are counted on the current unit size. The cash leg is a liquid fund's total return index (daily NAV returns; the regular plan to the splice date, the direct plan
after), because LIQUIDBEES' own price is flat. `end` cuts every array; the default is the end of the design period, so the frozen test years are never loaded by
accident.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np

DATA = Path(__file__).resolve().parents[1] / "data"
ASSETS = ["NIFTYBEES", "JUNIORBEES", "BANKBEES", "GOLDBEES"]
LIQUID_REGULAR, LIQUID_DIRECT = "100851", "118701"      # Nippon India Liquid Fund, regular plan and direct plan
SPLICE = date(2013, 1, 1)                               # the direct plan's first day
DESIGN_END = "2023-09-30"                               # the last 3 years (2023-10-01 on) stay frozen until the design is final


@dataclass(frozen=True)
class Panel:
    dates: np.ndarray            # datetime64[D], T
    assets: list[str]
    open: np.ndarray             # T x 4, split-adjusted
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    value: np.ndarray            # T x 4, traded value in rupees (as published)
    vwap: np.ndarray             # T x 4, traded value / traded quantity on the adjusted unit size: the price a fill is taken at
    cash: np.ndarray             # T, liquid fund total return index, 1.0 on the first day
    nifty: np.ndarray            # T, Nifty 50 close
    vix: np.ndarray              # T, India VIX close (NaN before it exists)
    pe: np.ndarray               # T, Nifty 50 P/E (NaN before 2012-07)
    pb: np.ndarray               # T, Nifty 50 P/B
    special_days: tuple[str, ...] = ()   # weekend sessions only some ETFs traded (gold ETFs on Akshaya Tritiya and Dhanteras): not in the table


def _rows(path: Path):
    with path.open(newline="") as f:
        yield from csv.DictReader(f)


def _num(s: str) -> float:
    return float(s) if s not in ("", None) else float("nan")


def _cash_index(root: Path, days: list[date]) -> np.ndarray:
    """Liquid fund total return index on the trading days. Chained over calendar days (liquid funds publish a NAV every day, weekends included):
    the regular plan's daily return up to the splice date, the direct plan's after it."""
    nav: dict[str, dict[date, float]] = {LIQUID_REGULAR: {}, LIQUID_DIRECT: {}}
    for r in _rows(root / "processed" / "amfi_nav_adjusted.csv"):
        if r["code"] in nav:
            nav[r["code"]][date.fromisoformat(r["date"])] = float(r["adj_nav"])
    if not nav[LIQUID_REGULAR]:
        raise ValueError(f"no NAV rows for the liquid fund {LIQUID_REGULAR}")
    first, last = days[0], days[-1]
    level, level_on, prev = 1.0, {first: 1.0}, {k: None for k in nav}
    c = first
    # NAV of the day or the last one before it (a fund may skip a day)
    def at(code, d):
        while d not in nav[code]:
            d -= timedelta(days=1)
            if d < first - timedelta(days=30):
                raise ValueError(f"liquid fund {code} has no NAV near {first}")
        return nav[code][d]

    while c < last:
        nxt = c + timedelta(days=1)
        code = LIQUID_REGULAR if nxt <= SPLICE else LIQUID_DIRECT
        level *= at(code, nxt) / at(code, c)
        level_on[nxt] = level
        c = nxt
    return np.array([level_on[d] for d in days])


def load_panel(root: Path = DATA, end: str = DESIGN_END) -> Panel:
    root = Path(root)
    by_sym: dict[str, dict[date, tuple]] = {s: {} for s in ASSETS}
    for r in _rows(root / "processed" / "etf_daily_adjusted.csv"):
        if r["symbol"] in by_sym and r["series"] == "EQ" and r["date"] <= end:
            by_sym[r["symbol"]][date.fromisoformat(r["date"])] = (float(r["adj_open"]), float(r["adj_high"]), float(r["adj_low"]), float(r["adj_close"]), float(r["value"]), float(r["adj_qty"]))
    days = sorted(set().union(*[set(d) for d in by_sym.values()]))
    if not days:
        raise ValueError("no ETF rows up to " + end)
    special = [d for d in days if d.weekday() >= 5 and not all(d in by_sym[s] for s in ASSETS)]
    days = [d for d in days if d not in special]
    for s in ASSETS:
        missing = [d for d in days if d not in by_sym[s]]
        if missing:
            raise ValueError(f"{s} has no row on {missing[0].isoformat()} ({len(missing)} days) while another ETF has: the panel needs every ETF on every weekday")
    o, h, lo, c, v, q = (np.array([[by_sym[s][d][k] for s in ASSETS] for d in days]) for k in range(6))
    with np.errstate(divide="ignore", invalid="ignore"):
        vwap = v / q
    bad = np.argwhere(~((vwap >= lo * 0.99) & (vwap <= h * 1.01)))      # also catches a day with no quantity
    if len(bad):
        i, j = bad[0]
        raise ValueError(f"{ASSETS[j]} on {days[i].isoformat()}: VWAP {vwap[i, j]:.4f} is outside the day's range {lo[i, j]} to {h[i, j]} ({len(bad)} cases); "
                         "the traded quantity and the prices are not on the same unit size")
    idx: dict[str, dict[date, dict]] = {"Nifty 50": {}, "India VIX": {}}
    for r in _rows(root / "processed" / "nse_index_daily.csv"):
        if r["name"] in idx and r["date"] <= end:
            idx[r["name"]][date.fromisoformat(r["date"])] = r
    pick = lambda name, col: np.array([_num(idx[name].get(d, {}).get(col, "")) for d in days])  # noqa: E731
    return Panel(dates=np.array(days, dtype="datetime64[D]"), assets=list(ASSETS), open=o, high=h, low=lo, close=c, value=v, vwap=vwap, cash=_cash_index(root, days),
                 nifty=pick("Nifty 50", "close"), vix=pick("India VIX", "close"), pe=pick("Nifty 50", "pe"), pb=pick("Nifty 50", "pb"),
                 special_days=tuple(d.isoformat() for d in special))
