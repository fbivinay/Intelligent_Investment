from datetime import date
from decimal import Decimal

import pytest

from calc import options as O


def test_there_are_at_least_eight_alternatives_with_unique_ids_and_the_three_product_levels():
    alts = [o for o in O.OPTIONS if o.kind != "product"]
    assert len(alts) >= 8 and len({o.id for o in O.OPTIONS}) == len(O.OPTIONS)
    assert [o.id for o in O.OPTIONS if o.kind == "product"] == ["PRODUCT_Conservative", "PRODUCT_Balanced", "PRODUCT_Aggressive"]
    classes = {o.id: o.instrument_class for o in alts}
    assert classes["NIFTYBEES"] == "etf_equity" and classes["GOLDBEES"] == "etf_gold" and classes["LIQUID_FUND"] == "mf_debt" and classes["ARBITRAGE_FUND"] == "mf_equity"
    assert O.get("NIFTY50_INDEX_FUND").kind == "fund" and O.get("BANKBEES").kind == "etf"
    with pytest.raises(KeyError, match="unknown option"):
        O.get("SENSEX")


def test_etf_bars_are_the_split_adjusted_exchange_prices_and_carry_the_dividends():
    bars, dividends, plan = O.history(O.get("NIFTYBEES"), date(2015, 1, 1))
    assert bars[0].on >= date(2015, 1, 1) and all(b.close > 0 and b.high >= b.close for b in bars[:50]) and plan == "exchange"
    assert dividends[date(2012, 3, 12)] == Decimal("1.0000")
    gold, _, _ = O.history(O.get("GOLDBEES"), date(2019, 12, 1))
    around = [b for b in gold if date(2019, 12, 17) <= b.on <= date(2019, 12, 20)]
    assert max(b.close for b in around) / min(b.close for b in around) < Decimal("1.05")        # the 1:100 split of 2019-12-19 does not show as a jump


def test_a_fund_uses_the_direct_plan_from_its_first_day_and_the_regular_plan_before():
    o = O.get("LIQUID_FUND")
    early, _, plan_early = O.history(o, date(2012, 6, 1))
    late, _, plan_late = O.history(o, date(2013, 2, 1))
    assert plan_early.startswith("regular") and plan_late.startswith("direct")
    assert early[0].on >= date(2012, 6, 1) and late[0].on >= date(2013, 2, 1) and early[0].close != late[0].close


def test_fund_navs_are_on_the_current_unit_size():
    bars, _, _ = O.history(O.get("LIQUID_FUND"), date(2012, 1, 1))
    jumps = [b2.close / b1.close for b1, b2 in zip(bars, bars[1:])]
    assert max(jumps) < Decimal("1.02") and min(jumps) > Decimal("0.98")                       # no x100 step from a unit change


def test_a_start_before_an_option_existed_is_refused_with_its_first_day():
    with pytest.raises(ValueError, match="2010-06-29"):
        O.history(O.get("NEXT50_INDEX_FUND"), date(2010, 5, 3))
    assert O.first_day(O.get("NIFTYBEES")) == date(2010, 4, 1) and O.first_day(O.get("PRODUCT_Balanced")) == date(2013, 4, 1)
