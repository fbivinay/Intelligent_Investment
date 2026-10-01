"""W1, tax-aware execution in the simulator: hold a lot a few more days when it is about to turn long-term, and each year realise long-term equity gains up to the
yearly exemption and buy the units back the next day."""
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

from engine.rules import Rules
from engine.tax import CGEvent, classify
from engine.trace import const
from research import sim
from research.panel import ASSETS, Panel

RULES = Rules.load(Path(__file__).resolve().parents[1] / "rules")


def weekdays(start, n):
    d, out = start, []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def panel(days, close):
    T = len(days)
    c = np.asarray(close, dtype=float).reshape(T, -1) * np.ones((1, 4))
    nan = np.full(T, np.nan)
    return Panel(dates=np.array(days, dtype="datetime64[D]"), assets=list(ASSETS), open=c, high=c, low=c, close=c, value=np.full((T, 4), 1e10), vwap=c, cash=np.ones(T),
                 nifty=c[:, 0], vix=nan, pe=nan, pb=nan)


def idx(days, d):
    return days.index(d)


def cfg(**kw):
    return sim.SimConfig(**{"capital": 1_000_000.0, "governor": False, "slippage": False, **kw})


def term(cls, acq, sale):
    e = CGEvent("x", sale, cls, acq, const("p", Decimal(100)), const("c", Decimal(0)), const("k", Decimal(90)), fmv_2018=const("f", Decimal(95)))
    return classify(RULES, e)[1][0]


@pytest.mark.parametrize("cls", ["etf_equity", "etf_gold", "mf_debt"])
def test_the_day_a_lot_turns_long_term_is_the_first_day_the_engine_calls_its_sale_long_term(cls):
    days = weekdays(date(2017, 1, 2), 2600)                                                  # 2017 to 2026
    lt = sim.lt_turn_days(RULES, days, cls)
    assert lt.shape == (2600,) and lt.dtype == np.int64
    for a in (0, 50, 300, 700, 1500, 2000):
        t = int(lt[a])
        if t < len(days):
            assert term(cls, days[a], days[t]) == "long" and (t - 1 <= a or term(cls, days[a], days[t - 1]) == "short"), (cls, days[a], days[t])
        else:
            assert term(cls, days[a], days[-1]) == "short"


def test_an_equity_lot_bought_on_2_april_2019_is_long_term_from_3_april_2020():
    days = weekdays(date(2019, 4, 1), 400)
    lt = sim.lt_turn_days(RULES, days, "etf_equity")
    assert days[int(lt[idx(days, date(2019, 4, 2))])] == date(2020, 4, 3)


def hold_case():
    """Bought on 2019-04-02 (decided on the 1st) at 100, rising to 120; on 2020-03-20 the target halves: the lot is 11 days short of turning long-term."""
    days = weekdays(date(2019, 4, 1), 290)
    close = np.r_[np.linspace(100, 120, 245), np.full(45, 120.0)]
    w = np.tile([1.0, 0, 0, 0, 0], (290, 1))
    d = idx(days, date(2020, 3, 20))
    return days, panel(days, close), w, d


def test_without_the_hold_rule_a_trim_eleven_days_before_the_lot_turns_long_term_is_sold_at_once_and_taxed_short_term():
    days, p, w, d = hold_case()
    w[d:] = [0.5, 0, 0, 0, 0.5]
    r = sim.simulate(p, w, RULES, cfg())
    assert r.units[d + 1, 0] < r.units[d, 0] and r.tax_by_fy[2019] > 10_000                     # about 15% of a gain near Rs 1 lakh


def test_with_the_hold_rule_the_trim_waits_for_the_lot_to_turn_long_term_and_the_gain_falls_under_the_yearly_exemption():
    days, p, w, d = hold_case()
    w[d:] = [0.5, 0, 0, 0, 0.5]
    r = sim.simulate(p, w, RULES, cfg(hold_days=30))
    turn = idx(days, date(2020, 4, 3))
    assert (r.units[d:turn, 0] == r.units[d, 0]).all() and r.units[turn, 0] < r.units[d, 0]
    assert r.tax_by_fy.get(2019, 0.0) == 0.0 and r.pending_tax == pytest.approx(0.0, abs=1.0)    # the year's long-term gain is within Rs 1 lakh


def test_the_hold_rule_never_delays_an_exit():
    days, p, w, d = hold_case()
    w[d:] = [0, 0, 0, 0, 1.0]
    r = sim.simulate(p, w, RULES, cfg(hold_days=30))
    assert r.units[d + 1, 0] == 0


def test_the_hold_rule_never_delays_a_sale_the_governor_asks_for():
    days = weekdays(date(2019, 4, 1), 290)
    close = np.full(290, 100.0)
    fall = idx(days, date(2020, 3, 12))
    close[fall:fall + 5] = np.linspace(97, 86, 5)
    close[fall + 5:] = 86.0
    w = np.tile([1.0, 0, 0, 0, 0], (290, 1))
    r = sim.simulate(panel(days, close), w, RULES, cfg(governor=True, cap=0.2, hold_days=30))
    cut = int(np.flatnonzero(r.multiplier < 1)[0])
    assert days[cut] < date(2020, 4, 3) and r.units[cut + 1, 0] < r.units[cut, 0]               # a 14% fall is past half the cap of 20%: risk is cut at once


def harvest_case(n=560):
    """Bought on 2018-04-03 at 100; the price rises to 130 by March 2019 and stays there: by March 2020 the lot is long-term with a gain of about Rs 3 lakh."""
    days = weekdays(date(2018, 4, 2), n)
    close = np.r_[np.linspace(100, 130, 250), np.full(n - 250, 130.0)]
    return days, panel(days, close), np.tile([1.0, 0, 0, 0, 0], (n, 1))


def test_the_harvest_day_is_the_fifth_to_last_trading_day_of_each_financial_year_and_none_for_a_year_the_data_does_not_finish():
    days = weekdays(date(2018, 4, 2), 560)
    h = sim.harvest_days(days, offset=5)
    marked = [days[i] for i in np.flatnonzero(h)]
    ends = [date(2019, 3, 29), date(2020, 3, 31)]
    assert [d.year for d in marked] == [2019, 2020] and all(days.index(m) == days.index(e) - 4 for m, e in zip(marked, ends))
    assert marked[0] == date(2019, 3, 25)


def test_harvesting_sells_long_term_gains_up_to_the_exemption_buys_the_units_back_the_next_day_and_pays_no_tax_on_them():
    days, p, w = harvest_case()
    r = sim.simulate(p, w, RULES, cfg(harvest=True))
    h = int(np.flatnonzero(sim.harvest_days(days, 5))[1])                                     # March 2020; in March 2019 the lot was not yet long-term
    assert days[h].year == 2020 and r.units[h, 0] < r.units[h - 1, 0]
    assert r.units[h - 1, 0] - 1 <= r.units[h + 1, 0] <= r.units[h - 1, 0]                     # bought back; the round trip's charges may cost one unit when there is no spare cash
    sold = r.units[h - 1, 0] - r.units[h, 0]
    assert 90_000 < sold * 30 < 100_000                                                        # the gain realised is just under the exemption of Rs 1 lakh
    assert r.tax_by_fy.get(2019, 0.0) == 0.0 and r.units[idx(days, date(2019, 3, 26)), 0] == r.units[1, 0]


def test_the_harvest_lowers_the_tax_of_selling_everything_later_by_the_rate_times_the_gain_it_realised():
    days, p, w = harvest_case()
    off = sim.simulate(p, w, RULES, cfg())
    on = sim.simulate(p, w, RULES, cfg(harvest=True))
    assert days[-1] > date(2020, 4, 1)                                                         # selling everything happens in the next financial year
    saved = off.liquidation_tax - on.liquidation_tax
    assert 8_500 < saved < 10_500 and on.liquidation_equity > off.liquidation_equity + 8_000     # about 10% of the Rs 95,000 harvested, less the round trip's charges


def test_there_is_no_harvest_while_long_term_equity_gains_were_exempt_in_full():
    days = weekdays(date(2015, 4, 1), 800)
    close = np.linspace(100, 160, 800)
    r = sim.simulate(panel(days, close), np.tile([0.99, 0, 0, 0, 0.01], (800, 1)), RULES, cfg(harvest=True))             # 1% in the fund pays the yearly fees
    before = idx(days, date(2018, 3, 29))
    assert (r.units[1:before, 0] == r.units[1, 0]).all()


def test_the_harvest_stops_at_the_first_lot_that_is_still_short_term():
    days = weekdays(date(2018, 4, 2), 560)
    close = np.r_[np.linspace(100, 104, 250), np.full(310, 104.0)]                             # the first lot gains only about Rs 20,000
    w = np.tile([0.5, 0, 0, 0, 0.5], (560, 1))
    second = idx(days, date(2019, 9, 2))
    w[second:] = [1.0, 0, 0, 0, 0]                                                             # a second lot, bought in September 2019, short-term in March 2020
    r = sim.simulate(panel(days, close), w, RULES, cfg(harvest=True))
    h = int(np.flatnonzero(sim.harvest_days(days, 5))[1])
    first_lot = r.units[second, 0]
    assert r.units[h - 1, 0] - r.units[h, 0] == first_lot and r.units[h - 1, 0] - 1 <= r.units[h + 1, 0] <= r.units[h - 1, 0]


def test_gold_and_the_cash_leg_are_never_harvested():
    days, p, w = harvest_case()
    w = np.tile([0, 0, 0, 0.99, 0.01], (560, 1))                                               # gold, and 1% in the fund for the yearly fees: nothing else to sell
    r = sim.simulate(p, w, RULES, cfg(harvest=True))
    assert (r.units[1:, 3] == r.units[1, 3]).all() and r.units[1, 4] > 0


def test_with_both_parts_off_the_results_are_those_of_the_plain_simulator():
    days, p, w = harvest_case()
    w[300:] = [0.6, 0, 0, 0, 0.4]
    a = sim.simulate(p, w, RULES, cfg())
    b = sim.simulate(p, w, RULES, cfg(hold_days=0, harvest=False))
    assert np.array_equal(a.equity, b.equity) and a.tax_by_fy == b.tax_by_fy


def test_a_trim_due_exactly_thirty_days_before_the_lot_turns_long_term_waits_and_one_due_thirty_one_days_before_does_not():
    days, p, w, _ = hold_case()
    turn = idx(days, date(2020, 4, 3))
    for decided, waits in ((date(2020, 3, 3), True), (date(2020, 3, 2), False)):          # filled on the 4th (30 days before) and on the 3rd (31 days before)
        ww = w.copy()
        ww[idx(days, decided):] = [0.5, 0, 0, 0, 0.5]
        r = sim.simulate(p, ww, RULES, cfg(hold_days=30))
        fill = idx(days, decided) + 1
        assert (r.units[fill, 0] == r.units[fill - 1, 0]) == waits and r.units[turn, 0] < r.units[1, 0]


def test_long_term_gains_already_realised_this_year_leave_less_of_the_exemption_to_harvest():
    days, p, w = harvest_case()
    early = idx(days, date(2019, 10, 1))
    w2 = w.copy()
    w2[early:] = [0.85, 0, 0, 0, 0.15]                                                        # a long-term sale in October 2019 realises about Rs 45,000
    r = sim.simulate(p, w2, RULES, cfg(harvest=True))
    h = int(np.flatnonzero(sim.harvest_days(days, 5))[1])
    realised = (r.units[early, 0] - r.units[early + 1, 0]) * 30
    sold = (r.units[h - 1, 0] - r.units[h, 0]) * 30
    assert 35_000 < realised < 55_000 and 90_000 < realised + sold < 100_000


def test_the_harvest_estimates_the_gain_at_the_previous_close_not_at_the_harvest_days_own_close():
    days, p, w = harvest_case()
    h = int(np.flatnonzero(sim.harvest_days(days, 5))[1])
    close = p.close.copy()
    close[h:] = 200.0                                                                          # a jump on the harvest day itself
    vwap = p.vwap.copy()
    vwap[h:] = 200.0
    vwap[h] = 130.0                                                                            # filled before the jump
    import dataclasses
    q = dataclasses.replace(p, close=close, vwap=vwap)
    r = sim.simulate(q, w, RULES, cfg(harvest=True))
    assert 90_000 < (r.units[h - 1, 0] - r.units[h, 0]) * 30 < 100_000


def test_a_lot_bought_before_31_january_2018_is_harvested_on_its_gain_above_that_days_value():
    days = weekdays(date(2017, 6, 1), 520)
    gf = idx(days, date(2018, 1, 31))
    close = np.r_[np.linspace(100, 125, gf + 1), np.linspace(125, 135, 520 - gf - 1)]
    p = panel(days, close)
    r = sim.simulate(p, np.tile([0.99, 0, 0, 0, 0.01], (520, 1)), RULES, cfg(harvest=True))
    h = int(np.flatnonzero(sim.harvest_days(days, 5))[1])                                     # March 2019, the first year with an exemption
    assert days[h] == date(2019, 3, 25)
    per_unit = p.close[h - 1, 0] - p.high[gf, 0]
    sold = r.units[h - 1, 0] - r.units[h, 0]
    assert 85_000 < sold * per_unit < 100_000 and sold > 0.5 * r.units[h - 1, 0]                 # about Rs 10 a unit above the value on 31 January 2018


def test_no_buy_back_when_the_strategy_exits_the_asset_and_only_one_buy_back():
    days, p, w = harvest_case()
    h = int(np.flatnonzero(sim.harvest_days(days, 5))[1])
    w2 = w.copy()
    w2[h:] = [0, 0, 0, 0, 1.0]                                                                 # decided after the harvest day's close: out
    r = sim.simulate(p, w2, RULES, cfg(harvest=True))
    assert r.units[h + 1, 0] == 0
    r2 = sim.simulate(p, w, RULES, cfg(harvest=True))
    assert r2.units[h + 2, 0] == r2.units[h + 1, 0] == r2.units[-1, 0]


def test_each_financial_year_starts_with_the_whole_exemption():
    days, p, w = harvest_case(n=820)                                                           # to May 2021: harvests in March 2020 and March 2021
    r = sim.simulate(p, w, RULES, cfg(harvest=True))
    hs = np.flatnonzero(sim.harvest_days(days, 5))
    assert len(hs) == 3
    for h in hs[1:]:
        assert 90_000 < (r.units[h - 1, 0] - r.units[h, 0]) * 30 < 100_000
    assert r.tax_by_fy.get(2019, 0.0) == 0.0 and r.tax_by_fy.get(2020, 0.0) == 0.0


def test_the_units_harvested_are_bought_back_even_when_the_gap_is_inside_the_trading_band():
    days, p, w = harvest_case()
    r = sim.simulate(p, w, RULES, cfg(harvest=True, band=0.5))                                # the normal rebalancing would never buy them back
    h = int(np.flatnonzero(sim.harvest_days(days, 5))[1])
    assert r.units[h, 0] < r.units[h - 1, 0] and r.units[h - 1, 0] - 1 <= r.units[h + 1, 0]


def test_after_an_exit_decided_on_the_harvest_day_nothing_is_bought_back_before_the_sale():
    days, p, w = harvest_case()
    h = int(np.flatnonzero(sim.harvest_days(days, 5))[1])
    w2 = w.copy()
    w2[h:] = [0, 0, 0, 0, 1.0]
    r = sim.simulate(p, w2, RULES, cfg(harvest=True))
    left = r.units[h, 0] * p.vwap[h + 1, 0]
    assert r.traded[h + 1] < 2 * left + r.cash[h] + 50_000                                      # the exit sale and the fund bought with all the cash; no buy and sell of the harvested units


def test_a_buy_back_happens_once_even_when_there_is_cash_left_over():
    days, p, w = harvest_case()
    w2 = np.tile([0.6, 0, 0, 0, 0.4], (560, 1))
    r = sim.simulate(p, w2, RULES, cfg(harvest=True, band=0.5))                               # with a band of 50% the 40% for the fund stays as spare cash
    h = int(np.flatnonzero(sim.harvest_days(days, 5))[1])
    assert r.cash[h + 1] > 100_000 and r.units[h + 2, 0] == r.units[h + 1, 0] == r.units[-1, 0]


def test_short_term_gains_realised_earlier_in_the_year_do_not_use_up_the_exemption():
    days, p, w = harvest_case()
    w2 = np.tile([0.7, 0, 0, 0, 0.3], (560, 1))
    buy, sell = idx(days, date(2019, 6, 3)), idx(days, date(2019, 11, 1))
    w2[buy:sell] = [0.7, 0.3, 0, 0, 0]                                                        # Junior BeES bought in June 2019 ...
    import dataclasses
    close = p.close.copy()
    close[:, 1] = np.where(np.arange(560) < buy, 100.0, np.linspace(100, 160, 560))          # ... rising fast ...
    q = dataclasses.replace(p, close=close, vwap=close, high=close, low=close, open=close)
    r = sim.simulate(q, w2, RULES, cfg(harvest=True))                                         # ... and sold in November: a short-term gain
    st_gain = r.units[sell, 1] * (close[sell + 1, 1] - close[buy + 1, 1])
    h = int(np.flatnonzero(sim.harvest_days(days, 5))[1])
    assert st_gain > 30_000 and r.units[sell + 1, 1] == 0
    assert 90_000 < (r.units[h - 1, 0] - r.units[h, 0]) * 30 < 100_000                        # the Nifty BeES harvest still uses the whole exemption


def test_a_long_term_gain_realised_on_a_lot_from_before_2018_counts_at_its_grandfathered_cost():
    days = weekdays(date(2017, 6, 1), 520)
    gf = idx(days, date(2018, 1, 31))
    close = np.r_[np.linspace(100, 125, gf + 1), np.linspace(125, 150, 520 - gf - 1)]
    p = panel(days, close)
    w = np.tile([0.99, 0, 0, 0, 0.01], (520, 1))
    trim = idx(days, date(2018, 10, 1))
    w[trim:] = [0.7, 0, 0, 0, 0.3]                                                            # sells about 30% in October 2018 at a grandfathered gain of about Rs 13 a unit
    r = sim.simulate(p, w, RULES, cfg(harvest=True))
    h = int(np.flatnonzero(sim.harvest_days(days, 5))[1])
    sold_early = r.units[trim, 0] - r.units[trim + 1, 0]
    early_gain = sold_early * (p.vwap[trim + 1, 0] - p.high[gf, 0])
    harvested = r.units[h - 1, 0] - r.units[h, 0]
    harvest_gain = harvested * (p.close[h - 1, 0] - p.high[gf, 0])
    assert 25_000 < early_gain < 50_000 and 0 < harvested < 0.6 * r.units[h - 1, 0]            # the exemption, not the units held, limits the harvest
    assert 85_000 < early_gain + harvest_gain < 100_000                                       # counted at the actual cost of 100 the early sale alone would use it up


def test_long_term_gold_is_not_harvested():
    days = weekdays(date(2018, 4, 2), 1050)                                                   # to April 2022: gold bought in April 2018 is long-term after 36 months
    close = np.r_[np.linspace(100, 130, 250), np.full(800, 130.0)]
    assert sim.harvest_days(days, 5)[idx(days, date(2022, 3, 25))]                            # a harvest day with the gold lot long-term
    r = sim.simulate(panel(days, close), np.tile([0, 0, 0, 0.99, 0.01], (1050, 1)), RULES, cfg(harvest=True))
    assert (r.units[1:, 3] == r.units[1, 3]).all()


def test_no_harvest_when_less_than_the_minimum_is_left_of_the_exemption():
    days, p, w = harvest_case()
    h = int(np.flatnonzero(sim.harvest_days(days, 5))[1])
    small = sim.simulate(p, w, RULES, cfg(harvest=True, harvest_share=0.95, harvest_min=96_000))
    assert small.units[h, 0] == small.units[h - 1, 0]
    big = sim.simulate(p, w, RULES, cfg(harvest=True, harvest_share=0.95, harvest_min=94_000))
    assert big.units[h, 0] < big.units[h - 1, 0]
