from datetime import date

import numpy as np
import pytest

from calc import paths


def test_a_monthly_plan_pays_on_the_start_day_and_the_same_day_of_each_month_up_to_the_end():
    assert paths.schedule(date(2024, 1, 31), date(2024, 4, 30)) == [date(2024, 1, 31), date(2024, 2, 29), date(2024, 3, 31), date(2024, 4, 30)]
    assert paths.schedule(date(2024, 1, 15), date(2024, 1, 14)) == []


def test_the_growth_index_leaves_the_payments_out_so_a_payment_is_neither_a_gain_nor_a_loss():
    values, paid = [100, 210, 189, 231], [100, 100, 0, 0]               # +10%, a payment of 100, then -10% and +22.2%
    ix = paths.growth_index(values, paid)
    assert np.allclose(ix, [1, 1.1, 0.99, 1.21])
    assert paths.drawdown(ix).max() == pytest.approx(0.1)
    assert np.allclose(paths.growth_index([100, 50, 100], [100, 0, 0]), [1, 0.5, 1])     # one payment: the value itself


def test_calendar_years_chain_from_the_last_day_of_the_year_before_and_mark_partial_years():
    dates = ["2020-03-02", "2020-12-31", "2021-06-30", "2021-12-31", "2022-03-01"]
    y = paths.years(dates, [1.0, 1.2, 1.5, 1.32, 1.452])
    assert [(r["year"], round(r["value"], 6), r["partial"]) for r in y] == [(2020, 0.2, True), (2021, 0.1, False), (2022, 0.1, True)]


def test_the_deepest_fall_starts_at_the_last_high_before_it_and_ends_when_that_high_is_back():
    dates = ["2020-01-01", "2020-02-01", "2020-03-01", "2020-04-01", "2020-05-01", "2020-06-01"]
    f = paths.deepest_fall(dates, [1.0, 1.2, 1.2, 0.9, 1.1, 1.25])
    assert f == {"peak": "2020-03-01", "trough": "2020-04-01", "recovered": "2020-06-01", "depth": 0.25, "days": 92}
    assert paths.deepest_fall(dates[:2], [1.0, 1.1]) is None
    assert paths.deepest_fall(dates[:3], [1.0, 2.0, 1.5])["recovered"] is None


def test_xirr_of_one_payment_is_the_plain_growth_a_year_and_of_a_plan_solves_its_own_equation():
    one = [(date(2018, 4, 2), -100000.0), (date(2026, 9, 30), 250000.0)]
    years = (date(2026, 9, 30) - date(2018, 4, 2)).days / 365.25
    assert paths.xirr(one) == pytest.approx(2.5 ** (1 / years) - 1, abs=1e-10)
    plan = [(date(2024, 1, 1), -1000.0), (date(2024, 7, 1), -1000.0), (date(2025, 1, 1), 2300.0)]
    r = paths.xirr(plan)
    assert sum(a / (1 + r) ** ((d - plan[0][0]).days / 365.25) for d, a in plan) == pytest.approx(0, abs=1e-6) and 0.15 < r < 0.25
    assert paths.xirr([(date(2024, 1, 1), -1000.0), (date(2025, 1, 1), 0.0)]) == -1.0
