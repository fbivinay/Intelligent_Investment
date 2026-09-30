from datetime import date
from decimal import Decimal as Dc

import pytest

from engine.rules import RuleNotFound
from engine.tax import add_months, classify, fy_of
from engine.trace import assert_balanced, rules_used
from tests.helpers import make_rules
from tests.synth_tax import TAX
from tests.tax_helpers import ev


@pytest.fixture
def rules(tmp_path):
    return make_rules(tmp_path, TAX)


def gain(rules, *a, **kw):
    node, key, _ = classify(rules, ev(*a, **kw))
    assert_balanced(node)
    return node.value, key


@pytest.mark.parametrize("acq, sale, term", [
    ("2020-01-15", "2021-01-15", "short"),   # exactly 12 months is still short-term
    ("2020-01-15", "2021-01-16", "long"),
    ("2016-02-29", "2017-02-28", "short"),   # leap day: 12 months ends 28 Feb
    ("2016-02-29", "2017-03-01", "long"),
    ("2020-01-31", "2021-01-31", "short"),
])
def test_holding_period_boundaries(rules, acq, sale, term):
    assert gain(rules, acq, sale, "1", "2")[1][0] == term


def test_add_months_clamps_to_month_end_and_fy_starts_in_april():
    assert add_months(date(2020, 1, 31), 1) == date(2020, 2, 29)
    assert fy_of(date(2021, 3, 31)) == 2020 and fy_of(date(2021, 4, 1)) == 2021


def test_pot_follows_the_rule_of_the_sale_date(rules):
    assert gain(rules, "2019-06-01", "2019-12-01", "10000", "20000") == (Dc("10000"), ("short", "special", Dc("0.15"), "111A", ""))
    assert gain(rules, "2015-01-01", "2017-06-01", "1", "2")[1] == ("long", "exempt", None, "10(38)", "")
    assert gain(rules, "2018-03-01", "2019-06-01", "1", "2")[1] == ("long", "special", Dc("0.10"), "112A", "112a")


def test_grandfathering_raises_cost_to_the_value_on_31_jan_2018(rules):
    assert gain(rules, "2016-01-01", "2019-06-01", "1000000", "2500000", fmv="2000000")[0] == Dc("500000")


def test_grandfathering_cannot_push_cost_above_the_sale_value(rules):
    assert gain(rules, "2016-01-01", "2019-06-01", "1000000", "2500000", fmv="3000000")[0] == 0


def test_missing_2018_value_is_an_error_not_a_silent_skip(rules):
    with pytest.raises(ValueError, match="fmv_2018"):
        gain(rules, "2016-01-01", "2019-06-01", "1", "2")


def test_grandfathering_is_not_needed_for_short_term_sales(rules):
    assert gain(rules, "2018-01-15", "2018-06-01", "1", "2")[0] == 1


def test_indexation_uses_the_old_series_for_a_sale_before_april_2017(rules):
    g, key = gain(rules, "2012-06-01", "2016-08-01", "100000", "200000", cls="etf_gold")
    assert key == ("long", "special", Dc("0.20"), "112", "")
    assert abs(g - (Dc(200000) - Dc(100000) * (Dc(620) / Dc(540)))) < Dc("1e-20")   # series 1981: 540 -> 620


def test_indexation_uses_the_new_series_from_april_2017(rules):
    g, _ = gain(rules, "2012-06-01", "2018-06-01", "100000", "200000", cls="etf_gold")
    assert abs(g - (Dc(200000) - Dc(100000) * (Dc(280) / Dc(220)))) < Dc("1e-20")   # series 2001: 220 -> 280


def test_the_series_switches_on_the_sale_date_not_the_purchase_date(rules):
    last_old, _ = gain(rules, "2012-06-01", "2017-03-31", "100000", "200000", cls="etf_gold")
    first_new, _ = gain(rules, "2012-06-01", "2017-04-01", "100000", "200000", cls="etf_gold")
    assert abs(last_old - (Dc(200000) - Dc(100000) * (Dc(620) / Dc(540)))) < Dc("1e-20")
    assert abs(first_new - (Dc(200000) - Dc(100000) * (Dc(270) / Dc(220)))) < Dc("1e-20")


def test_debt_fund_bought_after_march_2023_is_short_term_at_slab_rates(rules):
    node, key, _ = classify(rules, ev("2023-05-01", "2025-06-01", "100000", "200000", cls="mf_debt"))
    assert key == ("short", "slab", None, "50AA", "") and node.value == 100000
    assert "whatever the holding period" in node.note


def test_a_unit_may_pay_ten_percent_without_indexation_up_to_july_2014(rules):
    # indexed: cost 100000 x 540/500 = 108000, gain 192000 at 20% = 38400; option: gain 200000 at 10% = 20000
    g, key = gain(rules, "2010-06-01", "2013-03-01", "100000", "300000", cls="etf_gold")
    assert (g, key) == (Dc("200000"), ("long", "special", Dc("0.10"), "112 (10% option)", ""))


def test_the_indexed_route_wins_when_it_leaves_less_tax(rules):
    # indexed gain 105000 - 108000 = -3000 (no tax) against 5000 at 10% = 500
    g, key = gain(rules, "2010-06-01", "2013-03-01", "100000", "105000", cls="etf_gold")
    assert (g, key) == (Dc("-3000"), ("long", "special", Dc("0.20"), "112", ""))


def test_with_a_loss_either_way_the_bigger_indexed_loss_is_kept(rules):
    g, key = gain(rules, "2010-06-01", "2013-03-01", "100000", "90000", cls="etf_gold")
    assert (g, key) == (Dc("-18000"), ("long", "special", Dc("0.20"), "112", ""))   # -18000 indexed against -10000


def test_the_option_ends_with_transfers_on_10_july_2014(rules):
    before = gain(rules, "2010-06-01", "2014-07-10", "100000", "300000", cls="etf_gold")[1]
    after = gain(rules, "2010-06-01", "2014-07-11", "100000", "300000", cls="etf_gold")[1]
    assert before[2] == Dc("0.10") and after[2] == Dc("0.20")


def test_the_chosen_option_is_explained_in_the_gain_note(rules):
    node, _, _ = classify(rules, ev("2010-06-01", "2013-03-01", "100000", "300000", cls="etf_gold"))
    assert "10% option" in node.note and "lower tax" in node.note


def test_the_trace_cites_every_rule_row_it_read(rules):
    node, _, _ = classify(rules, ev("2012-06-01", "2016-08-01", "100000", "200000", cls="etf_gold"))
    ids = {r.rule_id for r in rules_used(node)}
    assert ids >= {"tax.buckets[asset_class=etf_gold]", "tax.capital_gains[bucket=gold]", "tax.cii[series=1981]"}


def test_sale_costs_reduce_the_gain(rules):
    assert gain(rules, "2019-06-01", "2019-12-01", "10000", "20000", sale_costs="150")[0] == Dc("9850")


def test_unknown_asset_class_raises(rules):
    with pytest.raises(RuleNotFound):
        classify(rules, ev("2019-01-01", "2019-06-01", "1", "2", cls="bitcoin"))
