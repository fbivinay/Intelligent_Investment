"""Charges on one order, each line a trace node. Rates come only from rules/."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from engine.rules import Rules
from engine.trace import Node, add, cite, const, from_rule, minn, mul, rnd

SEGMENT = {"etf_equity": "delivery", "etf_gold": "delivery", "fut_index": "futures",
           "mf_equity": "mf", "mf_debt": "mf"}
EXCHANGE = "NSE"
DEDUCTIBLE = "cg_deductible"  # tag: may be deducted from a capital gain (STT may not)
PAISE = "0.01"


@dataclass(frozen=True)
class Order:
    on: date
    instrument_class: str
    side: str  # buy | sell
    qty: Decimal
    price: Decimal

    def __post_init__(self):
        if self.instrument_class not in SEGMENT:
            raise ValueError(f"unknown instrument_class {self.instrument_class!r}")
        if self.side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        if self.qty <= 0 or self.price <= 0:
            raise ValueError("qty and price must be positive")


@dataclass(frozen=True)
class Charges:
    total: Node
    lines: dict[str, Node]
    deductible: Node
    turnover: Node


def _step(row) -> Node:
    return from_rule("Rounding step", row.data.get("round_step", PAISE), row.ref)


def _rate_line(rules: Rules, table: str, on: date, label: str, base: Node, tags, **key) -> Node:
    row = rules.at(table, on, **key)
    raw = mul(f"{label} before rounding", base, from_rule(f"{label} rate", row.value, row.ref))
    return rnd(label, raw, _step(row), tags=tags)


def _brokerage(rules: Rules, on: date, product: str, turnover: Node) -> Node:
    row = rules.at("fyers.brokerage", on, product=product)
    mode = row.data["mode"]

    def flat():
        return from_rule("Brokerage flat fee per order", row.dec("flat"), row.ref)

    def pct():
        return mul("Brokerage at % of turnover", turnover,
                   from_rule("Brokerage rate", row.dec("pct"), row.ref))

    if mode == "zero":
        raw = from_rule("Brokerage (none on this plan)", 0, row.ref)
    elif mode == "flat":
        raw = flat()
    elif mode == "pct":
        raw = pct()
    elif mode == "min_flat_pct":
        raw = minn("Brokerage: lower of flat fee and % of turnover", flat(), pct())
    else:
        raise ValueError(f"unknown brokerage mode {mode!r} in {row.ref.rule_id}")
    return rnd("Brokerage", raw, _step(row), tags={DEDUCTIBLE})


def _gst(rules: Rules, on: date, lines: dict[str, Node]) -> Node:
    row = rules.at("charges.gst", on)
    base = add("GST base", *[lines[k] for k in row.data["applies_to"] if k in lines])
    raw = mul("GST before rounding", base, from_rule("GST rate", row.value, row.ref))
    return rnd("GST", raw, _step(row), tags={DEDUCTIBLE})


def order_charges(rules: Rules, o: Order) -> Charges:
    seg = SEGMENT[o.instrument_class]
    turnover = mul("Turnover", const("Quantity", o.qty), const("Price", o.price))
    lines: dict[str, Node] = {}
    if seg != "mf":  # mutual funds are bought from the fund house: no broker, no exchange
        lines["brokerage"] = _brokerage(rules, o.on, seg, turnover)
    lines["stt"] = _rate_line(rules, "charges.stt", o.on, "STT", turnover, {"stt"},
                              instrument_class=o.instrument_class, side=o.side)
    if seg != "mf":
        lines["exchange_txn"] = _rate_line(rules, "charges.exchange_txn", o.on,
                                           "Exchange transaction charges", turnover, {DEDUCTIBLE},
                                           exchange=EXCHANGE, segment=seg)
        lines["sebi"] = _rate_line(rules, "charges.sebi", o.on, "SEBI turnover fee", turnover,
                                   {DEDUCTIBLE})
        lines["ipft"] = _rate_line(rules, "charges.ipft", o.on, "Investor protection fund charge",
                                   turnover, {DEDUCTIBLE}, exchange=EXCHANGE, segment=seg)
        lines["clearing"] = _rate_line(rules, "charges.clearing", o.on, "Clearing charges",
                                       turnover, {DEDUCTIBLE}, segment=seg)
    lines["stamp"] = _rate_line(rules, "charges.stamp", o.on, "Stamp duty", turnover, {DEDUCTIBLE},
                                segment=seg, side=o.side)
    lines["gst"] = _gst(rules, o.on, lines)
    total = add("Total charges", *lines.values())
    deductible = add("Charges deductible from capital gains",
                     *[n for n in lines.values() if DEDUCTIBLE in n.tags])
    return Charges(total, lines, deductible, turnover)


def dp_charge(rules: Rules, on: date) -> Node:
    """Depository charges for ONE charge event, GST included: Fyers' own DP fee plus the depository's share.

    What counts as one event is set by dp_basis: each sale, or each ISIN sold on a day.
    """
    broker, depo = rules.at("fyers.dp", on), rules.at("charges.dp_depository", on)
    fees = add("DP fees", from_rule("Broker DP fee", broker.value, broker.ref),
               from_rule("Depository fee", depo.value, depo.ref))
    return add("DP charges for one charge event", fees, _gst(rules, on, {"dp": fees}), tags={DEDUCTIBLE})


def dp_basis(rules: Rules, on: date) -> str:
    """`per_sale` or `per_isin_per_day`: how many times dp_charge applies to the sales of one day."""
    return rules.at("fyers.dp", on).data["basis"]


def amc_fee(rules: Rules, on: date, opened: date) -> Node:
    """Yearly demat account maintenance fee due on `on`, GST included, for an account opened on `opened`."""
    if on < opened:
        raise ValueError(f"the account was opened {opened}, after the fee date {on}")
    cohort = rules.at("fyers.amc_cohort", opened)
    row = rules.at("fyers.amc", on, cohort=cohort.data["cohort"])
    fee = cite(from_rule("Demat AMC for the year", row.value, row.ref,
                         note=f"AMC group {cohort.data['cohort']!r}: account opened {opened}"), cohort.ref)
    return add("Demat AMC with GST", fee, _gst(rules, on, {"amc": fee}))


def account_opening_fee(rules: Rules, opened: date) -> Node:
    """One-time account-opening fee for an account opened on `opened`, GST included."""
    row = rules.at("fyers.account_opening", opened)
    fee = from_rule("Account opening fee", row.value, row.ref)
    return add("Account opening fee with GST", fee, _gst(rules, opened, {"account_opening": fee}))
