from datetime import date
from decimal import Decimal

import numpy as np
import pytest

from calc import product as PR
from engine.tax import TaxProfile
from engine.trace import assert_balanced
from research import artifact as A

PROFILE = TaxProfile("new", Decimal(1500000))


@pytest.fixture(scope="module")
def balanced():
    return PR.run("Balanced", Decimal(1000000), date(2015, 6, 1), date(2020, 6, 1), PROFILE)


def test_the_product_cannot_start_before_its_first_april_pick_and_the_dates_must_make_sense():
    with pytest.raises(ValueError, match="2013-04-01"):
        PR.run("Balanced", Decimal(1000000), date(2012, 6, 1), date(2015, 6, 1), PROFILE)
    with pytest.raises(ValueError, match="after the start"):
        PR.run("Balanced", Decimal(1000000), date(2015, 6, 1), date(2015, 6, 1), PROFILE)
    with pytest.raises(ValueError, match="2026-09-30"):
        PR.run("Balanced", Decimal(1000000), date(2015, 6, 1), date(2027, 1, 1), PROFILE)
    with pytest.raises(ValueError, match="at least"):
        PR.run("Balanced", Decimal(5000), date(2015, 6, 1), date(2016, 6, 1), PROFILE)
    with pytest.raises(KeyError, match="level"):
        PR.run("Reckless", Decimal(1000000), date(2015, 6, 1), date(2016, 6, 1), PROFILE)


def test_a_run_follows_the_artifacts_weights_from_the_start_day_and_its_books_balance(balanced):
    r = balanced
    dates, w, strategy = A.load("Balanced")
    i = int(np.searchsorted(dates, np.datetime64(r.dates[0])))
    assert r.dates[0] == "2015-06-01" and np.allclose(r.weights, w[i:i + len(r.dates)]) and r.strategy[0] == strategy[i]
    assert_balanced(r.booked.sold)
    assert r.booked.trades[0]["date"] == r.dates[1]                                                # decided at the first close, filled the next day
    assert r.dates[-1] <= "2020-06-01" and len(r.equity) == len(r.dates) and r.equity[0] == pytest.approx(1000000.0, rel=1e-3)


def test_the_exact_books_and_the_fast_simulator_agree_and_the_gap_is_reported(balanced):
    assert abs(balanced.gap) < 100.0 and balanced.sim_final > 0


def test_growth_and_the_worst_fall_are_worked_out_from_the_books_and_the_daily_marks(balanced):
    r = balanced
    years = (date.fromisoformat(r.dates[-1]) - date.fromisoformat(r.dates[0])).days / 365.25
    assert r.growth_sold == pytest.approx((float(r.booked.sold.value) / 1e6) ** (1 / years) - 1)
    assert 0 < r.worst_fall < 0.5


def test_a_small_amount_still_trades_with_a_smaller_minimum_order():
    r = PR.run("Aggressive", Decimal(50000), date(2017, 4, 3), date(2019, 4, 1), PROFILE)
    assert len(r.booked.trades) > 3 and min(float(t["turnover"]) for t in r.booked.trades) < 5000


def test_the_same_inputs_give_the_same_books():
    a = PR.run("Conservative", Decimal(300000), date(2019, 1, 1), date(2021, 1, 1), PROFILE)
    b = PR.run("Conservative", Decimal(300000), date(2019, 1, 1), date(2021, 1, 1), PROFILE)
    assert a.booked.sold.value == b.booked.sold.value and a.booked.trades == b.booked.trades
