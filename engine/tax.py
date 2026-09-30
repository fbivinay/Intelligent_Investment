"""Income tax for one financial year on investment items. Every rate comes from rules/."""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from engine.money import D
from engine.rules import Rules
from engine.trace import (Node, RuleRef, add, cite, const, div, from_rule, maxn, minn, mul, rnd,
                          sub)

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
    biz: tuple[tuple[int, Node], ...] = ()  # business losses, usable against business income only


@dataclass(frozen=True)
class Business:
    pnl: Node    # realised profit (+) or loss (-) on futures, before costs
    costs: Node  # every deductible cost: charges including STT, and any audit fee


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
    included: Node | None = None  # counted in total income: after loss set-off, before the yearly exemption


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


def _apply(label: str, loss: Node, pots: list[Pot]) -> Node:
    """Set `loss` off against each pot in turn; returns what is still unused."""
    for p in pots:
        if loss.value <= 0:
            break
        if p.left.value <= 0:
            continue
        used = minn(f"{label} used against {p.section}", loss, p.left)
        p.left = sub(f"{p.section} gain after {label.lower()}", p.left, used)
        loss = sub(f"{label}, unused", loss, used)
    return loss


def _order(pots: list[Pot]) -> list[Pot]:
    """Highest special rate first, then slab-taxed pots."""
    return sorted((p for p in pots if p.kind == "special"), key=lambda p: -p.rate) + \
        [p for p in pots if p.kind == "slab"]


def _slab_tax(brackets: list[dict], income: Node, ref: RuleRef) -> Node:
    pieces, lower = [], ZERO_N
    for i, b in enumerate(brackets, 1):
        rate = from_rule(f"Slab {i} rate", b["rate"], ref)
        if b["upto"] == "":
            piece = maxn(f"Income in slab {i}", sub(f"Income above slab {i - 1} limit", income, lower), ZERO_N)
        else:
            upper = from_rule(f"Slab {i} upper limit", b["upto"], ref)
            top = minn(f"Income up to slab {i} limit", income, upper)
            piece = maxn(f"Income in slab {i}", sub(f"Slab {i} income before flooring", top, lower), ZERO_N)
            lower = upper
        pieces.append(mul(f"Tax in slab {i}", piece, rate))
    return add("Tax at slab rates", *pieces)


def fy_tax(rules: Rules, fy: int, profile: TaxProfile, events: list[CGEvent],
           carry_in: Carry = Carry(), dividends: Node | None = None,
           interest: Node | None = None, business: Business | None = None) -> FYTax:
    start, end = date(fy, 4, 1), fy_end(fy)
    if profile.other_income < 0:
        raise ValueError("other_income cannot be negative")
    for e in events:
        if fy_of(e.sale_date) != fy:
            raise ValueError(f"{e.label!r} sold {e.sale_date} is not in {fy_label(fy)}")
    loss_row = rules.at("tax.loss_rules", end, kind="capital")
    years = int(loss_row.value)
    conv_setoff = rules.at("tax.conventions", end, name="setoff_order")
    conv_short = rules.at("tax.conventions", end, name="shortfall_order")
    conv_round = rules.at("tax.conventions", end, name="tax_round_step")
    reg = profile.regime if rules.has("tax.slabs", start, regime=profile.regime) else "old"

    pots: dict[tuple, Pot] = {}
    for e in events:
        gain, key, ref = classify(rules, e)
        pots.setdefault(key, Pot(*key, ref=ref, gains=[])).gains.append(gain)
    live: list[Pot] = []
    for p in pots.values():
        p.net = add(f"Net {p.section} gains ({p.term}-term)", *p.gains)
        if p.kind == "exempt":  # neither taxed nor available to set off
            continue
        p.left = maxn(f"{p.section} gain to tax", p.net, ZERO_N)
        p.loss = maxn(f"{p.section} loss", sub("Net gain below zero", ZERO_N, p.net), ZERO_N)
        live.append(p)

    before = {id(p): p.left.value for p in live}

    # Loss set-off. Order: this year's ST loss on ST gains, LT loss on LT gains, leftover ST loss on LT
    # gains, then losses brought forward (LT, then ST), oldest first.
    st, lt = [p for p in live if p.term == "short"], [p for p in live if p.term == "long"]
    st_o, lt_o = _order(st), _order(lt)
    st_loss = _apply("Short-term loss this year", add("Short-term losses this year", *[p.loss for p in st]), st_o)
    lt_loss = _apply("Long-term loss this year", add("Long-term losses this year", *[p.loss for p in lt]), lt_o)
    st_loss = _apply("Short-term loss this year, leftover", st_loss, lt_o)
    new_st: list[tuple[int, Node]] = []
    new_lt: list[tuple[int, Node]] = []
    for origin, amt in sorted(carry_in.lt, key=lambda t: t[0]):
        if fy - origin > years:
            continue
        rem = _apply(f"Long-term loss brought forward from {fy_label(origin)}", amt, lt_o)
        if rem.value > 0:
            new_lt.append((origin, rem))
    for origin, amt in sorted(carry_in.st, key=lambda t: t[0]):
        if fy - origin > years:
            continue
        rem = _apply(f"Short-term loss brought forward from {fy_label(origin)}", amt, st_o)
        rem = _apply(f"Short-term loss brought forward from {fy_label(origin)}, leftover", rem, lt_o)
        if rem.value > 0:
            new_st.append((origin, rem))
    if lt_loss.value > 0:
        new_lt.append((fy, lt_loss))
    if st_loss.value > 0:
        new_st.append((fy, st_loss))
    setoff_happened = any(p.left.value != before[id(p)] for p in live)
    for p in live:
        p.included = p.left  # the yearly exemption below lowers the tax base, not the income

    # Yearly exemption on long-term gains, per group.
    groups: dict[str, list[Pot]] = {}
    for p in lt:
        if p.group:
            groups.setdefault(p.group, []).append(p)
    for g, ps in groups.items():
        ex = rules.at("tax.lt_exemption", end, group=g)
        room = from_rule(f"Yearly long-term gains exemption ({g})", ex.value, ex.ref)
        for p in sorted(ps, key=lambda p: p.rate, reverse=ex.data["order"] == "highest_rate_first"):
            if room.value <= 0:
                break
            used = minn(f"Exemption used against {p.section} at {p.rate}", room, p.left)
            p.left = sub(f"{p.section} gain after exemption", p.left, used)
            room = sub("Exemption unused", room, used)

    # Income taxed at slab rates, and gains taxed at special rates.
    parts = [const("Other taxable income", profile.other_income)]
    parts += [p.left for p in live if p.kind == "slab"]
    if interest is not None:
        parts.append(interest)
    specials = [p for p in live if p.kind == "special"]
    div_ref = None
    if dividends is not None:
        drow = rules.at("tax.dividend", end)
        div_ref, mode = drow.ref, drow.data["mode"]
        if mode == "slab":
            parts.append(cite(dividends, drow.ref))
        elif mode == "above_threshold":
            over = maxn("Dividends above the threshold",
                        sub("Dividends less threshold", dividends,
                            from_rule("Dividend threshold", drow.dec("threshold"), drow.ref)), ZERO_N)
            specials.append(Pot("income", "special", drow.dec("rate"), "115BBDA", "", drow.ref, [],
                                left=over, included=over))
        elif mode != "exempt":
            raise ValueError(f"unknown dividend mode {mode!r}")
    # Futures income is business income at slab rates. A loss is set off against income taxed at slab rates only (never against
    # gains taxed at special rates: conservative, the business_loss_setoff convention) and the rest is carried forward for
    # business income.
    new_biz: list[tuple[int, Node]] = []
    biz_row = biz_conv = None
    if business is not None or carry_in.biz:
        biz_row = rules.at("tax.loss_rules", end, kind="business")
        old = [(o, a) for o, a in sorted(carry_in.biz, key=lambda t: t[0]) if fy - o <= int(biz_row.value)]
        net = sub("Business income after costs", business.pnl, business.costs) if business else ZERO_N
        if net.value >= 0:
            left = net
            for o, a in old:
                if left.value <= 0:
                    new_biz.append((o, a))
                    continue
                used = minn(f"Business loss from {fy_label(o)} used", a, left)
                left = sub("Business income after that loss", left, used)
                rest = sub(f"Business loss from {fy_label(o)}, unused", a, used)
                if rest.value > 0:
                    new_biz.append((o, rest))
            parts.append(left)
        else:
            biz_conv = rules.at("tax.conventions", end, name="business_loss_setoff")
            loss = sub("Business loss this year", ZERO_N, net)
            room = maxn("Slab income not below zero", add("Slab income before the business loss", *parts), ZERO_N)
            used = minn("Business loss set off against slab income", loss, room)
            parts.append(sub("Business loss set off", ZERO_N, used))
            rest = sub("Business loss carried forward", loss, used)
            new_biz = old + ([(fy, rest)] if rest.value > 0 else [])
    ordinary = add("Income taxed at slab rates", *parts)
    slab = rules.at("tax.slabs", start, regime=reg)
    brackets = slab.data["brackets"]
    ordinary_tax = _slab_tax(brackets, ordinary, slab.ref)

    # A resident individual's unused basic exemption shelters gains taxed at special rates.
    basic = from_rule("Basic exemption limit", brackets[0]["upto"] if D(brackets[0]["rate"]) == 0 else 0, slab.ref)
    shortfall = maxn("Basic exemption unused by slab income", sub("Basic exemption less slab income", basic, ordinary), ZERO_N)
    taxable: dict[int, Node] = {}
    tax_of: dict[int, Node] = {}
    by_rate = sorted(specials, key=lambda p: -p.rate)
    for p in by_rate:
        cur = p.left
        if shortfall.value > 0 and cur.value > 0:
            used = minn(f"Shortfall used against {p.section}", shortfall, cur)
            cur = sub(f"{p.section} gain after basic-exemption adjustment", cur, used)
            shortfall = sub("Shortfall unused", shortfall, used)
        taxable[id(p)] = cur
        tax_of[id(p)] = mul(f"Tax on {p.section} at {p.rate}", cur, from_rule(f"{p.section} rate", p.rate, p.ref))
    shortfall_used = any(taxable[id(p)].value != p.left.value for p in specials)
    special_tax = add("Tax at special rates", *[tax_of[id(p)] for p in by_rate])

    # Total income counts the gains in full, whatever the yearly exemption or the basic-exemption shortfall did to the tax base.
    total = add("Total income", ordinary, *[p.included for p in specials])
    tax_before = add("Tax before rebate", ordinary_tax, special_tax)

    reb = rules.at("tax.rebate_87a", start, regime=reg)
    limit = from_rule("Rebate income limit", reb.dec("income_limit"), reb.ref)
    if reb.data["applies_to_special"]:
        left_out = set(reb.data.get("excluded_sections", []))
        base = add("Tax the rebate is taken from", ordinary_tax,
                   *[tax_of[id(p)] for p in by_rate if p.section not in left_out])
    else:
        base = ordinary_tax
    if total.value <= limit.value:
        rebate = minn("Section 87A rebate", from_rule("Maximum rebate", reb.dec("max_rebate"), reb.ref), base)
    elif reb.data.get("marginal_relief", False):
        over = sub("Income over the rebate limit", total, limit)
        rebate = maxn("Marginal relief at the rebate limit", sub("Tax above the income over the limit", base, over), ZERO_N)
    else:
        rebate = from_rule("No rebate: income above the limit", 0, reb.ref)
    after_rebate = sub("Tax after rebate", tax_before, rebate)

    sc = rules.at("tax.surcharge", start, regime=reg)

    def tested_on(tier):  # the 25% and 37% tiers look at income without dividends and special-rate gains
        return ordinary if tier.get("basis") == "excluding_special" else total

    crossed = [t for t in sc.data["tiers"] if tested_on(t).value > D(t["above"])]
    if crossed:
        rate, prev = D(crossed[-1]["rate"]), (D(crossed[-2]["rate"]) if len(crossed) > 1 else D(0))
        cap = D(sc.data["cap_special"]) if sc.data.get("cap_special") else None
        cap_sections = sc.data.get("cap_sections")
        capped = [p for p in by_rate if cap is not None and (cap_sections is None or p.section in cap_sections)]
        capped_tax = add("Tax on gains whose surcharge is capped", *[tax_of[id(p)] for p in capped])
        free_tax = add("Tax on gains whose surcharge is not capped", *[tax_of[id(p)] for p in by_rate if p not in capped])

        def rates(r):  # (rate on slab tax and uncapped gains, rate on capped gains)
            return r, (min(r, cap) if cap is not None else r)

        (r1, r2), (p1, p2) = rates(rate), rates(prev)
        surcharge = add("Surcharge",
                        mul("Surcharge on slab tax", ordinary_tax, from_rule("Surcharge rate", r1, sc.ref)),
                        mul("Surcharge on uncapped special-rate tax", free_tax, from_rule("Surcharge rate", r1, sc.ref)),
                        mul("Surcharge on capped special-rate tax", capped_tax, from_rule("Surcharge rate on capped tax", r2, sc.ref)))
        threshold = from_rule("Surcharge threshold", crossed[-1]["above"], sc.ref)
        excess = sub("Income above the surcharge threshold", tested_on(crossed[-1]), threshold)
        if excess.value <= ordinary.value:  # ponytail: relief only when the excess is slab income
            tax_t = _slab_tax(brackets, sub("Slab income at the threshold", ordinary, excess), slab.ref)
            at_t = add("Tax and surcharge at the threshold", tax_t, special_tax,
                       mul("Surcharge at the lower rate", add("Tax at the threshold and uncapped gains", tax_t, free_tax),
                           from_rule("Lower surcharge rate", p1, sc.ref)),
                       mul("Surcharge at the lower rate, capped gains", capped_tax, from_rule("Lower surcharge rate, capped", p2, sc.ref)))
            ceiling = add("Most tax and surcharge may be", at_t, excess)
            now = add("Tax and surcharge now", ordinary_tax, special_tax, surcharge)
            relief = maxn("Marginal relief", sub("Tax and surcharge over the ceiling", now, ceiling), ZERO_N)
        else:
            relief = from_rule("No marginal relief computed", 0, sc.ref,
                               note="the income above the threshold is special-rate income; relief not computed")
        surcharge_final = sub("Surcharge after marginal relief", surcharge, relief)
    else:
        surcharge_final = from_rule("No surcharge", 0, sc.ref)

    cess_row = rules.at("tax.cess", start)
    cess = mul("Health and education cess", add("Tax and surcharge", after_rebate, surcharge_final),
               from_rule("Cess rate", cess_row.value, cess_row.ref))
    unrounded = add("Tax before rounding", after_rebate, surcharge_final, cess)
    tax = rnd(f"Income tax for {fy_label(fy)}", unrounded, from_rule("Tax rounding step", conv_round.value, conv_round.ref))
    if setoff_happened:
        tax = cite(tax, conv_setoff.ref)
    if shortfall_used:
        tax = cite(tax, conv_short.ref)
    if carry_in.st or carry_in.lt or new_st or new_lt:
        tax = cite(tax, loss_row.ref)
    if div_ref is not None:
        tax = cite(tax, div_ref)
    if biz_row is not None:
        tax = cite(tax, biz_row.ref)
    if biz_conv is not None:
        tax = cite(tax, biz_conv.ref)
    return FYTax(fy, tax, {"ordinary_income": ordinary, "ordinary_tax": ordinary_tax, "special_tax": special_tax,
                           "total_income": total, "rebate": rebate, "surcharge": surcharge_final,
                           "cess": cess, "before_rounding": unrounded},
                 Carry(tuple(new_st), tuple(new_lt), tuple(new_biz)))


def investment_tax(rules: Rules, fy: int, profile: TaxProfile, events: list[CGEvent],
                   carry_in: Carry = Carry(), dividends: Node | None = None,
                   interest: Node | None = None, business: Business | None = None) -> InvestmentTax:
    """Tax caused by the investments: the year's tax with them minus the year's tax without."""
    w = fy_tax(rules, fy, profile, events, carry_in, dividends, interest, business)
    wo = fy_tax(rules, fy, profile, [], Carry(), None, None)
    return InvestmentTax(sub(f"Tax caused by your investments in {fy_label(fy)}", w.tax, wo.tax), w, wo)
