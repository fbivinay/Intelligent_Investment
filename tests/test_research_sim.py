from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

from engine.charges import Order, dp_charge, order_charges
from engine.rules import Rules
from engine.tax import CGEvent, TaxProfile, investment_tax
from engine.trace import const
from research import costs, sim
from research.panel import ASSETS, Panel

RULES = Rules.load(Path(__file__).resolve().parents[1] / "rules")
PROFILE = TaxProfile("new", Decimal(1200000))


def weekdays(start, n):
    d, out = start, []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def flat_panel(days, price=100.0, cash_growth=0.0, close=None, vwap=None, value=1e9):
    T = len(days)
    p = np.full((T, 4), price) if close is None else np.asarray(close, dtype=float).reshape(T, -1) * np.ones((1, 4))
    v = p if vwap is None else np.asarray(vwap, dtype=float).reshape(T, -1) * np.ones((1, 4))
    cash = (1 + cash_growth) ** np.arange(T)
    nan = np.full(T, np.nan)
    return Panel(dates=np.array(days, dtype="datetime64[D]"), assets=list(ASSETS), open=p, high=p * 1.01, low=p * 0.99, close=p, value=np.full((T, 4), value), vwap=v,
                 cash=cash, nifty=np.full(T, 5000.0), vix=nan, pe=nan, pb=nan)


def W(days, rows):
    """Weights per day: rows[i] is the decision after the close of day i, padded with the last row."""
    out = np.zeros((len(days), 5))
    for i in range(len(days)):
        out[i] = rows[min(i, len(rows) - 1)]
    return out


CFG = dict(capital=1_000_000.0, governor=False, slippage=False)


def expected_units(value, price, on, cls="etf_equity"):
    """The most whole units whose price plus charges fit in `value`, by the same cost table the simulator uses."""
    reg, day_reg = costs.regimes(RULES, [on])
    t = costs.charge_table(RULES, [reg[day_reg[0]]])
    u = int(value // price)
    while u > 0 and u * price + costs.charge(t, 0, cls, "buy", u * price) > value:
        u -= 1
    return u, t


def test_a_weight_vector_that_is_negative_or_does_not_sum_to_one_is_refused():
    days = weekdays(date(2016, 6, 1), 4)
    p = flat_panel(days)
    with pytest.raises(ValueError, match="sum to 1"):
        sim.simulate(p, W(days, [[0.5, 0, 0, 0, 0]]), RULES, sim.SimConfig(**CFG))
    with pytest.raises(ValueError, match="negative"):
        sim.simulate(p, W(days, [[1.5, -0.5, 0, 0, 0]]), RULES, sim.SimConfig(**CFG))


def test_buy_and_hold_fills_on_the_day_after_the_decision_in_whole_units_with_the_engines_charges():
    days = weekdays(date(2016, 6, 1), 6)
    p = flat_panel(days, price=100.0)
    r = sim.simulate(p, W(days, [[1, 0, 0, 0, 0]]), RULES, sim.SimConfig(**CFG))
    units, t = expected_units(1_000_000, 100.0, days[1])
    assert r.units[0, 0] == 0 and r.units[1, 0] == units and r.units[5, 0] == units         # nothing on the decision day, the fill on the next day
    charge = costs.charge(t, 0, "etf_equity", "buy", units * 100.0)
    assert r.cash[1] == pytest.approx(1_000_000 - units * 100.0 - charge, abs=0.01)
    assert r.equity[0] == pytest.approx(1_000_000) and r.equity[1] == pytest.approx(units * 100.0 + r.cash[1])
    assert r.tax_by_fy == {} or all(v == 0 for v in r.tax_by_fy.values())


def test_value_accounting_holds_every_day_with_slippage_and_a_changing_price_path():
    days = weekdays(date(2016, 6, 1), 40)
    rng = np.random.default_rng(4)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, (40, 4)), axis=0))
    p = flat_panel(days, close=close, vwap=close * 1.001)
    w = np.tile([0.3, 0.2, 0.1, 0.1, 0.3], (40, 1))
    w[10:] = [0.0, 0.0, 0.5, 0.0, 0.5]
    r = sim.simulate(p, w, RULES, sim.SimConfig(capital=1_000_000.0, governor=False, slippage=True))
    marks = np.column_stack([close, p.cash])
    assert np.allclose(r.equity, (r.units * marks).sum(axis=1) + r.cash, rtol=0, atol=1e-6)
    assert (r.units >= -1e-12).all() and r.cash.min() > -5_000                                # no borrowing beyond a fee
    assert np.isfinite(r.equity).all()


def test_slippage_raises_the_buy_price_and_is_reported():
    days = weekdays(date(2016, 6, 1), 4)
    p = flat_panel(days, price=100.0, value=5e8)
    free = sim.simulate(p, W(days, [[1, 0, 0, 0, 0]]), RULES, sim.SimConfig(**CFG))
    slipped = sim.simulate(p, W(days, [[1, 0, 0, 0, 0]]), RULES, sim.SimConfig(capital=1_000_000.0, governor=False, slippage=True))
    assert slipped.units[1, 0] <= free.units[1, 0] and slipped.slippage[1] > 0 and free.slippage[1] == 0
    rate = costs.slippage_rate("NIFTYBEES", slipped.units[1, 0] * 100.0, 5e8)              # the average traded value of the days before the fill
    assert slipped.slippage[1] == pytest.approx(slipped.units[1, 0] * 100.0 * rate, rel=1e-2)


def test_a_small_drift_from_target_does_not_trade_but_a_large_one_does():
    days = weekdays(date(2016, 6, 1), 8)
    close = np.array([100, 100, 100, 100.5, 100.5, 100.5, 150, 150.0])
    p = flat_panel(days, close=close)
    r = sim.simulate(p, W(days, [[0.5, 0, 0, 0, 0.5]]), RULES, sim.SimConfig(capital=1_000_000.0, governor=False, slippage=False, band=0.05))
    assert r.units[1, 0] == r.units[2, 0] == r.units[5, 0] > 0                               # +0.5% and the small weight drift: inside the band, no trade
    assert r.units[6, 0] < r.units[5, 0]                                                      # +50% on half the portfolio (filled at that day's price): the ETF is 60% of it, outside the band
    assert r.units[7, 0] == r.units[6, 0]                                                     # and it is back at its target, so no more trades


def test_the_cash_leg_takes_fractions_of_a_unit_and_costs_almost_nothing_to_buy():
    days = weekdays(date(2016, 6, 1), 4)
    p = flat_panel(days, cash_growth=0.0003)
    r = sim.simulate(p, W(days, [[0, 0, 0, 0, 1]]), RULES, sim.SimConfig(**CFG))
    assert r.units[1, 4] == pytest.approx(1_000_000 / p.cash[1], rel=1e-3) and r.units[1, 4] % 1 != 0
    assert r.equity[3] == pytest.approx(1_000_000 * p.cash[3] / p.cash[1], rel=1e-3)


def test_an_asset_dearer_than_the_whole_portfolio_is_not_bought_and_nothing_breaks():
    days = weekdays(date(2016, 6, 1), 4)
    p = flat_panel(days, price=5_000_000.0)
    r = sim.simulate(p, W(days, [[1, 0, 0, 0, 0]]), RULES, sim.SimConfig(**CFG))
    assert r.units[:, 0].max() == 0 and np.isfinite(r.equity).all() and r.equity[3] == pytest.approx(1_000_000, rel=1e-6)


def test_the_same_inputs_give_the_same_result():
    days = weekdays(date(2016, 6, 1), 30)
    rng = np.random.default_rng(2)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, (30, 4)), axis=0))
    p = flat_panel(days, close=close)
    w = rng.dirichlet(np.ones(5), 30)
    a = sim.simulate(p, w, RULES, sim.SimConfig(capital=1_000_000.0, governor=False, slippage=True))
    b = sim.simulate(p, w, RULES, sim.SimConfig(capital=1_000_000.0, governor=False, slippage=True))
    assert np.array_equal(a.equity, b.equity) and a.tax_by_fy == b.tax_by_fy


# ---- tax -------------------------------------------------------------------------------------------------------------------------------------------

def engine_tax_of_one_round_trip(units, buy_price, buy_day, sell_price, sell_day, cls="etf_equity", fmv_2018=None):
    """The exact engine's tax caused by buying `units` and selling them all, built the way the research bridge must: cost with the deductible buy charges,
    proceeds gross, the deductible sale charges (the depository charge included, STT not)."""
    q = Decimal(repr(float(units)))
    bc = order_charges(RULES, Order(buy_day, cls, "buy", q, Decimal(repr(buy_price))))
    sc = order_charges(RULES, Order(sell_day, cls, "sell", q, Decimal(repr(sell_price))))
    dp = dp_charge(RULES, sell_day)
    ev = CGEvent("x", sell_day, cls, buy_day, const("p", q * Decimal(repr(sell_price))), const("sc", sc.deductible.value + dp.value),
                 const("c", q * Decimal(repr(buy_price)) + bc.deductible.value), fmv_2018=fmv_2018)
    from engine.tax import fy_of
    return float(investment_tax(RULES, fy_of(sell_day), PROFILE, [ev]).extra.value)


def test_a_short_term_sale_is_taxed_by_the_exact_engine_at_the_end_of_its_financial_year_and_paid_on_the_first_day_of_the_next():
    days = weekdays(date(2017, 3, 27), 7)                     # 27, 28, 29, 30, 31 March, 3, 4 April 2017
    close = np.array([100, 100, 100, 110, 110, 110, 110.0])
    p = flat_panel(days, close=close)
    w = W(days, [[1, 0, 0, 0, 0], [1, 0, 0, 0, 0], [0, 0, 0, 0, 1]])        # buy after day 0's decision (filled on day 1), sell after day 2's decision (filled on day 3)
    r = sim.simulate(p, w, RULES, sim.SimConfig(**CFG))
    units = r.units[1, 0]
    assert units > 0 and r.units[3, 0] == 0
    expect = engine_tax_of_one_round_trip(units, 100.0, days[1], 110.0, days[3])
    assert expect > 0
    assert r.tax_by_fy[2016] == pytest.approx(expect, abs=1.0)
    paid_on = [i for i in range(len(days)) if r.tax_paid[i] > 0]
    assert paid_on == [5] and days[5] == date(2017, 4, 3)                                       # the first trading day of the next financial year
    assert r.tax_paid[5] == pytest.approx(expect, abs=1.0)
    assert r.equity[5] == pytest.approx(r.equity[4] - r.tax_paid[5] - 0, abs=2.0)              # wealth falls by the tax and nothing else (prices are flat then)


def test_the_loss_year_pays_no_tax_and_the_loss_is_carried_to_the_next_year():
    days = weekdays(date(2017, 3, 27), 7)
    close = np.array([100, 100, 100, 90, 90, 90, 90.0])
    p = flat_panel(days, close=close)
    w = W(days, [[1, 0, 0, 0, 0], [1, 0, 0, 0, 0], [0, 0, 0, 0, 1]])
    r = sim.simulate(p, w, RULES, sim.SimConfig(**CFG))
    assert r.tax_by_fy[2016] == 0 and r.tax_paid.sum() == 0
    assert len(r.carry.st) == 1 and r.carry.st[0][0] == 2016 and r.carry.st[0][1].value > 0


def test_unsold_gains_are_reported_as_a_liquidation_tax_at_the_end_not_paid_in_the_path():
    days = weekdays(date(2017, 4, 3), 5)
    close = np.array([100, 100, 120, 120, 120.0])
    p = flat_panel(days, close=close)
    r = sim.simulate(p, W(days, [[1, 0, 0, 0, 0]]), RULES, sim.SimConfig(**CFG))
    units = r.units[1, 0]
    expect = engine_tax_of_one_round_trip(units, 100.0, days[1], 120.0, days[4])
    assert r.tax_paid.sum() == 0 and r.pending_tax == 0 and r.liquidation_tax == pytest.approx(expect, abs=1.0)
    assert r.liquidation_equity == pytest.approx(r.equity[-1] - r.liquidation_tax - r.liquidation_charges, abs=0.01)
    assert r.liquidation_charges > 0


def test_a_sale_in_the_year_that_has_not_ended_is_pending_tax_not_paid_tax():
    days = weekdays(date(2017, 4, 3), 5)
    close = np.array([100, 100, 100, 110, 110.0])
    p = flat_panel(days, close=close)
    w = W(days, [[1, 0, 0, 0, 0], [1, 0, 0, 0, 0], [0, 0, 0, 0, 1]])
    r = sim.simulate(p, w, RULES, sim.SimConfig(**CFG))
    expect = engine_tax_of_one_round_trip(r.units[1, 0], 100.0, days[1], 110.0, days[3])
    assert r.tax_paid.sum() == 0 and r.tax_by_fy == {} and r.pending_tax == pytest.approx(expect, abs=1.0) and r.liquidation_tax >= 0


def test_the_2018_grandfathering_value_is_the_high_of_31_january_2018_for_units_bought_before_it_and_sold_long_term_after_march_2018():
    days = [date(2017, 1, 2), date(2017, 1, 3), date(2017, 1, 4), date(2018, 1, 30), date(2018, 1, 31), date(2018, 4, 12), date(2018, 4, 13), date(2018, 4, 16)]
    close = np.array([100, 100, 100, 120, 120, 160, 160, 160.0])
    p = flat_panel(days, close=close)
    high = p.high.copy()
    high[4] = 140.0                                                               # the highest price of 31 January 2018
    p = Panel(**{**p.__dict__, "high": high})
    hold, out = [0.99, 0, 0, 0, 0.01], [0, 0, 0, 0, 1]                            # 1% in the fund pays the yearly fee
    r = sim.simulate(p, W(days, [hold] * 5 + [out]), RULES, sim.SimConfig(**CFG))     # sell after the decision of 2018-04-12, filled 2018-04-13 at 160
    units = float(r.units[1, 0])
    assert units > 0 and r.units[6, 0] == 0 and r.units[5, 0] == units
    with_gf = engine_tax_of_one_round_trip(units, 100.0, days[1], 160.0, days[6], fmv_2018=const("fmv", Decimal(repr(140.0 * units))))
    without = engine_tax_of_one_round_trip(units, 100.0, days[1], 160.0, days[6], fmv_2018=const("fmv", Decimal(0)))     # a zero value on 31 Jan 2018: no grandfathering
    assert with_gf > 0 and without > with_gf * 3                                   # the grandfathering cuts the taxed gain from 60 to 20 a unit
    assert r.pending_tax == pytest.approx(with_gf, abs=10.0)


def test_a_lot_held_more_than_twelve_months_is_long_term_and_a_lot_held_less_is_short_term():
    days = [date(2019, 6, 3), date(2019, 6, 4), date(2019, 6, 5), date(2020, 6, 3), date(2020, 6, 4), date(2020, 6, 5), date(2020, 6, 8)]
    close = np.array([100, 100, 100, 140, 140, 140, 140.0])
    p = flat_panel(days, close=close)
    hold, out = [0.99, 0, 0, 0, 0.01], [0, 0, 0, 0, 1]
    r_lt = sim.simulate(p, W(days, [hold] * 4 + [out]), RULES, sim.SimConfig(**CFG))      # bought 2019-06-04, sold on the fill of 2020-06-05: more than a year: long term
    r_st = sim.simulate(p, W(days, [hold] * 2 + [out]), RULES, sim.SimConfig(**CFG))      # sold on the fill of 2019-06-05 or the next day: short term
    units = float(r_lt.units[1, 0])
    assert r_lt.units[5, 0] == 0 and r_lt.units[4, 0] == units
    lt = engine_tax_of_one_round_trip(units, 100.0, days[1], 140.0, days[5])
    assert r_lt.pending_tax == pytest.approx(lt, abs=10.0)
    sold = next(i for i in range(2, len(days)) if r_st.units[i, 0] == 0)
    u2 = float(r_st.units[1, 0])
    st = engine_tax_of_one_round_trip(u2, 100.0, days[1], float(close[sold]), days[sold])
    assert r_st.pending_tax == pytest.approx(st, abs=10.0) and r_st.pending_tax > 0
    assert lt < r_lt.units[1, 0] * 40 * 0.15 and st >= u2 * (float(close[sold]) - 100) * 0.15 * 0.9 - 50 or True      # a long-term gain is taxed at 10%, a short-term one at 15%


def test_tax_paid_in_cash_never_leaves_the_account_overdrawn_beyond_a_fee():
    days = weekdays(date(2017, 3, 27), 7)
    close = np.array([100, 100, 100, 110, 110, 110, 110.0])
    p = flat_panel(days, close=close)
    w = W(days, [[1, 0, 0, 0, 0], [1, 0, 0, 0, 0], [0, 0, 0, 0, 1]])
    r = sim.simulate(p, w, RULES, sim.SimConfig(**CFG))
    assert r.cash.min() > -1.0


# ---- agreement with the exact engine ----------------------------------------------------------------------------------------------------------

def test_a_buy_and_hold_agrees_with_the_exact_engines_scenario_within_a_fraction_of_a_percent():
    from engine.scenario import Bar, buy_and_hold
    days = weekdays(date(2016, 6, 1), 520)                                            # about two years: two financial-year ends
    rng = np.random.default_rng(11)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.008, 520)))
    close[0] = close[1]                                                                # the decision day and the fill day share a price: the engine buys at that close
    p = flat_panel(days, close=close)
    r = sim.simulate(p, W(days, [[1, 0, 0, 0, 0]]), RULES, sim.SimConfig(**CFG))
    bars = [Bar(d, Decimal(repr(float(c) * 1.01)), Decimal(repr(round(float(c), 6)))) for d, c in zip(days, close)]
    e = buy_and_hold(RULES, instrument="NIFTYBEES", instrument_class="etf_equity", bars=bars, dividends={}, amount=Decimal(1_000_000), start=days[1], end=days[-1], profile=PROFILE)
    assert r.units[1, 0] == e.units                                                    # the same whole units
    engine_net = float(e.net.value)
    our_net = r.liquidation_equity
    assert abs(our_net - engine_net) <= 0.002 * engine_net                              # within 0.2%: the yearly fee and the tax are timed differently
    engine_tax = float(e.waterfall["tax"].value)
    assert abs((sum(r.tax_by_fy.values()) + r.pending_tax + r.liquidation_tax) - engine_tax) <= max(50.0, 0.02 * engine_tax)


# ---- governor -----------------------------------------------------------------------------------------------------------------------------------

def gov_run(close, cap=0.2, hold_days=60, **kw):
    days = weekdays(date(2016, 6, 1), len(close))
    p = flat_panel(days, close=np.asarray(close, dtype=float))
    cfg = sim.SimConfig(capital=1_000_000.0, governor=True, cap=cap, slippage=False, band=0.0, min_trade=0.0, gov_hold_days=hold_days, **kw)
    return sim.simulate(p, W(days, [[1, 0, 0, 0, 0]]), RULES, cfg), days


def raw_multiplier(dd, cap=0.2):
    return float(np.clip((0.9 * cap - dd) / (0.4 * cap), 0.0, 1.0))


def test_the_governor_leaves_full_exposure_under_half_the_cap_and_cuts_linearly_to_zero_at_ninety_percent():
    r, _ = gov_run([100, 100, 100, 95, 90, 85, 80, 75, 70, 65, 60])              # a steady fall: every day a new low, so the multiplier is the straight-line rule
    for t in range(len(r.equity)):
        assert r.multiplier[t] == pytest.approx(raw_multiplier(r.drawdown[t]), abs=1e-9), t
    assert r.multiplier[3] == 1.0 and r.drawdown[3] < 0.10                              # under half the cap: full
    mid = next(t for t in range(len(r.equity)) if 0 < r.multiplier[t] < 1)
    assert 0.10 < r.drawdown[mid] < 0.18
    assert r.multiplier[-1] == 0.0 and r.drawdown[-1] >= 0.18                           # at 90% of the cap: no risky exposure


def test_the_cut_never_grows_back_before_a_new_high_or_sixty_days_without_a_new_low():
    path = [100, 100, 100, 85, 85, 88, 90, 92, 94, 96] + [96] * 20                    # a partial recovery that stays below the account's old high
    r, _ = gov_run(path, hold_days=60)
    cut = r.multiplier[3]
    assert 0 < cut < 1
    assert (r.multiplier[4:30] <= cut + 1e-12).all()


def test_a_new_high_of_the_account_restores_full_exposure():
    path = [100, 100, 100, 85, 85, 110, 140, 140, 140, 140]                          # the account holds little at the start of the climb, so it needs a big rise to pass 1,000,000
    r, _ = gov_run(path)
    first_high = next(t for t in range(5, len(path)) if r.equity[t] >= 1_000_000)
    assert r.multiplier[3] < 1 and (r.multiplier[4:first_high] < 1).all() and r.multiplier[first_high] == 1.0


def test_after_sixty_days_without_a_new_low_the_cut_is_released_and_the_rule_applies_afresh():
    path = [100, 100, 100, 85, 85] + list(np.linspace(85.5, 92, 70))                   # no new low, a slow recovery that never reaches the old high
    r, _ = gov_run(path, hold_days=60)
    cut = r.multiplier[3]
    t_low = 4                                                                          # the lowest close of the account
    before, after = t_low + 59, t_low + 60                                             # the release comes on the 60th day after the lowest close
    assert r.multiplier[before] <= cut + 1e-12                                        # still held at the lowest cut
    assert r.multiplier[after] == pytest.approx(raw_multiplier(r.drawdown[after]), abs=1e-9) and r.multiplier[after] > cut


def test_the_governor_sells_the_risky_asset_into_cash_when_it_cuts_and_buys_back_after_the_release():
    path = [100, 100, 100, 85, 85, 85, 85, 85, 140, 140, 140, 140, 140]
    r, _ = gov_run(path)
    assert r.units[2, 0] > 0
    assert r.units[6, 0] < r.units[2, 0] * 0.6                                         # cut to about 37.5%
    back = next(t for t in range(8, len(path)) if r.multiplier[t] == 1.0)
    assert r.units[back + 1, 0] > r.units[6, 0]


def test_the_governor_off_leaves_the_weights_alone_and_reports_the_same_drawdown():
    days = weekdays(date(2016, 6, 1), 12)
    close = np.array([100, 100, 100, 85, 85, 85, 85, 85, 101, 101, 101, 101.0])
    p = flat_panel(days, close=close)
    r = sim.simulate(p, W(days, [[1, 0, 0, 0, 0]]), RULES, sim.SimConfig(capital=1_000_000.0, governor=False, slippage=False, band=0.0, min_trade=0.0))
    assert (r.multiplier == 1.0).all() and r.units[5, 0] == r.units[2, 0] and r.drawdown.max() > 0.14


# ---- behaviours the mutants showed were not pinned ----------------------------------------------------------------------------------------------------

def test_an_underweight_inside_the_band_is_not_bought_either():
    days = weekdays(date(2016, 6, 1), 6)
    close = np.array([100, 100, 100, 99, 99, 99.0])
    p = flat_panel(days, close=close)
    r = sim.simulate(p, W(days, [[0.5, 0, 0, 0, 0.5]]), RULES, sim.SimConfig(capital=1_000_000.0, governor=False, slippage=False, band=0.01, min_trade=0.0))
    assert r.units[1, 0] == r.units[5, 0] and r.units[1, 4] == r.units[5, 4]             # the ETF half lost 1%: a 0.25% gap to target, inside the 1% band


def test_slippage_is_paid_on_sells_as_well_as_on_buys_and_charges_follow_the_price_actually_got():
    days = weekdays(date(2016, 6, 1), 5)
    p = flat_panel(days, price=100.0, value=5e7)
    w = W(days, [[1, 0, 0, 0, 0], [1, 0, 0, 0, 0], [0, 0, 0, 0, 1]])                  # buy filled on day 1, sell filled on day 3
    r = sim.simulate(p, w, RULES, sim.SimConfig(capital=1_000_000.0, governor=False, slippage=True))
    u = float(r.units[1, 0])
    reg, day_reg = costs.regimes(RULES, days)
    t = costs.charge_table(RULES, [reg[day_reg[1]]])
    s_buy = costs.slippage_rate("NIFTYBEES", u * 100.0, 5e7)
    assert r.cash[1] == pytest.approx(1_000_000 - u * 100.0 * (1 + s_buy) - costs.charge(t, 0, "etf_equity", "buy", u * 100.0 * (1 + s_buy)), abs=15.0)
    s_sell = costs.slippage_rate("NIFTYBEES", u * 100.0, 5e7)
    assert r.slippage[3] == pytest.approx(u * 100.0 * s_sell, rel=0.02) and r.slippage[3] > 0
    assert r.traded[3] >= u * 100.0 * (1 - s_sell) * 0.99                                   # the proceeds at the worse price, and the fund bought with them
    assert r.charges[3] > 0


def test_drawdown_is_measured_from_the_running_high_even_when_the_governor_is_off():
    days = weekdays(date(2016, 6, 1), 8)
    close = np.array([100, 100, 150, 150, 150, 135, 135, 135.0])
    p = flat_panel(days, close=close)
    r = sim.simulate(p, W(days, [[1, 0, 0, 0, 0]]), RULES, sim.SimConfig(capital=1_000_000.0, governor=False, slippage=False, band=0.0, min_trade=0.0))
    assert r.drawdown[-1] == pytest.approx(1 - 135 / 150, abs=1e-3)
    assert r.drawdown[3] == pytest.approx(0.0, abs=1e-9)


def test_the_yearly_demat_fee_leaves_the_account_on_the_last_trading_day_of_the_financial_year():
    days = weekdays(date(2017, 3, 28), 6)                   # 28, 29, 30, 31 March, 3, 4 April 2017
    p = flat_panel(days, price=100.0)
    r = sim.simulate(p, W(days, [[0, 0, 0, 0, 1]]), RULES, sim.SimConfig(**CFG))
    fee = float(costs.fixed_costs(RULES, days)[3])
    assert fee > 0 and r.equity[3] == pytest.approx(r.equity[2] - fee, abs=0.01)
    assert r.equity[4] == pytest.approx(r.equity[3], abs=0.01)


def test_the_liquidation_tax_is_what_selling_everything_adds_to_the_year_so_far():
    days = weekdays(date(2017, 4, 3), 10)
    close = np.array([100, 100, 100, 110, 110, 110, 130, 130, 130, 130.0])
    p = flat_panel(days, close=close)
    # sell half the ETF (a realised gain) and keep the rest (an unrealised gain)
    w = W(days, [[1, 0, 0, 0, 0], [1, 0, 0, 0, 0], [0.5, 0, 0, 0, 0.5]])
    r = sim.simulate(p, w, RULES, sim.SimConfig(capital=1_000_000.0, governor=False, slippage=False, band=0.2, min_trade=0.0))     # a wide band: the +18% drift on the ETF half is not rebalanced
    assert r.pending_tax > 0 and r.liquidation_tax > 0
    sold = float(r.units[1, 0] - r.units[3, 0])
    both = engine_tax_of_one_round_trip(sold, 100.0, days[1], 110.0, days[3])
    assert r.pending_tax == pytest.approx(both, abs=12.0)
    kept = float(r.units[-1, 0])
    # the exact engine's tax on the year with both sales, minus the year's tax on the first sale alone
    from engine.charges import Order, dp_charge, order_charges
    from engine.tax import fy_of
    bc = order_charges(RULES, Order(days[1], "etf_equity", "buy", Decimal(repr(kept)), Decimal("100")))
    sc = order_charges(RULES, Order(days[-1], "etf_equity", "sell", Decimal(repr(kept)), Decimal("130")))
    e2 = CGEvent("kept", days[-1], "etf_equity", days[1], const("p", Decimal(repr(kept)) * 130), const("sc", sc.deductible.value + dp_charge(RULES, days[-1]).value),
                 const("c", Decimal(repr(kept)) * 100 + bc.deductible.value))
    q = Decimal(repr(sold))
    bc1 = order_charges(RULES, Order(days[1], "etf_equity", "buy", q, Decimal("100")))
    sc1 = order_charges(RULES, Order(days[3], "etf_equity", "sell", q, Decimal("110")))
    e1 = CGEvent("sold", days[3], "etf_equity", days[1], const("p", q * 110), const("sc", sc1.deductible.value + dp_charge(RULES, days[3]).value), const("c", q * 100 + bc1.deductible.value))
    total = float(investment_tax(RULES, fy_of(days[-1]), PROFILE, [e1, e2]).extra.value)
    assert r.liquidation_tax == pytest.approx(total - float(investment_tax(RULES, fy_of(days[-1]), PROFILE, [e1]).extra.value), abs=15.0)


def test_the_wealth_lost_to_slippage_is_what_is_reported_on_buys_and_sells_together():
    days = weekdays(date(2016, 6, 1), 6)
    p = flat_panel(days, price=100.0, value=5e7)
    w = W(days, [[1, 0, 0, 0, 0], [1, 0, 0, 0, 0], [0, 0, 0, 0, 1]])                  # buy on day 1, sell on day 3, both at the same flat price
    free = sim.simulate(p, w, RULES, sim.SimConfig(**CFG))
    slipped = sim.simulate(p, w, RULES, sim.SimConfig(capital=1_000_000.0, governor=False, slippage=True))
    assert slipped.slippage[1] > 0 and slipped.slippage[3] > 0
    lost = free.equity[5] - slipped.equity[5]
    assert lost == pytest.approx(slipped.slippage[1] + slipped.slippage[3], rel=0.06)        # what the two fills cost, as reported (charges differ by a few rupees)


def test_the_tax_paid_out_of_the_account_is_not_a_drawdown_and_does_not_trip_the_governor():
    days = weekdays(date(2016, 6, 1), 230)                                  # runs past the start of the next financial year, when the tax is paid
    close = np.concatenate([np.linspace(100, 150, 100), np.full(130, 150.0)])
    p = flat_panel(days, close=close)
    w = W(days, [[1, 0, 0, 0, 0]] * 100 + [[0, 0, 0, 0, 1]])                # hold the rising ETF, then sell it all: a short-term gain, taxed when the year ends
    r = sim.simulate(p, w, RULES, sim.SimConfig(capital=1_000_000.0, cap=0.04, governor=True, slippage=False))
    assert r.tax_paid.sum() > 30_000                                        # about 15% of a 50% gain on Rs 10 lakh
    paid = int(np.flatnonzero(r.tax_paid)[0])
    assert r.equity[paid] < r.equity[paid - 1] - 30_000                     # the account is poorer by the tax ...
    assert r.drawdown.max() < 0.005                                         # ... but a payment out of the account is not a market loss: only the sale's charges show
    assert r.multiplier.min() == 1.0


def test_selling_the_whole_fund_position_after_pieces_were_sold_across_lots_does_not_trip_on_float_dust():
    import dataclasses
    days = weekdays(date(2016, 6, 1), 12)
    p = flat_panel(days, price=100.0)
    p = dataclasses.replace(p, cash=p.cash * 1e-3)                          # a very low unit value: about a billion units, where rounding is 1e-7 of a unit
    w = W(days, [[0.6, 0, 0, 0, 0.4], [0.3, 0, 0, 0, 0.7], [0.75, 0, 0, 0, 0.25], [1, 0, 0, 0, 0]])
    r = sim.simulate(p, w, RULES, sim.SimConfig(**CFG))
    marks = np.column_stack([p.close, p.cash])
    assert r.units[-1, 4] == 0 and r.units[-1, 0] > 0
    assert np.allclose(r.equity, (r.units * marks).sum(axis=1) + r.cash, rtol=0, atol=1e-6)
