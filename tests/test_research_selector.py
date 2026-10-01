from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

from engine.rules import Rules
from research import selector as S, sim, strategies as st
from research.panel import ASSETS, Panel

RULES = Rules.load(Path(__file__).resolve().parents[1] / "rules")


def weekdays(start, n):
    d, out = start, []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def days_array(start, n):
    return np.array(weekdays(start, n), dtype="datetime64[D]")


def idx(dates, iso):
    return int(np.flatnonzero(dates == np.datetime64(iso))[0])


def test_the_cut_is_the_first_trading_day_of_april_even_when_the_first_is_a_weekend():
    dates = days_array(date(2012, 1, 2), 900)                                        # to 2015-06
    cuts = S.cut_days(dates, first="2012-01-01")
    assert [str(dates[c]) for c in cuts] == ["2012-04-02", "2013-04-01", "2014-04-01", "2015-04-01"]       # 2012-04-01 is a Sunday


def test_cuts_start_at_the_first_date_given_and_a_year_without_a_prior_day_has_none():
    dates = days_array(date(2012, 1, 2), 900)
    assert [str(dates[c]) for c in S.cut_days(dates, first="2013-04-01")] == ["2013-04-01", "2014-04-01", "2015-04-01"]
    late = days_array(date(2013, 4, 10), 600)                                          # starts inside April: the first trading day of that April is not in the panel
    assert [str(late[c])[:4] for c in S.cut_days(late, first="2013-01-01")] == ["2014", "2015"]
    after = days_array(date(2013, 6, 3), 300)
    assert S.cut_days(after, first="2013-01-01") == [idx(after, "2014-04-01")]


def run_of(id_, equity, drawdown, tax, family="S2", cap=0.2):
    return S.Run(id=id_, family=family, cap=cap, equity=np.asarray(equity, dtype=float), drawdown=np.asarray(drawdown, dtype=float), tax_by_fy=dict(tax), pending_tax=0.0)


def test_prefix_statistics_use_only_the_days_before_the_cut_and_take_the_tax_of_the_year_that_just_ended_off_the_wealth():
    dates = days_array(date(2010, 4, 1), 800)
    c = idx(dates, "2013-04-01")
    n = len(dates)
    smooth = 1_000_000 * 1.10 ** (np.arange(n) / 252)
    dd = np.zeros(n)
    dd[100] = 0.08                                                                    # inside the window
    dd[c - 1] = 0.09                                                                  # the last day before the cut counts
    dd[c] = 0.40                                                                      # the cut day itself and after: must not count
    dd[c + 5] = 0.50
    a = run_of("a", smooth, dd, {2012: 20_000.0})
    b = run_of("b", smooth * 0.5, np.zeros(n), {})
    st_ = S.prefix_stats([a, b], dates, c, 1_000_000.0)
    years = (dates[c - 1] - dates[0]).astype(int) / 365.25
    assert st_.wealth[0] == pytest.approx(smooth[c - 1] - 20_000.0) and st_.wealth[1] == pytest.approx(smooth[c - 1] * 0.5)
    assert st_.growth[0] == pytest.approx(np.log((smooth[c - 1] - 20_000.0) / 1_000_000.0) / years)
    assert st_.growth[1] < 0 < st_.growth[0]
    assert st_.maxdd[0] == pytest.approx(0.09) and st_.maxdd[1] == 0.0


def test_a_run_whose_wealth_is_not_positive_at_the_cut_has_no_growth():
    dates = days_array(date(2010, 4, 1), 800)
    c = idx(dates, "2013-04-01")
    broke = run_of("x", np.full(len(dates), 10_000.0), np.zeros(len(dates)), {2012: 50_000.0})
    assert np.isnan(S.prefix_stats([broke], dates, c, 1_000_000.0).growth[0])


def test_a_cut_inside_a_financial_year_is_refused_because_the_tax_of_the_year_is_not_yet_known():
    dates = days_array(date(2010, 4, 1), 800)
    r = run_of("a", np.full(len(dates), 1e6), np.zeros(len(dates)), {})
    with pytest.raises(ValueError, match="financial year"):
        S.prefix_stats([r], dates, idx(dates, "2012-09-03"), 1e6)


def test_a_run_is_made_from_a_simulation_result_without_copying_what_it_does_not_need():
    days = weekdays(date(2016, 6, 1), 60)
    close = np.full((60, 4), 100.0)
    nan = np.full(60, np.nan)
    p = Panel(dates=np.array(days, dtype="datetime64[D]"), assets=list(ASSETS), open=close, high=close, low=close, close=close, value=np.full((60, 4), 1e9), vwap=close,
              cash=np.ones(60), nifty=close[:, 0], vix=nan, pe=nan, pb=nan)
    r = sim.simulate(p, np.tile([1.0, 0, 0, 0, 0], (60, 1)), RULES, sim.SimConfig(governor=False))
    run = S.run_of_result("t", "S1", 0.2, r)
    assert run.id == "t" and run.family == "S1" and run.cap == 0.2
    assert np.array_equal(run.equity, r.equity) and np.array_equal(run.drawdown, r.drawdown) and run.tax_by_fy == r.tax_by_fy and run.pending_tax == r.pending_tax
    assert not hasattr(run, "units")


# ---- the pick rule -------------------------------------------------------------------------------------------------------------------------------------------

CAPITAL = 1_000_000.0


def path_run(id_, daily, cap=0.2, family="S2"):
    eq = CAPITAL * np.exp(np.cumsum(np.r_[0.0, np.asarray(daily, dtype=float)]))
    dd = 1 - eq / np.maximum.accumulate(eq)
    return S.Run(id=id_, family=family, cap=cap, equity=eq, drawdown=dd, tax_by_fy={}, pending_tax=0.0)


def field(n=800, seed=3):
    """A calendar, its April 2013 cut, and S0's daily log changes."""
    dates = days_array(date(2010, 4, 1), n)
    rng = np.random.default_rng(seed)
    return dates, idx(dates, "2013-04-01"), rng.normal(0.0002, 0.005, n - 1)


def decide(runs, dates, c, cap=0.2, margin=1.0):
    stats = S.prefix_stats(runs, dates, c, CAPITAL)
    s0 = [i for i, r in enumerate(runs) if r.family == "S0"][0]
    return S.pick(runs, stats, dates, c, cap, s0, margin)


def test_a_clear_winner_among_the_eligible_is_picked_over_s0():
    dates, c, base = field()
    rng = np.random.default_rng(4)
    runs = [path_run("s0", base, family="S0"), path_run("a", base + 0.0004 + rng.normal(0, 0.0003, len(base))), path_run("c", base + rng.normal(0, 0.004, len(base)))]
    i, log = decide(runs, dates, c)
    assert runs[i].id == "a" and log["decision"] == "picked" and log["best"] == "a" and log["diff"] > 0.05 and log["diff"] > log["se"] > 0 and log["eligible"] == 3
    assert log["cut"] == "2013-04-01" and log["s0"] == "s0"


def test_a_run_with_a_better_growth_but_a_drawdown_above_the_cap_is_not_eligible():
    dates, c, base = field()
    crash = base + 0.0006
    crash[300:310] -= 0.03                                                          # a 30% fall in two weeks
    runs = [path_run("s0", base, family="S0"), path_run("risky", crash)]
    stats = S.prefix_stats(runs, dates, c, CAPITAL)
    assert stats.growth[1] > stats.growth[0] and stats.maxdd[1] > 0.2
    i, log = decide(runs, dates, c, cap=0.2)
    assert runs[i].id == "s0" and log["eligible"] == 1 and log["decision"] == "S0"


def test_a_small_noisy_edge_is_not_enough_and_s0_stays_whatever_the_margin_says():
    dates, c, base = field()
    rng = np.random.default_rng(9)
    noisy = base + 0.00003 + rng.normal(0, 0.004, len(base))
    runs = [path_run("s0", base, family="S0"), path_run("noisy", noisy)]
    stats = S.prefix_stats(runs, dates, c, CAPITAL)
    assert stats.growth[1] > stats.growth[0] - 0.02                                 # it looks about as good ...
    i, log = decide(runs, dates, c)
    assert runs[i].id == "s0" and log["decision"] == "S0" and "standard error" in log["reason"]
    assert decide(runs, dates, c, margin=0.0)[1]["best"] in ("noisy", "s0")        # with no margin the comparison is just the sign


def test_the_margin_scales_the_bar_the_edge_has_to_clear():
    dates, c, base = field()
    rng = np.random.default_rng(5)
    edge = base + 0.00015 + rng.normal(0, 0.002, len(base))
    runs = [path_run("s0", base, family="S0"), path_run("edge", edge)]
    _, log = decide(runs, dates, c)
    ratio = log["diff"] / log["se"]
    assert ratio > 0
    assert decide(runs, dates, c, margin=ratio * 0.9)[1]["decision"] == "picked" and decide(runs, dates, c, margin=ratio * 1.1)[1]["decision"] == "S0"


def test_when_nothing_is_eligible_s0_stays_and_the_log_says_why():
    dates, c, base = field()
    runs = [path_run("s0", base, family="S0"), path_run("a", base + 0.0005)]
    i, log = decide(runs, dates, c, cap=0.001)
    assert runs[i].id == "s0" and log["eligible"] == 0 and log["best"] == "" and "eligible" in log["reason"]


def test_s0_stays_when_it_is_itself_the_best_eligible_and_its_own_drawdown_is_logged():
    dates, c, base = field()
    runs = [path_run("s0", base + 0.0005, family="S0"), path_run("a", base)]
    i, log = decide(runs, dates, c)
    assert runs[i].id == "s0" and log["best"] == "s0" and log["decision"] == "S0" and log["s0_maxdd"] == pytest.approx(runs[0].drawdown[:c].max())
    assert log["reason"] == "S0 is the best eligible strategy" and np.isnan(log["diff"])


def test_s0_is_the_default_even_when_its_own_drawdown_is_above_the_cap():
    dates, c, base = field()
    s0 = base.copy()
    s0[300:310] -= 0.03
    runs = [path_run("s0", s0, family="S0"), path_run("calm", base * 0.3)]
    i, log = decide(runs, dates, c, cap=0.2)
    assert runs[i].id == "s0" and log["s0_eligible"] is False and log["eligible"] == 1


def test_two_runs_with_the_same_growth_go_to_the_first_in_the_ledger_order():
    dates, c, base = field()
    rng = np.random.default_rng(4)
    better = base + 0.0004 + rng.normal(0, 0.0003, len(base))
    runs = [path_run("s0", base, family="S0"), path_run("first", better), path_run("second", better)]
    assert decide(runs, dates, c)[1]["best"] == "first"


def test_the_bootstrap_standard_error_of_independent_differences_is_close_to_sigma_over_root_n_annualised():
    rng = np.random.default_rng(8)
    n = 750
    a = CAPITAL * np.exp(np.cumsum(np.r_[0.0, rng.normal(0.0004, 0.004, n)]))
    b = CAPITAL * np.exp(np.cumsum(np.r_[0.0, rng.normal(0.0001, 0.004, n)]))
    mean, se = S.paired_se(a, b, seed=1)
    d = np.diff(np.log(a)) - np.diff(np.log(b))
    assert mean == pytest.approx(d.mean() * 252)
    assert se == pytest.approx(d.std(ddof=1) / np.sqrt(n) * 252, rel=0.15)
    assert S.paired_se(a, b, seed=1) == (mean, se) and S.paired_se(a, b, seed=2)[1] != se


def test_the_bootstrap_keeps_serial_dependence_a_trending_difference_has_a_larger_error_than_independent_draws_of_the_same_size():
    rng = np.random.default_rng(2)
    n = 1500
    trend = np.sin(np.arange(n) / 60.0) * 0.003                                       # slow swings: positive then negative for months
    a = CAPITAL * np.exp(np.cumsum(np.r_[0.0, trend + rng.normal(0, 0.001, n)]))
    b = np.full(n + 1, CAPITAL)
    _, se = S.paired_se(a, b, seed=1)
    d = np.diff(np.log(a))
    assert se > 2 * d.std(ddof=1) / np.sqrt(n) * 252


def test_a_path_that_is_not_positive_is_refused():
    with pytest.raises(ValueError, match="positive"):
        S.paired_se(np.array([1.0, 2.0, 0.0]), np.array([1.0, 1.0, 1.0]), seed=1)


def test_nothing_after_the_cut_can_change_the_pick_or_its_log():
    dates, c, base = field()
    rng = np.random.default_rng(4)
    runs = [path_run("s0", base, family="S0"), path_run("a", base + 0.0004 + rng.normal(0, 0.0003, len(base))), path_run("b", base + 0.0001 + rng.normal(0, 0.001, len(base)))]
    i1, log1 = decide(runs, dates, c)
    changed = []
    for r in runs:
        eq, dd = r.equity.copy(), r.drawdown.copy()
        eq[c:] = eq[c:] * rng.uniform(0.2, 5.0, len(eq) - c)
        dd[c:] = rng.uniform(0, 0.9, len(dd) - c)
        changed.append(S.Run(r.id, r.family, r.cap, eq, dd, dict(r.tax_by_fy), r.pending_tax))
    i2, log2 = decide(changed, dates, c)
    assert i1 == i2 and log1 == log2


def test_a_run_with_a_drawdown_exactly_at_the_cap_is_eligible():
    dates, c, base = field()
    runs = [path_run("s0", base, family="S0"), path_run("a", base + 0.0004)]
    stats = S.prefix_stats(runs, dates, c, CAPITAL)
    at_cap = S.Stats(stats.wealth, stats.growth, np.array([0.2, 0.2]))
    i, log = S.pick(runs, at_cap, dates, c, 0.2, 0, 1.0)
    assert log["eligible"] == 2 and log["best"] == "a" and log["s0_eligible"] is True
    over = S.Stats(stats.wealth, stats.growth, np.array([0.2 + 1e-9, 0.2 + 1e-9]))
    assert S.pick(runs, over, dates, c, 0.2, 0, 1.0)[1]["eligible"] == 0 and S.pick(runs, over, dates, c, 0.2, 0, 1.0)[1]["s0_eligible"] is False


def test_a_run_with_no_growth_is_never_eligible_however_small_its_drawdown():
    dates, c, base = field()
    runs = [path_run("s0", base, family="S0"), path_run("broke", base + 0.0004)]
    stats = S.prefix_stats(runs, dates, c, CAPITAL)
    nan_growth = S.Stats(stats.wealth, np.array([stats.growth[0], np.nan]), np.array([0.1, 0.01]))
    i, log = S.pick(runs, nan_growth, dates, c, 0.2, 0, 1.0)
    assert log["eligible"] == 1 and runs[i].id == "s0"


def test_a_copy_of_s0_listed_before_it_does_not_beat_it_because_an_equal_edge_is_not_more_than_the_margin():
    dates, c, base = field()
    runs = [path_run("copy", base), path_run("s0", base, family="S0")]
    i, log = decide(runs, dates, c)
    assert runs[i].id == "s0" and log["best"] == "copy" and log["diff"] == 0.0 and log["se"] == 0.0 and log["decision"] == "S0"


def test_the_log_carries_the_growth_of_s0_at_the_capital_given():
    dates, c, base = field()
    runs = [path_run("s0", base, family="S0"), path_run("a", base + 0.0004)]
    sel = S.walk_forward(runs, lambda i: np.tile([0, 0, 0, 0, 1.0], (len(dates), 1)), dates, cap=0.2, margin=1.0, capital=CAPITAL)
    assert sel.log.s0_growth.iloc[0] == pytest.approx(S.prefix_stats(runs, dates, c, CAPITAL).growth[0])
    sel2 = S.walk_forward(runs, lambda i: np.tile([0, 0, 0, 0, 1.0], (len(dates), 1)), dates, cap=0.2, margin=1.0, capital=CAPITAL / 2)
    assert sel2.log.s0_growth.iloc[0] > sel.log.s0_growth.iloc[0]


# ---- walk forward and stitching -----------------------------------------------------------------------------------------------------------------------------

def vector_weights(table):
    """weights_of for runs whose weights are one constant vector each."""
    return lambda i: np.tile(table[i], (N_DAYS, 1))


N_DAYS = 1150


def three_runs():
    dates = days_array(date(2010, 4, 1), N_DAYS)
    c1, c2 = idx(dates, "2013-04-01"), idx(dates, "2014-04-01")
    rng = np.random.default_rng(6)
    base = rng.normal(0.0002, 0.005, N_DAYS - 1)
    a = base + 0.0004 + rng.normal(0, 0.0003, N_DAYS - 1)                           # clearly the best at the first cut
    a[c1 + 20:c1 + 60] -= 0.012                                                       # then a crash in the first year: above the cap at the second cut
    b = base + 0.0002 + rng.normal(0, 0.0003, N_DAYS - 1)                             # a smaller but clear edge, calm
    runs = [path_run("s0", base, family="S0"), path_run("a", a, family="S1"), path_run("b", b, family="S3")]
    table = [np.array([0, 0, 0, 0, 1.0]), np.array([1.0, 0, 0, 0, 0]), np.array([0, 0.5, 0.5, 0, 0])]
    return dates, runs, vector_weights(table), c1, c2


def test_the_stitched_weights_are_the_picked_runs_inside_each_financial_year_and_s0s_before_the_first_cut():
    dates, runs, weights_of, c1, c2 = three_runs()
    sel = S.walk_forward(runs, weights_of, dates, cap=0.2, margin=1.0, capital=CAPITAL)
    assert list(sel.log.cut) == ["2013-04-01", "2014-04-01"] and list(sel.log.picked) == ["a", "b"] and list(sel.log.family) == ["S1", "S3"]
    w = sel.weights
    assert w.shape == (N_DAYS, 5) and np.allclose(w.sum(axis=1), 1.0) and (w >= 0).all()
    assert np.allclose(w[:c1], [0, 0, 0, 0, 1]) and np.allclose(w[c1:c2], [1, 0, 0, 0, 0]) and np.allclose(w[c2:], [0, 0.5, 0.5, 0, 0])
    assert (sel.holder[:c1] == 0).all() and (sel.holder[c1:c2] == 1).all() and (sel.holder[c2:] == 2).all() and sel.first_cut == c1


def test_before_the_first_cut_the_weights_are_those_of_s0_wherever_it_sits_in_the_list_and_the_margin_given_is_the_one_used():
    dates, runs, weights_of, c1, c2 = three_runs()
    order = [1, 0, 2]                                                                 # S0 second
    shuffled = [runs[i] for i in order]
    sel = S.walk_forward(shuffled, lambda i: weights_of(order[i]), dates, cap=0.2, margin=1.0, capital=CAPITAL)
    assert np.allclose(sel.weights[:c1], [0, 0, 0, 0, 1]) and (sel.holder[:c1] == 1).all() and list(sel.log.picked) == ["a", "b"]
    never = S.walk_forward(runs, weights_of, dates, cap=0.2, margin=1e9, capital=CAPITAL)
    assert list(never.log.picked) == ["s0", "s0"] and (never.log.margin == 1e9).all()


def test_the_second_cut_drops_the_run_that_crashed_in_the_year_between():
    dates, runs, weights_of, c1, c2 = three_runs()
    sel = S.walk_forward(runs, weights_of, dates, cap=0.2, margin=1.0, capital=CAPITAL)
    second = sel.log.iloc[1]
    assert second.eligible == 2 and second.best == "b" and second.decision == "picked"                    # s0 and b are eligible; a's drawdown is above the cap


def test_every_logged_pick_is_unchanged_when_the_data_after_its_cut_is_cut_away():
    dates, runs, weights_of, c1, c2 = three_runs()
    full = S.walk_forward(runs, weights_of, dates, cap=0.2, margin=1.0, capital=CAPITAL)
    for k, c in enumerate((c1, c2)):
        cutruns = [S.Run(r.id, r.family, r.cap, r.equity[:c + 1], r.drawdown[:c + 1], dict(r.tax_by_fy), r.pending_tax) for r in runs]
        part = S.walk_forward(cutruns, lambda i: weights_of(i)[:c + 1], dates[:c + 1], cap=0.2, margin=1.0, capital=CAPITAL)
        assert part.log.iloc[:k + 1].reset_index(drop=True).equals(full.log.iloc[:k + 1].reset_index(drop=True))


def test_there_must_be_exactly_one_s0_among_the_runs():
    dates, runs, weights_of, c1, c2 = three_runs()
    with pytest.raises(ValueError, match="one S0"):
        S.walk_forward(runs[1:], weights_of, dates, cap=0.2, margin=1.0, capital=CAPITAL)
    with pytest.raises(ValueError, match="one S0"):
        S.walk_forward(runs + [path_run("s0b", np.zeros(N_DAYS - 1), family="S0")], weights_of, dates, cap=0.2, margin=1.0, capital=CAPITAL)


def test_a_panel_with_no_cut_gives_s0_all_the_way_and_an_empty_log():
    dates = days_array(date(2010, 4, 1), 300)
    rng = np.random.default_rng(1)
    runs = [path_run("s0", rng.normal(0, 0.005, 299), family="S0"), path_run("a", rng.normal(0, 0.005, 299))]
    sel = S.walk_forward(runs, lambda i: np.tile([[0, 0, 0, 0, 1.0], [1.0, 0, 0, 0, 0]][i], (300, 1)), dates, cap=0.2, margin=1.0, capital=CAPITAL)
    assert len(sel.log) == 0 and np.allclose(sel.weights, [0, 0, 0, 0, 1]) and sel.first_cut is None


def small_world(n=1000, vol=0.01, crash_at=None):
    days = weekdays(date(2010, 4, 1), n)
    rng = np.random.default_rng(11)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0003, vol, (n, 4)), axis=0))
    if crash_at is not None:                                                            # a 30% fall in 20 days after a calm climb
        close = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.003, (n, 4)), axis=0))
        fall = np.r_[np.linspace(1.0, 0.7, 20), np.full(n - crash_at - 20, 0.7)]
        close[crash_at:] *= fall[:, None]
    nan = np.full(n, np.nan)
    return Panel(dates=np.array(days, dtype="datetime64[D]"), assets=list(ASSETS), open=close, high=close * 1.01, low=close * 0.99, close=close, value=np.full((n, 4), 1e9), vwap=close,
                 cash=(1.0002) ** np.arange(n), nifty=close[:, 0], vix=nan, pe=nan, pb=nan)


def test_candidates_are_the_trials_that_apply_at_this_cap_and_weights_of_rebuilds_a_runs_weights():
    p = small_world()
    trials = [t for t in st.trials(s1_steps=2) if t.family == "S0" or (t.family == "S4" and t.params["lookback"] == 20 and t.band == 0.05 and t.params["target"] == 0.12)]
    runs, weights_of = S.candidates(p, RULES, trials, cap=0.3)
    assert [r.id for r in runs] == [t.id for t in trials if t.cap in (None, 0.3)] and sum(r.family == "S0" for r in runs) == 1 and runs[0].id.startswith("S0|cap=0.3")
    s4 = [i for i, r in enumerate(runs) if r.family == "S4"][0]
    assert np.array_equal(weights_of(s4), [t for t in trials if t.family == "S4"][0].fn(p))
    direct = sim.simulate(p, weights_of(s4), RULES, sim.SimConfig(cap=0.3, band=0.05))
    assert np.array_equal(runs[s4].equity, direct.equity) and runs[s4].cap == 0.3


def test_the_stitched_account_is_a_fresh_account_from_the_first_cut_with_the_governor_and_equals_s0_alone_when_s0_is_always_held():
    p = small_world(crash_at=850)                                                       # S0 is fully in the Nifty ETF when it falls 30%: the governor acts
    trials = [t for t in st.trials(s1_steps=2) if t.family == "S0"]
    runs, weights_of = S.candidates(p, RULES, trials, cap=0.3)
    sel = S.walk_forward(runs, weights_of, p.dates, cap=0.3, margin=1e9, capital=2_000_000.0)             # an impossible margin: S0 every time
    assert len(sel.log) > 0 and (sel.log.picked == runs[0].id).all()
    acct = S.stitched_account(p, sel, RULES, cap=0.3, capital=2_000_000.0)
    assert acct.dates[0] == p.dates[sel.first_cut] and acct.equity[0] == pytest.approx(2_000_000.0)
    assert acct.multiplier.min() < 1.0                                                  # the governor cut exposure at some point
    alone = sim.simulate(pn_from(p, sel.first_cut), weights_of(0)[sel.first_cut:], RULES, sim.SimConfig(cap=0.3, capital=2_000_000.0))
    assert np.array_equal(acct.equity, alone.equity)


def pn_from(p, i0):
    from research import panel as pn
    return pn.from_day(p, i0)


def test_the_references_start_fresh_on_the_same_day_with_the_same_capital():
    p = small_world()
    trials = [t for t in st.trials(s1_steps=2) if t.family == "S0"]
    runs, weights_of = S.candidates(p, RULES, trials, cap=0.2)
    sel = S.walk_forward(runs, weights_of, p.dates, cap=0.2, margin=1e9, capital=1_000_000.0)
    refs = S.references(p, sel, weights_of(0), RULES, cap=0.2, capital=1_000_000.0)
    assert list(refs) == ["S0", "Nifty BeES", "Junior BeES", "Bank BeES", "Gold BeES", "Liquid fund"]
    for r in refs.values():
        assert r.dates[0] == p.dates[sel.first_cut] and r.equity[0] == pytest.approx(1_000_000.0, rel=2e-3)
    assert np.array_equal(refs["S0"].equity, S.stitched_account(p, sel, RULES, cap=0.2, capital=1_000_000.0).equity)
    window = pn_from(p, sel.first_cut)
    hold = sim.simulate(window, st.s1_static([1, 0, 0, 0, 0], "never")(window), RULES, sim.SimConfig(governor=False, capital=1_000_000.0))
    assert np.array_equal(refs["Nifty BeES"].equity, hold.equity)                                    # bought on the first day, held, no governor


# ---- a candidate that may be picked only from a given date --------------------------------------------------------------------------------------------------

def test_a_run_is_not_eligible_before_its_eligible_from_date_and_is_from_that_cut_on():
    dates, c, base = field()
    rng = np.random.default_rng(4)
    late = path_run("late", base + 0.0004 + rng.normal(0, 0.0003, len(base)))
    runs = [path_run("s0", base, family="S0"), S.Run(late.id, late.family, late.cap, late.equity, late.drawdown, {}, 0.0, eligible_from="2013-04-02")]
    i, log = decide(runs, dates, c)
    assert runs[i].id == "s0" and log["eligible"] == 1 and log["best"] == "s0"
    on_time = [runs[0], S.Run(late.id, late.family, late.cap, late.equity, late.drawdown, {}, 0.0, eligible_from="2013-04-01")]
    i, log = decide(on_time, dates, c)
    assert on_time[i].id == "late" and log["eligible"] == 2


def test_candidates_carry_a_trials_eligible_from_date_into_its_run():
    from dataclasses import replace
    p = small_world()
    trials = [t for t in st.trials(s1_steps=2) if t.family == "S0" or (t.family == "S4" and t.params["lookback"] == 20 and t.band == 0.05 and t.params["target"] == 0.12)]
    trials = [replace(t, eligible_from="2016-04-01") if t.family == "S4" else t for t in trials]
    runs, _ = S.candidates(p, RULES, trials, cap=0.2)
    assert [r.eligible_from for r in runs] == [None, "2016-04-01"]


def test_the_execution_settings_reach_the_candidates_the_stitched_account_and_s0_but_not_the_reference_holdings():
    p = small_world(n=1300)
    trials = [t for t in st.trials(s1_steps=2) if t.family == "S0"]
    runs, weights_of = S.candidates(p, RULES, trials, cap=0.3, sim_kw={"harvest": True})
    direct = sim.simulate(p, weights_of(0), RULES, sim.SimConfig(cap=0.3, harvest=True))
    assert np.array_equal(runs[0].equity, direct.equity)
    sel = S.walk_forward(runs, weights_of, p.dates, cap=0.3, margin=1e9, capital=1_000_000.0)
    acct = S.stitched_account(p, sel, RULES, cap=0.3, sim_kw={"harvest": True})
    assert np.array_equal(acct.equity, sim.simulate(pn_from(p, sel.first_cut), weights_of(0)[sel.first_cut:], RULES, sim.SimConfig(cap=0.3, harvest=True)).equity)
    later = S.cut_days(p.dates)[1]
    acct2 = S.stitched_account(p, sel, RULES, cap=0.3, sim_kw={"harvest": True}, start=later)
    assert acct2.dates[0] == p.dates[later]
    refs = S.references(p, sel, weights_of(0), RULES, cap=0.3, sim_kw={"harvest": True}, start=later)
    assert np.array_equal(refs["S0"].equity, acct2.equity) and refs["Nifty BeES"].dates[0] == p.dates[later]
    window = pn_from(p, later)
    plain = sim.simulate(window, st.s1_static([1, 0, 0, 0, 0], "never")(window), RULES, sim.SimConfig(governor=False))
    assert np.array_equal(refs["Nifty BeES"].equity, plain.equity)
