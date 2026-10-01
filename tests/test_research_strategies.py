from collections import Counter

import numpy as np
import pytest

from research import causal, strategies as st
from research.panel import ASSETS, Panel


def panel_from(close, value=None, cash_rate=0.0002, dates_start="2012-01-02"):
    close = np.asarray(close, dtype=float)
    if close.ndim == 1:
        close = np.tile(close[:, None], (1, 4))
    T = len(close)
    dates = np.arange(np.datetime64(dates_start), np.datetime64(dates_start) + T, dtype="datetime64[D]")
    nan = np.full(T, np.nan)
    return Panel(dates=dates, assets=list(ASSETS), open=close, high=close * 1.01, low=close * 0.99, close=close, value=np.full((T, 4), 1e8 if value is None else value),
                 vwap=close, cash=np.cumprod(np.full(T, 1 + cash_rate)), nifty=close[:, 0], vix=nan, pe=nan, pb=nan)


def walk(T=700, seed=1, drift=0.0005, vol=0.01, assets=4):
    rng = np.random.default_rng(seed)
    return 100 * np.exp(np.cumsum(rng.normal(drift, vol, (T, assets)), axis=0))


def check_valid(w, T):
    assert w.shape == (T, 5) and np.isfinite(w).all() and (w >= -1e-12).all() and np.allclose(w.sum(axis=1), 1.0, atol=1e-9)


def first_days(p, months=None):
    """Indices of day 0 and of the first day of each calendar month (of the listed months, if given)."""
    m = [str(d)[:7] for d in p.dates]
    return [i for i in range(len(m)) if (i == 0 or m[i] != m[i - 1]) and (months is None or int(m[i][5:]) in months)]


def fresh_days(p, w):
    """The days whose weights are not just yesterday's weights drifted with the day's price changes: the days a target was set."""
    out = []
    for i in range(1, len(w)):
        x = w[i - 1] * np.r_[p.close[i] / p.close[i - 1], p.cash[i] / p.cash[i - 1]]
        if not np.allclose(w[i], x / x.sum()):
            out.append(i)
    return out


MIX = [0.4, 0.2, 0.1, 0.1, 0.2]
ALL = [
    ("s0", lambda: st.s0_plain(cap=0.2)),
    ("s1 band", lambda: st.s1_static(MIX)),
    ("s1 year", lambda: st.s1_static(MIX, rebalance="year")),
    ("s1 never", lambda: st.s1_static(MIX, rebalance="never")),
    ("s2 equal", lambda: st.s2_trend(length=50, weighting="equal")),
    ("s2 invvol", lambda: st.s2_trend(length=100, weighting="invvol")),
    ("s3 monthly", lambda: st.s3_momentum(lookback=63, k=2, every="month")),
    ("s3 quarterly", lambda: st.s3_momentum(lookback=126, k=1, every="quarter")),
    ("s4", lambda: st.s4_voltarget(target=0.10, lookback=21)),
    ("s5", lambda: st.s5_marketdd(start=0.05, end=0.20)),
]


@pytest.mark.parametrize("name,make", ALL)
def test_every_strategy_returns_valid_long_only_weights_one_row_per_day(name, make):
    p = panel_from(walk())
    check_valid(make()(p), 700)


@pytest.mark.parametrize("name,make", ALL)
def test_every_strategy_passes_the_causality_harness(name, make):
    p = panel_from(walk(T=500, seed=3))
    causal.assert_causal(make(), p, n_cuts=6, seed=2)


@pytest.mark.parametrize("make", [
    lambda: st.s1_static(MIX, rebalance="weekly"), lambda: st.s2_trend(50, "median"), lambda: st.s3_momentum(63, 2, "week"),
    lambda: st.s3_momentum(63, 0, "month"), lambda: st.s3_momentum(63, 5, "month"), lambda: st.s4_voltarget(0.0, 20),
    lambda: st.s5_marketdd(0.20, 0.05), lambda: st.s5_marketdd(0.10, 0.10), lambda: st.s5_marketdd(0.10, 1.5), lambda: st.s5_marketdd(-0.10, 0.20)])
def test_nonsense_parameters_are_refused_when_the_strategy_is_made(make):
    with pytest.raises(ValueError):
        make()


def test_s1_holds_the_target_as_a_constant_vector_and_the_grid_lists_every_mix_once():
    p = panel_from(walk(T=50))
    w = st.s1_static(MIX)(p)
    assert (w == np.array(MIX)).all()
    grid = st.s1_grid(4)                                          # steps of 25%
    assert len(grid) == 70 and all(abs(sum(g) - 1) < 1e-12 for g in grid) and len({tuple(g) for g in grid}) == 70
    assert [1.0, 0, 0, 0, 0] in [list(g) for g in grid] and [0, 0, 0, 0, 1.0] in [list(g) for g in grid]
    with pytest.raises(ValueError):
        st.s1_static([0.5, 0.5, 0.5, 0, 0])
    with pytest.raises(ValueError):
        st.s1_static([1.2, -0.2, 0, 0, 0])


def test_s1_never_rebalancing_buys_the_mix_on_the_first_day_and_lets_it_drift_with_the_prices_through_every_financial_year_start():
    n = 500
    close = np.column_stack([100 * 1.01 ** np.arange(n), np.full(n, 100.0), np.full(n, 100.0), np.full(n, 100.0)])
    p = panel_from(close, cash_rate=0.0)
    w = st.s1_static([0.5, 0, 0, 0, 0.5], rebalance="never")(p)
    g = 1.01 ** np.arange(n)
    assert np.allclose(w[:, 0], g / (g + 1)) and np.allclose(w[:, 4], 1 / (g + 1)) and np.allclose(w[:, 1:4], 0)
    assert np.allclose(w[0], [0.5, 0, 0, 0, 0.5])


def test_s1_yearly_goes_back_to_the_target_on_the_first_trading_day_of_each_financial_year_and_drifts_in_between():
    n = 500
    close = np.column_stack([100 * 1.01 ** np.arange(n), np.full(n, 100.0), np.full(n, 100.0), np.full(n, 100.0)])
    p = panel_from(close, cash_rate=0.0)
    w = st.s1_static([0.5, 0, 0, 0, 0.5], rebalance="year")(p)
    a1 = int(np.flatnonzero(p.dates == np.datetime64("2012-04-01"))[0])
    a2 = int(np.flatnonzero(p.dates == np.datetime64("2013-04-01"))[0])
    for i in (0, a1, a2):
        assert np.allclose(w[i], [0.5, 0, 0, 0, 0.5])
    assert w[a1 - 1, 0] > 0.6 and w[a2 - 1, 0] > 0.6                      # drifted away from 50% before each reset
    g = 1.01 ** (np.arange(n) - a1)
    assert np.allclose(w[a1:a2, 0], g[a1:a2] / (g[a1:a2] + 1))            # after a reset the drift starts over
    assert set(fresh_days(p, w)) == {a1, a2}


def test_s2_holds_an_asset_only_while_it_is_above_its_moving_average():
    up = 100 * 1.001 ** np.arange(400)
    down = 100 * 0.999 ** np.arange(400)
    close = np.column_stack([up, down, up, down])
    p = panel_from(close)
    w = st.s2_trend(length=50, weighting="equal")(p)
    assert np.allclose(w[-1], [0.25, 0, 0.25, 0, 0.5])                   # two of four slots in trend: a quarter each, the rest in cash
    assert np.allclose(w[:49, :4], 0) and np.allclose(w[:49, 4], 1)       # no average yet: cash
    iv = st.s2_trend(length=50, weighting="invvol")(p)
    assert iv[-1, 1] == 0 and iv[-1, 3] == 0 and iv[-1, 4] == pytest.approx(0, abs=1e-12) and iv[-1, 0] + iv[-1, 2] == pytest.approx(1)


def test_s2_with_no_asset_in_trend_is_all_cash_in_both_weightings_and_an_asset_exactly_at_its_average_is_not_in_trend():
    for close in (100 * 0.998 ** np.arange(300), np.full(300, 100.0)):
        p = panel_from(close)
        for weighting in ("equal", "invvol"):
            w = st.s2_trend(length=100, weighting=weighting)(p)
            assert np.allclose(w[-1], [0, 0, 0, 0, 1])


def test_s2_inverse_volatility_gives_a_price_with_no_volatility_a_finite_weight():
    n = 400
    step = np.concatenate([np.full(300, 100.0), np.full(100, 150.0)])        # above its 200 day average, and flat for the last 100 days
    down = 100 * 0.999 ** np.arange(n)
    p = panel_from(np.column_stack([step, down, down, down]))
    w = st.s2_trend(length=200, weighting="invvol")(p)
    assert np.allclose(w[-1], [1, 0, 0, 0, 0])


def test_s2_inverse_volatility_gives_the_calmer_trending_asset_the_bigger_weight_and_waits_for_a_volatility_estimate():
    rng = np.random.default_rng(5)
    n = 400
    calm = 100 * np.exp(np.cumsum(np.full(n, 0.0008) + rng.normal(0, 0.002, n)))
    wild = 100 * np.exp(np.cumsum(np.full(n, 0.0008) + rng.normal(0, 0.012, n)))
    p = panel_from(np.column_stack([calm, wild, calm * 0 + 50, calm * 0 + 50]))
    w = st.s2_trend(length=50, weighting="invvol")(p)
    assert w[-1, 0] > w[-1, 1] > 0
    assert np.allclose(w[:st.VOL_DAYS, 4], 1)                              # the average exists from day 50 but the volatility only from day 63: cash until then


def test_s3_picks_the_top_k_by_past_return_on_the_first_trading_day_of_the_month():
    n = 300
    t = np.arange(n)
    close = np.column_stack([100 * 1.0000 ** t, 100 * 1.002 ** t, 100 * 1.001 ** t, 100 * 0.999 ** t])
    p = panel_from(close)
    w = st.s3_momentum(lookback=63, k=2, every="month")(p)
    assert np.allclose(w[first_days(p)[-1]], [0, 0.5, 0.5, 0, 0])            # the two fastest risers; the flat and the falling one are out
    assert np.allclose(w[:63, 4], 1)                                       # no 63 day return yet: cash
    w3 = st.s3_momentum(lookback=63, k=3, every="month")(p)
    assert np.allclose(w3[first_days(p)[-1]], [0, 1 / 3, 1 / 3, 0, 1 / 3])  # a return of exactly zero is not above zero: the flat asset's slot stays in cash


def test_s3_leaves_the_slots_of_assets_with_a_negative_past_return_in_cash():
    n = 200
    t = np.arange(n)
    close = np.column_stack([100 * 1.002 ** t, 100 * 0.998 ** t, 100 * 0.998 ** t, 100 * 0.997 ** t])
    p = panel_from(close)
    w = st.s3_momentum(lookback=63, k=3, every="month")(p)
    assert np.allclose(w[first_days(p)[-1]], [1 / 3, 0, 0, 0, 2 / 3])


def test_s3_looks_back_exactly_the_stated_number_of_days():
    n = 200
    i = first_days(panel_from(np.ones((n, 4))))[-1]                        # the last rebalance day, known from the dates alone
    t = np.arange(n)
    zero = np.where(t <= i - 64, 100.0, np.where(t == i - 63, 150.0, 200.0))        # 62 days back: 0%, 63: +33%, 64: +100%
    slow = 100 * 1.001 ** t                                                # about +6.5% over any of the three
    big = np.where(t <= i - 64, 50.0, 200.0)                               # 62 days back: 0%, 63: 0%, 64: +300%
    p = panel_from(np.column_stack([zero, slow, big, 100 * 0.99 ** t]))
    for lookback, winner in ((62, 1), (63, 0), (64, 2)):
        w = st.s3_momentum(lookback=lookback, k=1, every="month")(p)
        assert np.argmax(w[i]) == winner and w[i, winner] == 1.0


def test_s3_quarterly_on_data_that_starts_outside_a_rebalance_month_is_cash_until_the_first_one():
    p = panel_from(walk(T=300, seed=4), dates_start="2012-02-06")
    w = st.s3_momentum(lookback=63, k=2, every="quarter")(p)
    check_valid(w, 300)
    apr = int(np.flatnonzero(p.dates == np.datetime64("2012-04-01"))[0])
    assert np.allclose(w[:apr], [0, 0, 0, 0, 1])


def test_s3_trades_nothing_between_rebalance_days_so_its_weights_drift_with_prices():
    n = 300
    t = np.arange(n)
    close = np.column_stack([100 * 1.0000 ** t, 100 * 1.002 ** t, 100 * 1.001 ** t, 100 * 0.999 ** t])
    p = panel_from(close)
    w = st.s3_momentum(lookback=63, k=2, every="month")(p)
    i = first_days(p)[-1]
    j = i + 10
    x = w[i] * np.r_[close[j] / close[i], p.cash[j] / p.cash[i]]
    assert np.allclose(w[j], x / x.sum()) and not np.allclose(w[j], w[i])


def test_s3_sets_a_new_target_only_on_the_first_trading_day_of_a_month_and_of_a_quarter_when_quarterly():
    p = panel_from(walk(T=600, seed=8))
    monthly = fresh_days(p, st.s3_momentum(lookback=63, k=2, every="month")(p))
    quarterly = fresh_days(p, st.s3_momentum(lookback=63, k=2, every="quarter")(p))
    assert monthly and set(monthly) <= set(first_days(p))
    assert quarterly and set(quarterly) <= set(first_days(p, months=(1, 4, 7, 10)))
    assert len(quarterly) < len(monthly)


def test_s4_scales_the_nifty_etf_to_the_target_volatility_and_holds_the_rest_in_cash():
    rng = np.random.default_rng(6)
    n = 300
    r = rng.normal(0, 0.02, n)                                            # about 32% annual volatility
    nifty = 100 * np.exp(np.cumsum(r))
    p = panel_from(np.column_stack([nifty, walk(T=n, seed=7, vol=0.001, assets=3)]))                # the other ETFs are much calmer
    w = st.s4_voltarget(target=0.10, lookback=21)(p)
    t = 250
    realised = np.log(nifty[t - 20:t + 1] / nifty[t - 21:t]).std(ddof=1) * np.sqrt(252)
    assert w[t, 0] == pytest.approx(min(1.0, 0.10 / realised)) and w[t, 4] == pytest.approx(1 - w[t, 0]) and w[t, 1:4].sum() == 0
    assert w[0, 0] == 0 and w[0, 4] == 1                                   # no volatility yet: cash
    calm = st.s4_voltarget(target=0.50, lookback=21)(p)
    assert calm[t, 0] == pytest.approx(min(1.0, 0.50 / realised))
    assert w[t, 0] < 1.0 and calm[t, 0] <= 1.0                             # never more than fully invested: no leverage


def test_s4_a_flat_price_has_no_volatility_and_gets_the_full_share_without_dividing_by_zero():
    import warnings
    p = panel_from(np.full(100, 100.0))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        w = st.s4_voltarget(target=0.10, lookback=21)(p)
    assert w[-1, 0] == 1.0 and w[5, 0] == 0.0


def test_s5_scales_the_nifty_etf_down_linearly_as_the_market_falls_from_its_year_high():
    close = np.concatenate([np.linspace(100, 100, 260), np.linspace(100, 70, 60)])
    p = panel_from(close)
    w = st.s5_marketdd(start=0.05, end=0.20)(p)
    dd = 1 - close / np.maximum.accumulate(close)
    t = 290
    exp = float(np.clip((0.20 - dd[t]) / 0.15, 0, 1))
    assert w[t, 0] == pytest.approx(exp) and w[t, 4] == pytest.approx(1 - exp) and 0 < exp < 1
    assert w[259, 0] == 1.0                                                # no drawdown: fully invested
    assert w[-1, 0] == 0.0                                                 # 30% down: out


def test_s5_measures_the_fall_from_the_highest_close_of_the_last_252_days_not_of_all_history():
    close = np.concatenate([np.full(10, 100.0), [200.0], np.full(489, 100.0)])                 # the high is day 10
    p = panel_from(close)
    w = st.s5_marketdd(start=0.05, end=0.20)(p)
    assert w[10, 0] == 1.0 and w[11, 0] == 0.0                              # at the high; then 50% below it
    assert w[10 + 251, 0] == 0.0                                           # the window of 252 days still holds the high
    assert w[10 + 252, 0] == 1.0                                           # one day later the high is out: flat at 100 is no drawdown


def test_s0_holds_the_largest_nifty_share_whose_history_so_far_stayed_within_the_cap_and_never_more():
    p = panel_from(walk(T=900, seed=2, drift=0.0003, vol=0.012))
    shares = {cap: st.s0_plain(cap)(p)[-1, 0] for cap in (0.05, 0.10, 0.20, 0.30, 1.0)}
    assert list(shares.values()) == sorted(shares.values())              # a looser cap allows at least as much Nifty
    assert shares[1.0] == 1.0 and shares[0.05] < 1.0
    w = st.s0_plain(0.10)(p)
    assert np.allclose(w[:, 1:4], 0) and np.allclose(w[:, 0] + w[:, 4], 1)
    # the mix at that share, rebalanced daily, stayed inside the cap over the whole history
    e = w[-1, 0]
    nifty_r = p.close[1:, 0] / p.close[:-1, 0] - 1
    cash_r = p.cash[1:] / p.cash[:-1] - 1
    path = np.cumprod(1 + e * nifty_r + (1 - e) * cash_r)
    assert (1 - path / np.maximum.accumulate(path)).max() <= 0.10 + 1e-9
    # and the next step up in share would not have
    up = e + 0.05
    path = np.cumprod(1 + up * nifty_r + (1 - up) * cash_r)
    assert (1 - np.concatenate([[1.0], path]) / np.maximum.accumulate(np.concatenate([[1.0], path]))).max() > 0.10


def test_s0_only_ever_reduces_its_share_as_a_worse_drawdown_is_seen_once_it_has_a_years_history():
    p = panel_from(walk(T=900, seed=9, drift=0.0002, vol=0.014))
    e = st.s0_plain(0.10)(p)[:, 0]
    assert (np.diff(e[251:]) <= 1e-12).all() and e[251] > e[-1]


def test_s0_share_is_exactly_the_cap_divided_by_a_single_40_percent_fall():
    p = panel_from(np.concatenate([np.full(300, 100.0), np.full(100, 60.0)]), cash_rate=0.0)
    assert st.s0_plain(0.10)(p)[-1, 0] == pytest.approx(0.25)              # 25% of the money x 40% = 10%, right at the cap, and allowed
    assert st.s0_plain(0.099)(p)[-1, 0] == pytest.approx(0.20)             # a hair under: the next share down
    assert st.s0_plain(0.10)(p)[299, 0] == 1.0                             # before the fall there is no drawdown on record


def test_s0_holds_only_cash_until_a_years_history_exists():
    p = panel_from(walk(T=400))
    w = st.s0_plain(1.0, min_days=252)(p)
    assert np.allclose(w[:251], [0, 0, 0, 0, 1]) and w[251, 0] == 1.0


def test_the_trial_list_is_the_committed_grid_with_unique_ids_and_a_working_strategy_for_each_family():
    trials = st.trials(s1_steps=4)
    ids = [t.id for t in trials]
    assert len(ids) == len(set(ids))
    assert Counter(t.family for t in trials) == {"S0": 3, "S1": 140, "S2": 12, "S3": 18, "S4": 20, "S5": 12}
    assert {t.cap for t in trials if t.family == "S0"} == {0.10, 0.20, 0.30} and all(t.cap is None for t in trials if t.family != "S0")
    assert {t.band for t in trials} == {0.01, 0.05}
    by = {f: [t.params for t in trials if t.family == f] for f in ("S2", "S3", "S4", "S5")}
    assert {q["length"] for q in by["S2"]} == {50, 100, 200} and {q["weighting"] for q in by["S2"]} == {"equal", "invvol"}
    assert {q["lookback"] for q in by["S3"]} == {63, 126, 252} and {q["k"] for q in by["S3"]} == {1, 2, 3} and {q["every"] for q in by["S3"]} == {"month", "quarter"}
    assert {q["target"] for q in by["S4"]} == {0.06, 0.09, 0.12, 0.15, 0.18} and {q["lookback"] for q in by["S4"]} == {20, 60}
    assert {(q["start"], q["end"]) for q in by["S5"]} == {(a, b) for a in (0.05, 0.10, 0.15) for b in (0.25, 0.35)}
    assert {t.params["rebalance"] for t in trials if t.family == "S1"} == {"year", "never"}
    p = panel_from(walk(T=300))
    for t in trials[:: max(1, len(trials) // 15)]:
        check_valid(t.fn(p), 300)
    assert len(st.trials()) == 3 + 2002 + 12 + 18 + 20 + 12                # the 10% grid has 1001 mixes, each rebalanced yearly or never


def test_each_trial_runs_the_strategy_its_parameters_describe():
    factory = {"S0": st.s0_plain, "S1": st.s1_static, "S2": st.s2_trend, "S3": st.s3_momentum, "S4": st.s4_voltarget, "S5": st.s5_marketdd}
    p = panel_from(walk(T=400, seed=11))
    for n, t in enumerate(st.trials(s1_steps=4)):
        if t.family != "S1" or n % 9 == 0:
            assert np.array_equal(t.fn(p), factory[t.family](**t.params)(p)), t.id
