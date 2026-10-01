"""Buy and hold one ETF, sell at the end: the first end-to-end scenario, every rupee traced.

Simplifications, all shown on the report: buys and sells at the day's close (the real fill model
comes with the strategy engine), cash earns nothing, and units are whole. The demat account is
taken to be opened on the day of the purchase, for this investment: its opening fee and yearly AMC
are charged to the investment.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_FLOOR, Decimal

from engine.charges import Order, account_opening_fee, amc_fee, dp_charge, order_charges
from engine.lots import Inventory
from engine.rules import Rules
from engine.tax import CGEvent, Carry, TaxProfile, fy_end, fy_label, fy_of, investment_tax
from engine.trace import Node, add, const, mul, sub

GRANDFATHER_DATE = date(2018, 1, 31)  # value on this day is the floor for older units' cost (s.55(2)(ac))


@dataclass(frozen=True)
class Bar:
    on: date
    high: Decimal
    close: Decimal


@dataclass(frozen=True)
class Result:
    net: Node                    # what you end up with: the root of the whole trace
    waterfall: dict[str, Node]
    units: Decimal                # whole units for an ETF, to the fund's unit step for a fund
    bought_on: date
    ended_on: date
    sold: bool


def buy_and_hold(rules: Rules, *, instrument: str, instrument_class: str, bars: list[Bar],
                 dividends: dict[date, Decimal], amount: Decimal, start: date, end: date,
                 profile: TaxProfile, sell_at_end: bool = True, unit_step: Decimal = Decimal(1), demat: bool = True) -> Result:
    """`unit_step`: the smallest unit you can buy (1 for an ETF on the exchange, 0.001 for a fund's units). `demat`: units held in a demat account (an ETF) pay the
    account's opening fee, its yearly fee and the depository charge on a sale; fund units bought from the fund house (demat=False) pay none of them."""
    if amount <= 0:
        raise ValueError("amount must be positive")
    if unit_step <= 0:
        raise ValueError("unit_step must be positive")
    buy = next((b for b in bars if b.on >= start), None)
    last = [b for b in bars if b.on <= end]
    if buy is None or not last or last[-1].on <= buy.on:
        raise ValueError(f"no usable price history between {start} and {end}")
    sell = last[-1]

    q = (amount / buy.close / unit_step).to_integral_value(rounding=ROUND_FLOOR) * unit_step
    while q > 0:
        bc = order_charges(rules, Order(buy.on, instrument_class, "buy", q, buy.close))
        if bc.turnover.value + bc.total.value <= amount:
            break
        q -= unit_step
    if q <= 0:
        raise ValueError(f"{amount} is too small to buy one unit at {buy.close} after charges")
    units = q

    initial = const("Money invested", amount)
    cost = add("Cost of acquisition (price + buy charges you may deduct)", bc.turnover, bc.deductible)

    # dividends: paid on units held before the ex-date, up to the end date
    div_by_fy: dict[int, list[Node]] = {}
    for ex, per_unit in sorted(dividends.items()):
        if buy.on < ex <= sell.on:
            div_by_fy.setdefault(fy_of(ex), []).append(
                mul(f"Dividend paid on {ex}", const("Units held", q), const("Dividend per unit", per_unit)))
    div_fy = {fy: add(f"Dividends received in {fy_label(fy)}", *ns) for fy, ns in div_by_fy.items()}

    if demat:
        opened = buy.on  # ponytail: the account is opened for this purchase; a user with an older account pays no opening fee
        opening = account_opening_fee(rules, opened)
        amc = [amc_fee(rules, min(fy_end(fy), sell.on), opened) for fy in range(fy_of(buy.on), fy_of(sell.on) + 1)]
    else:
        opening, amc = const("Account opening fee (none: fund units, no demat account)", 0), []

    sale_value = mul("Value of units at the end", const("Units held", q), const("Closing price on the last day", sell.close))
    if sell_at_end:
        sc = order_charges(rules, Order(sell.on, instrument_class, "sell", q, sell.close))
        dp = dp_charge(rules, sell.on) if demat else const("Depository charge (none: fund units, no demat account)", 0)  # one sale of one ISIN on one day: one event
        inv = Inventory()
        inv.buy(instrument, buy.on, q, cost)
        piece = inv.sell(instrument, q)[0]
        fmv = None
        if buy.on <= GRANDFATHER_DATE:
            ref_bar = [b for b in bars if b.on <= GRANDFATHER_DATE]
            if ref_bar:
                fmv = mul("Value on 31 Jan 2018 (highest price that day)", const("Units held", q),
                          const("Highest price on 31 Jan 2018", ref_bar[-1].high))
        event = CGEvent(f"{units} units of {instrument}", sell.on, instrument_class, piece.acq_date,
                        sc.turnover, add("Sale costs you may deduct", sc.deductible, dp), piece.cost, fmv)
        sale_charges = add("Sale charges (incl. STT and depository fees)", sc.total, dp)
    else:
        event, sale_charges = None, add("Sale charges (none: still holding)")

    taxes, carry = [], Carry()
    for fy in range(fy_of(buy.on), fy_of(sell.on) + 1):
        events = [event] if event is not None and fy == fy_of(sell.on) else []
        r = investment_tax(rules, fy, profile, events, carry, dividends=div_fy.get(fy), dividend_payer="fund")  # units of an ETF or fund
        carry = r.with_items.carry_out
        taxes.append(r.extra)

    price_gain = sub("Price gain before charges and tax", sale_value, bc.turnover)
    total_div = add("All dividends received", *div_fy.values())
    gross_profit = add("Gross profit (price gain + dividends)", price_gain, total_div)
    gross_end = add("Gross end value, before any charge or tax", initial, gross_profit)
    charges = add("All charges", bc.total, sale_charges, opening, *amc)
    tax = add("All income tax caused by this investment", *taxes)
    net = sub("Final amount after all charges and tax", sub("Gross end value less all charges", gross_end, charges), tax)
    return Result(net, {"initial": initial, "gross_profit": gross_profit, "gross_end": gross_end,
                        "buy_charges": bc.total, "sale_charges": sale_charges, "account_opening": opening,
                        "amc": add("Demat AMC for all years", *amc), "charges": charges, "tax": tax, "net": net},
                  units, buy.on, sell.on, sell_at_end)
