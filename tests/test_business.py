from decimal import Decimal as Dc

import pytest

from engine.business import audit_fee, futures_turnover
from engine.tax import Business, Carry, TaxProfile, investment_tax
from engine.trace import assert_balanced, const, flags, rules_used
from tests.helpers import make_rules
from tests.synth_tax import TAX
from tests.tax_helpers import ev


@pytest.fixture
def rules(tmp_path):
    return make_rules(tmp_path, TAX)


def biz(pnl, costs="0"):
    return Business(const("Futures P&L", pnl), const("Costs", costs))


def extra(rules, fy, business=None, income="1000000", **kw):
    r = investment_tax(rules, fy, TaxProfile("old", Dc(income)), [], business=business, **kw)
    assert_balanced(r.extra)
    return r


def test_profit_after_costs_is_taxed_at_slab_rates(rules):
    assert extra(rules, 2019, biz("150000", "50000")).extra.value == Dc("31200")   # 100,000 x 30% x 1.04


def test_loss_is_never_set_off_against_the_other_income_given_because_it_may_be_salary(rules):
    r = extra(rules, 2019, biz("-200000"))                                         # other income 1,000,000: section 71(2A)
    assert r.extra.value == 0 and r.with_items.parts["ordinary_income"].value == Dc("1000000")
    assert [(o, n.value) for o, n in r.with_items.carry_out.biz] == [(2019, Dc("200000"))]


def test_loss_is_set_off_against_interest_and_the_rest_is_carried_forward(rules):
    r = extra(rules, 2019, biz("-200000"), interest=const("Interest", "300000"))
    assert r.with_items.parts["ordinary_income"].value == Dc("1100000")           # 1,000,000 + 300,000 - 200,000
    assert r.with_items.carry_out.biz == ()
    r = extra(rules, 2019, biz("-400000"), interest=const("Interest", "300000"))
    assert r.with_items.parts["ordinary_income"].value == Dc("1000000")           # the interest is wiped out, no more
    assert [(o, n.value) for o, n in r.with_items.carry_out.biz] == [(2019, Dc("100000"))]


def test_loss_is_set_off_against_a_gain_taxed_at_slab_rates(rules):
    debt = ev("2023-05-01", "2024-06-01", "100000", "400000", cls="mf_debt")      # bought after March 2023: 300,000 short-term at slab rates
    r = investment_tax(rules, 2024, TaxProfile("old", Dc("1000000")), [debt], business=biz("-200000"))
    assert r.with_items.parts["ordinary_income"].value == Dc("1100000")           # 1,000,000 + 300,000 - 200,000
    assert r.with_items.carry_out.biz == ()


def test_loss_bigger_than_the_income_it_can_reach_is_carried_forward_not_refunded(rules):
    r = extra(rules, 2019, biz("-250000"), interest=const("Interest", "100000"))
    assert r.with_items.parts["ordinary_income"].value == Dc("1000000")           # the interest is wiped out, no more
    assert [(o, n.value) for o, n in r.with_items.carry_out.biz] == [(2019, Dc("150000"))]
    assert r.with_items.tax.value == r.without_items.tax.value                    # and nothing is refunded


def test_carried_loss_is_used_against_later_profit(rules):
    carry = Carry(biz=((2019, const("loss", "150000")),))
    r = extra(rules, 2020, biz("200000"), carry_in=carry)
    assert r.extra.value == Dc("15600")                                            # 50,000 x 30% x 1.04
    assert r.with_items.carry_out.biz == ()


@pytest.mark.parametrize("origin, expected", [(2011, "15600"), (2010, "62400")])
def test_business_losses_expire_after_eight_years(rules, origin, expected):
    carry = Carry(biz=((origin, const("loss", "150000")),))
    assert extra(rules, 2019, biz("200000"), carry_in=carry).extra.value == Dc(expected)


def test_unused_carried_loss_survives_a_year_with_no_business(rules):
    carry = Carry(biz=((2019, const("loss", "150000")),))
    r = extra(rules, 2020, None, carry_in=carry)
    assert [(o, n.value) for o, n in r.with_items.carry_out.biz] == [(2019, Dc("150000"))]


def test_audit_fee_only_above_the_turnover_limit(rules):
    turnover = futures_turnover([const("a", "-3000000"), const("b", "4000000"), const("c", "5000001")])
    assert turnover.value == Dc("12000001")
    assert audit_fee(rules, 2019, turnover).value == Dc("25000")
    assert audit_fee(rules, 2019, futures_turnover([const("a", "-3000000")])).value == 0


def test_audit_is_needed_only_when_turnover_exceeds_the_limit_and_not_when_it_equals_it(rules):
    assert audit_fee(rules, 2019, const("Turnover", "10000000")).value == 0
    assert audit_fee(rules, 2019, const("Turnover", "10000001")).value == Dc("25000")


def test_no_closed_trades_means_no_turnover_and_no_audit(rules):
    turnover = futures_turnover([])
    assert turnover.value == 0 and audit_fee(rules, 2019, turnover).value == 0


def test_carried_losses_are_used_oldest_first_and_the_rest_stays_dated(rules):
    carry = Carry(biz=((2018, const("newer", "100000")), (2017, const("older", "60000"))))
    r = extra(rules, 2019, biz("100000"), carry_in=carry)
    assert r.extra.value == 0                                                      # 60,000 + 40,000 wipe the profit out
    assert [(o, n.value) for o, n in r.with_items.carry_out.biz] == [(2018, Dc("60000"))]


def test_this_years_loss_is_added_after_the_ones_brought_forward(rules):
    carry = Carry(biz=((2017, const("older", "50000")),))
    r = extra(rules, 2019, biz("-250000"), income="100000", carry_in=carry)
    assert [(o, n.value) for o, n in r.with_items.carry_out.biz] == [(2017, Dc("50000")), (2019, Dc("250000"))]


def test_a_business_loss_is_not_set_off_against_gains_taxed_at_special_rates(rules):
    gain = ev("2019-06-01", "2019-12-01", "10000", "1010000")                      # 1,000,000 short-term gain at 15%
    r = investment_tax(rules, 2019, TaxProfile("old", Dc("0")), [gain], interest=const("Interest", "600000"), business=biz("-700000"))
    assert r.with_items.parts["ordinary_income"].value == 0                        # the loss wiped out the 600,000 of interest
    assert r.with_items.parts["special_tax"].value == Dc("112500")                 # (1,000,000 - unused basic exemption 250,000) x 15%
    assert [(o, n.value) for o, n in r.with_items.carry_out.biz] == [(2019, Dc("100000"))]   # the rest waits for business profit


def test_the_business_rows_are_cited_and_the_assumed_convention_shows_only_when_a_loss_is_set_off(rules):
    profit = extra(rules, 2019, biz("100000")).with_items.tax
    loss = extra(rules, 2019, biz("-100000")).with_items.tax
    cited = lambda n: {x.rule_id for x in rules_used(n)}
    assert "tax.loss_rules[kind=business]" in cited(profit) and flags(profit) == []
    assert cited(loss) >= {"tax.loss_rules[kind=business]", "tax.conventions[name=business_loss_setoff]"}
    assert [f.rule_id for f in flags(loss)] == ["tax.conventions[name=business_loss_setoff]"]
