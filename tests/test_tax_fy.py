from decimal import Decimal as Dc

import pytest

from engine.tax import Business, Carry, TaxProfile, fy_tax, investment_tax
from engine.trace import assert_balanced, const, flags, rules_used
from tests.helpers import make_rules
from tests.synth_tax import TAX
from tests.tax_helpers import ev


@pytest.fixture
def rules(tmp_path):
    return make_rules(tmp_path, TAX)


def extra(rules, fy, events, income="1000000", regime="old", **kw):
    r = investment_tax(rules, fy, TaxProfile(regime, Dc(income)), events, **kw)
    assert_balanced(r.extra)
    return r


# ---- capital gains --------------------------------------------------------

def test_short_term_gain_is_taxed_at_the_special_rate_on_top_of_slab_income(rules):
    r = extra(rules, 2019, [ev("2019-06-01", "2019-12-01", "10000", "20000")])
    assert r.extra.value == Dc("1560")       # 10,000 x 15% x 1.04 cess
    assert flags(r.extra) == []              # nothing assumed was used


def test_basic_exemption_shelters_gains_when_other_income_is_zero(rules):
    r = extra(rules, 2019, [ev("2019-06-01", "2019-12-01", "10000", "20000")], income="0")
    assert r.extra.value == 0
    assert [f.rule_id for f in flags(r.with_items.tax)] == ["tax.conventions[name=shortfall_order]"]


def test_new_regime_rebate_does_not_cover_special_rate_tax(rules):
    r = extra(rules, 2021, [ev("2021-06-01", "2021-12-01", "10000", "20000")], income="295000", regime="new")
    assert r.extra.value == Dc("780")        # 5,000 left after basic exemption x 15% x 1.04


def test_long_term_gain_uses_the_yearly_exemption(rules):
    r = extra(rules, 2019, [ev("2018-03-01", "2019-06-01", "100000", "250000")])
    assert r.extra.value == Dc("5200")       # (150,000 - 100,000) x 10% x 1.04


def test_long_term_gain_before_2018_is_exempt(rules):
    assert extra(rules, 2017, [ev("2015-01-01", "2017-06-01", "100000", "250000")]).extra.value == 0


def test_grandfathering_raises_cost_to_the_value_on_31_jan_2018(rules):
    e = ev("2016-01-01", "2019-06-01", "1000000", "2500000", fmv="2000000")
    assert extra(rules, 2019, [e]).extra.value == Dc("41600")   # (500,000 - 100,000) x 10% x 1.04


def test_grandfathering_cannot_push_cost_above_the_sale_value(rules):
    e = ev("2016-01-01", "2019-06-01", "1000000", "2500000", fmv="3000000")
    assert extra(rules, 2019, [e]).extra.value == 0


def test_indexation_scales_cost_by_the_inflation_index(rules):
    e = ev("2012-06-01", "2016-08-01", "100000", "200000", cls="etf_gold")
    r = extra(rules, 2016, [e])
    # old series 540 -> 620: cost 114,814.81, gain 85,185.19, tax 20% = 17,037.04; with cess 134,718.52 -> 134,720
    # against 117,000 without the sale
    assert r.extra.value == Dc("17720")


def test_debt_fund_bought_after_march_2023_is_always_short_term_at_slab_rates(rules):
    e = ev("2023-05-01", "2025-06-01", "100000", "200000", cls="mf_debt")
    assert extra(rules, 2025, [e]).extra.value == Dc("31200")   # 100,000 x 30% x 1.04


def test_sale_outside_the_year_is_refused(rules):
    with pytest.raises(ValueError, match="not in FY2019-20"):
        fy_tax(rules, 2019, TaxProfile("old", Dc(0)), [ev("2019-06-01", "2020-06-01", "1", "2")])


def test_negative_other_income_is_refused(rules):
    with pytest.raises(ValueError, match="negative"):
        fy_tax(rules, 2019, TaxProfile("old", Dc(-1)), [])


# ---- losses ---------------------------------------------------------------

def test_short_term_loss_is_set_off_against_long_term_gain(rules):
    loss = ev("2019-01-10", "2019-06-01", "100000", "70000", label="loss")
    gain = ev("2018-03-01", "2019-07-01", "100000", "250000", label="gain")
    r = extra(rules, 2019, [loss, gain])
    assert r.extra.value == Dc("2080")       # (150,000 - 30,000 - 100,000 exemption) x 10% x 1.04
    assert r.with_items.carry_out == Carry()
    assert "tax.conventions[name=setoff_order]" in [f.rule_id for f in flags(r.with_items.tax)]


def test_unused_loss_is_carried_forward_then_used(rules):
    y1 = extra(rules, 2018, [ev("2018-05-01", "2018-09-01", "100000", "60000")])
    assert y1.extra.value == 0
    assert [(o, n.value) for o, n in y1.with_items.carry_out.st] == [(2018, Dc("40000"))]
    y2 = extra(rules, 2019, [ev("2019-05-01", "2019-09-01", "100000", "200000")], carry_in=y1.with_items.carry_out)
    assert y2.extra.value == Dc("9360")      # (100,000 - 40,000) x 15% x 1.04
    assert y2.with_items.carry_out == Carry()


@pytest.mark.parametrize("origin, expected", [(2011, "9360"), (2010, "15600")])
def test_losses_expire_after_eight_years(rules, origin, expected):
    carry = Carry(st=((origin, const("old loss", "40000")),))
    r = extra(rules, 2019, [ev("2019-05-01", "2019-09-01", "100000", "200000")], carry_in=carry)
    assert r.extra.value == Dc(expected)


def carried_out(r, kind):
    return [(o, n.value) for o, n in getattr(r.with_items.carry_out, kind)]


def test_a_long_term_loss_brought_forward_never_reduces_a_short_term_gain(rules):
    # section 74(1)(b): a long-term loss is set off against long-term gains only
    stcg = ev("2019-06-01", "2019-12-01", "10000", "110000")                     # 100,000 short-term gain at 15%
    r = extra(rules, 2019, [stcg], carry_in=Carry(lt=((2018, const("loss", "60000")),)))
    assert r.extra.value == Dc("15600")                                          # 100,000 x 15% x 1.04: the loss changes nothing
    assert carried_out(r, "lt") == [(2018, Dc("60000"))]


@pytest.mark.parametrize("origin, expected", [(2011, "0"), (2010, "5200")])
def test_long_term_losses_expire_after_eight_years(rules, origin, expected):
    ltcg = ev("2018-03-01", "2019-07-01", "100000", "250000")                    # 150,000 long-term gain, 100,000 of it exempt
    r = extra(rules, 2019, [ltcg], carry_in=Carry(lt=((origin, const("loss", "60000")),)))
    assert r.extra.value == Dc(expected)      # usable: 90,000 is under the exemption; expired: 50,000 x 10% x 1.04


@pytest.mark.parametrize("kind, gain", [("st", ev("2019-06-01", "2019-12-01", "10000", "50000")),       # 40,000 short-term gain
                                        ("lt", ev("2018-03-01", "2019-07-01", "100000", "140000"))])   # 40,000 long-term gain
def test_losses_brought_forward_are_used_oldest_first(rules, kind, gain):
    losses = ((2018, const("newer", "30000")), (2017, const("older", "30000")))                        # given newest first
    r = extra(rules, 2019, [gain], carry_in=Carry(**{kind: losses}))
    assert carried_out(r, kind) == [(2018, Dc("20000"))]                          # all of 2017's 30,000, then 10,000 of 2018's


def test_the_unused_basic_exemption_shelters_the_highest_rate_gain_first(rules):
    events = [ev("2019-06-01", "2019-12-01", "10000", "210000", label="stcg"),                          # 200,000 at 15%
              ev("2018-03-01", "2019-07-01", "100000", "400000", label="ltcg")]                         # 300,000, 200,000 above the exemption, at 10%
    r = extra(rules, 2019, events, income="0")
    # the 250,000 unused basic exemption covers all of the 15% gain, then 50,000 of the 10% gain: 150,000 x 10%
    assert r.with_items.parts["special_tax"].value == Dc("15000")


def test_the_carry_forward_rule_row_is_cited_when_a_carried_loss_is_used(rules):
    carry = Carry(st=((2018, const("old loss", "40000")),))
    r = extra(rules, 2019, [ev("2019-05-01", "2019-09-01", "100000", "200000")], carry_in=carry)
    assert "tax.loss_rules[kind=capital]" in {x.rule_id for x in rules_used(r.with_items.tax)}


def test_a_loss_on_an_exempt_sale_is_not_carried_forward(rules):
    r = extra(rules, 2017, [ev("2015-01-01", "2017-06-01", "200000", "100000")])
    assert r.with_items.carry_out == Carry()


# ---- dividends ------------------------------------------------------------

@pytest.mark.parametrize("fy, dividends, expected", [
    (2013, "1200000", "0"),        # company-paid tax era: exempt
    (2017, "1200000", "20800"),    # only the part above Rs 10 lakh, at 10% x 1.04
    (2021, "100000", "31200"),     # slab rate 30% x 1.04
])
def test_dividend_tax_follows_the_rule_of_the_year(rules, fy, dividends, expected):
    r = extra(rules, fy, [], dividends=const("Dividends", dividends))
    assert r.extra.value == Dc(expected)


def test_the_dividend_rule_row_is_cited_even_when_dividends_are_exempt(rules):
    r = fy_tax(rules, 2013, TaxProfile("old", Dc(0)), [], dividends=const("Dividends", "5000"))
    assert "tax.dividend[]" in {x.rule_id for x in rules_used(r.tax)}


# ---- slabs, rebate, surcharge, cess ---------------------------------------

def test_new_regime_falls_back_to_old_before_it_existed(rules):
    assert fy_tax(rules, 2018, TaxProfile("new", Dc("1000000")), []).tax.value == Dc("117000")
    assert fy_tax(rules, 2021, TaxProfile("new", Dc("1000000")), []).tax.value == Dc("78000")


@pytest.mark.parametrize("income, expected", [("700000", "0"), ("710000", "10400")])
def test_new_regime_rebate_and_its_marginal_relief(rules, income, expected):
    assert fy_tax(rules, 2021, TaxProfile("new", Dc(income)), []).tax.value == Dc(expected)


def test_the_yearly_exempt_part_of_a_gain_still_counts_as_income_for_the_rebate_limit(rules):
    # total income is 400,000 + 150,000 = 550,000, above the Rs 5 lakh limit, although Rs 100,000 of the gain pays no tax
    r = extra(rules, 2019, [ev("2018-03-01", "2019-06-01", "100000", "250000")], income="400000")
    assert r.with_items.parts["total_income"].value == Dc("550000")
    assert r.with_items.parts["rebate"].value == 0
    assert r.extra.value == Dc("13000")      # (7,500 + 5,000) x 1.04; the year without the sale paid nothing


def test_the_rebate_takes_in_short_term_equity_tax_but_leaves_out_section_112a_tax(rules):
    events = [ev("2019-06-01", "2019-12-01", "10000", "60000", label="stcg"),            # 50,000 at 15% = 7,500
              ev("2018-03-01", "2019-06-15", "100000", "250000", label="ltcg")]           # 150,000, 50,000 above the exemption
    r = extra(rules, 2019, events, income="250000")
    assert r.with_items.parts["total_income"].value == Dc("450000")
    assert r.with_items.parts["special_tax"].value == Dc("12500")
    assert r.with_items.parts["rebate"].value == Dc("7500")   # the 111A tax only; not the 5,000 on the 112A gain
    assert r.extra.value == Dc("5200")                          # (12,500 - 7,500) x 1.04


def test_surcharge_marginal_relief_just_above_the_threshold(rules):
    p = fy_tax(rules, 2019, TaxProfile("old", Dc("5010000")), []).parts
    assert p["surcharge"].value == Dc("7000")   # tax + surcharge capped at tax at 50 lakh + the 10,000 above it
    assert fy_tax(rules, 2019, TaxProfile("old", Dc("6000000")), []).parts["surcharge"].value == Dc("161250")


def test_the_top_tier_looks_at_income_without_special_rate_gains(rules):
    # slab income 15,000,000 (tax 4,312,500) and a 10,000,000 short-term gain (tax 1,500,000): total income is above 20,000,000
    # but the 25% tier needs slab income above it, so the 15% tier applies to both
    e = ev("2019-06-01", "2019-12-01", "10000", "10010000")
    p = fy_tax(rules, 2019, TaxProfile("old", Dc("15000000")), [e]).parts
    assert p["surcharge"].value == Dc("871875")   # 15% x (4,312,500 + 1,500,000)


def test_the_surcharge_cap_covers_only_the_sections_the_rule_lists(rules):
    # slab income 25,000,000 puts everything in the 25% tier; the cap of 15% is listed for 111A gains only
    events = [ev("2019-06-01", "2019-12-01", "10000", "110000", label="stcg"),                         # 100,000 at 15%
              ev("2012-06-01", "2019-08-01", "100000", "200000", cls="etf_gold", label="gold")]        # section 112 at 20%
    p = fy_tax(rules, 2019, TaxProfile("old", Dc("25000000")), events).parts
    gold_gain = Dc(200000) - Dc(100000) * (Dc(290) / Dc(220))                                           # series 2001: 220 -> 290
    want = Dc("0.25") * Dc("7312500") + Dc("0.15") * Dc("15000") + Dc("0.25") * (gold_gain * Dc("0.20"))
    assert abs(p["surcharge"].value - want) < Dc("1e-9")


def test_tax_never_falls_and_never_jumps_across_the_surcharge_threshold(rules):
    prev = None
    for income in range(4_995_000, 5_005_001, 250):
        t = fy_tax(rules, 2019, TaxProfile("old", Dc(income)), []).parts["before_rounding"].value
        if prev is not None:
            assert 0 <= t - prev <= Dc("1.04") * 250
        prev = t


def test_zero_income_and_no_events_is_zero_tax(rules):
    assert fy_tax(rules, 2019, TaxProfile("old", Dc(0)), []).tax.value == 0


@pytest.mark.parametrize("income", ["0", "1", "249999", "250000", "499999", "500001", "1000000", "5000001", "20000000"])
@pytest.mark.parametrize("regime, fy", [("old", 2015), ("old", 2019), ("new", 2021)])
def test_tax_is_never_negative(rules, income, regime, fy):
    assert fy_tax(rules, fy, TaxProfile(regime, Dc(income)), []).tax.value >= 0


# ---- inputs the engine refuses instead of quietly reading -----------------------

@pytest.mark.parametrize("regime", ["New", "OLD", "", "newer", None])
def test_an_unknown_regime_is_refused_not_read_as_the_old_regime(regime):
    with pytest.raises(ValueError, match="regime"):
        TaxProfile(regime, Dc("1000000"))


def test_a_sale_dated_before_its_purchase_is_refused():
    with pytest.raises(ValueError, match="before it was bought"):
        ev("2019-06-02", "2019-06-01", "10", "20")
    ev("2019-06-01", "2019-06-01", "10", "20")            # bought and sold the same day is allowed


@pytest.mark.parametrize("what", ["proceeds", "sale_costs", "cost", "fmv"])
def test_negative_proceeds_costs_or_values_are_refused(what):
    args = dict(proceeds="20", sale_costs="0", cost="10", fmv="5")
    args[what] = "-1"
    with pytest.raises(ValueError, match="negative"):
        ev("2016-06-01", "2019-06-01", args["cost"], args["proceeds"], sale_costs=args["sale_costs"], fmv=args["fmv"])


def test_zero_proceeds_and_zero_cost_are_allowed():
    ev("2019-06-01", "2019-12-01", "10", "0")              # a worthless sale
    ev("2019-06-01", "2019-12-01", "0", "10")              # bonus units cost nothing


@pytest.mark.parametrize("kind", ["st", "lt", "biz"])
@pytest.mark.parametrize("origin", [2019, 2020, 2030])
def test_a_loss_from_the_same_or_a_later_year_cannot_be_brought_forward(rules, kind, origin):
    with pytest.raises(ValueError, match="cannot be brought forward"):
        fy_tax(rules, 2019, TaxProfile("old", Dc("1000000")), [], Carry(**{kind: ((origin, const("loss", "1000")),)}))


def test_a_negative_brought_forward_loss_is_refused(rules):
    with pytest.raises(ValueError, match="negative"):
        fy_tax(rules, 2019, TaxProfile("old", Dc("1000000")), [], Carry(st=((2018, const("loss", "-1000")),)))


def test_negative_dividends_interest_or_business_costs_are_refused(rules):
    p = TaxProfile("old", Dc("1000000"))
    with pytest.raises(ValueError, match="negative"):
        fy_tax(rules, 2019, p, [], dividends=const("d", "-1"))
    with pytest.raises(ValueError, match="negative"):
        fy_tax(rules, 2019, p, [], interest=const("i", "-1"))
    with pytest.raises(ValueError, match="negative"):
        Business(const("p", "10"), const("c", "-1"))


def test_the_new_regime_before_it_existed_still_falls_back_to_the_old_one(rules):
    # the one deliberate fallback: the answer for a year with no new regime is the old regime, and a valid name is never guessed at
    assert fy_tax(rules, 2015, TaxProfile("new", Dc("1000000")), []).tax.value == fy_tax(rules, 2015, TaxProfile("old", Dc("1000000")), []).tax.value


# ---- losses that lapse are named in the derivation ------------------------------

def test_a_loss_that_lapses_after_eight_years_is_named_on_the_years_tax(rules):
    carry = Carry(st=((2010, const("old", "40000")),), lt=((2011, const("edge", "60000")),), biz=((2009, const("older", "5000")),))
    r = fy_tax(rules, 2019, TaxProfile("old", Dc("1000000")), [], carry)
    note = r.tax.note
    assert "lapsed" in note and "Rs 40,000.00" in note and "short-term loss from FY2010-11" in note
    assert "business loss from FY2009-10" in note and "Rs 5,000.00" in note
    assert "FY2011-12" not in note                                        # a loss in its eighth year is still usable, so it is not named


def test_a_year_with_no_lapsed_loss_has_no_lapse_note(rules):
    r = fy_tax(rules, 2019, TaxProfile("old", Dc("1000000")), [], Carry(st=((2018, const("fresh", "40000")),)))
    assert "lapsed" not in r.tax.note
