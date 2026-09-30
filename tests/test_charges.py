from datetime import date
from decimal import Decimal as Dc

import pytest

from engine.charges import Order, account_opening_fee, amc_fee, dp_basis, dp_charge, order_charges
from engine.rules import RuleNotFound
from engine.trace import assert_balanced
from tests.helpers import make_rules
from tests.synth_charges import CHARGES


@pytest.fixture
def rules(tmp_path):
    return make_rules(tmp_path, CHARGES)


def order(on, cls, side, qty, price):
    return Order(date.fromisoformat(on), cls, side, Dc(qty), Dc(price))


def test_etf_sell_lines_and_totals(rules):
    c = order_charges(rules, order("2015-06-01", "etf_equity", "sell", "100", "850.55"))
    assert c.turnover.value == Dc("85055.00")
    assert {k: v.value for k, v in c.lines.items()} == {
        "brokerage": Dc("0.00"), "stt": Dc("85"),          # 0.001 x 85055 = 85.055 -> rupee
        "exchange_txn": Dc("2.55"), "sebi": Dc("0.09"),    # 2.55165 / 0.085055 -> paise
        "ipft": Dc("0.00"), "clearing": Dc("0.00"), "stamp": Dc("0.00"),
        "gst": Dc("0.48"),                                  # 18% of (2.55 + 0.09) = 0.4752
    }
    assert c.total.value == Dc("88.12")
    assert c.deductible.value == Dc("3.12")  # everything except STT
    assert_balanced(c.total)


def test_rate_change_takes_effect_on_its_date(rules):
    before = order_charges(rules, order("2015-12-31", "etf_equity", "sell", "100", "1000"))
    after = order_charges(rules, order("2016-01-01", "etf_equity", "sell", "100", "1000"))
    assert before.lines["stt"].value == Dc("100") and after.lines["stt"].value == Dc("50")


def test_buy_side_pays_stamp_not_stt(rules):
    c = order_charges(rules, order("2020-01-01", "etf_equity", "buy", "100", "850.55"))
    assert c.lines["stt"].value == 0 and c.lines["stamp"].value == Dc("12.76")


@pytest.mark.parametrize("price, expect", [("1000", "20"), ("200", "6")])
def test_futures_brokerage_is_lower_of_flat_and_percent(rules, price, expect):
    c = order_charges(rules, order("2020-01-01", "fut_index", "buy", "100", price))
    assert c.lines["brokerage"].value == Dc(expect)  # 0.03% of 100000 = 30 -> 20 ; of 20000 = 6


def test_mutual_fund_has_no_broker_or_exchange_lines(rules):
    c = order_charges(rules, order("2021-01-01", "mf_equity", "sell", "10.5", "250"))
    assert set(c.lines) == {"stt", "stamp", "gst"}
    assert c.lines["stt"].value == Dc("0.03")  # 0.00001 x 2625 = 0.02625


def test_dp_includes_the_depository_share_and_gst(rules):
    assert dp_charge(rules, date(2020, 1, 1)).value == Dc("19.47")   # (13 + 3.5) x 1.18
    assert dp_charge(rules, date(2021, 1, 1)).value == Dc("14.75")   # (9 + 3.5) x 1.18


def test_dp_basis_follows_the_rule_row(rules):
    assert dp_basis(rules, date(2020, 12, 31)) == "per_sale"
    assert dp_basis(rules, date(2021, 1, 1)) == "per_isin_per_day"


def test_amc_depends_on_the_day_the_account_was_opened(rules):
    due = date(2021, 3, 31)
    assert amc_fee(rules, due, opened=date(2020, 6, 1)).value == Dc("354.00")  # 300 x 1.18
    assert amc_fee(rules, due, opened=date(2019, 6, 1)).value == Dc("0.00")    # legacy group: no AMC
    assert_balanced(amc_fee(rules, due, opened=date(2020, 6, 1)))


def test_amc_before_the_account_existed_is_refused(rules):
    with pytest.raises(ValueError):
        amc_fee(rules, date(2020, 3, 31), opened=date(2020, 6, 1))


def test_account_opening_fee_follows_the_opening_date_and_includes_gst(rules):
    assert account_opening_fee(rules, date(2020, 6, 1)).value == Dc("472.00")  # 400 x 1.18
    assert account_opening_fee(rules, date(2019, 6, 1)).value == Dc("0.00")


@pytest.mark.parametrize("bad", [
    dict(qty="0", price="10"), dict(qty="-1", price="10"), dict(qty="1", price="0"),
])
def test_non_positive_inputs_are_refused(bad):
    with pytest.raises(ValueError):
        order("2020-01-01", "etf_equity", "buy", **bad)


def test_unknown_class_and_side_are_refused():
    with pytest.raises(ValueError):
        order("2020-01-01", "bitcoin", "buy", "1", "1")
    with pytest.raises(ValueError):
        order("2020-01-01", "etf_equity", "hold", "1", "1")


def test_a_date_with_no_rule_raises(rules):
    with pytest.raises(RuleNotFound):
        order_charges(rules, order("2009-01-01", "etf_equity", "buy", "1", "1"))
