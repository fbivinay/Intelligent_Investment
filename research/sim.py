"""The fast simulator: one account, four ETFs and a liquid fund as cash, daily decisions.

A strategy decides target weights after the close of day t. The fill is on day t+1 at that day's VWAP (the fund: its NAV), with slippage, in whole units for the ETFs, charged
by the engine's own rules (research/costs.py). Lots are FIFO. The day loop is numba; it runs one financial year at a time, and at each year end the year's sales go to the
exact engine (`engine.tax.investment_tax`, 2 to 10 ms) and the tax is paid out of the portfolio on the first trading day of the next year, so the tax feeds back into what the
strategy can hold. The year in progress at the end is reported as pending tax, and what selling everything at the last close would add as the liquidation tax.
A governor cuts risky weights as the account's drawdown nears its cap (spec section 4).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

import numpy as np
import pandas as pd
from numba import njit

from engine.rules import Rules
from engine.tax import CGEvent, Carry, TaxProfile, fy_end, fy_of, investment_tax
from engine.trace import const
from research import costs as C
from research.panel import ASSETS, Panel

N = 5                                              # the four ETFs and the cash leg (asset 4)
ASSET_CLASS = ("etf_equity", "etf_equity", "etf_equity", "etf_gold", "mf_debt")
CLS = np.array([0, 0, 0, 1, 2], dtype=np.int64)    # index into costs.CLASSES
WHOLE = np.array([1, 1, 1, 1, 0], dtype=np.int64)  # whole units for the ETFs, fractions for the fund
HALF = np.array([C.HALF_SPREAD[a] for a in ASSETS] + [0.0])
GRANDFATHER = date(2018, 1, 31)


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


@dataclass
class Result:
    dates: np.ndarray
    equity: np.ndarray            # T, marked at the close, after tax paid
    drawdown: np.ndarray          # T, from the high-water mark
    multiplier: np.ndarray        # T, the governor's scaling of risky weights decided at this close
    units: np.ndarray             # T x 5, held after the day's fills
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
    if use == 0 or value <= 0.0 or a == 4:
        return 0.0
    part = 1.0
    if adv == adv and adv > 0.0:
        part = min(value / adv, 1.0)
    return min(half[a] + impact * math.sqrt(part), maxs)


@njit(cache=True)
def _sell(i, u, t, px, adv, reg, cvals, cded, sizes, cls, half, impact, maxs, use_slip, units, cash, lot_units, lot_cost, lot_day, head,
          sl_asset, sl_acq, sl_sale, sl_units, sl_cost, sl_proc, sl_scost, sl_n, acc):
    s = _slip(i, u * px[t, i], adv[t, i], half, impact, maxs, use_slip)
    price = px[t, i] * (1.0 - s)
    proceeds = u * price
    ch = _charge(cvals, sizes, reg[t], cls[i], 1, proceeds)
    ded = _charge(cded, sizes, reg[t], cls[i], 1, proceeds)
    cash[0] += proceeds - ch
    acc[0] += proceeds
    acc[1] += ch
    acc[2] += u * px[t, i] * s
    acc[3] += 1.0
    remaining = u
    while remaining > 1e-9:
        k = head[i]
        lu = lot_units[i, k]
        take = min(remaining, lu)
        cost_part = lot_cost[i, k] * take / lu
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


@njit(cache=True)
def _run(t0, t1, px, close, adv, reg, fixed, target, cvals, cded, sizes, cls, whole, half, impact, maxs, use_slip, band, min_trade, cap, use_gov, gstart, gend, ghold,
         units, cash, lot_units, lot_cost, lot_day, head, tail, pend_w, pend_valid, gov, tax_due,
         equity, dd, mult, traded, chg, slipc, taxpaid, nord, units_out, cash_out,
         sl_asset, sl_acq, sl_sale, sl_units, sl_cost, sl_proc, sl_scost, sl_n):
    acc = np.zeros(4)
    for t in range(t0, t1):
        acc[:] = 0.0
        cash[0] -= fixed[t]
        if pend_valid[0] == 1:
            if tax_due[0] > 0.0:
                cash[0] -= tax_due[0]
                taxpaid[t] = tax_due[0]
                tax_due[0] = 0.0
            total = cash[0]
            for i in range(N):
                total += units[i] * px[t, i]
            thr = max(min_trade, band * total)
            # sells first: they raise the cash the buys use
            for i in range(N):
                cur = units[i] * px[t, i]
                gap = pend_w[i] * total - cur
                sell_all = pend_w[i] <= 0.0 and units[i] > 0.0
                if not (gap < -thr or sell_all):
                    continue
                sv = cur if sell_all else min(-gap, cur)
                if whole[i] == 1:
                    est = px[t, i] * (1.0 - _slip(i, sv, adv[t, i], half, impact, maxs, use_slip))
                    u = units[i] if sell_all else min(math.floor(sv / est), units[i])
                else:
                    u = units[i] if sell_all else min(sv / px[t, i], units[i])
                if u <= 0.0:
                    continue
                _sell(i, u, t, px, adv, reg, cvals, cded, sizes, cls, half, impact, maxs, use_slip, units, cash, lot_units, lot_cost, lot_day, head,
                      sl_asset, sl_acq, sl_sale, sl_units, sl_cost, sl_proc, sl_scost, sl_n, acc)
            # an overdraft (tax, fees) is covered by selling: the fund first, then the ETFs in turn
            if cash[0] < 0.0:
                for k in range(N):
                    i = 4 if k == 0 else k - 1
                    if cash[0] >= 0.0 or units[i] <= 0.0:
                        continue
                    need = -cash[0] * 1.002 + 1.0
                    if whole[i] == 1:
                        u = min(math.ceil(need / px[t, i]), units[i])
                    else:
                        u = min(need / px[t, i], units[i])
                    if u > 0.0:
                        _sell(i, u, t, px, adv, reg, cvals, cded, sizes, cls, half, impact, maxs, use_slip, units, cash, lot_units, lot_cost, lot_day, head,
                              sl_asset, sl_acq, sl_sale, sl_units, sl_cost, sl_proc, sl_scost, sl_n, acc)
            for i in range(N):
                cur = units[i] * px[t, i]
                gap = pend_w[i] * total - cur
                if gap <= thr or cash[0] <= 0.0:
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
                ch = _charge(cvals, sizes, reg[t], cls[i], 0, value)
                ded = _charge(cded, sizes, reg[t], cls[i], 0, value)
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
        traded[t] = acc[0]
        chg[t] = acc[1]
        slipc[t] = acc[2]
        nord[t] = acc[3]
        eq = cash[0]
        for i in range(N):
            eq += units[i] * close[t, i]
            units_out[t, i] = units[i]
        cash_out[t] = cash[0]
        equity[t] = eq
        if eq >= gov[0]:
            gov[0] = eq
            if gov[2] == 1.0:
                gov[2] = 0.0
            gov[1] = 1.0
        ddv = 1.0 - eq / gov[0]
        dd[t] = ddv
        m = 1.0
        if use_gov == 1:
            raw = (gend * cap - ddv) / ((gend - gstart) * cap)
            raw = min(1.0, max(0.0, raw))
            if gov[2] == 1.0:
                if eq < gov[3]:
                    gov[3] = eq
                    gov[4] = t
                if t - gov[4] >= ghold:
                    gov[2] = 0.0
            if gov[2] == 0.0:
                if raw < 1.0:
                    gov[2] = 1.0
                    gov[3] = eq
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
        for i in range(4):
            pend_w[i] = target[t, i] * m
            risky += pend_w[i]
        pend_w[4] = 1.0 - risky
        pend_valid[0] = 1


_TABLE_CACHE: dict = {}


def _cost_table(rules: Rules):
    """The charge table for every regime of the rules, worked out once per Rules object."""
    key = id(rules)
    if key not in _TABLE_CACHE:
        starts = sorted({r.valid_from for t in C.CHARGE_RULES for r in rules.tables[t].all_rows()})
        _TABLE_CACHE[key] = (rules, starts, C.charge_table(rules, starts))
    return _TABLE_CACHE[key][1:]


def _events(rules: Rules, sl, days, fmv_unit) -> list[CGEvent]:
    out = []
    for k in range(len(sl["asset"])):
        a = int(sl["asset"][k])
        acq, sale = days[int(sl["acq"][k])], days[int(sl["sale"][k])]
        units = float(sl["units"][k])
        fmv = None
        if ASSET_CLASS[a] == "etf_equity" and acq <= GRANDFATHER and fmv_unit is not None:
            fmv = const("Value on 31 Jan 2018", Decimal(repr(round(fmv_unit[a] * units, 2))))
        out.append(CGEvent(f"{ASSETS[a] if a < 4 else 'liquid fund'} sold {sale}", sale, ASSET_CLASS[a], acq,
                           const("Sale proceeds", Decimal(repr(round(max(float(sl["proc"][k]), 0.0), 2)))),
                           const("Sale charges deductible", Decimal(repr(round(max(float(sl["scost"][k]), 0.0), 2)))),
                           const("Cost of acquisition", Decimal(repr(round(max(float(sl["cost"][k]), 0.0), 2)))), fmv_2018=fmv))
    return out


def _check_weights(w: np.ndarray, T: int) -> None:
    if w.shape != (T, N):
        raise ValueError(f"weights must be {T} x {N}, not {w.shape}")
    if (w < -1e-12).any():
        raise ValueError("weights cannot be negative (no shorting in this simulator)")
    if not np.allclose(w.sum(axis=1), 1.0, atol=1e-6):
        raise ValueError("the weights of every day must sum to 1")


def simulate(panel: Panel, weights: np.ndarray, rules: Rules, cfg: SimConfig = SimConfig()) -> Result:
    days = [date.fromisoformat(str(d)) for d in panel.dates]
    T = len(days)
    weights = np.asarray(weights, dtype=float)
    _check_weights(weights, T)
    px = np.ascontiguousarray(np.column_stack([panel.vwap, panel.cash]))
    close = np.ascontiguousarray(np.column_stack([panel.close, panel.cash]))
    adv = pd.DataFrame(panel.value).rolling(cfg.adv_days, min_periods=1).mean().shift(1).to_numpy()
    adv = np.ascontiguousarray(np.column_stack([adv, np.zeros(T)]))
    starts, table = _cost_table(rules)
    from bisect import bisect_right
    reg = np.array([max(0, bisect_right(starts, d) - 1) for d in days], dtype=np.int64)
    fixed = C.fixed_costs(rules, days) if cfg.tax or True else np.zeros(T)
    hi = {}
    for d_i, d in enumerate(days):
        if d <= GRANDFATHER:
            hi = {a: float(panel.high[d_i, a]) for a in range(4)}
    fmv_unit = hi if hi and days[0] <= GRANDFATHER else None

    L = T + 10
    units = np.zeros(N)
    cash = np.array([cfg.capital])
    lot_units, lot_cost = np.zeros((N, L)), np.zeros((N, L))
    lot_day = np.zeros((N, L), dtype=np.int64)
    head, tail = np.zeros(N, dtype=np.int64), np.zeros(N, dtype=np.int64)
    pend_w, pend_valid = np.zeros(N), np.zeros(1, dtype=np.int64)
    gov = np.array([cfg.capital, 1.0, 0.0, 0.0, 0.0])
    tax_due = np.zeros(1)
    equity, dd, mult = np.zeros(T), np.zeros(T), np.ones(T)
    traded, chg, slipc, taxpaid, nord = np.zeros(T), np.zeros(T), np.zeros(T), np.zeros(T), np.zeros(T)
    units_out, cash_out = np.zeros((T, N)), np.zeros(T)
    cap_sl = 4 * L
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
        _run(t0, t1, px, close, adv, reg, fixed, weights, cvals, cded, sizes, CLS, WHOLE, HALF, C.IMPACT, C.MAX_SLIPPAGE, 1 if cfg.slippage else 0, cfg.band, cfg.min_trade,
             cfg.cap, 1 if cfg.governor else 0, cfg.gov_start, cfg.gov_end, cfg.gov_hold_days,
             units, cash, lot_units, lot_cost, lot_day, head, tail, pend_w, pend_valid, gov, tax_due,
             equity, dd, mult, traded, chg, slipc, taxpaid, nord, units_out, cash_out,
             sl["asset"], sl["acq"], sl["sale"], sl["units"], sl["cost"], sl["proc"], sl["scost"], sl_n)
        n = int(sl_n[0])
        part = {k: v[:n] for k, v in sl.items()}
        events = _events(rules, part, days, fmv_unit) if cfg.tax else []
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
        total = float(investment_tax(rules, int(fy[-1]), cfg.profile, last_events + _events(rules, lq, days, fmv_unit), carry).extra.value)
        liq_tax = max(total - pending, 0.0)
    else:
        liq_tax = 0.0
    return Result(dates=panel.dates, equity=equity, drawdown=dd, multiplier=mult, units=units_out, cash=cash_out, traded=traded, charges=chg, slippage=slipc, tax_paid=taxpaid,
                  tax_by_fy=tax_by_fy, carry=carry, pending_tax=pending, liquidation_tax=liq_tax, liquidation_charges=liq_charges,
                  liquidation_equity=float(equity[-1]) - pending - liq_tax - liq_charges, orders=int(nord.sum()))
