"""The fast simulator: one account, the panel's ETFs and a liquid fund as cash (the last asset), daily decisions.

A strategy decides target weights after the close of day t. The fill is on day t+1 at that day's VWAP (the fund: its NAV), with slippage, in whole units for the ETFs, charged
by the engine's own rules (research/costs.py). Lots are FIFO. The day loop is numba; it runs one financial year at a time, and at each year end the year's sales go to the
exact engine (`engine.tax.investment_tax`, 2 to 10 ms) and the tax is paid out of the portfolio on the first trading day of the next year, so the tax feeds back into what the
strategy can hold. The year in progress at the end is reported as pending tax, and what selling everything at the last close would add as the liquidation tax.
A governor cuts risky weights as the account's drawdown nears its cap (spec section 4).

W1, tax-aware execution (off unless asked for): `hold_days` holds back a sale for as long as the lot it would sell first is still short-term but turns long-term within
that many days, unless the strategy exits the asset or the governor is cutting risk; `harvest` sells, on a fixed day near the end of each financial year, the long-term
equity lots whose gain fits in what is left of the year's exemption, and buys the units back the next day, so the gain is taxed at zero and the cost basis steps up.
"""
from __future__ import annotations

import math
from bisect import bisect_left
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd
from numba import njit

from engine.rules import Rules
from engine.tax import CGEvent, Carry, TaxProfile, add_months, fy_end, fy_of, investment_tax
from engine.trace import const
from research import costs as C
from research.panel import ASSETS, CLASS_OF, Panel

N = 5                                              # the four ETFs and the cash leg (asset 4) of the first universe
GRANDFATHER = date(2018, 1, 31)


def classes(assets) -> tuple[str, ...]:
    """The engine's class of each asset of a panel, the cash leg (a liquid fund) last."""
    return tuple(CLASS_OF.get(a, "eq_share") for a in assets) + ("mf_debt",)       # a symbol not listed is a listed share


ASSET_CLASS = classes(ASSETS)


@dataclass(frozen=True)
class SimConfig:
    capital: float = 1_000_000.0
    cap: float = 0.20                      # drawdown cap of the risk level
    governor: bool = True
    gov_start: float = 0.5                 # full exposure while the drawdown is under this share of the cap
    gov_end: float = 0.9                   # no risky exposure at this share of the cap
    gov_hold_days: int = 60                # back to full only after a new high or this many days without a new low
    band: float = 0.01                     # trade only when the gap to target exceeds this share of wealth
    min_trade: float = 5_000.0
    slippage: bool = True
    tax: bool = True
    profile: TaxProfile = field(default_factory=lambda: TaxProfile("new", Decimal(1200000)))
    adv_days: int = 20
    hold_days: int = 0                     # W1: hold back a sale while the first lot turns long-term within this many days (0: off)
    harvest: bool = False                  # W1: realise long-term equity gains up to the yearly exemption and buy back the next day
    harvest_offset: int = 5                # the harvest is on the 5th-to-last trading day of the financial year
    harvest_share: float = 0.95            # aim at this share of the exemption left: the estimate uses the previous close
    harvest_min: float = 1_000.0           # no harvest for a smaller gain: the round trip would cost more than it saves
    max_orders: int = 0                    # rows kept for the order log (0: 5 per asset and day, enough for any run; set it for a panel of hundreds of shares)


@dataclass
class Result:
    dates: np.ndarray
    equity: np.ndarray            # T, marked at the close, after tax paid
    drawdown: np.ndarray          # T, before tax (equity plus the tax paid so far) from its high-water mark: what the cap and the governor measure
    multiplier: np.ndarray        # T, the governor's scaling of risky weights decided at this close
    units: np.ndarray             # T x (n + 1), held after the day's fills
    cash: np.ndarray              # T, uninvested rupees
    traded: np.ndarray            # T, rupees bought plus sold
    charges: np.ndarray           # T
    slippage: np.ndarray          # T, rupees lost to slippage
    tax_paid: np.ndarray          # T, paid on the first trading day of a financial year
    tax_by_fy: dict               # tax of each completed financial year (paid the day after it ends)
    carry: Carry                  # losses carried out of the last completed year
    pending_tax: float            # tax on the sales of the financial year still in progress
    liquidation_tax: float        # extra tax if everything were sold at the last close
    liquidation_charges: float
    liquidation_equity: float     # what remains after pending tax, liquidation tax and its charges
    orders: int
    order_log: np.ndarray = None  # orders x 6: day index, asset, side (0 buy, 1 sell), units, fill price after slippage, charges taken (ETF sales include the depository charge)


@njit(cache=True)
def _charge(vals, sizes, reg, c, s, value):
    if value <= 0.0:
        return 0.0
    n = sizes.shape[0]
    if value <= sizes[0]:
        return vals[reg, c, s, 0] * value / sizes[0]
    if value >= sizes[n - 1]:
        return vals[reg, c, s, n - 1] * value / sizes[n - 1]
    k = np.searchsorted(sizes, value)
    x0, x1 = sizes[k - 1], sizes[k]
    y0, y1 = vals[reg, c, s, k - 1], vals[reg, c, s, k]
    return y0 + (y1 - y0) * (value - x0) / (x1 - x0)


@njit(cache=True)
def _slip(a, value, adv, half, impact, maxs, use):
    if use == 0 or value <= 0.0 or a == half.shape[0] - 1:                 # the cash leg is last: a fund unit has no spread
        return 0.0
    part = 1.0
    if adv == adv and adv > 0.0:
        part = min(value / adv, 1.0)
    return min(half[a] + impact * math.sqrt(part), maxs)


@njit(cache=True)
def _log(olog, ol_n, t, i, side, u, price, ch):
    """One row of the order log: day, asset, side (0 buy, 1 sell), units, fill price after slippage, the charges the simulator took."""
    n = ol_n[0]
    olog[n, 0] = t
    olog[n, 1] = i
    olog[n, 2] = side
    olog[n, 3] = u
    olog[n, 4] = price
    olog[n, 5] = ch
    ol_n[0] = n + 1


@njit(cache=True)
def _sell(i, u, t, px, adv, reg, cvals, cded, sizes, cls, half, impact, maxs, use_slip, units, cash, lot_units, lot_cost, lot_day, head, tail, lt_turn, fmv, gf_idx, ltcg,
          sl_asset, sl_acq, sl_sale, sl_units, sl_cost, sl_proc, sl_scost, sl_n, acc, olog, ol_n):
    s = _slip(i, u * px[t, i], adv[t, i], half, impact, maxs, use_slip)
    price = px[t, i] * (1.0 - s)
    proceeds = u * price
    ch = _charge(cvals, sizes, reg[t], cls[i], 1, proceeds)
    ded = _charge(cded, sizes, reg[t], cls[i], 1, proceeds)
    _log(olog, ol_n, t, i, 1, u, price, ch)
    cash[0] += proceeds - ch
    acc[0] += proceeds
    acc[1] += ch
    acc[2] += u * px[t, i] * s
    acc[3] += 1.0
    remaining = u
    while remaining > 1e-9 and head[i] < tail[i]:                           # the lots can fall short of `units` by float dust, never run past them
        k = head[i]
        lu = lot_units[i, k]
        take = min(remaining, lu)
        cost_part = lot_cost[i, k] * take / lu
        if cls[i] == 0 and lt_turn[lot_day[i, k], i] <= t:                  # a long-term equity gain: it uses up the year's exemption
            pp = proceeds * take / u
            c_eff = cost_part
            if lot_day[i, k] <= gf_idx and fmv[i] > 0.0:
                c_eff = max(cost_part, min(fmv[i] * take, pp))
            ltcg[0] += pp - ded * take / u - c_eff
        n = sl_n[0]
        sl_asset[n] = i
        sl_acq[n] = lot_day[i, k]
        sl_sale[n] = t
        sl_units[n] = take
        sl_cost[n] = cost_part
        sl_proc[n] = proceeds * take / u
        sl_scost[n] = ded * take / u
        sl_n[0] = n + 1
        lot_units[i, k] -= take
        lot_cost[i, k] -= cost_part
        remaining -= take
        if lot_units[i, k] <= 1e-9:
            head[i] += 1
    units[i] -= u
    if head[i] >= tail[i]:
        units[i] = 0.0                                                      # no lots left: whatever is left in `units` is rounding dust


@njit(cache=True)
def _add_lot(i, u, value, s, t, px, reg, cvals, cded, sizes, cls, units, cash, lot_units, lot_cost, lot_day, tail, acc, olog, ol_n):
    ch = _charge(cvals, sizes, reg[t], cls[i], 0, value)
    ded = _charge(cded, sizes, reg[t], cls[i], 0, value)
    _log(olog, ol_n, t, i, 0, u, value / u, ch)
    cash[0] -= value + ch
    k = tail[i]
    lot_units[i, k] = u
    lot_cost[i, k] = value + ded
    lot_day[i, k] = t
    tail[i] = k + 1
    units[i] += u
    acc[0] += value
    acc[1] += ch
    acc[2] += u * px[t, i] * s
    acc[3] += 1.0


@njit(cache=True)
def _run(t0, t1, px, close, adv, reg, fixed, dep, target, cvals, cded, sizes, cls, whole, half, impact, maxs, use_slip, band, min_trade, cap, use_gov, gstart, gend, ghold,
         hold_days, dayn, lt_turn, harvest, exempt, hshare, hmin, fmv, gf_idx,
         units, cash, lot_units, lot_cost, lot_day, head, tail, pend_w, pend_valid, gov, tax_due, rebuy, ltcg,
         equity, dd, mult, traded, chg, slipc, taxpaid, nord, units_out, cash_out,
         sl_asset, sl_acq, sl_sale, sl_units, sl_cost, sl_proc, sl_scost, sl_n, olog, ol_n):
    acc = np.zeros(4)
    ltcg[0] = 0.0                                                            # each call is one financial year
    T = dayn.shape[0]
    N = units.shape[0]                                                       # the ETFs and the cash leg, last
    for t in range(t0, t1):
        acc[:] = 0.0
        cash[0] -= fixed[t]
        cash[0] += dep[t]                                                    # a payment arrives before the day's orders
        if pend_valid[0] == 1:
            if tax_due[0] > 0.0:
                cash[0] -= tax_due[0]
                taxpaid[t] = tax_due[0]
                gov[5] += tax_due[0]
                tax_due[0] = 0.0
            # Only assets held, wanted or awaiting a rebuy can act; the loops visit those alone, in the same order, so a panel of hundreds of shares costs
            # what its few dozen live ones do (a zero term added to a sum leaves it bit for bit the same).
            for i in np.nonzero(rebuy > 0.0)[0]:
                if pend_w[i] > 0.0:
                    s = _slip(i, rebuy[i] * px[t, i], adv[t, i], half, impact, maxs, use_slip)
                    price = px[t, i] * (1.0 + s)
                    u = rebuy[i]
                    while u > 0.0 and u * price + _charge(cvals, sizes, reg[t], cls[i], 0, u * price) > cash[0]:
                        u -= 1.0
                    if u > 0.0:
                        _add_lot(i, u, u * price, s, t, px, reg, cvals, cded, sizes, cls, units, cash, lot_units, lot_cost, lot_day, tail, acc, olog, ol_n)
                rebuy[i] = 0.0
            held = np.nonzero(units)[0]
            total = cash[0]
            for i in held:
                total += units[i] * px[t, i]
            thr = max(min_trade, band * total)
            # sells first: they raise the cash the buys use (an asset with no units has nothing to sell)
            for i in held:
                cur = units[i] * px[t, i]
                gap = pend_w[i] * total - cur
                sell_all = pend_w[i] <= 0.0 and units[i] > 0.0
                if not (gap < -thr or sell_all):
                    continue
                if hold_days > 0 and i < N - 1 and not sell_all and t > 0 and mult[t - 1] >= 1.0 and head[i] < tail[i]:
                    lt = lt_turn[lot_day[i, head[i]], i]
                    if lt > t and lt < T and dayn[lt] - dayn[t] <= hold_days:
                        continue                                             # the first lot turns long-term soon: wait for it
                sv = cur if sell_all else min(-gap, cur)
                if whole[i] == 1:
                    est = px[t, i] * (1.0 - _slip(i, sv, adv[t, i], half, impact, maxs, use_slip))
                    u = units[i] if sell_all else min(math.floor(sv / est), units[i])
                else:
                    u = units[i] if sell_all else min(sv / px[t, i], units[i])
                if u <= 0.0:
                    continue
                _sell(i, u, t, px, adv, reg, cvals, cded, sizes, cls, half, impact, maxs, use_slip, units, cash, lot_units, lot_cost, lot_day, head, tail, lt_turn, fmv, gf_idx, ltcg,
                      sl_asset, sl_acq, sl_sale, sl_units, sl_cost, sl_proc, sl_scost, sl_n, acc, olog, ol_n)
            # an overdraft (tax, fees) is covered by selling: the fund first, then the ETFs in turn
            if cash[0] < 0.0:
                held = np.nonzero(units > 0.0)[0]
                for k in range(held.shape[0] + 1):
                    if k == 0:
                        i = N - 1
                    else:
                        i = held[k - 1]
                        if i == N - 1:
                            continue
                    if cash[0] >= 0.0 or units[i] <= 0.0:
                        continue
                    need = -cash[0] * 1.002 + 1.0
                    if whole[i] == 1:
                        u = min(math.ceil(need / px[t, i]), units[i])
                    else:
                        u = min(need / px[t, i], units[i])
                    if u > 0.0:
                        _sell(i, u, t, px, adv, reg, cvals, cded, sizes, cls, half, impact, maxs, use_slip, units, cash, lot_units, lot_cost, lot_day, head, tail, lt_turn, fmv, gf_idx,
                              ltcg, sl_asset, sl_acq, sl_sale, sl_units, sl_cost, sl_proc, sl_scost, sl_n, acc, olog, ol_n)
            thr_buy = min_trade if dep[t] > 0.0 else thr                     # a payment is put to work at once, not left waiting for the band
            for i in np.nonzero(pend_w > 0.0)[0]:                            # an asset with no weight is never bought
                cur = units[i] * px[t, i]
                gap = pend_w[i] * total - cur
                if gap <= thr_buy or cash[0] <= 0.0:
                    continue
                bv = min(gap, cash[0])
                if whole[i] == 1:
                    s = _slip(i, bv, adv[t, i], half, impact, maxs, use_slip)
                    price = px[t, i] * (1.0 + s)
                    u = math.floor(bv / price)
                    while u > 0.0:
                        value = u * price
                        if value + _charge(cvals, sizes, reg[t], cls[i], 0, value) <= cash[0]:
                            break
                        u -= 1.0
                    if u <= 0.0:
                        continue
                    value = u * price
                else:
                    s = 0.0
                    value = bv
                    for _ in range(3):
                        value = bv - _charge(cvals, sizes, reg[t], cls[i], 0, value)
                    if value <= 0.0:
                        continue
                    u = value / px[t, i]
                _add_lot(i, u, value, s, t, px, reg, cvals, cded, sizes, cls, units, cash, lot_units, lot_cost, lot_day, tail, acc, olog, ol_n)
            # W1 harvest: the long-term equity lots at the head of each queue whose gain (at yesterday's close) fits in what is left of the exemption
            if harvest[t] == 1 and exempt[t] > 0.0 and t > 0:
                for i in range(N - 1):
                    if cls[i] != 0:
                        continue                                             # only equity gains have the exemption
                    goal = hshare * (exempt[t] - ltcg[0])
                    if goal < hmin:
                        break
                    p_est = close[t - 1, i]
                    g_sum = 0.0
                    u_sum = 0.0
                    k = head[i]
                    while k < tail[i]:
                        lu = lot_units[i, k]
                        if lu > 1e-9:
                            if lt_turn[lot_day[i, k], i] > t:
                                break                                        # first in, first out: a short-term lot ends the harvest
                            cpu = lot_cost[i, k] / lu
                            if lot_day[i, k] <= gf_idx and fmv[i] > 0.0:
                                cpu = max(cpu, min(fmv[i], p_est))
                            g = p_est - cpu
                            if g_sum + g * lu <= goal:
                                g_sum += g * lu
                                u_sum += lu
                            else:
                                if g > 0.0:
                                    extra = math.floor((goal - g_sum) / g)
                                    if extra > 0.0:
                                        u_sum += extra
                                        g_sum += extra * g
                                break
                        k += 1
                    if u_sum > 0.0 and g_sum > 0.0:
                        u_sum = min(u_sum, units[i])
                        _sell(i, u_sum, t, px, adv, reg, cvals, cded, sizes, cls, half, impact, maxs, use_slip, units, cash, lot_units, lot_cost, lot_day, head, tail,
                              lt_turn, fmv, gf_idx, ltcg, sl_asset, sl_acq, sl_sale, sl_units, sl_cost, sl_proc, sl_scost, sl_n, acc, olog, ol_n)
                        rebuy[i] += u_sum
        traded[t] = acc[0]
        chg[t] = acc[1]
        slipc[t] = acc[2]
        nord[t] = acc[3]
        eq = cash[0]
        for i in np.nonzero(units)[0]:
            eq += units[i] * close[t, i]
        units_out[t, :] = units
        cash_out[t] = cash[0]
        equity[t] = eq
        eqp = eq + gov[5]                      # before tax: what has been paid out of the account is not a market loss (spec section 2)
        if eqp >= gov[0]:
            gov[0] = eqp
            if gov[2] == 1.0:
                gov[2] = 0.0
            gov[1] = 1.0
        ddv = 1.0 - eqp / gov[0]
        dd[t] = ddv
        m = 1.0
        if use_gov == 1:
            raw = (gend * cap - ddv) / ((gend - gstart) * cap)
            raw = min(1.0, max(0.0, raw))
            if gov[2] == 1.0:
                if eqp < gov[3]:
                    gov[3] = eqp
                    gov[4] = t
                if t - gov[4] >= ghold:
                    gov[2] = 0.0
            if gov[2] == 0.0:
                if raw < 1.0:
                    gov[2] = 1.0
                    gov[3] = eqp
                    gov[4] = t
                    gov[1] = raw
                    m = raw
                else:
                    gov[1] = 1.0
            else:
                m = min(gov[1], raw)
                gov[1] = m
        mult[t] = m
        risky = 0.0
        pend_w[:N - 1] = target[t, :N - 1] * m
        for i in np.nonzero(pend_w[:N - 1])[0]:
            risky += pend_w[i]
        pend_w[N - 1] = 1.0 - risky
        pend_valid[0] = 1


_TABLE_CACHE: dict = {}
_LT_CACHE: dict = {}


def _segments(rules: Rules, table: str, key: str, value: str) -> list:
    rows = [r for r in rules.tables[table].all_rows() if dict(r.key).get(key) == value]
    return sorted(rows, key=lambda r: r.valid_from)


def lt_turn_days(rules: Rules, days: list[date], asset_class: str) -> np.ndarray:
    """For each acquisition day index a, the first day index t at which a sale of that lot is long-term by the engine's rules (bucket by the acquisition date,
    holding period by the sale date); len(days) + 1 when that is not within the days."""
    T = len(days)
    out = np.full(T, T + 1, dtype=np.int64)
    buckets = _segments(rules, "tax.buckets", "asset_class", asset_class)
    terms = {}
    for a, acq in enumerate(days):
        b = next(r for r in buckets if r.covers(acq)).data["bucket"]
        if b not in terms:
            terms[b] = [(r.valid_from, r.valid_to, None if r.data.get("always_short", False) else int(r.data["lt_months"]))
                        for r in _segments(rules, "tax.capital_gains", "bucket", b)]
        for start, end, months in terms[b]:
            if months is None:
                continue
            lo = max(add_months(acq, months) + timedelta(days=1), start)
            if end is not None and lo > end:
                continue
            t = bisect_left(days, lo)
            if t < T and (end is None or days[t] <= end):
                out[a] = t
                break
    return out


def _lt_table(rules: Rules, days: list[date], cls: tuple[str, ...]) -> np.ndarray:
    key = (id(rules), days[0], days[-1], len(days), cls)
    if key not in _LT_CACHE:
        once = {c: lt_turn_days(rules, days, c) for c in dict.fromkeys(cls)}      # a column per asset, worked out once per tax class
        _LT_CACHE[key] = (rules, np.ascontiguousarray(np.column_stack([once[c] for c in cls])))
    return _LT_CACHE[key][1]


def harvest_days(days: list[date], offset: int = 5) -> np.ndarray:
    """True on the offset-th to last trading day of every financial year whose last trading day is in the days."""
    fy = np.array([fy_of(d) for d in days])
    out = np.zeros(len(days), dtype=bool)
    ends = [t for t in range(len(days) - 1) if fy[t + 1] != fy[t]]
    if days[-1] == fy_end(fy[-1]):
        ends.append(len(days) - 1)
    for e in ends:
        if e - offset + 1 >= 0 and fy[e - offset + 1] == fy[e]:
            out[e - offset + 1] = True
    return out


def _exemptions(rules: Rules, days: list[date]) -> np.ndarray:
    """The yearly exemption of long-term equity gains in force on each day (0 when there is none, as before FY 2018-19 when they were exempt in full)."""
    by_fy = {}
    for fy in sorted({fy_of(d) for d in days}):
        ok = rules.has_fy("tax.lt_exemption", fy, group="equity_112a")
        by_fy[fy] = float(rules.at_fy("tax.lt_exemption", fy, group="equity_112a").value) if ok else 0.0
    return np.array([by_fy[fy_of(d)] for d in days])


def _cost_table(rules: Rules):
    """The charge table for every regime of the rules, worked out once per Rules object."""
    key = id(rules)
    if key not in _TABLE_CACHE:
        starts = sorted({r.valid_from for t in C.CHARGE_RULES for r in rules.tables[t].all_rows()})
        _TABLE_CACHE[key] = (rules, starts, C.charge_table(rules, starts))
    return _TABLE_CACHE[key][1:]


def _events(rules: Rules, sl, days, fmv_unit, names: list[str], cls: tuple[str, ...]) -> list[CGEvent]:
    out = []
    for k in range(len(sl["asset"])):
        a = int(sl["asset"][k])
        acq, sale = days[int(sl["acq"][k])], days[int(sl["sale"][k])]
        units = float(sl["units"][k])
        fmv = None
        if cls[a] in ("etf_equity", "eq_share") and acq <= GRANDFATHER and fmv_unit is not None:
            fmv = const("Value on 31 Jan 2018", Decimal(repr(round(fmv_unit[a] * units, 2))))
        out.append(CGEvent(f"{names[a] if a < len(names) else 'liquid fund'} sold {sale}", sale, cls[a], acq,
                           const("Sale proceeds", Decimal(repr(round(max(float(sl["proc"][k]), 0.0), 2)))),
                           const("Sale charges deductible", Decimal(repr(round(max(float(sl["scost"][k]), 0.0), 2)))),
                           const("Cost of acquisition", Decimal(repr(round(max(float(sl["cost"][k]), 0.0), 2)))), fmv_2018=fmv))
    return out


def _check_weights(w: np.ndarray, T: int, n: int) -> None:
    if w.shape != (T, n):
        raise ValueError(f"weights must be {T} x {n}, not {w.shape}")
    if (w < -1e-12).any():
        raise ValueError("weights cannot be negative (no shorting in this simulator)")
    if not np.allclose(w.sum(axis=1), 1.0, atol=1e-6):
        raise ValueError("the weights of every day must sum to 1")


def simulate(panel: Panel, weights: np.ndarray, rules: Rules, cfg: SimConfig = SimConfig(), deposits: np.ndarray | None = None) -> Result:
    """`deposits`: rupees paid into the account at the start of each day (a monthly plan), on top of `cfg.capital` on the first day. A day with a payment buys
    whatever is under its weight by more than `min_trade`. Not with the governor: its drawdown would count the payments as gains."""
    days = [date.fromisoformat(str(d)) for d in panel.dates]
    T = len(days)
    n = len(panel.assets)
    N = n + 1
    cls_names = classes(panel.assets)
    CLS = np.array([C.CLASSES.index(c) for c in cls_names], dtype=np.int64)       # index into costs.CLASSES
    WHOLE = np.array([1] * n + [0], dtype=np.int64)                              # whole units for the ETFs, fractions for the fund
    HALF = np.array([C.HALF_SPREAD.get(a, C.STOCK_HALF_SPREAD) for a in panel.assets] + [0.0])
    weights = np.asarray(weights, dtype=float)
    _check_weights(weights, T, N)
    dep = np.zeros(T) if deposits is None else np.ascontiguousarray(deposits, dtype=float)
    if dep.shape != (T,) or (dep < 0).any() or not np.isfinite(dep).all():
        raise ValueError(f"deposits must be {T} rupee amounts of zero or more")
    if cfg.governor and dep.any():
        raise ValueError("deposits cannot be used with the governor")
    px = np.ascontiguousarray(np.column_stack([panel.vwap, panel.cash]))
    close = np.ascontiguousarray(np.column_stack([panel.close, panel.cash]))
    adv = pd.DataFrame(panel.value).rolling(cfg.adv_days, min_periods=1).mean().shift(1).to_numpy()
    adv = np.ascontiguousarray(np.column_stack([adv, np.zeros(T)]))
    starts, table = _cost_table(rules)
    from bisect import bisect_right
    reg = np.array([max(0, bisect_right(starts, d) - 1) for d in days], dtype=np.int64)
    fixed = C.fixed_costs(rules, days) if cfg.tax or True else np.zeros(T)
    hi, gf_idx = {}, -1
    for d_i, d in enumerate(days):
        if d <= GRANDFATHER:
            hi = {a: float(panel.high[d_i, a]) for a in range(n)}
            gf_idx = d_i
    fmv_unit = hi if hi and days[0] <= GRANDFATHER else None
    w1 = cfg.hold_days > 0 or cfg.harvest
    dayn = np.array([d.toordinal() for d in days], dtype=np.int64)
    lt_turn = _lt_table(rules, days, cls_names) if w1 else np.zeros((T, N), dtype=np.int64)
    harvest = (harvest_days(days, cfg.harvest_offset) if cfg.harvest else np.zeros(T, dtype=bool)).astype(np.int8)
    exempt = _exemptions(rules, days) if cfg.harvest else np.zeros(T)
    fmv = np.array([fmv_unit[a] for a in range(n)] + [0.0]) if fmv_unit else np.zeros(N)

    L = T + 10
    units = np.zeros(N)
    cash = np.array([cfg.capital])
    lot_units, lot_cost = np.zeros((N, L)), np.zeros((N, L))
    lot_day = np.zeros((N, L), dtype=np.int64)
    head, tail = np.zeros(N, dtype=np.int64), np.zeros(N, dtype=np.int64)
    pend_w, pend_valid = np.zeros(N), np.zeros(1, dtype=np.int64)
    gov = np.array([cfg.capital, 1.0, 0.0, 0.0, 0.0, 0.0])        # high-water mark, multiplier, cut flag, low since the cut, its day, tax paid so far
    tax_due = np.zeros(1)
    rebuy, ltcg = np.zeros(N), np.zeros(1)
    olog, ol_n = np.zeros((cfg.max_orders or 5 * N * T + 16, 6)), np.zeros(1, dtype=np.int64)
    equity, dd, mult = np.zeros(T), np.zeros(T), np.ones(T)
    traded, chg, slipc, taxpaid, nord = np.zeros(T), np.zeros(T), np.zeros(T), np.zeros(T), np.zeros(T)
    units_out, cash_out = np.zeros((T, N)), np.zeros(T)
    cap_sl = max(4, n) * L
    sl = dict(asset=np.zeros(cap_sl, dtype=np.int64), acq=np.zeros(cap_sl, dtype=np.int64), sale=np.zeros(cap_sl, dtype=np.int64), units=np.zeros(cap_sl),
              cost=np.zeros(cap_sl), proc=np.zeros(cap_sl), scost=np.zeros(cap_sl))
    sl_n = np.zeros(1, dtype=np.int64)
    fy = np.array([fy_of(d) for d in days])
    bounds = [0] + [t for t in range(1, T) if fy[t] != fy[t - 1]] + [T]
    carry, tax_by_fy, pending = Carry(), {}, 0.0
    cvals = np.ascontiguousarray(table.values)
    cded = np.ascontiguousarray(table.ded)
    sizes = np.ascontiguousarray(C.SIZES)
    last_events: list[CGEvent] = []
    for c in range(len(bounds) - 1):
        t0, t1 = bounds[c], bounds[c + 1]
        sl_n[0] = 0
        _run(t0, t1, px, close, adv, reg, fixed, dep, weights, cvals, cded, sizes, CLS, WHOLE, HALF, C.IMPACT, C.MAX_SLIPPAGE, 1 if cfg.slippage else 0, cfg.band, cfg.min_trade,
             cfg.cap, 1 if cfg.governor else 0, cfg.gov_start, cfg.gov_end, cfg.gov_hold_days,
             cfg.hold_days, dayn, lt_turn, harvest, exempt, cfg.harvest_share, cfg.harvest_min, fmv, gf_idx if fmv_unit else -1,
             units, cash, lot_units, lot_cost, lot_day, head, tail, pend_w, pend_valid, gov, tax_due, rebuy, ltcg,
             equity, dd, mult, traded, chg, slipc, taxpaid, nord, units_out, cash_out,
             sl["asset"], sl["acq"], sl["sale"], sl["units"], sl["cost"], sl["proc"], sl["scost"], sl_n, olog, ol_n)
        n = int(sl_n[0])
        part = {k: v[:n] for k, v in sl.items()}
        events = _events(rules, part, days, fmv_unit, panel.assets, cls_names) if cfg.tax else []
        if c < len(bounds) - 2:
            if cfg.tax:
                it = investment_tax(rules, int(fy[t0]), cfg.profile, events, carry)
                tax = float(it.extra.value)
                carry = it.with_items.carry_out
            else:
                tax = 0.0
            tax_by_fy[int(fy[t0])] = tax
            tax_due[0] = tax
        else:
            last_events = events
            pending = float(investment_tax(rules, int(fy[t0]), cfg.profile, events, carry).extra.value) if (cfg.tax and events or (cfg.tax and carry.st or carry.lt)) else 0.0
    # selling everything at the last close
    liq_events, liq_charges = [], 0.0
    lq = dict(asset=[], acq=[], sale=[], units=[], cost=[], proc=[], scost=[])
    for i in range(N):
        u_tot = float(units[i])
        if u_tot <= 0:
            continue
        value = u_tot * float(close[T - 1, i])
        ch = _charge(cvals, sizes, int(reg[T - 1]), int(CLS[i]), 1, value)
        ded = _charge(cded, sizes, int(reg[T - 1]), int(CLS[i]), 1, value)
        liq_charges += ch
        for k in range(int(head[i]), int(tail[i])):
            lu = float(lot_units[i, k])
            if lu <= 1e-9:
                continue
            lq["asset"].append(i); lq["acq"].append(int(lot_day[i, k])); lq["sale"].append(T - 1); lq["units"].append(lu)
            lq["cost"].append(float(lot_cost[i, k])); lq["proc"].append(value * lu / u_tot); lq["scost"].append(ded * lu / u_tot)
    lq = {k: np.array(v) for k, v in lq.items()}
    if cfg.tax and len(lq["asset"]):
        total = float(investment_tax(rules, int(fy[-1]), cfg.profile, last_events + _events(rules, lq, days, fmv_unit, panel.assets, cls_names), carry).extra.value)
        liq_tax = max(total - pending, 0.0)
    else:
        liq_tax = 0.0
    return Result(dates=panel.dates, equity=equity, drawdown=dd, multiplier=mult, units=units_out, cash=cash_out, traded=traded, charges=chg, slippage=slipc, tax_paid=taxpaid,
                  tax_by_fy=tax_by_fy, carry=carry, pending_tax=pending, liquidation_tax=liq_tax, liquidation_charges=liq_charges,
                  liquidation_equity=float(equity[-1]) - pending - liq_tax - liq_charges, orders=int(nord.sum()), order_log=olog[:int(ol_n[0])].copy())
