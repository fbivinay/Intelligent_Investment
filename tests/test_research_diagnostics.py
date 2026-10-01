import numpy as np
import pytest
from scipy import stats

from research import diagnostics as D


def two_point(mu, sigma, n):
    """Half the days mu + sigma, half mu - sigma: skew 0, kurtosis 1, so the deflation formula's denominator is exactly 1."""
    return np.tile([mu + sigma, mu - sigma], n // 2)


def test_the_sharpe_ratio_is_the_mean_over_the_sample_deviation_of_the_daily_return():
    r = two_point(0.001, 0.01, 100)
    assert D.sharpe(r) == pytest.approx(0.001 / (0.01 * np.sqrt(100 / 99)))


def test_with_one_trial_the_deflated_sharpe_ratio_is_the_probabilistic_sharpe_ratio_against_zero_worked_by_hand():
    r = two_point(0.001, 0.01, 100)
    out = D.deflated_sharpe(r, n_trials=1, var_sr=0.0004)
    sr = 0.001 / (0.01 * np.sqrt(100 / 99))
    assert out["sr0"] == 0.0 and out["skew"] == pytest.approx(0.0, abs=1e-12) and out["kurt"] == pytest.approx(1.0)
    assert out["dsr"] == pytest.approx(stats.norm.cdf(sr * np.sqrt(99)))                    # the denominator is 1 for this series
    assert out["n"] == 100 and out["sr"] == pytest.approx(sr)


def test_the_expected_best_sharpe_of_many_trials_follows_the_published_formula():
    g = 0.5772156649015329
    for n, v in ((100, 1.0), (1000, 0.25), (2, 4.0)):
        want = np.sqrt(v) * ((1 - g) * stats.norm.ppf(1 - 1 / n) + g * stats.norm.ppf(1 - 1 / (n * np.e)))
        assert D.expected_max_sharpe(n, v) == pytest.approx(want)
    assert D.expected_max_sharpe(100, 1.0) == pytest.approx(2.53, abs=0.01)                 # the figure the original paper quotes for 100 trials
    assert D.expected_max_sharpe(1, 1.0) == 0.0 and D.expected_max_sharpe(1000, 0.0) == 0.0


def test_deflation_falls_as_the_trials_grow_and_rises_with_the_sharpe_ratio():
    rng = np.random.default_rng(3)
    r = rng.normal(0.0006, 0.01, 750)
    few, many = D.deflated_sharpe(r, 10, 0.0001)["dsr"], D.deflated_sharpe(r, 1000, 0.0001)["dsr"]
    assert 0 < many < few < 1
    better = D.deflated_sharpe(r + 0.0004, 100, 0.0001)["dsr"]
    assert better > D.deflated_sharpe(r, 100, 0.0001)["dsr"]


def test_fat_tails_and_negative_skew_lower_the_probability_for_the_same_sharpe_ratio():
    rng = np.random.default_rng(5)
    calm = rng.normal(0.0006, 0.01, 1000)
    crashy = calm.copy()
    crashy[::100] = -0.08                                                                    # ten crashes ...
    crashy = (crashy - crashy.mean()) / crashy.std() * calm.std() + calm.mean()             # ... with the same mean and deviation
    a, b = D.deflated_sharpe(calm, 1, 0.0), D.deflated_sharpe(crashy, 1, 0.0)
    assert b["sr"] == pytest.approx(a["sr"]) and b["skew"] < a["skew"] and b["kurt"] > a["kurt"] and b["dsr"] < a["dsr"]


def test_effective_trials_is_one_for_identical_series_and_close_to_n_for_independent_ones():
    rng = np.random.default_rng(1)
    one = rng.normal(0, 0.01, 500)
    assert D.effective_trials(np.tile(one[:, None], (1, 40))) == pytest.approx(1.0)
    assert D.effective_trials(rng.normal(0, 0.01, (4000, 40))) == pytest.approx(40, rel=0.005)
    half = np.column_stack([np.tile(one[:, None], (1, 20)), rng.normal(0, 0.01, (500, 20))])
    assert 28 < D.effective_trials(half) < 32                                               # mean correlation 190 / 780 = 0.24: 0.24 + 0.76 x 40 = 30.5 (the published rule is crude on clusters)
    assert D.effective_trials(half) < D.effective_trials(rng.normal(0, 0.01, (500, 40)))


def test_a_constant_column_is_left_out_of_the_effective_count():
    rng = np.random.default_rng(1)
    m = np.column_stack([rng.normal(0, 0.01, (300, 5)), np.zeros(300)])
    assert D.effective_trials(m) == pytest.approx(D.effective_trials(m[:, :5]))


def test_pbo_is_one_when_the_best_in_sample_is_always_the_worst_out_of_sample_by_hand():
    a = np.repeat([4.0, 1.0, -2.0, -3.0], 4) * 0.01                                         # four blocks of four days whose means add to zero
    m = np.column_stack([a, -a])
    out = D.pbo(m, blocks=4)
    assert out["n_combos"] == 6 and out["pbo"] == 1.0 and np.allclose(out["logits"], np.log(0.5))          # always the worst of two: relative rank 1/3, logit ln(1/2)


def test_pbo_is_zero_when_one_strategy_is_better_in_every_block():
    rng = np.random.default_rng(2)
    m = rng.normal(0, 0.01, (800, 30))
    m[:, 0] += 0.02
    out = D.pbo(m, blocks=8)
    assert out["pbo"] == 0.0 and out["n_combos"] == 70 and (out["logits"] > 0).all()


def test_pbo_of_pure_noise_strategies_is_about_one_half():
    rng = np.random.default_rng(7)
    out = D.pbo(rng.normal(0, 0.01, (1280, 60)), blocks=16)
    assert out["n_combos"] == 12870 and 0.4 < out["pbo"] < 0.75                              # noise: about a half, a little over because in-sample and out-of-sample parts of a fixed total lean against each other


def test_pbo_refuses_an_odd_number_of_blocks_and_too_few_rows():
    with pytest.raises(ValueError, match="even"):
        D.pbo(np.zeros((100, 3)), blocks=5)
    with pytest.raises(ValueError, match="rows"):
        D.pbo(np.zeros((10, 3)), blocks=16)
    with pytest.raises(ValueError, match="rows"):
        D.pbo(np.zeros((20, 3)), blocks=16)                                                  # two days a block is the least that gives a deviation


def test_a_strategy_that_is_best_in_sample_and_exactly_the_median_out_of_sample_counts_as_overfit():
    level = np.array([[3.0, 0.0], [1.0, -1.0], [2.0, 5.0]]).T                               # block levels of three strategies: x = (3, 0), y = (1, -1), z = (2, 5)
    wiggle = np.tile([0.01, -0.01], 2)
    m = np.column_stack([np.concatenate([lv[0] * 0.01 + wiggle, lv[1] * 0.01 + wiggle]) for lv in level.T])
    out = D.pbo(m, blocks=2)
    assert out["n_combos"] == 2 and np.allclose(out["logits"], 0.0) and out["pbo"] == 1.0   # relative rank 2/4 = one half in both splits: logit 0
