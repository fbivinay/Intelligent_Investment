from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

from engine.charges import Order, order_charges
from engine.rules import Rules
from engine.tax import TaxProfile, investment_tax, fy_of
from engine.trace import assert_balanced, walk
from calc import replay as R
from research import sim
from research.panel import ASSETS, Panel

RULES = Rules.load(Path(__file__).resolve().parents[1] / "rules")
PROFILE = TaxProfile("new", Decimal(1500000))


def weekdays(start, n):
    d, out = start, []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def world(n=900, start=date(2016, 6, 1), seed=5):
    days = weekdays(start, n)
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.01, (n, 4)), axis=0))
    nan = np.full(n, np.nan)
    return Panel(dates=np.array(days, dtype="datetime64[D]"), assets=list(ASSETS), open=close, high=close * 1.01, low=close * 0.99, close=close, value=np.full((n, 4), 3e8),
                 vwap=close * 1.001, cash=1.0002 ** np.arange(n), nifty=close[:, 0], vix=nan, pe=nan, pb=nan)


def weights(n, seed=4):
    rng = np.random.default_rng(seed)
    return rng.dirichlet(np.ones(5), n // 60 + 1).repeat(60, axis=0)[:n]


def run(p, w, amount=Decimal(1000000), profile=PROFILE):
    r = sim.simulate(p, w, RULES, sim.SimConfig(capital=float(amount), governor=False, harvest=True, profile=profile))
    return r, R.book(RULES, p, r.order_log, amount, profile)


def last_year_amc(p):
    """The book charges the demat fee for the year in progress too, as the engine's buy-and-hold does; the fast simulator does not."""
    from engine.charges import amc_fee
    days = [date.fromisoformat(str(d)) for d in p.dates]
    return float(amc_fee(RULES, days[-1], days[0]).value) if fy_of(days[-1]) != fy_of(days[0]) or True else 0.0


def test_every_number_of_both_endings_balances_and_the_waterfall_adds_up():
    p = world()
    _, b = run(p, weights(900))
    for net in (b.sold, b.held):
        assert_balanced(net)
    w = b.waterfall["sold"]
    assert w["net"].value == w["gross_end"].value - w["charges"].value - w["tax"].value and w["initial"].value == Decimal(1000000)
    assert sum(n.value for n in b.charges_by_kind["sold"].values()) == w["charges"].value


def test_each_orders_charges_are_the_engines_own():
    p = world()
    r, b = run(p, weights(900))
    t = b.trades[7]
    on = date.fromisoformat(t["date"])
    ch = order_charges(RULES, Order(on, t["class"], t["side"], Decimal(t["units"]), Decimal(t["price"])))
    assert Decimal(t["charges"]) == ch.total.value and len(b.trades) == r.orders


def test_the_tax_of_each_completed_year_is_the_engines_on_that_years_sales():
    p = world()
    _, b = run(p, weights(900))
    carry = None
    for fy, events in sorted(b.events_by_fy.items()):
        if fy == max(b.events_by_fy):
            break
        from engine.tax import Carry
        it = investment_tax(RULES, fy, PROFILE, events, carry or Carry())
        carry = it.with_items.carry_out
        assert b.tax_by_fy[fy].value == it.extra.value


def test_the_exact_books_agree_with_the_fast_simulator_within_the_charge_interpolation():
    p = world()
    r, b = run(p, weights(900))
    amc = last_year_amc(p)
    assert float(b.held.value) == pytest.approx(r.equity[-1] - r.pending_tax - amc, abs=60.0)
    assert float(b.sold.value) == pytest.approx(r.liquidation_equity - amc, abs=60.0)


def test_selling_everything_costs_exactly_the_liquidations_charges_and_tax():
    p = world()
    _, b = run(p, weights(900))
    s, h = b.waterfall["sold"], b.waterfall["held"]
    assert b.sold.value - b.held.value == -(s["charges"].value - h["charges"].value) - (s["tax"].value - h["tax"].value)
    assert s["gross_end"].value == h["gross_end"].value                                            # sold at the same close the holdings are valued at


def test_fund_units_bought_and_sold_many_times_never_oversell_and_the_end_holdings_match_the_simulator():
    p = world(n=700)
    n = 700
    share = np.clip(0.5 + np.cumsum(np.random.default_rng(1).normal(0, 0.03, n)), 0, 1)
    w = np.column_stack([share, np.zeros((n, 3)), 1 - share])
    r, b = run(p, w)
    assert float(b.holdings["NIFTYBEES"]) == r.units[-1, 0] and float(b.holdings["LIQUID_FUND"]) == pytest.approx(r.units[-1, 4], rel=1e-9)


def test_a_lot_bought_before_31_january_2018_is_grandfathered_when_sold():
    p = world(n=700, start=date(2017, 6, 1))
    w = np.tile([0.9, 0, 0, 0, 0.1], (700, 1))
    w[400:] = [0.3, 0, 0, 0, 0.7]                                                                   # sold down in late 2018
    _, b = run(p, w)
    sold_2018 = [e for fy, es in b.events_by_fy.items() for e in es if e.acq_date <= date(2018, 1, 31) and e.asset_class == "etf_equity"]
    assert sold_2018 and all(e.fmv_2018 is not None for e in sold_2018)


def test_the_trade_and_tax_lines_hold_what_a_csv_needs():
    p = world()
    _, b = run(p, weights(900))
    assert set(b.trades[0]) >= {"date", "asset", "class", "side", "units", "price", "vwap", "slippage", "turnover", "charges", "dp"}
    line = b.tax_lines[0]
    assert set(line) >= {"financial_year", "asset", "bought", "sold", "units", "proceeds", "sale_costs", "cost", "term"}
    assert R.csv_text(b.trades).splitlines()[0].startswith("date,asset,class,side")


def test_no_order_at_all_leaves_the_money_less_the_fees():
    p = world(n=60)
    w = np.tile([0, 0, 0, 0, 1.0], (60, 1))
    r = sim.simulate(p, w, RULES, sim.SimConfig(governor=False))
    b = R.book(RULES, p, r.order_log[:0], Decimal(1000000), PROFILE)
    assert b.held.value == b.sold.value == Decimal(1000000) - b.waterfall["held"]["charges"].value and b.trades == []


def flat_world(start, n, price=100.0):
    days = weekdays(start, n)
    close = np.full((n, 4), price)
    nan = np.full(n, np.nan)
    return Panel(dates=np.array(days, dtype="datetime64[D]"), assets=list(ASSETS), open=close, high=close, low=close, close=close, value=np.full((n, 4), 1e9), vwap=close,
                 cash=np.ones(n), nifty=close[:, 0], vix=nan, pe=nan, pb=nan), days


def test_a_fund_sale_a_hair_above_the_units_held_sells_what_is_held():
    p, days = flat_world(date(2021, 6, 1), 30)
    log = np.array([[1, 4, 0, 100.1, 1.0, 0.0], [5, 4, 1, 100.10000000000001, 1.0, 0.0]])
    b = R.book(RULES, p, log, Decimal(1000), PROFILE)
    assert b.holdings["LIQUID_FUND"] == 0 and Decimal(b.trades[1]["units"]) == Decimal(b.trades[0]["units"])


def test_from_june_2025_two_sales_of_one_etf_on_one_day_pay_one_depository_charge_and_before_it_two():
    for start, want in ((date(2025, 7, 1), 1), (date(2024, 7, 1), 2)):
        p, days = flat_world(start, 30)
        log = np.array([[1, 0, 0, 100, 100.0, 0.0], [5, 0, 1, 40, 100.0, 0.0], [5, 0, 1, 60, 100.0, 0.0]])
        b = R.book(RULES, p, log, Decimal(20000), PROFILE)
        assert sum(1 for t in b.trades if t["dp"] != "0") == want


def test_an_account_opened_when_fyers_charged_for_opening_pays_that_fee():
    p, days = flat_world(date(2020, 6, 1), 30)
    b = R.book(RULES, p, np.zeros((0, 6)), Decimal(1000000), PROFILE)
    fee = b.charges_by_kind["held"]["fees"].value
    from engine.charges import account_opening_fee, amc_fee
    assert account_opening_fee(RULES, days[0]).value > 0 and fee == account_opening_fee(RULES, days[0]).value + amc_fee(RULES, days[-1], days[0]).value


def test_a_loss_in_one_year_is_carried_to_set_off_a_gain_the_next_year():
    n = 300
    days = weekdays(date(2021, 6, 1), n)
    close = np.full((n, 4), 100.0)
    fy2 = next(i for i, d in enumerate(days) if d >= date(2022, 4, 1))
    close[100:fy2 + 20, :] = 80.0                                                                      # bought at 100, sold at 80 in FY 2021-22
    close[fy2 + 20:, :] = 120.0
    nan = np.full(n, np.nan)
    p = Panel(dates=np.array(days, dtype="datetime64[D]"), assets=list(ASSETS), open=close, high=close, low=close, close=close, value=np.full((n, 4), 1e9), vwap=close,
              cash=np.ones(n), nifty=close[:, 0], vix=nan, pe=nan, pb=nan)
    log = np.array([[1, 0, 0, 1000, 100.0, 0.0], [110, 0, 1, 1000, 80.0, 0.0], [fy2 + 5, 0, 0, 1000, 80.0, 0.0], [fy2 + 30, 0, 1, 1000, 120.0, 0.0]])
    b = R.book(RULES, p, log, Decimal(200000), TaxProfile("new", Decimal(1500000)))
    alone = R.book(RULES, p, log[2:], Decimal(200000), TaxProfile("new", Decimal(1500000)))
    assert b.tax_by_fy[2021].value == 0 and 0 < b.tax_by_fy[2022].value < alone.tax_by_fy[2022].value        # the Rs 20,000 loss halves the Rs 40,000 gain
