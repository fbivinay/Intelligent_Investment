import numpy as np
import pytest

from research import causal, features as F
from research.dl import data as D, train as T, walk as W
from research.panel import ASSETS, Panel


def panel(n=700, seed=2):
    dates = np.arange(np.datetime64("2011-01-03"), np.datetime64("2011-01-03") + n, dtype="datetime64[D]")
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, (n, 4)), axis=0))
    pe = np.where(np.arange(n) >= 200, 20 + rng.normal(0, 1, n), np.nan)
    return Panel(dates=dates, assets=list(ASSETS), open=close, high=close * 1.01, low=close * 0.99, close=close, value=1e9 * (1 + rng.random((n, 4))), vwap=close * 1.001,
                 cash=1.0002 ** np.arange(n), nifty=close[:, 0], vix=15 + rng.normal(0, 1, n), pe=pe, pb=pe / 6)


CFG = T.Config(arch="mlp", seq_len=5, cost=0.0005, hidden=4, lr=0.02, weight_decay=0.0, max_epochs=6, patience=3)
CUTS = [420, 520]


def walk(p, cuts=CUTS, **kw):
    kw = {"seeds": (0, 1), "val_days": 60, "min_samples": 100, **kw}
    return W.walk_weights(F.build(p), p.vwap, p.cash, cuts, CFG, **kw)


def test_the_weights_are_missing_before_the_first_cut_and_valid_long_only_weights_from_it_on():
    p = panel()
    w = walk(p)
    assert w.shape == (700, 5) and np.isnan(w[:420]).all() and np.isfinite(w[420:]).all()
    assert (w[420:] >= 0).all() and np.allclose(w[420:].sum(axis=1), 1.0, atol=1e-5)


def test_too_few_training_days_leave_the_equal_weight_prior_for_that_financial_year():
    p = panel()
    w = walk(p, min_samples=10_000)
    assert np.allclose(w[420:], 0.2)


def test_a_window_too_short_for_the_validation_set_also_leaves_the_prior():
    p = panel()
    w = walk(p, val_days=400)
    assert np.allclose(w[420:], 0.2)


def test_the_weights_of_every_day_are_unchanged_when_the_data_after_it_is_cut_away():
    p = panel()
    full = walk(p)
    for n in (560, 620):
        part = walk(causal.truncate(p, n))
        assert part.shape == (n, 5)
        assert np.allclose(part, full[:n], atol=1e-6, equal_nan=True)


def test_each_cut_retrains_so_a_later_year_can_differ_from_an_earlier_one_and_the_progress_is_reported():
    p = panel()
    seen = []
    w = walk(p, progress=lambda k, n: seen.append((k, n)))
    assert seen == [(1, 2), (2, 2)]
    assert w[420:520].shape == (100, 5) and w[520:].shape == (180, 5)


def test_the_label_timing_matches_the_simulator_the_weights_of_day_t_earn_the_return_from_the_fill_of_t_plus_1_to_that_of_t_plus_2():
    p = panel(n=50)
    R = D.labels(p.vwap, p.cash)
    assert np.allclose(R[7, :4], p.vwap[9] / p.vwap[8] - 1)
