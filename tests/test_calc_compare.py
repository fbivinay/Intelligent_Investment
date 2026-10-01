from datetime import date
from decimal import Decimal

import pytest

from calc import compare as CP, options as O
from engine.tax import TaxProfile
from engine.trace import assert_balanced

PROFILE = TaxProfile("new", Decimal(1500000))


def test_an_etf_is_bought_and_held_with_its_demat_fees_and_both_endings_balance():
    r = CP.run_option(O.get("NIFTYBEES"), Decimal(100000), date(2014, 4, 1), date(2026, 9, 28), PROFILE)
    assert r.plan == "exchange" and r.units > 0 and r.units == int(r.units)
    for n in (r.sold.net, r.held.net):
        assert_balanced(n)
    assert r.sold.net.value < r.held.net.value                                                     # selling pays sale charges and tax
    assert r.sold.waterfall["amc"].value > 0 and r.dates[0] == r.sold.bought_on.isoformat() and len(r.values) == len(r.dates)


def test_a_fund_holds_units_to_three_decimals_without_demat_fees():
    r = CP.run_option(O.get("LIQUID_FUND"), Decimal(100000), date(2014, 4, 1), date(2026, 9, 28), PROFILE)
    assert r.plan.startswith("direct") and r.units % 1 != 0 and r.units == r.units.quantize(Decimal("0.001"))
    assert r.sold.waterfall["amc"].value == 0 and r.sold.waterfall["account_opening"].value == 0


def test_the_daily_values_are_units_times_the_price_plus_the_cash_left_over():
    r = CP.run_option(O.get("GOLDBEES"), Decimal(100000), date(2016, 1, 1), date(2017, 1, 1), PROFILE)
    left = Decimal(100000) - r.sold.waterfall["buy_charges"].value - r.units * r.buy_price
    assert r.values[0] == pytest.approx(float(r.units * r.buy_price + left), rel=1e-12)


def test_growth_a_year_and_the_worst_fall_are_worked_out():
    r = CP.run_option(O.get("BANKBEES"), Decimal(100000), date(2015, 4, 1), date(2021, 4, 1), PROFILE)
    years = (date.fromisoformat(r.dates[-1]) - date.fromisoformat(r.dates[0])).days / 365.25
    assert r.growth_sold == pytest.approx((float(r.sold.net.value) / 100000) ** (1 / years) - 1) and 0.3 < r.worst_fall < 0.6       # the 2020 fall


def test_an_option_that_did_not_exist_on_the_start_day_or_an_amount_below_one_unit_is_a_message():
    with pytest.raises(ValueError, match="2010-06-29"):
        CP.run_option(O.get("NEXT50_INDEX_FUND"), Decimal(100000), date(2010, 4, 5), date(2015, 1, 1), PROFILE)
    with pytest.raises(ValueError, match="too small"):
        CP.run_option(O.get("BANKBEES"), Decimal(50), date(2015, 4, 1), date(2016, 4, 1), PROFILE)
