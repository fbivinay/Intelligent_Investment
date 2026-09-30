"""Surcharge marginal relief on the REAL rules.

Across a surcharge threshold the tax and surcharge may not exceed the tax on the threshold income plus the income above it, so tax
never jumps by more than the extra income (plus cess and the Rs 10 rounding). This must hold whatever the income is made of: pay,
long-term gains, short-term gains or a mix. The anchors below are worked by hand.
"""
from datetime import date
from decimal import Decimal as Dc
from pathlib import Path

import pytest

from engine.rules import Rules
from engine.tax import TaxProfile, fy_tax
from engine.trace import assert_balanced, rules_used
from tests.tax_helpers import ev

RULES = Rules.load(Path(__file__).resolve().parents[1] / "rules")
BASE = Dc(1_000_000)


def gain_event(fy, kind, gain):
    """One equity ETF sale in `fy` with exactly `gain` of gain: short-term (kind stcg) or long-term (kind ltcg), never grandfathered."""
    sale = date(fy, 12, 1)
    acq = date(2018, 6, 1) if kind == "ltcg" else date(fy, 10, 1)
    return ev(acq.isoformat(), sale.isoformat(), str(BASE), str(BASE + Dc(gain)))


def year(fy, regime, kind, income):
    """Tax for a year in which the total income is `income`, made of: pay only (salary), gains only (ltcg, stcg), or 30 lakh of pay plus gains."""
    if kind == "salary":
        return fy_tax(RULES, fy, TaxProfile(regime, Dc(income)), [])
    pay = Dc(3_000_000) if kind.startswith("mixed") else Dc(0)
    gains = "ltcg" if kind in ("ltcg", "mixed_ltcg") else "stcg"
    return fy_tax(RULES, fy, TaxProfile(regime, pay), [gain_event(fy, gains, Dc(income) - pay)])


def test_ltcg_just_over_50_lakh_pays_the_tax_on_50_lakh_plus_the_excess():
    # FY2025-26, new regime, no other income, long-term gain of 50,00,250: total income 50,00,250.
    # Taxable: 5,000,250 - 125,000 exemption - 400,000 unused basic exemption = 4,475,250; x 12.5% = 559,406.25.
    # Surcharge before relief 10% = 55,940.625. The threshold income (250 less) pays 559,375 with no surcharge, so tax + surcharge
    # may not pass 559,375 + 250 = 559,625: relief 55,721.875, surcharge 218.75. Cess 4% on 559,625 = 22,385.
    p = year(2025, "new", "ltcg", 5_000_250).parts
    assert p["surcharge"].value == Dc("218.75")
    assert p["before_rounding"].value == Dc("582010.00")
    at_threshold = year(2025, "new", "ltcg", 5_000_000).parts
    assert at_threshold["surcharge"].value == 0 and at_threshold["before_rounding"].value == Dc("581750.00")


def test_stcg_just_over_50_lakh_pays_the_tax_on_50_lakh_plus_the_excess():
    # Short-term gain of 50,00,250 at 20%: (5,000,250 - 400,000) x 20% = 920,050; surcharge before relief 92,005.
    # Threshold income pays 920,000, so tax + surcharge may not pass 920,250: surcharge 200. Cess 4% on 920,250 = 36,810.
    p = year(2025, "new", "stcg", 5_000_250).parts
    assert p["surcharge"].value == Dc("200.00")
    assert p["before_rounding"].value == Dc("957060.00")


def test_ltcg_just_over_1_crore_relieves_down_to_the_tax_at_the_lower_rate_plus_the_excess():
    # Long-term gain of 1,00,00,250 (15% tier, cap 15%): (10,000,250 - 125,000 - 400,000) x 12.5% = 1,184,406.25; surcharge 177,660.9375.
    # Threshold income pays 1,184,375 + 10% surcharge 118,437.5 = 1,302,812.5, so the total may not pass 1,303,062.5:
    # surcharge 118,656.25. Cess 4% on 1,303,062.5 = 52,122.5.
    p = year(2025, "new", "ltcg", 10_000_250).parts
    assert p["surcharge"].value == Dc("118656.25")
    assert p["before_rounding"].value == Dc("1355185.00")


def test_with_two_kinds_of_gain_the_excess_comes_out_of_the_lower_rate_gain():
    # FY2025-26, new regime, no pay: short-term gain 3,000,000 (20%) and long-term gain 2,000,250 (12.5%); total income 5,000,250.
    # The 400,000 unused basic exemption shelters the 20% gain first: 2,600,000 x 20% = 520,000. Long-term: 2,000,250 - 125,000 = 1,875,250
    # x 12.5% = 234,406.25. Tax 754,406.25; surcharge before relief 75,440.625. The 250 over the threshold comes out of the 12.5% gain, so the
    # threshold income pays 520,000 + 234,375 = 754,375: the total may not pass 754,625, and the surcharge is 218.75.
    events = [gain_event(2025, "stcg", 3_000_000), gain_event(2025, "ltcg", 2_000_250)]
    p = fy_tax(RULES, 2025, TaxProfile("new", Dc(0)), events).parts
    assert p["total_income"].value == Dc("5000250") and p["special_tax"].value == Dc("754406.25")
    assert p["surcharge"].value == Dc("218.75")


def test_pay_smaller_than_the_excess_is_given_up_first_and_the_rest_comes_out_of_the_gain():
    # FY2025-26, new regime, pay 100 and a long-term gain of 5,000,200: total income 5,000,300, 300 over the threshold.
    # Now: unused basic exemption 399,900, so (5,000,200 - 125,000 - 399,900) x 12.5% = 559,412.5; surcharge before relief 55,941.25.
    # Threshold income: pay 0 and gain 200 less, so the full 400,000 exemption: 4,475,000 x 12.5% = 559,375. The total may not pass 559,675:
    # surcharge 262.50, tax before rounding 559,675 x 1.04 = 582,062.
    events = [gain_event(2025, "ltcg", 5_000_200)]
    p = fy_tax(RULES, 2025, TaxProfile("new", Dc(100)), events).parts
    assert p["total_income"].value == Dc("5000300")
    assert p["surcharge"].value == Dc("262.50") and p["before_rounding"].value == Dc("582062.00")


@pytest.mark.parametrize("fy, regime", [(2019, "old"), (2022, "old"), (2025, "old"), (2025, "new")])
@pytest.mark.parametrize("kind", ["salary", "ltcg", "stcg", "mixed_ltcg", "mixed_stcg"])
@pytest.mark.parametrize("threshold", [5_000_000, 10_000_000])
def test_tax_never_jumps_by_more_than_the_extra_income_across_a_surcharge_threshold(fy, regime, kind, threshold):
    at = year(fy, regime, kind, threshold).tax.value
    for extra in (1, 250, 10_000, 100_000, 400_000):
        now = year(fy, regime, kind, threshold + extra).tax.value
        assert 0 <= now - at <= Dc("1.04") * extra + 10, f"{fy} {regime} {kind}: +{extra} of income at {threshold} raised tax by {now - at}"


def test_the_convention_for_taking_the_excess_from_gains_is_cited_only_when_it_was_used():
    used = year(2025, "new", "ltcg", 5_000_250).tax
    not_used = year(2025, "new", "salary", 5_000_250).tax
    assert_balanced(used)
    name = "tax.conventions[name=marginal_relief_order]"
    assert name in {r.rule_id for r in rules_used(used)}
    assert name not in {r.rule_id for r in rules_used(not_used)}
