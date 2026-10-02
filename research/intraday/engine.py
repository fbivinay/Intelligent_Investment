"""Intraday NIFTY option and futures strategies on the minute paths: one trade a day at most, closed the same day, an account that sizes by margin.

Assumptions (labelled): fills at the modelled minute price plus slippage max(0.5 point, 1% of the premium) a side, a stop fills 2% beyond its level; brokerage
Rs 20 an order (Fyers), STT on the sold premium (0.05% to 2023-03, 0.0625% to 2024-09, 0.1% to 2026-03, 0.15% after), exchange charges 0.053% of premium to
2024-09 and 0.03503% after, SEBI Rs 10 a crore, stamp 0.003% on bought premium, GST 18% on brokerage and exchange charges. Margin a lot: 12% of the Nifty's
value for a set with sold options not covered, the widest loss for a covered spread, the premium for bought options, 12% for futures. The money sits in a
liquid fund (pledged for margin) and earns its return. Futures and option income is business income: each financial year's net profit is taxed at 31.2%
(the 30% slab and cess), a loss carried to the next years.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from research.intraday import paths as PA, prep

ROOT = Path(__file__).resolve().parents[2]
def paths_file(symbol: str = "NIFTY") -> Path:
    return ROOT / "data" / "processed" / ("intraday_paths.npy" if symbol == "NIFTY" else f"intraday_paths_{symbol}.npy")
EXIT = 365                    # 15:20
TAX = 0.312
CE, PE = 0, 1


def build_paths(T: dict, symbol: str = "NIFTY") -> np.ndarray:
    """D x BARS x 2 (CE, PE) x K float32 prices on the nearest expiry, NaN where a strike has no volatility."""
    D, K = len(T["days"]), len(T["offs"])
    out = np.full((D, prep.BARS, 2, K), np.nan, dtype=np.float32)
    for i in range(D):
        _, ce, pe = PA.option_paths(T, i, 0)
        out[i, :, 0], out[i, :, 1] = ce, pe
    try:
        np.save(paths_file(symbol), out)
    except OSError:
        pass
    return out


@dataclass
class Data:
    T: dict
    P: np.ndarray             # option paths
    lot: np.ndarray           # D, Nifty lot size
    cash: np.ndarray          # D, liquid fund daily return
    fy: np.ndarray            # D, financial year
    dte: np.ndarray           # D, calendar days to the nearest expiry
    spot5: np.ndarray = field(default=None)   # D x 75, 5-minute closes


def load(symbol: str = "NIFTY") -> Data:
    T = prep.load(symbol)
    P = np.load(paths_file(symbol)) if paths_file(symbol).exists() else build_paths(T, symbol)
    days = pd.DatetimeIndex(T["days"].astype("datetime64[ns]"))
    lots = pd.read_csv(ROOT / "data" / "lot_sizes.csv", parse_dates=["expiry"])
    lots = lots[lots.symbol == symbol].sort_values("expiry")
    lot = lots.set_index("expiry").lot.reindex(days, method="bfill").fillna(lots.lot.iloc[-1]).to_numpy()
    nav = pd.read_csv(ROOT / "data" / "processed" / "amfi_nav_adjusted.csv", dtype={"code": str}, parse_dates=["date"])
    nav = nav[nav.code == "118701"].set_index("date").adj_nav.sort_index()
    nav = nav.reindex(nav.index.union(days)).ffill().reindex(days)
    cash = nav.pct_change().fillna(0).to_numpy()
    fy = np.where(days.month >= 4, days.year, days.year - 1)
    dte = (T["expiry"][:, 0] - T["days"]).astype(int)
    return Data(T, P, lot, cash, fy, dte, T["spot"][:, 4::5])


def _stt(days):
    return np.select([days < np.datetime64("2023-04-01"), days < np.datetime64("2024-10-01"), days < np.datetime64("2026-04-01")], [0.0005, 0.000625, 0.001], 0.0015)


def _exch(days):
    return np.where(days < np.datetime64("2024-10-01"), 0.00053, 0.0003503)


@dataclass(frozen=True)
class Spec:
    name: str
    family: str
    legs: tuple                   # ((CE or PE, strike offset from the money at entry, +1 bought / -1 sold), ...); direction-relative when signal gives one
    entry: int = 5                # bar (09:20); ignored when `signal` gives the bar
    exit: int = EXIT
    leg_sl: float | None = None   # sold leg stops at entry x (1 + leg_sl)
    tgt: float | None = None      # whole position closes at this profit, as a share of the premium at stake
    sl: float | None = None       # ... or at this loss
    days: str = "all"             # all | expiry | nonexpiry | dte2 (two days before expiry or nearer)
    vix: tuple | None = None      # VIX change from the day before's close at entry, within (lo, hi) in %
    signal: str | None = None     # a research.intraday.signals name: gives the entry bar and the direction per day
    futures: bool = False         # trade the Nifty itself (synthetic future) instead of options: legs ignored, direction from the signal


def _day_mask(d: Data, s: Spec) -> np.ndarray:
    m = np.ones(len(d.lot), dtype=bool)
    if s.days == "expiry":
        m &= d.dte == 0
    elif s.days == "nonexpiry":
        m &= d.dte > 0
    elif s.days == "dte2":
        m &= d.dte <= 2
    return m


def trades(d: Data, s: Spec, signals: dict | None = None) -> pd.DataFrame:
    """One row per day traded: points made per unit (after slippage), the premium at stake, margin a lot, charges a lot in rupees."""
    T, P = d.T, d.P
    D = len(d.lot)
    mask = _day_mask(d, s)
    entry = np.full(D, s.entry)
    direction = np.ones(D, dtype=int)
    if s.signal:
        e, dirn = signals[s.signal]
        entry, direction = e.copy(), dirn.copy()
        mask &= entry >= 0
    if s.vix:
        prev = np.r_[np.nan, T["vix"][:-1, -1]]
        chg = (T["vix"][np.arange(D), np.clip(entry, 0, prep.BARS - 1)] / prev - 1) * 100
        mask &= (chg >= s.vix[0]) & (chg <= s.vix[1])
    mask &= entry < s.exit
    idx = np.flatnonzero(mask)
    rows = []
    mid = len(T["offs"]) // 2
    for i in idx:
        e = int(entry[i])
        spot = T["spot"][i]
        if s.futures:
            sign = direction[i]
            path = sign * (spot[e:s.exit + 1] - spot[e])
            ref = spot[e] * 0.01                      # the premium at stake for a future: 1% of the index, so tgt/sl read as index moves of that size
            pnl, out = _close(path, ref, s, np.zeros(1), np.zeros(1))
            slip = 2 * 0.5
            rows.append((i, pnl - slip, ref, 0.12 * spot[e], 4 * 20 + 0.0002 * spot[e] * (1 + 0.18), 2))
            continue
        step = int(T["step"]) if "step" in T else prep.STEP
        shift = int(round((spot[e] - T["atm"][i]) / step))
        legs = [(t if direction[i] > 0 else 1 - t, (off if direction[i] > 0 else -off), side) for t, off, side in s.legs]
        cols = [mid + shift + off for _, off, _ in legs]
        if min(cols) < 0 or max(cols) >= len(T["offs"]):
            continue
        lp = np.stack([P[i, e:s.exit + 1, t, c] for (t, _, _), c in zip(legs, cols)], axis=1).astype(float)     # bars x legs
        if not np.isfinite(lp[0]).all() or (lp[0] <= 0.05).any():
            continue
        lp = np.nan_to_num(lp, nan=0.0)
        sides = np.array([side for _, _, side in legs], dtype=float)
        enter = lp[0]
        credit = -(sides * enter).sum()                    # >0 for a credit position
        # sold legs with their own stop: frozen at the stop level (+2%) from the first bar it is touched
        if s.leg_sl is not None:
            for j, side in enumerate(sides):
                if side < 0:
                    hit = np.flatnonzero(lp[:, j] >= enter[j] * (1 + s.leg_sl))
                    if len(hit):
                        lp[hit[0]:, j] = enter[j] * (1 + s.leg_sl) * 1.02
        mtm = (sides * (lp - enter)).sum(axis=1)           # points per unit, bar by bar
        stake = abs(credit) if abs(credit) > 0 else enter.sum()
        pnl, out = _close(mtm, stake, s, lp, enter)
        exit_px = lp[min(out, len(lp) - 1)]
        slip = (np.maximum(0.5, 0.01 * enter) + np.maximum(0.5, 0.01 * exit_px)).sum()
        sold_value = np.where(sides < 0, enter, exit_px).sum()
        bought_value = np.where(sides > 0, enter, exit_px).sum()
        n_orders = 2 * len(legs)
        if credit > 0 and (sides > 0).any():               # covered: the widest gap between a sold and a bought strike of one type, less the credit
            width = 0.0
            for t in (CE, PE):
                ks = [off * step for (tt, off, _), side in zip(legs, sides) if tt == t]
                sd = [side for (tt, _, _), side in zip(legs, sides) if tt == t]
                if -1 in sd and 1 in sd:
                    width = max(width, max(ks) - min(ks))
            margin = max(width - credit, 0.1 * width) if width else 0.12 * spot[e]
        elif credit > 0:
            margin = 0.12 * spot[e]
        else:
            margin = max(-credit, 1.0)
        rows.append((i, pnl - slip, stake, margin, None, n_orders, sold_value, bought_value))
    cols = ["i", "points", "stake", "margin_unit", "fut_cost", "orders", "sold", "bought"]
    df = pd.DataFrame([r if len(r) == 8 else (*r[:5], r[5], 0.0, 0.0) for r in rows], columns=cols)
    return df


def _close(mtm, stake, s: Spec, lp, enter):
    """Points at the close of the position: the first bar the combined target or stop is met, else the exit bar."""
    out = len(mtm) - 1
    if s.tgt is not None:
        h = np.flatnonzero(mtm >= s.tgt * stake)
        out = min(out, h[0]) if len(h) else out
    if s.sl is not None:
        h = np.flatnonzero(mtm <= -s.sl * stake)
        out = min(out, h[0]) if len(h) else out
    return float(mtm[out]), out


def account(d: Data, tr: pd.DataFrame, capital: float = 1_000_000.0, scale: float = 1.0, lo: int = 0, hi: int | None = None, whole: bool = False) -> pd.DataFrame:
    """Daily account over days lo..hi-1: lots = what the margin allows on the equity times `scale` (fractions of a lot unless `whole`: a research view, the
    real minimum is one lot), charges, the liquid fund's return after tax at the same rate, yearly tax on net trading profit."""
    days = d.T["days"]
    hi = len(days) if hi is None else hi
    D = len(days)
    stt, exch = _stt(days), _exch(days)
    by = tr.set_index("i") if len(tr) else tr
    eq, carry, year_pnl = capital, 0.0, 0.0
    out = np.zeros(D)
    for i in range(lo, hi):
        if i > lo and d.fy[i] != d.fy[i - 1]:
            taxable = year_pnl + carry
            if taxable > 0:
                eq -= TAX * taxable
                carry = 0.0
            else:
                carry = taxable
            year_pnl = 0.0
        eq *= 1 + d.cash[i] * (1 - TAX)
        if len(tr) and i in by.index:
            r = by.loc[i]
            lot = d.lot[i]
            n = eq * scale / (r.margin_unit * lot)
            n = np.floor(n) if whole else n
            if n > 0:
                gross = r.points * lot * n
                if pd.notna(r.fut_cost):
                    cost = r.fut_cost * n
                else:
                    prem = (r.sold + r.bought) * lot * n
                    brokerage = 20 * r.orders * max(1.0, np.ceil(n / 24))        # an order holds up to 24 lots (exchange freeze limit, about)
                    cost = brokerage + stt[i] * r.sold * lot * n + exch[i] * prem + 1e-6 * prem + 0.00003 * r.bought * lot * n + 0.18 * (brokerage + exch[i] * prem)
                eq += gross - cost
                year_pnl += gross - cost
        out[i] = eq
    return pd.DataFrame({"equity": out[lo:hi]}, index=pd.DatetimeIndex(days[lo:hi].astype("datetime64[ns]")))


def stats(eq: pd.Series) -> dict:
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    v = eq.to_numpy()
    return dict(cagr=(v[-1] / v[0]) ** (1 / yrs) - 1 if v[-1] > 0 else -1.0, worst_fall=float((1 - v / np.maximum.accumulate(v)).max()))


def arrays(d: Data, tr: pd.DataFrame) -> np.ndarray:
    """One strategy's trades as a D x 6 array (points, margin a unit, sold, bought, orders, futures cost; NaN points on days it does not trade)."""
    a = np.full((len(d.lot), 6), np.nan)
    if len(tr):
        i = tr.i.to_numpy(dtype=int)
        a[i] = tr[["points", "margin_unit", "sold", "bought", "orders", "fut_cost"]].to_numpy(dtype=float)
    return a


def _flat_tax(fy, pnl, interest, carry):
    """The research default: 31.2% of the year's trading profit and liquid fund gain, a trading loss carried forward."""
    carry = carry or 0.0
    taxable = pnl + carry
    return TAX * (max(taxable, 0.0) + max(interest, 0.0)), min(taxable, 0.0)


def installments(days: np.ndarray) -> np.ndarray:
    """Share of the year's tax due by each day as advance tax (section 211: 15% by 15 June, 45% by 15 September, 75% by 15 December, 100% by 15 March),
    on the first trading day on or after each date; 0 on other days."""
    out = np.zeros(len(days))
    d = pd.DatetimeIndex(days.astype("datetime64[ns]"))
    for month, share in ((6, 0.15), (9, 0.45), (12, 0.75), (3, 1.0)):
        due = (d.month == month) & (d.day >= 15)
        first = due & ~np.r_[False, due[:-1]]
        out[first] = share
    return out


def account_multi(ds: list, books: list, scales, capital: float, lo: int = 0, hi: int | None = None, count: bool = False, tax: bool = True,
                  charges: bool = True, tax_fn=None, advance: bool = True):
    """Several strategies in one account with whole lots: strategy k trades floor(equity x scale_k / (margin a lot)) lots, and the day's margins together
    never pass the equity (the later strategies are cut first). `ds[k]` is strategy k's index data (all on the same days), `books[k]` its arrays().
    Tax: `tax_fn(fy, trading profit, liquid fund gain, state) -> (tax, state)`, the flat 31.2% by default, none with tax=False. With `advance`, the tax is
    paid in the legal advance-tax installments on the year-to-date figures, and settled after the year ends (a refund if overpaid); else all after the year."""
    d0 = ds[0]
    days = d0.T["days"]
    hi = len(days) if hi is None else hi
    stt, exch = _stt(days), _exch(days)
    fn = (tax_fn or _flat_tax) if tax else None
    inst = installments(days) if advance else np.zeros(len(days))
    eq, year_pnl, year_int, paid = capital, 0.0, 0.0, 0.0
    state = None                                   # the tax function's carry (losses) between years
    out = np.zeros(hi - lo)
    active = 0
    for i in range(lo, hi):
        traded = False
        if i > lo and d0.fy[i] != d0.fy[i - 1]:
            if fn is not None:
                t, state = fn(int(d0.fy[i - 1]), year_pnl, year_int, state)
                eq -= t - paid
            year_pnl, year_int, paid = 0.0, 0.0, 0.0
        gain = eq * d0.cash[i]
        year_int += gain
        eq += gain
        room = eq
        for d, a, sc in zip(ds, books, scales):
            pts, mu, sold, bought, orders, fut = a[i]
            if pts != pts or eq <= 0:
                continue
            lot = d.lot[i]
            n = np.floor(min(eq * sc, room) / (mu * lot))
            if n < 1:
                continue
            room -= n * mu * lot
            if fut == fut:
                cost = fut * n
            else:
                prem = (sold + bought) * lot * n
                brokerage = 20 * orders * max(1.0, np.ceil(n / 24))
                cost = brokerage + stt[i] * sold * lot * n + exch[i] * prem + 1e-6 * prem + 0.00003 * bought * lot * n + 0.18 * (brokerage + exch[i] * prem)
            pnl = pts * lot * n - (cost if charges else 0.0)
            eq += pnl
            year_pnl += pnl
            traded = True
        if fn is not None and inst[i] > 0:
            due = inst[i] * fn(int(d0.fy[i]), year_pnl, year_int, state)[0] - paid
            if due > 0:
                eq -= due
                paid += due
        active += traded
        out[i - lo] = eq
    if fn is not None:                             # the year in progress at the end: its tax as if it ended there
        t, _ = fn(int(d0.fy[hi - 1]), year_pnl, year_int, state)
        out[-1] -= t - paid
    return (out, active) if count else out


def stats_arr(v: np.ndarray, days: np.ndarray) -> dict:
    yrs = (days[-1] - days[0]).astype(int) / 365.25
    return dict(cagr=(v[-1] / v[0]) ** (1 / yrs) - 1 if v[-1] > 0 else -1.0, worst_fall=float((1 - v / np.maximum.accumulate(v)).max()))
