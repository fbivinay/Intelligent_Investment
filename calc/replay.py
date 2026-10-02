"""Exact books for the product: every order the fast simulator placed, booked again through the engine in Decimal, every number a trace node.

The fast simulator decides (what to buy and sell, when, at what fill price with the slippage assumption); this module accounts: each order's charges by the engine's
rules of that date, the depository charge on ETF sales, FIFO lots, each financial year's tax with the user's profile, the account's opening fee and yearly fee (as the
engine's buy-and-hold charges them, the year in progress included), and two endings: everything sold at the last close, or still holding.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from engine.charges import Order, account_opening_fee, amc_fee, dp_basis, dp_charge, order_charges
from engine.lots import Inventory
from engine.rules import Rules
from engine.tax import CGEvent, Carry, TaxProfile, classify, fy_end, fy_label, fy_of, investment_tax
from engine.trace import Node, add, const, div, mul, sub
from research.panel import Panel
from research.sim import classes

NAMES = ("NIFTYBEES", "JUNIORBEES", "BANKBEES", "GOLDBEES", "LIQUID_FUND")      # the four-ETF panel's; a panel's own are names_of(panel)
GRANDFATHER = date(2018, 1, 31)
KIND_LABELS = {"brokerage": "Brokerage", "stt": "STT", "exchange_txn": "Exchange transaction charges", "sebi": "SEBI turnover fee", "ipft": "IPF charge",
               "clearing": "Clearing charges", "stamp": "Stamp duty", "gst": "GST", "dp": "Depository charges", "fees": "Account opening and yearly demat fees"}


@dataclass
class Booked:
    sold: Node                 # net if everything is sold at the last close and that tax paid
    held: Node                 # net if still holding: holdings at the last close, the tax of the sales made so far
    waterfall: dict            # {"sold": {...}, "held": {...}}: initial, gross_end, charges, tax, net
    charges_by_kind: dict      # {"sold": {kind: Node}, "held": {kind: Node}}
    tax_by_fy: dict            # financial year -> Node, the last year including the liquidation
    tax_by_fy_held: dict
    events_by_fy: dict         # financial year -> the sales made (no liquidation)
    trades: list               # one dict per order
    tax_lines: list            # one dict per lot sold (the liquidation's included, marked)
    holdings: dict             # units held at the end, before any liquidation


def _dec(x) -> Decimal:
    return Decimal(repr(float(x)))


def names_of(panel: Panel) -> tuple[str, ...]:
    """The panel's ETFs and the liquid fund (the cash leg, last)."""
    return tuple(panel.assets) + ("LIQUID_FUND",)


def csv_text(rows: list[dict]) -> str:
    if not rows:
        return ""
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return out.getvalue()


def book(rules: Rules, panel: Panel, log, amount: Decimal, profile: TaxProfile) -> Booked:
    days = [date.fromisoformat(str(d)) for d in panel.dates]
    NAMES, CLS, cash = names_of(panel), classes(panel.assets), len(panel.assets)
    gf = [i for i, d in enumerate(days) if d <= GRANDFATHER]
    fmv_unit = {a: _dec(panel.high[gf[-1], a]) for a in range(cash) if CLS[a] in ("etf_equity", "eq_share")} if gf else {}
    inv, kinds, buys, sells = Inventory(), {}, [], []
    events: dict[int, list[CGEvent]] = {}
    trades, lines, dp_seen = [], [], set()

    def sale(on: date, a: int, qty: Decimal, price: Decimal, tag: str):
        """Book a sale: its charges, the depository charge, and one capital gains event per lot it takes."""
        cls, name = CLS[a], NAMES[a]
        o = order_charges(rules, Order(on, cls, "sell", qty, price))
        dp = None
        if cls != "mf_debt":
            key = (on, a) if dp_basis(rules, on) == "per_isin_per_day" else (on, a, tag, len(trades))
            if key not in dp_seen:
                dp_seen.add(key)
                dp = dp_charge(rules, on)
        costs = add("Sale costs you may deduct", o.deductible, *([dp] if dp is not None else []))
        out = []
        for sl in inv.sell(name, qty):
            share = div("Share of the sale", const("Units from this lot", sl.qty), const("Units sold", qty))
            fmv = None
            if a in fmv_unit and sl.acq_date <= GRANDFATHER:
                fmv = mul("Value on 31 Jan 2018 (highest price that day)", const("Units", sl.qty), const("Highest price on 31 Jan 2018", fmv_unit[a]))
            e = CGEvent(f"{sl.qty} {name} sold {on}" + (" (selling everything at the end)" if tag else ""), on, cls, sl.acq_date,
                        mul("Sale proceeds of these units", o.turnover, share), mul("Sale costs of these units", costs, share), sl.cost, fmv)
            out.append(e)
            gain, (term, *_), _ = classify(rules, e)
            lines.append({"financial_year": fy_label(fy_of(on)), "asset": name, "bought": sl.acq_date.isoformat(), "sold": on.isoformat(), "units": str(sl.qty),
                          "proceeds": str(e.proceeds.value), "sale_costs": str(e.sale_costs.value), "cost": str(e.cost.value), "gain": str(gain.value), "term": term,
                          "at_end": bool(tag)})
        return o, dp, out

    for t, a, side, u, price, _taken in log:
        t, a = int(t), int(a)
        on, name, cls = days[t], NAMES[a], CLS[a]
        qty, px = (Decimal(int(round(u))) if a < cash else _dec(u)), _dec(price)
        if side and a == cash:
            qty = min(qty, inv.units(name))                                       # the simulator's fund units carry float dust
        if qty <= 0:
            continue
        if side:
            o, dp, evs = sale(on, a, qty, px, "")
            sells.append(o.turnover)
            events.setdefault(fy_of(on), []).extend(evs)
        else:
            o, dp = order_charges(rules, Order(on, cls, "buy", qty, px)), None
            buys.append(o.turnover)
            inv.buy(name, on, qty, add(f"Cost of {qty} {name} bought {on} (price plus charges you may deduct)", o.turnover, o.deductible))
        for k, n in o.lines.items():
            kinds.setdefault(k, []).append(n)
        if dp is not None:
            kinds.setdefault("dp", []).append(dp)
        vwap = float(panel.vwap[t, a]) if a < cash else float(panel.cash[t])
        trades.append({"date": on.isoformat(), "asset": name, "class": cls, "side": "sell" if side else "buy", "units": str(qty), "price": str(px), "vwap": repr(vwap),
                       "slippage": repr(float(px) / vwap - 1.0) if vwap else "0", "turnover": str(o.turnover.value), "charges": str(o.total.value),
                       "dp": str(dp.value) if dp is not None else "0"})

    last, end = len(days) - 1, days[-1]
    holdings = {n: inv.units(n) for n in NAMES}
    close = {a: (_dec(panel.close[last, a]) if a < cash else _dec(panel.cash[last])) for a in range(cash + 1)}
    valued = [mul(f"{NAMES[a]} held at the end", const("Units held", holdings[NAMES[a]]), const(f"Price on {end}", close[a])) for a in range(cash + 1)
              if holdings[NAMES[a]] > 0]
    fees = [account_opening_fee(rules, days[0])] + [amc_fee(rules, min(fy_end(fy), end), days[0]) for fy in range(fy_of(days[0]), fy_of(end) + 1)]

    def taxes(extra: list[CGEvent]) -> dict:
        carry, out = Carry(), {}
        for fy in range(fy_of(days[0]), fy_of(end) + 1):
            it = investment_tax(rules, fy, profile, events.get(fy, []) + (extra if fy == fy_of(end) else []), carry)
            carry, out[fy] = it.with_items.carry_out, it.extra
        return out

    initial = const("Money invested", amount)
    traded = sub("Sales less purchases before charges", add("All sales", *sells), add("All purchases", *buys))
    by_kind_held = {k: add(f"{KIND_LABELS.get(k, k)} on every order", *ns) for k, ns in kinds.items()}
    by_kind_held["fees"] = add(KIND_LABELS["fees"], *fees)
    tax_held = taxes([])
    held_w = {"initial": initial, "gross_end": add("Gross end value, before any charge or tax", initial, traded, add("Value of the holdings at the last close", *valued))}
    held_w["charges"] = add("All charges", *by_kind_held.values())
    held_w["tax"] = add("All income tax caused by this investment (the year in progress: its sales so far)", *tax_held.values())
    held_w["net"] = sub("Final amount if still holding, after all charges and tax", sub("Gross end value less all charges", held_w["gross_end"], held_w["charges"]), held_w["tax"])

    liq_turnover, liq_kinds, liq_events = [], {}, []
    for a in range(cash + 1):
        q = holdings[NAMES[a]]
        if q > 0:
            o, dp, evs = sale(end, a, q, close[a], "end")
            liq_turnover.append(o.turnover)
            liq_events.extend(evs)
            for k, n in o.lines.items():
                liq_kinds.setdefault(k, []).append(n)
            if dp is not None:
                liq_kinds.setdefault("dp", []).append(dp)
    by_kind_sold = {k: add(f"{KIND_LABELS.get(k, k)} on every order and the final sale", *(kinds.get(k, []) + liq_kinds.get(k, []))) for k in {**kinds, **liq_kinds}}
    by_kind_sold["fees"] = by_kind_held["fees"]
    tax_sold = taxes(liq_events)
    sold_w = {"initial": initial, "gross_end": add("Gross end value, before any charge or tax", initial, traded, add("Everything sold at the last close", *liq_turnover))}
    sold_w["charges"] = add("All charges", *by_kind_sold.values())
    sold_w["tax"] = add("All income tax caused by this investment", *tax_sold.values())
    sold_w["net"] = sub("Final amount after selling everything, after all charges and tax", sub("Gross end value less all charges", sold_w["gross_end"], sold_w["charges"]),
                        sold_w["tax"])
    return Booked(sold_w["net"], held_w["net"], {"sold": sold_w, "held": held_w}, {"sold": by_kind_sold, "held": by_kind_held}, tax_sold, tax_held, events, trades, lines,
                  holdings)
