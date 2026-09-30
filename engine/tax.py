"""Income tax for one financial year on investment items. Every rate comes from rules/."""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from engine.rules import Rules
from engine.trace import Node, RuleRef, cite, const, div, from_rule, maxn, minn, mul, sub

ZERO_N = const("Zero", 0)


def fy_of(d: date) -> int:
    """Financial year as its starting calendar year: 1 Apr 2024 to 31 Mar 2025 is 2024."""
    return d.year if d.month >= 4 else d.year - 1


def fy_end(fy: int) -> date:
    return date(fy + 1, 3, 31)


def fy_label(fy: int) -> str:
    return f"FY{fy}-{str(fy + 1)[2:]}"


def add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    y, m = d.year + y, m + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


@dataclass(frozen=True)
class TaxProfile:
    regime: str            # "old" | "new"; "old" is used in years before the new regime existed
    other_income: Decimal  # other taxable income for the year, after deductions


@dataclass(frozen=True)
class CGEvent:
    label: str
    sale_date: date
    asset_class: str
    acq_date: date
    proceeds: Node                 # full value of consideration
    sale_costs: Node               # transfer costs deductible from the gain (never STT)
    cost: Node                     # cost of acquisition, buy-side costs included
    fmv_2018: Node | None = None   # value of these units on 31 Jan 2018 (needed if bought on or before it)


@dataclass(frozen=True)
class Carry:
    st: tuple[tuple[int, Node], ...] = ()  # (financial year the loss arose, amount), oldest first
    lt: tuple[tuple[int, Node], ...] = ()


@dataclass(frozen=True)
class FYTax:
    fy: int
    tax: Node
    parts: dict[str, Node]
    carry_out: Carry


@dataclass(frozen=True)
class InvestmentTax:
    extra: Node
    with_items: FYTax
    without_items: FYTax


@dataclass
class Pot:
    term: str          # short | long | income
    kind: str          # special | slab | exempt
    rate: Decimal | None
    section: str
    group: str         # exemption group, "" if none
    ref: RuleRef
    gains: list[Node]
    net: Node | None = None
    left: Node | None = None  # still to tax after loss set-off and exemption
    loss: Node | None = None


def classify(rules: Rules, e: CGEvent):
    """Gain of one sale, and which pot it belongs to: (gain node, (term, kind, rate, section, group), rule ref)."""
    brow = rules.at("tax.buckets", e.acq_date, asset_class=e.asset_class)
    cg = rules.at("tax.capital_gains", e.sale_date, bucket=brow.data["bucket"])
    deemed = cg.data.get("always_short", False)  # section 50AA: short-term whatever the holding period
    months = None if deemed else int(cg.data["lt_months"])
    long_ = not deemed and e.sale_date > add_months(e.acq_date, months)
    cost = e.cost
    gf = cg.data.get("grandfather_acq_upto")
    if long_ and gf is not None and e.acq_date <= gf:
        if e.fmv_2018 is None:
            raise ValueError(f"{e.label}: bought {e.acq_date} (on or before {gf}), so fmv_2018 is required")
        cost = maxn("Cost after 31 Jan 2018 grandfathering", cost,
                    minn("Lower of value on 31 Jan 2018 and sale value", e.fmv_2018, e.proceeds))
    net_sale = sub("Net sale value", e.proceeds, e.sale_costs)
    series = "1981" if rules.has("tax.cii", e.sale_date, series="1981") else "2001"

    def gain_with(indexed: bool, note: str) -> Node:
        c = cost
        if indexed:
            f = div("Indexation factor",
                    from_rule(f"Cost inflation index, year of sale (series {series})", *_cii(rules, series, e.sale_date)),
                    from_rule(f"Cost inflation index, year of purchase (series {series})", *_cii(rules, series, e.acq_date)))
            c = mul("Indexed cost of acquisition", cost, f)
        return sub(f"Taxable gain: {e.label}", net_sale, c, note=note)

    if deemed:
        held = f"held {e.acq_date} to {e.sale_date}; deemed short-term whatever the holding period ({cg.data['st_section']})"
    else:
        held = f"held {e.acq_date} to {e.sale_date}; long-term needs more than {months} months"
    side = "lt" if long_ else "st"
    treatment, section = cg.data[f"{side}_treatment"], cg.data[f"{side}_section"]
    rate = cg.dec(f"{side}_rate") if treatment == "special" else None
    indexed = long_ and cg.data.get("indexation", False)
    if long_ and "lt_alt_rate" in cg.data:
        # The taxpayer may instead pay the option rate on the gain worked out as the option says; the lower tax is used
        # (and, on a tie, the lower gain: a bigger loss can be carried forward).
        if rate is None:
            raise ValueError(f"{cg.ref.rule_id}: lt_alt_rate needs lt_treatment = special")
        main, alt = gain_with(indexed, held), gain_with(cg.data["lt_alt_indexation"], held)
        alt_rate = cg.dec("lt_alt_rate")
        t_main, t_alt = max(main.value, 0) * rate, max(alt.value, 0) * alt_rate
        if (t_alt, alt.value) < (t_main, main.value):
            held += (f"; lower tax by the {cg.data['lt_alt_section']}: tax {t_alt} on a gain of {alt.value} "
                     f"instead of tax {t_main} on {main.value}")
            indexed, rate, section = cg.data["lt_alt_indexation"], alt_rate, cg.data["lt_alt_section"]
        else:
            held += (f"; lower tax by the ordinary route: tax {t_main} on a gain of {main.value} "
                     f"instead of tax {t_alt} on {alt.value} under the {cg.data['lt_alt_section']}")
    gain = cite(gain_with(indexed, held), cg.ref, brow.ref)
    group = cg.data.get("lt_exemption_group", "") if long_ and treatment == "special" else ""
    return gain, ("long" if long_ else "short", treatment, rate, section, group), cg.ref


def _cii(rules: Rules, series: str, on: date):
    row = rules.at("tax.cii", on, series=series)
    return row.value, row.ref
