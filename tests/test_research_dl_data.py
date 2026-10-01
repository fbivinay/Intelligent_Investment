import numpy as np
import pytest

from research import causal, features as F
from research.dl import data as D
from research.panel import ASSETS, Panel


def panel(n=700, seed=2, vix_from=30, with_pe=True):
    dates = np.arange(np.datetime64("2011-01-03"), np.datetime64("2011-01-03") + n, dtype="datetime64[D]")
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, (n, 4)), axis=0))
    vix = np.where(np.arange(n) >= vix_from, 15 + rng.normal(0, 1, n), np.nan)
    pe = np.where(np.arange(n) >= 200, 20 + rng.normal(0, 1, n), np.nan) if with_pe else np.full(n, np.nan)
    return Panel(dates=dates, assets=list(ASSETS), open=close, high=close * 1.01, low=close * 0.99, close=close, value=1e9 * (1 + rng.random((n, 4))), vwap=close * 1.001,
                 cash=1.0002 ** np.arange(n), nifty=close[:, 0], vix=vix, pe=pe, pb=pe / 6)


def test_the_feature_matrix_lists_the_per_asset_features_asset_by_asset_then_the_market_ones_then_a_missing_flag_for_each_that_can_be_missing():
    p = panel()
    f = F.build(p)
    X, names = D.feature_matrix(f)
    assert X.shape == (700, len(names)) and len(names) == 11 * 4 + 6 + 4
    assert names[0] == "ret1:NIFTYBEES" and names[3] == "ret1:GOLDBEES" and names[4] == "ret5:NIFTYBEES" and "vix" in names and names[-4:] == ["vix:missing", "vixchg5:missing", "pe_pct:missing", "pb_pct:missing"]
    j = names.index("ret21:BANKBEES")
    assert np.array_equal(X[:, j], f["ret21"][:, 2], equal_nan=True)
    k = names.index("vix:missing")
    assert np.array_equal(X[:, k], np.isnan(f["vix"]).astype(float))
    assert np.isnan(X[:, names.index("vix")][:30]).all()                                        # raw values stay NaN here; normalise fills them


def test_the_first_valid_day_is_the_first_with_every_always_present_feature():
    p = panel()
    X, names = D.feature_matrix(F.build(p))
    t0 = D.first_valid(X, names)
    assert t0 == 252                                                                          # ret252 and dd252 need a year
    core = [i for i, n in enumerate(names) if not n.startswith(("vix", "pe_pct", "pb_pct")) and not n.endswith(":missing")]
    assert np.isfinite(X[t0:, core]).all() and not np.isfinite(X[t0 - 1, core]).all()


def test_the_normaliser_uses_only_the_rows_before_the_cut_and_ignores_missing_values():
    p = panel()
    X, names = D.feature_matrix(F.build(p))
    t0 = D.first_valid(X, names)
    mu, sd = D.fit_norm(X, t0, 500)
    X2 = X.copy()
    X2[500:] = X2[500:] * 100 + 7                                                              # changing the future changes nothing
    mu2, sd2 = D.fit_norm(X2, t0, 500)
    assert np.array_equal(mu, mu2) and np.array_equal(sd, sd2)
    j = names.index("pe_pct")
    assert mu[j] == pytest.approx(np.nanmean(X[t0:500, j]))
    assert (sd > 0).all()


def test_normalising_standardises_clips_and_turns_missing_values_into_zero():
    X = np.array([[1.0, np.nan], [3.0, 5.0], [100.0, 7.0]])
    mu, sd = np.array([2.0, 6.0]), np.array([1.0, 2.0])
    Z = D.normalise(X, mu, sd, clip=5.0)
    assert np.allclose(Z, [[-1.0, 0.0], [1.0, -0.5], [5.0, 0.5]])                              # 100 is clipped to 5 standard deviations, NaN becomes 0


def test_a_constant_column_gets_a_unit_deviation_so_it_normalises_to_zero():
    X = np.column_stack([np.arange(10, dtype=float), np.full(10, 3.0)])
    mu, sd = D.fit_norm(X, 0, 10)
    assert sd[1] == 1.0 and np.allclose(D.normalise(X, mu, sd)[:, 1], 0.0)


def test_sequences_are_the_windows_that_end_on_each_day_and_see_nothing_later():
    Z = np.arange(40, dtype=float).reshape(20, 2)
    S = D.sequences(Z, np.array([5, 9, 19]), 4)
    assert S.shape == (3, 4, 2) and np.array_equal(S[0], Z[2:6]) and np.array_equal(S[2], Z[16:20])
    Z2 = Z.copy()
    Z2[10:] = -1
    assert np.array_equal(D.sequences(Z2, np.array([5, 9]), 4), S[:2])


def test_a_sequence_that_would_start_before_the_data_is_refused():
    with pytest.raises(ValueError, match="start"):
        D.sequences(np.zeros((10, 2)), np.array([2]), 4)


def test_the_label_of_day_t_is_the_return_from_the_fill_price_of_t_plus_1_to_that_of_t_plus_2_and_the_last_two_days_have_none():
    p = panel(n=50)
    R = D.labels(p.vwap, p.cash)
    assert R.shape == (50, 5)
    assert np.allclose(R[10, :4], p.vwap[12] / p.vwap[11] - 1) and R[10, 4] == pytest.approx(p.cash[12] / p.cash[11] - 1)
    assert np.isnan(R[-2:]).all() and np.isfinite(R[:-2]).all()


def test_features_and_labels_pass_the_causality_harness_in_the_sense_the_row_of_a_day_never_depends_on_later_days():
    p = panel(n=500, seed=4)
    causal.assert_causal(lambda q: D.feature_matrix(F.build(q))[0], p, n_cuts=5, seed=1)


def test_the_normaliser_statistics_are_the_sample_mean_and_deviation_over_the_rows_from_the_first_valid_day():
    X = np.array([[1.0], [2.0], [3.0], [4.0], [50.0]])
    mu, sd = D.fit_norm(X, 0, 4)
    assert mu[0] == pytest.approx(2.5) and sd[0] == pytest.approx(np.std([1, 2, 3, 4], ddof=1))
    mu2, _ = D.fit_norm(X, 1, 4)
    assert mu2[0] == pytest.approx(3.0)                                                         # the start row is honoured
    p = panel()
    Xp, names = D.feature_matrix(F.build(p))
    t0 = D.first_valid(Xp, names)
    j = names.index("ret1:NIFTYBEES")
    assert D.fit_norm(Xp, t0, 500)[0][j] == pytest.approx(np.nanmean(Xp[t0:500, j]))


def test_a_sequence_may_start_on_the_very_first_row_but_not_before():
    Z = np.arange(20, dtype=float).reshape(10, 2)
    assert np.array_equal(D.sequences(Z, np.array([3]), 4)[0], Z[0:4])
    with pytest.raises(ValueError, match="start"):
        D.sequences(Z, np.array([2]), 4)
