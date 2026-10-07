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
from engine.trace import Node, add, const, div, mul, sub

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
    buys: tuple = ()              # a monthly plan's days: (day, paid that day, units bought, rupees spent with the charges)


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

    return _close(rules, instrument_class, profile, initial, [bc], div_fy, opening, amc, sale_value, event and [event], sale_charges, sell.on, units, buy.on,
                  sell_at_end)


def buy_monthly(rules: Rules, *, instrument: str, instrument_class: str, bars: list[Bar], dividends: dict[date, Decimal],
                payments: list[tuple[date, Decimal]], end: date, profile: TaxProfile, sell_at_end: bool = True, unit_step: Decimal = Decimal(1),
                demat: bool = True) -> Result:
    """A monthly plan: each payment, with what the earlier ones left over, buys as many units as it can at the close of the first day on or after its date;
    every purchase is a lot, sold first in first out at the end. Charges, dividends, fees and tax as in buy_and_hold; one payment gives its result."""
    if not payments or any(a <= 0 for _, a in payments):
        raise ValueError("a plan needs payments of more than Rs 0")
    last = [b for b in bars if b.on <= end]
    if not last:
        raise ValueError(f"no usable price history up to {end}")
    sell = last[-1]
    inv, cash, buys, orders, held = Inventory(), Decimal(0), [], [], []      # held: (day, units) of each lot, for the dividends
    for on, amt in payments:
        bar = next((b for b in last if b.on >= on), None)
        if bar is None:
            raise ValueError(f"no price on or after the payment of {on} up to {end}")
        cash += amt
        q = (cash / bar.close / unit_step).to_integral_value(rounding=ROUND_FLOOR) * unit_step
        while q > 0:
            bc = order_charges(rules, Order(bar.on, instrument_class, "buy", q, bar.close))
            if bc.turnover.value + bc.total.value <= cash:
                break
            q -= unit_step
        if q > 0:
            inv.buy(instrument, bar.on, q, add("Cost of acquisition (price + buy charges you may deduct)", bc.turnover, bc.deductible))
            cash -= bc.turnover.value + bc.total.value
            orders.append(bc)
            held.append((bar.on, q))
        buys.append((bar.on, amt, q if q > 0 else Decimal(0), (bc.turnover.value + bc.total.value) if q > 0 else Decimal(0)))
    if not held:
        raise ValueError(f"the payments are too small to buy one unit of {instrument} after charges")
    first = held[0][0]
    if sell.on <= first:
        raise ValueError(f"no usable price history between {payments[0][0]} and {end}")
    units = sum((q for _, q in held), Decimal(0))
    initial = const(f"Money invested ({len(payments)} payments)", sum((a for _, a in payments), Decimal(0)))

    div_by_fy: dict[int, list[Node]] = {}
    for ex, per_unit in sorted(dividends.items()):
        q = sum((u for on, u in held if on < ex), Decimal(0))
        if q > 0 and first < ex <= sell.on:
            div_by_fy.setdefault(fy_of(ex), []).append(mul(f"Dividend paid on {ex}", const("Units held", q), const("Dividend per unit", per_unit)))
    div_fy = {fy: add(f"Dividends received in {fy_label(fy)}", *ns) for fy, ns in div_by_fy.items()}

    if demat:
        opening = account_opening_fee(rules, first)  # ponytail: the account is opened for this plan, as in buy_and_hold
        amc = [amc_fee(rules, min(fy_end(fy), sell.on), first) for fy in range(fy_of(first), fy_of(sell.on) + 1)]
    else:
        opening, amc = const("Account opening fee (none: fund units, no demat account)", 0), []

    sale_value = mul("Value of units at the end", const("Units held", units), const("Closing price on the last day", sell.close))
    events = None
    if sell_at_end:
        sc = order_charges(rules, Order(sell.on, instrument_class, "sell", units, sell.close))
        dp = dp_charge(rules, sell.on) if demat else const("Depository charge (none: fund units, no demat account)", 0)
        costs = add("Sale costs you may deduct", sc.deductible, dp)
        ref_bar = [b for b in bars if b.on <= GRANDFATHER_DATE]
        events = []
        for piece in inv.sell(instrument, units):
            share = div("Share of the sale", const("Units from this lot", piece.qty), const("Units sold", units))
            fmv = None
            if piece.acq_date <= GRANDFATHER_DATE and ref_bar:
                fmv = mul("Value on 31 Jan 2018 (highest price that day)", const("Units", piece.qty), const("Highest price on 31 Jan 2018", ref_bar[-1].high))
            events.append(CGEvent(f"{piece.qty} units of {instrument} bought {piece.acq_date}", sell.on, instrument_class, piece.acq_date,
                                  mul("Sale proceeds of these units", sc.turnover, share), mul("Sale costs of these units", costs, share), piece.cost, fmv))
        sale_charges = add("Sale charges (incl. STT and depository fees)", sc.total, dp)
    else:
        sale_charges = add("Sale charges (none: still holding)")
    r = _close(rules, instrument_class, profile, initial, orders, div_fy, opening, amc, sale_value, events, sale_charges, sell.on, units, first, sell_at_end)
    return Result(r.net, r.waterfall, r.units, r.bought_on, r.ended_on, r.sold, tuple(buys))


def _close(rules, instrument_class, profile, initial, orders, div_fy, opening, amc, sale_value, events, sale_charges, sell_on, units, bought_on, sold) -> Result:
    """Tax each financial year (the sale's events in the last), then the waterfall to the net."""
    taxes, carry = [], Carry()
    for fy in range(fy_of(bought_on), fy_of(sell_on) + 1):
        r = investment_tax(rules, fy, profile, list(events) if events and fy == fy_of(sell_on) else [], carry, dividends=div_fy.get(fy), dividend_payer="fund")
        carry = r.with_items.carry_out
        taxes.append(r.extra)
    bought = orders[0].turnover if len(orders) == 1 else add("All purchases", *(o.turnover for o in orders))
    buy_charges = orders[0].total if len(orders) == 1 else add("Buy charges of every purchase", *(o.total for o in orders))
    price_gain = sub("Price gain before charges and tax", sale_value, bought)
    total_div = add("All dividends received", *div_fy.values())
    gross_profit = add("Gross profit (price gain + dividends)", price_gain, total_div)
    gross_end = add("Gross end value, before any charge or tax", initial, gross_profit)
    charges = add("All charges", buy_charges, sale_charges, opening, *amc)
    tax = add("All income tax caused by this investment", *taxes)
    net = sub("Final amount after all charges and tax", sub("Gross end value less all charges", gross_end, charges), tax)
    return Result(net, {"initial": initial, "gross_profit": gross_profit, "gross_end": gross_end,
                        "buy_charges": buy_charges, "sale_charges": sale_charges, "account_opening": opening,
                        "amc": add("Demat AMC for all years", *amc), "charges": charges, "tax": tax, "net": net},
                  units, bought_on, sell_on, sold)
