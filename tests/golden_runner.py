"""Golden cases: hand-worked expected values, checked against the engine and against the rule rows.

A case is a [[case]] table in tests/golden/*.toml. Every case needs `id`, `kind`, `source`.
Kinds register themselves below; a case's `boundary = ["<rule_id>@<YYYY-MM-DD>:before|after"]` says it
probes one side of a rule change, and the runner checks that the engine really used that row.
"""
from __future__ import annotations

import tomllib
from datetime import date, timedelta
from pathlib import Path

from engine.money import D
from engine.rules import Rules

KINDS: dict = {}


def kind(name):
    def deco(fn):
        KINDS[name] = fn
        return fn
    return deco


def load_cases(folder: Path) -> list[dict]:
    cases = []
    for p in sorted(Path(folder).glob("*.toml")):
        for c in tomllib.loads(p.read_text(encoding="utf-8")).get("case", []):
            for f in ("id", "kind", "source"):
                if f not in c:
                    raise ValueError(f"{p.name}: a case is missing `{f}`: {c}")
            c["file"] = p.name
            cases.append(c)
    ids = [c["id"] for c in cases]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate golden case ids: {sorted(dupes)}")
    return cases


def same(actual, expected) -> bool:
    """Numbers compare as exact decimals; anything else (text, dates, lists) by equality."""
    try:
        return D(actual) == D(expected)
    except (ArithmeticError, TypeError, ValueError):
        return actual == expected


@kind("rule_value")
def _rule_value(rules: Rules, c: dict):
    """Fields of a rule row on a date equal the values typed from the source. Returns the rule refs used."""
    row = rules.at(c["table"], c["on"], **c.get("key", {}))
    for field, want in c["expect"].items():
        assert same(row.data.get(field), want), f"{c['id']}: {field} is {row.data.get(field)!r}, source says {want!r}"
    return {row.ref}


def run_case(rules: Rules, c: dict):
    return KINDS[c["kind"]](rules, c)


def check_boundary_tags(c: dict, refs) -> None:
    """A tagged case must really have used the row on the named side of the change."""
    for tag in c.get("boundary", []):
        rid_day, phase = tag.rsplit(":", 1)
        rid, day = rid_day.rsplit("@", 1)
        d = date.fromisoformat(day)
        if phase == "after":
            ok = any(r.rule_id == rid and r.valid_from == d for r in refs)
        else:
            ok = any(r.rule_id == rid and r.valid_to == d - timedelta(days=1) for r in refs)
        assert ok, f"{c['id']}: tagged {tag} but the engine did not use that row"


def all_boundaries(rules: Rules):
    """Every (rule_id, change date) where one row ends and the next begins."""
    for t in rules.tables.values():
        for rows in t.groups.values():
            for a, b in zip(rows, rows[1:]):
                yield a.ref.rule_id, b.valid_from


def missing_coverage(rules: Rules, cases: list[dict]) -> list[str]:
    """Rule changes lacking a case on the day before or on the day of the change."""
    tagged = {t for c in cases for t in c.get("boundary", [])}
    return [f"{rid}@{d}:{phase}" for rid, d in all_boundaries(rules) for phase in ("before", "after")
            if f"{rid}@{d}:{phase}" not in tagged]


@kind("charges")
def _charges(rules: Rules, c: dict):
    """Order charges: each named line, `total`, `deductible` or `turnover` equals the hand-worked value."""
    from engine.charges import Order, order_charges
    from engine.trace import assert_balanced, rules_used
    i = c["input"]
    ch = order_charges(rules, Order(i["on"], i["instrument_class"], i["side"], D(i["qty"]), D(i["price"])))
    named = {**ch.lines, "total": ch.total, "deductible": ch.deductible, "turnover": ch.turnover}
    for name, want in c["expect"].items():
        assert same(named[name].value, want), f"{c['id']}: {name} is {named[name].value}, hand-worked {want}"
    assert_balanced(ch.total)
    return rules_used(ch.total)


@kind("dp")
def _dp(rules: Rules, c: dict):
    """One DP charge event (`total`) and, if given, the rule's `basis`."""
    from engine.charges import dp_basis, dp_charge
    from engine.trace import assert_balanced, rules_used
    on = c["input"]["on"]
    n = dp_charge(rules, on)
    assert same(n.value, c["expect"]["total"]), f"{c['id']}: total is {n.value}, hand-worked {c['expect']['total']}"
    if "basis" in c["expect"]:
        assert dp_basis(rules, on) == c["expect"]["basis"], f"{c['id']}: basis is {dp_basis(rules, on)}, hand-worked {c['expect']['basis']}"
    assert_balanced(n)
    return rules_used(n)


@kind("amc")
def _amc(rules: Rules, c: dict):
    """Yearly AMC due on `on` for an account opened on `opened`."""
    from engine.charges import amc_fee
    from engine.trace import assert_balanced, rules_used
    n = amc_fee(rules, c["input"]["on"], c["input"]["opened"])
    assert same(n.value, c["expect"]["total"]), f"{c['id']}: total is {n.value}, hand-worked {c['expect']['total']}"
    assert_balanced(n)
    return rules_used(n)


@kind("account_opening")
def _account_opening(rules: Rules, c: dict):
    """Account-opening fee for an account opened on `opened`."""
    from engine.charges import account_opening_fee
    from engine.trace import assert_balanced, rules_used
    n = account_opening_fee(rules, c["input"]["opened"])
    assert same(n.value, c["expect"]["total"]), f"{c['id']}: total is {n.value}, hand-worked {c['expect']['total']}"
    assert_balanced(n)
    return rules_used(n)


@kind("tax_fy")
def _tax_fy(rules: Rules, c: dict):
    """One year's tax: `extra` (caused by the investments), `tax_with`, `tax_without` or any part."""
    from engine.tax import Business, Carry, CGEvent, TaxProfile, investment_tax
    from engine.trace import assert_balanced, const, rules_used
    i = c["input"]
    events = [CGEvent(e.get("label", "sale"), e["sale_date"], e["asset_class"], e["acq_date"],
                      const("Proceeds", e["proceeds"]), const("Sale costs", e.get("sale_costs", "0")),
                      const("Cost", e["cost"]),
                      const("Value on 31 Jan 2018", e["fmv_2018"]) if "fmv_2018" in e else None)
              for e in i.get("events", [])]

    def carried(name):
        return tuple((x["origin"], const("Loss brought forward", x["amount"])) for x in i.get(name, []))

    b = i.get("business")
    business = Business(const("Futures P&L", b["pnl"]), const("Costs", b["costs"])) if b else None
    r = investment_tax(rules, i["fy"], TaxProfile(i["regime"], D(i["other_income"])), events,
                       carry_in=Carry(carried("carry_st"), carried("carry_lt"), carried("carry_biz")),
                       dividends=const("Dividends", i["dividends"]) if "dividends" in i else None,
                       dividend_payer=i.get("dividend_payer"),           # "fund" or "company"; the engine refuses dividends without one
                       interest=const("Interest", i["interest"]) if "interest" in i else None,
                       business=business)
    named = {"extra": r.extra, "tax_with": r.with_items.tax, "tax_without": r.without_items.tax,
             **r.with_items.parts}
    for name, want in c["expect"].items():
        assert same(named[name].value, want), f"{c['id']}: {name} is {named[name].value}, hand-worked {want}"
    assert_balanced(r.extra)
    return rules_used(r.extra)


@kind("audit")
def _audit(rules: Rules, c: dict):
    """Audit fee for a year, from the profit or loss of each closed futures trade."""
    from engine.business import audit_fee, futures_turnover
    from engine.trace import assert_balanced, const, rules_used
    i = c["input"]
    turnover = futures_turnover([const("Trade", p) for p in i["trade_pnls"]])
    if "turnover" in c["expect"]:
        assert same(turnover.value, c["expect"]["turnover"]), f"{c['id']}: turnover is {turnover.value}, hand-worked {c['expect']['turnover']}"
    fee = audit_fee(rules, i["fy"], turnover)
    assert same(fee.value, c["expect"]["fee"]), f"{c['id']}: fee is {fee.value}, hand-worked {c['expect']['fee']}"
    assert_balanced(fee)
    return rules_used(fee)
