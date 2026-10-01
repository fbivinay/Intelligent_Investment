from datetime import date
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

from engine.charges import Order, dp_charge, order_charges
from engine.rules import Rules
from research import costs

RULES = Rules.load(Path(__file__).resolve().parents[1] / "rules")


def engine_total(cls, side, on, value):
    price = Decimal(100)
    return float(order_charges(RULES, Order(on, cls, side, Decimal(str(value)) / price, price)).total.value)


def test_regime_dates_are_the_days_a_charge_rule_changes_and_each_day_maps_to_the_latest_one_before_it():
    days = [date(2020, 6, 30), date(2020, 7, 1), date(2020, 7, 2), date(2016, 1, 4)]
    reg, day_reg = costs.regimes(RULES, days)
    assert list(reg) == sorted(set(reg)) and reg[0] <= date(2010, 4, 1)
    assert date(2020, 7, 1) in reg                                        # uniform stamp duty from 2020-07-01
    assert day_reg[0] != day_reg[1] and day_reg[1] == day_reg[2]          # a day before and a day after the change fall in different regimes
    assert reg[day_reg[3]] <= days[3] < (reg[day_reg[3] + 1] if day_reg[3] + 1 < len(reg) else date.max)


@pytest.mark.parametrize("cls,side,on,value", [
    ("etf_equity", "buy", date(2016, 6, 1), 500_000), ("etf_equity", "sell", date(2016, 6, 1), 500_000),
    ("etf_equity", "sell", date(2019, 3, 1), 100_000), ("etf_equity", "buy", date(2025, 1, 2), 1_000_000),
    ("etf_gold", "sell", date(2021, 6, 1), 250_000), ("mf_debt", "buy", date(2018, 1, 2), 100_000), ("mf_debt", "sell", date(2024, 5, 2), 5_000_000),
])
def test_the_charge_table_equals_the_engine_at_the_grid_sizes(cls, side, on, value):
    t = costs.charge_table(RULES, [on])
    got = costs.charge(t, 0, cls, side, value)
    assert got == pytest.approx(engine_total(cls, side, on, value) + (0 if cls == "mf_debt" or side == "buy" else float(dp_charge(RULES, on).value)), abs=0.011)


def test_between_grid_sizes_the_table_stays_within_a_rupee_or_half_a_percent_of_the_engine():
    on = date(2022, 8, 1)
    t = costs.charge_table(RULES, [on])
    for cls in ("etf_equity", "etf_gold", "mf_debt"):
        for side in ("buy", "sell"):
            for value in (7_300, 61_000, 333_333, 1_700_000, 12_000_000):
                exact = engine_total(cls, side, on, value) + (float(dp_charge(RULES, on).value) if side == "sell" and cls != "mf_debt" else 0)
                got = costs.charge(t, 0, cls, side, value)
                assert abs(got - exact) <= max(1.0, 0.005 * exact), (cls, side, value, got, exact)


def test_a_zero_order_costs_nothing_and_sizes_beyond_the_grid_are_extended_in_proportion():
    t = costs.charge_table(RULES, [date(2022, 8, 1)])
    assert costs.charge(t, 0, "etf_equity", "sell", 0.0) == 0.0
    big = costs.charge(t, 0, "etf_equity", "buy", costs.SIZES[-1] * 10)
    assert big == pytest.approx(costs.charge(t, 0, "etf_equity", "buy", costs.SIZES[-1]) * 10, rel=0.02)


def test_depository_charges_apply_to_the_sale_of_etf_units_and_not_to_fund_units_or_buys():
    on = date(2022, 8, 1)
    t = costs.charge_table(RULES, [on])
    v = 250_000                                                                     # a grid size, so the table equals the engine exactly
    assert costs.charge(t, 0, "etf_equity", "sell", v) == pytest.approx(engine_total("etf_equity", "sell", on, v) + float(dp_charge(RULES, on).value), abs=0.011)
    assert costs.charge(t, 0, "mf_debt", "sell", v) == pytest.approx(engine_total("mf_debt", "sell", on, v), abs=0.011)
    assert costs.charge(t, 0, "etf_equity", "buy", v) == pytest.approx(engine_total("etf_equity", "buy", on, v), abs=0.011)


def test_yearly_and_opening_fees_are_charged_to_the_account_on_their_own_days():
    days = [date(2016, 6, 1), date(2016, 6, 2), date(2017, 3, 31), date(2017, 4, 3)]
    fixed = costs.fixed_costs(RULES, days)
    assert fixed.shape == (4,) and fixed[0] >= 0 and fixed[1] == 0
    assert fixed[2] > 0                                                   # the yearly fee falls on the last trading day of the financial year
    assert fixed[3] == 0


def test_slippage_is_a_half_spread_plus_an_impact_that_grows_with_the_share_of_a_normal_days_trading():
    small = costs.slippage_rate("NIFTYBEES", order_value=100_000, adv=5e8)
    big = costs.slippage_rate("NIFTYBEES", order_value=50_000_000, adv=5e8)
    assert 0 < small < big
    assert costs.slippage_rate("JUNIORBEES", 100_000, 5e8) > costs.slippage_rate("NIFTYBEES", 100_000, 5e8)        # the thinner ETF has the wider spread
    assert costs.slippage_rate("NIFTYBEES", 0.0, 5e8) == 0.0
    assert costs.slippage_rate("CASH", 1e6, 5e8) == 0.0                                                          # fund units are bought at the NAV


def test_slippage_does_not_divide_by_a_missing_or_zero_average_traded_value():
    r = costs.slippage_rate("GOLDBEES", 100_000, 0.0)
    assert np.isfinite(r) and r > 0
    assert costs.slippage_rate("GOLDBEES", 100_000, float("nan")) == r
    assert costs.slippage_rate("GOLDBEES", 100_000, 0.0) <= costs.MAX_SLIPPAGE


def test_orders_below_the_first_grid_size_are_charged_in_proportion_and_a_negative_order_costs_nothing():
    t = costs.charge_table(RULES, [date(2022, 8, 1)])
    full = costs.charge(t, 0, "etf_equity", "buy", costs.SIZES[0])
    assert full > 0 and costs.charge(t, 0, "etf_equity", "buy", costs.SIZES[0] / 2) == pytest.approx(full / 2)
    assert costs.charge(t, 0, "etf_equity", "buy", -500.0) == 0.0


def test_the_opening_fee_is_charged_on_the_first_day():
    days = [date(2020, 7, 1), date(2020, 7, 2)]
    from engine.charges import account_opening_fee
    opening = float(account_opening_fee(RULES, days[0]).value)
    assert opening > 0 and costs.fixed_costs(RULES, days)[0] == pytest.approx(opening)


def test_slippage_values_follow_the_stated_formula(monkeypatch):
    assert costs.slippage_rate("NIFTYBEES", 500_000, 5e8) == pytest.approx(0.0003 + 0.005 * (500_000 / 5e8) ** 0.5)
    assert costs.slippage_rate("GOLDBEES", 100_000, 0.0) == pytest.approx(0.0006 + 0.005)          # no known traded value: the worst case, a whole day's trading
    assert costs.slippage_rate("NIFTYBEES", 9e9, 5e8) == pytest.approx(0.0003 + 0.005)               # never more than a whole day's trading
    monkeypatch.setattr(costs, "IMPACT", 0.5)
    assert costs.slippage_rate("NIFTYBEES", 1e9, 5e8) == costs.MAX_SLIPPAGE


def test_regimes_follow_every_charge_table_not_only_the_first():
    reg, _ = costs.regimes(RULES, [date(2016, 1, 4)])
    for d in (date(2013, 6, 1), date(2018, 3, 4), date(2020, 7, 1), date(2024, 10, 1)):                 # an STT, a clearing, a stamp duty and a brokerage change
        assert d in reg


def engine_deductible(cls, side, on, value):
    price = Decimal(100)
    ch = order_charges(RULES, Order(on, cls, side, Decimal(str(value)) / price, price))
    return float(ch.deductible.value), float(ch.total.value)


@pytest.mark.parametrize("cls,side,on,value", [("etf_equity", "sell", date(2022, 8, 1), 250_000), ("etf_equity", "buy", date(2022, 8, 1), 250_000),
                                               ("etf_gold", "sell", date(2016, 6, 1), 500_000), ("mf_debt", "buy", date(2021, 6, 1), 1_000_000)])
def test_the_deductible_part_is_what_the_engine_calls_deductible_plus_the_depository_charge_on_etf_sales_and_leaves_out_stt(cls, side, on, value):
    t = costs.charge_table(RULES, [on])
    ded, total = engine_deductible(cls, side, on, value)
    dp = float(dp_charge(RULES, on).value) if (side == "sell" and cls != "mf_debt") else 0.0
    assert costs.deductible(t, 0, cls, side, value) == pytest.approx(ded + dp, abs=0.011)
    assert costs.charge(t, 0, cls, side, value) - costs.deductible(t, 0, cls, side, value) == pytest.approx(total - ded, abs=0.011)     # what is left is STT
    if cls == "etf_equity" and side == "sell":
        assert total - ded > 0
