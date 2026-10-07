import pytest

from calc import future


def test_one_payment_compounds_once_a_year():
    assert future.lump(0.10, 2) == pytest.approx(1.21)
    assert future.lump(-0.20, 1) == pytest.approx(0.8)


def test_a_monthly_payment_grows_for_the_months_it_stays_and_a_zero_rate_returns_the_payments():
    g = 1.12 ** (1 / 12)
    assert future.monthly(0.12, 1) == pytest.approx(sum(g ** (12 - m) for m in range(12)))
    assert future.monthly(0.0, 5) == pytest.approx(60)
    assert future.monthly(0.12, 5) > 60


def test_the_factor_table_covers_one_to_thirty_years_for_every_option():
    t = future.factors({"A": 0.2, "B": 0.05})
    assert set(t) == {"A", "B"} and len(t["A"]["lump"]) == 30 and len(t["A"]["sip"]) == 30
    assert t["A"]["lump"][4] == pytest.approx(1.2 ** 5) and t["B"]["sip"][0] == pytest.approx(future.monthly(0.05, 1))
