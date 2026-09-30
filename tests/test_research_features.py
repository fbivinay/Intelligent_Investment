import numpy as np
import pytest

from research import causal, features
from research.panel import ASSETS, Panel


def mini_panel(T=400, seed=1):
    rng = np.random.default_rng(seed)
    dates = np.arange(np.datetime64("2012-01-02"), np.datetime64("2012-01-02") + T, dtype="datetime64[D]")
    close = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.01, (T, 4)), axis=0))
    open_ = close * (1 + rng.normal(0, 0.002, (T, 4)))
    value = rng.uniform(1e6, 5e6, (T, 4))
    cash = np.cumprod(1 + np.full(T, 0.0002))
    nifty = 5000 * np.exp(np.cumsum(rng.normal(0.0004, 0.01, T)))
    vix = 15 + np.cumsum(rng.normal(0, 0.3, T))
    pe = np.where(np.arange(T) >= 100, 18 + np.cumsum(rng.normal(0, 0.1, T)), np.nan)
    pb = np.where(np.arange(T) >= 100, 2.8 + np.cumsum(rng.normal(0, 0.01, T)), np.nan)
    return Panel(dates=dates, assets=list(ASSETS), open=open_, high=close * 1.01, low=close * 0.99, close=close, value=value, vwap=close, cash=cash, nifty=nifty, vix=vix, pe=pe, pb=pb)


def test_returns_over_k_days_are_close_over_close_k_days_ago_and_nan_before_that():
    p = mini_panel()
    f = features.build(p)
    for k in (1, 5, 21, 63, 252):
        r = f[f"ret{k}"]
        assert r.shape == (400, 4)
        assert np.isnan(r[:k]).all() and np.isfinite(r[k:]).all()
        t = k + 7
        assert r[t, 2] == pytest.approx(p.close[t, 2] / p.close[t - k, 2] - 1)


def test_volatility_is_the_std_of_the_last_k_daily_log_returns_annualised():
    p = mini_panel()
    f = features.build(p)
    lr = np.diff(np.log(p.close), axis=0)
    for k in (21, 63):
        t = 100
        expect = lr[t - k:t, 1].std(ddof=1) * np.sqrt(252)            # returns of days t-k+1 .. t
        assert f[f"vol{k}"][t, 1] == pytest.approx(expect)
        assert np.isnan(f[f"vol{k}"][:k]).all()


def test_drawdown_and_the_distance_from_moving_averages():
    p = mini_panel()
    f = features.build(p)
    t = 300
    assert f["dd252"][t, 0] == pytest.approx(p.close[t, 0] / p.close[t - 251:t + 1, 0].max() - 1)
    assert f["dist50"][t, 3] == pytest.approx(p.close[t, 3] / p.close[t - 49:t + 1, 3].mean() - 1)
    assert f["dist200"][t, 3] == pytest.approx(p.close[t, 3] / p.close[t - 199:t + 1, 3].mean() - 1)
    assert np.isnan(f["dist200"][198]).all() and np.isfinite(f["dist200"][199]).all()


def test_traded_value_spike_is_today_over_the_mean_of_the_last_63_days():
    p = mini_panel()
    f = features.build(p)
    t = 200
    assert f["vspike"][t, 2] == pytest.approx(p.value[t, 2] / p.value[t - 62:t + 1, 2].mean())


def test_vix_level_and_five_day_change():
    p = mini_panel()
    f = features.build(p)
    assert f["vix"][50] == p.vix[50] and f["vixchg5"][50] == pytest.approx(p.vix[50] / p.vix[45] - 1)


def test_pe_and_pb_percentiles_are_the_share_of_past_values_not_above_todays_and_nan_until_a_year_of_history():
    p = mini_panel(T=500)
    f = features.build(p)
    t = 400
    hist = p.pe[100:t + 1]
    assert f["pe_pct"][t] == pytest.approx((hist <= hist[-1]).mean())
    assert np.isnan(f["pe_pct"][:100 + 249]).all() and np.isfinite(f["pe_pct"][100 + 249])
    assert f["pb_pct"][t] == pytest.approx((p.pb[100:t + 1] <= p.pb[t]).mean())


def test_gold_against_equity_strength_and_the_trailing_cash_yield():
    p = mini_panel()
    f = features.build(p)
    t = 150
    assert f["gold_vs_equity63"][t] == pytest.approx(f["ret63"][t, 3] - f["ret63"][t, 0])
    assert f["cash_yield63"][t] == pytest.approx((p.cash[t] / p.cash[t - 63]) ** (252 / 63) - 1)


def test_every_feature_passes_the_causality_harness():
    p = mini_panel(T=500)
    for name in features.build(p):
        causal.assert_causal(lambda q, n=name: features.build(q)[n], p, n_cuts=6, seed=3)


def test_the_harness_catches_a_centred_window_and_a_full_sample_normalisation():
    p = mini_panel()
    import pandas as pd
    centred = lambda q: pd.Series(q.close[:, 0]).rolling(21, center=True).mean().to_numpy()         # noqa: E731
    with pytest.raises(AssertionError, match="look"):
        causal.assert_causal(centred, p, n_cuts=8, seed=1)
    zscore = lambda q: (q.close[:, 0] - q.close[:, 0].mean()) / q.close[:, 0].std()               # noqa: E731
    with pytest.raises(AssertionError, match="look"):
        causal.assert_causal(zscore, p, n_cuts=8, seed=1)
    next_day = lambda q: np.concatenate([q.close[1:, 0], [np.nan]])                                # noqa: E731
    with pytest.raises(AssertionError, match="look"):
        causal.assert_causal(next_day, p, n_cuts=8, seed=1)


def test_truncate_cuts_every_array_to_the_first_n_days():
    p = mini_panel()
    q = causal.truncate(p, 50)
    assert len(q.dates) == 50 and q.open.shape == (50, 4) and q.value.shape == (50, 4) and q.cash.shape == (50,) and q.pe.shape == (50,)
    assert np.array_equal(q.close, p.close[:50]) and q.assets == p.assets


def test_cut_points_are_reproducible_and_include_the_earliest_and_latest_useful_days():
    p = mini_panel()
    a = causal.cut_points(len(p.dates), n_cuts=6, seed=5)
    assert a == causal.cut_points(len(p.dates), n_cuts=6, seed=5) and a != causal.cut_points(len(p.dates), n_cuts=6, seed=6)
    assert 1 in a and len(p.dates) - 2 in a and len(a) >= 6


def test_a_function_that_does_not_return_one_row_per_day_is_an_error():
    p = mini_panel()
    with pytest.raises(AssertionError, match="must return one row per day"):
        causal.assert_causal(lambda q: np.zeros(3), p, n_cuts=2, seed=0)


def test_a_look_ahead_that_only_changes_earlier_rows_is_caught_too():
    p = mini_panel()
    # only the first day's value depends on the end of the data; the last row of every run is the same
    sneaky = lambda q: np.concatenate([[q.close[-1, 0]], q.close[1:, 0]])                          # noqa: E731
    with pytest.raises(AssertionError, match="look"):
        causal.assert_causal(sneaky, p, n_cuts=4, seed=2)


def test_drawdown_uses_exactly_the_last_252_days_and_is_nan_before_then():
    p = mini_panel()
    close = p.close.copy()
    close[:, 0] = 100.0
    close[48, 0] = 200.0                      # the high sits at the very start of the window that ends on day 299 (days 48 .. 299 are 252 days)
    q = Panel(**{**p.__dict__, "close": close})
    f = features.build(q)
    assert f["dd252"][299, 0] == pytest.approx(100 / 200 - 1)
    assert f["dd252"][300, 0] == pytest.approx(0.0)           # on day 300 the window starts on day 49: the high has dropped out
    assert np.isnan(f["dd252"][:251]).all() and np.isfinite(f["dd252"][251]).all()
