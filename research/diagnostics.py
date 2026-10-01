"""Protection against fooling ourselves (spec section 6): the deflated Sharpe ratio, the effective number of trials, and the probability of backtest overfitting.

Bailey and Lopez de Prado, "The Deflated Sharpe Ratio" (2014); Bailey, Borwein, Lopez de Prado and Zhu, "The Probability of Backtest Overfitting" (2017).
Every function takes daily returns (excess over the cash leg, so the Sharpe ratio is the one in the ledger) and works in per-day units.
"""
from __future__ import annotations

from itertools import combinations
from math import e

import numpy as np
from scipy import stats

EULER = 0.5772156649015329


def sharpe(returns: np.ndarray) -> float:
    """Mean over sample deviation of the daily returns (not annualised)."""
    return float(np.mean(returns) / np.std(returns, ddof=1))


def expected_max_sharpe(n_trials: float, var_sr: float) -> float:
    """The best Sharpe ratio to expect among n_trials strategies with no skill, whose estimated ratios vary with variance var_sr."""
    if n_trials <= 1 or var_sr <= 0:
        return 0.0
    return float(np.sqrt(var_sr) * ((1 - EULER) * stats.norm.ppf(1 - 1 / n_trials) + EULER * stats.norm.ppf(1 - 1 / (n_trials * e))))


def deflated_sharpe(returns: np.ndarray, n_trials: float, var_sr: float) -> dict:
    """Probability that the true Sharpe ratio is above what the best of n_trials unskilled strategies would show, allowing for the skew and fat tails of the returns."""
    r = np.asarray(returns, dtype=float)
    n, sr = len(r), sharpe(r)
    skew, kurt = float(stats.skew(r)), float(stats.kurtosis(r, fisher=False))
    sr0 = expected_max_sharpe(n_trials, var_sr)
    z = (sr - sr0) * np.sqrt(n - 1) / np.sqrt(1 - skew * sr + (kurt - 1) / 4 * sr ** 2)
    return dict(sr=sr, sr0=sr0, dsr=float(stats.norm.cdf(z)), skew=skew, kurt=kurt, n=n)


def effective_trials(matrix: np.ndarray) -> float:
    """How many independent strategies a set of correlated ones amounts to: rho + (1 - rho) N for the mean pairwise correlation rho. Constant columns are left out."""
    m = np.asarray(matrix, dtype=float)
    m = m[:, m.std(axis=0) > 0]
    n = m.shape[1]
    if n < 2:
        return float(n)
    corr = np.corrcoef(m, rowvar=False)
    rho = (corr.sum() - n) / (n * (n - 1))
    return float(rho + (1 - rho) * n)


def pbo(matrix: np.ndarray, blocks: int = 16, chunk: int = 500) -> dict:
    """Probability of backtest overfitting by combinatorially symmetric cross-validation. Rows are days, columns are strategies. Cut the days into `blocks`; for every way
    of taking half the blocks as the in-sample part, find the strategy that is best in it and look where it ranks among all strategies in the other half. The probability is
    the share of splits in which it ranks at or below the median. `logits` holds ln(w / (1 - w)) of its relative rank w for every split."""
    m = np.asarray(matrix, dtype=float)
    if blocks % 2:
        raise ValueError("the number of blocks must be even")
    if len(m) < 2 * blocks:
        raise ValueError(f"at least {2 * blocks} rows are needed for {blocks} blocks")
    edges = np.linspace(0, len(m), blocks + 1).astype(int)
    count = np.diff(edges).astype(float)
    total = np.add.reduceat(m, edges[:-1], axis=0), np.add.reduceat(m ** 2, edges[:-1], axis=0)
    splits = np.array(list(combinations(range(blocks), blocks // 2)))
    n = m.shape[1]
    logits = []

    def sharpe_of(mask: np.ndarray) -> np.ndarray:
        k = mask @ count
        s1, s2 = mask @ total[0], mask @ total[1]
        mean = s1 / k[:, None]
        return mean / np.sqrt((s2 - k[:, None] * mean ** 2) / (k[:, None] - 1))

    for lo in range(0, len(splits), chunk):
        ins = np.zeros((len(splits[lo:lo + chunk]), blocks))
        np.put_along_axis(ins, splits[lo:lo + chunk], 1.0, axis=1)
        sr_in, sr_out = sharpe_of(ins), sharpe_of(1.0 - ins)
        best = np.argmax(sr_in, axis=1)
        chosen = sr_out[np.arange(len(best)), best]
        rank = (sr_out < chosen[:, None]).sum(axis=1) + 0.5 * ((sr_out == chosen[:, None]).sum(axis=1) + 1)       # ties share their ranks
        w = rank / (n + 1)
        logits.append(np.log(w / (1 - w)))
    logits = np.concatenate(logits)
    return dict(pbo=float((logits <= 0).mean()), logits=logits, n_combos=len(splits))
