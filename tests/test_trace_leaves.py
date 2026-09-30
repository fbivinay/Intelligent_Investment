"""Every number a rule supplies to a trace must be a number in its own row, so a derivation can never say a source states
something the row does not. Walks real traces (charges of every kind of order across the years, and a spread of tax years)."""
import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from engine.charges import Order, account_opening_fee, amc_fee, dp_charge, order_charges
from engine.rules import Rules
from engine.tax import Business, Carry, CGEvent, TaxProfile, investment_tax
from engine.trace import const, from_row, walk
from tests.helpers import make_rules, table

RULES = Rules.load(Path(__file__).resolve().parents[1] / "rules")
START, END = date(2010, 4, 1), date(2026, 9, 28)


def numbers(value) -> set[Decimal]:
    """Every number in a row's payload, nested lists and tables included."""
    if isinstance(value, dict):
        return set().union(*[numbers(v) for v in value.values()]) if value else set()
    if isinstance(value, (list, tuple)):
        return set().union(*[numbers(v) for v in value]) if value else set()
    try:
        return {Decimal(str(value))} if not isinstance(value, bool) and str(value) != "" else set()
    except Exception:  # noqa: BLE001  (a label such as "equity" is not a number)
        return set()


def row_of(rules, ref):
    table, _, rest = ref.rule_id.partition("[")
    key = tuple(tuple(p.split("=", 1)) for p in rest.rstrip("]").split(",")) if rest.rstrip("]") else ()
    return next(r for r in rules.tables[table].groups[key] if r.valid_from == ref.valid_from)


def check_leaves(rules, root):
    for n in walk(root):
        if n.op != "rule":
            continue
        row = row_of(rules, n.rules[0])          # a rule leaf's first rule is the row its value came from
        assert n.value == 0 or n.value in numbers(row.data), f"{n.label!r} = {n.value} is not a number in {n.rules[0].rule_id}"


def test_from_row_reads_value_and_reference_from_one_row(tmp_path):
    r = make_rules(tmp_path, {"t": table(["seg"], ['seg = "eq"\nfrom = 2010-04-01\nvalue = "0.5"\nfee = "7"'])})
    row = r.at("t", date(2020, 1, 1), seg="eq")
    rate, fee = from_row("Rate", row), from_row("Fee", row, "fee", note="per order")
    assert rate.value == Decimal("0.5") and fee.value == Decimal("7") and rate.op == "rule"
    assert rate.rules == (row.ref,) and fee.note == "per order"
    with pytest.raises(KeyError):
        from_row("Nothing", row, "not_a_field")


def test_a_rule_leaf_is_a_number_in_its_own_row_for_every_charge_the_engine_makes():
    rnd = random.Random(7)
    span = (END - START).days
    for _ in range(400):
        on = START + timedelta(days=rnd.randrange(span))
        cls = rnd.choice(["etf_equity", "etf_gold", "fut_index", "mf_equity", "mf_debt"])
        check_leaves(RULES, order_charges(RULES, Order(on, cls, rnd.choice(["buy", "sell"]), Decimal(rnd.choice([1, 100, 1567])), Decimal("123.45"))).total)
        check_leaves(RULES, dp_charge(RULES, on))
        opened = START + timedelta(days=rnd.randrange((on - START).days + 1))
        check_leaves(RULES, amc_fee(RULES, on, opened))
        check_leaves(RULES, account_opening_fee(RULES, opened))


def test_a_rule_leaf_is_a_number_in_its_own_row_for_a_spread_of_tax_years():
    rnd = random.Random(11)
    for _ in range(250):
        fy = rnd.randrange(2010, 2027)
        sale = date(fy, 4, 1) + timedelta(days=rnd.randrange(365))
        sale = min(sale, END)
        acq = max(sale - timedelta(days=rnd.choice([30, 400, 900, 2000])), START)
        events = [CGEvent("x", sale, rnd.choice(["etf_equity", "etf_gold", "mf_debt", "mf_equity"]), acq,
                          const("p", rnd.choice([80_000, 400_000, 30_000_000])), const("c", 0), const("k", 100_000),
                          const("f", 150_000) if acq <= date(2018, 1, 31) else None)]
        biz = Business(const("p", rnd.choice([-3_000_000, 500_000])), const("c", 5_000)) if rnd.random() < 0.4 else None
        r = investment_tax(RULES, fy, TaxProfile(rnd.choice(["old", "new"]), Decimal(rnd.choice([0, 400_000, 1_500_000, 30_000_000]))),
                           events if rnd.random() < 0.8 else [], dividends=const("d", 20_000) if rnd.random() < 0.3 else None, dividend_payer=rnd.choice(["fund", "company"]),
                           interest=const("i", 5_000) if rnd.random() < 0.3 else None, business=biz)
        check_leaves(RULES, r.with_items.tax)
        check_leaves(RULES, r.extra)


def test_the_rounding_step_is_credited_to_a_row_only_when_the_row_states_it():
    on = date(2020, 1, 1)
    line = order_charges(RULES, Order(on, "etf_equity", "sell", Decimal("100"), Decimal("100"))).lines
    step = next(n for n in walk(line["stt"]) if n.label == "Rounding step")
    assert step.op == "rule" and step.rules[0].rule_id.startswith("charges.stt")            # STT rows state a step
    step = next(n for n in walk(line["gst"]) if n.label == "Rounding step")
    assert step.op == "const" and step.rules == () and "engine convention" in step.note      # the GST row does not
