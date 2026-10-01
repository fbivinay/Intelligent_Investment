"""The walk-forward selector (spec section 5): every first trading day of April, pick the strategy to hold for the financial year from data before that day only.

The simulator is causal, so one full run of a strategy gives its training-window result at every April: its after-tax wealth on the last day before the cut (the equity
then, less the tax of the financial year that just ended, which is paid on the cut day itself), its drawdown so far, its growth. Nothing is re-simulated per window.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from engine.tax import fy_of
from research import baseline, panel as P, sim


@dataclass(frozen=True)
class Run:
    """What the selector needs of one full simulation: arrays only, so thousands fit in memory."""
    id: str
    family: str
    cap: float
    equity: np.ndarray            # T, after tax paid
    drawdown: np.ndarray          # T, before tax, from the high-water mark
    tax_by_fy: dict               # tax of each completed financial year, paid the day after it ends
    pending_tax: float
    eligible_from: str | None = None


def run_of_result(id_: str, family: str, cap: float, r, eligible_from: str | None = None) -> Run:
    return Run(id_, family, cap, r.equity, r.drawdown, dict(r.tax_by_fy), r.pending_tax, eligible_from)


def cut_days(dates: np.ndarray, first: str = "2013-04-01") -> list[int]:
    """Indices of the first trading day of April, from `first` on. Day 0 has no day before it, so it is never a cut."""
    month = dates.astype("datetime64[M]")
    new = np.r_[False, month[1:] != month[:-1]]
    return [int(i) for i in np.flatnonzero(new & (month.astype(int) % 12 + 1 == 4) & (dates >= np.datetime64(first)))]


@dataclass(frozen=True)
class Stats:
    wealth: np.ndarray            # per run: after-tax wealth on the last day before the cut
    growth: np.ndarray            # per run: log(wealth / capital) a year since day 0; NaN when the wealth is not positive
    maxdd: np.ndarray             # per run: the largest drawdown before the cut


def prefix_stats(runs: list[Run], dates: np.ndarray, c: int, capital: float) -> Stats:
    """Each run's training-window result at cut day c, which must be the first day of a financial year."""
    before = dates[c - 1].item()
    if fy_of(before) == fy_of(dates[c].item()):
        raise ValueError("a cut must be the first day of a financial year: the tax of the year before it is known only then")
    wealth = np.array([r.equity[c - 1] - r.tax_by_fy.get(fy_of(before), 0.0) for r in runs])
    years = (dates[c - 1] - dates[0]).astype(int) / 365.25
    growth = np.full(len(runs), np.nan)
    ok = wealth > 0
    growth[ok] = np.log(wealth[ok] / capital) / years
    return Stats(wealth, growth, np.array([r.drawdown[:c].max() for r in runs]))


BLOCK = 21                    # mean block length of the stationary bootstrap, trading days (about a month)
DRAWS = 1000


def _block_means(x: np.ndarray, rng: np.random.Generator, draws: int = DRAWS, block: int = BLOCK) -> np.ndarray:
    """Means of `draws` stationary bootstrap resamples of x (Politis and Romano): blocks of geometric length that wrap around the end."""
    n = len(x)
    restart = rng.random((draws, n)) < 1.0 / block
    restart[:, 0] = True
    start = rng.integers(0, n, (draws, n))
    t = np.arange(n)
    began = np.maximum.accumulate(np.where(restart, t, 0), axis=1)              # the day on which the current block began
    return x[(np.take_along_axis(start, began, axis=1) + t - began) % n].mean(axis=1)


def paired_se(a: np.ndarray, b: np.ndarray, seed: int, draws: int = DRAWS) -> tuple[float, float]:
    """The annualised mean difference between the daily log changes of wealth paths a and b, and its standard error by stationary block bootstrap."""
    if (a <= 0).any() or (b <= 0).any():
        raise ValueError("a wealth path must be positive")
    d = np.diff(np.log(a)) - np.diff(np.log(b))
    return float(d.mean() * 252), float(_block_means(d, np.random.default_rng(seed), draws).std(ddof=1) * 252)


def pick(runs: list[Run], stats: Stats, dates: np.ndarray, c: int, cap: float, s0: int, margin: float, draws: int = DRAWS) -> tuple[int, dict]:
    """The run to hold from cut day c, and the log row of why. Eligible: growth known and drawdown so far within the cap. The best eligible by growth is held only if its
    paired edge over S0 (the default, eligible or not) exceeds `margin` standard errors; otherwise S0 stays. Uses the paths up to the day before the cut."""
    ok = np.isfinite(stats.growth[s0]) and stats.maxdd[s0] <= cap
    log = dict(cut=str(dates[c]), eligible=0, s0=runs[s0].id, s0_growth=float(stats.growth[s0]), s0_maxdd=float(stats.maxdd[s0]), s0_eligible=bool(ok), best="",
               best_growth=float("nan"), best_maxdd=float("nan"), diff=float("nan"), se=float("nan"), margin=margin)
    in_time = np.array([r.eligible_from is None or dates[c] >= np.datetime64(r.eligible_from) for r in runs])
    eligible = np.flatnonzero(np.isfinite(stats.growth) & (stats.maxdd <= cap) & in_time)
    log["eligible"] = int(len(eligible))
    if not len(eligible):
        return s0, {**log, "decision": "S0", "reason": "no strategy is eligible: every one has had a drawdown above the cap"}
    best = int(eligible[np.argmax(stats.growth[eligible])])
    log.update(best=runs[best].id, best_growth=float(stats.growth[best]), best_maxdd=float(stats.maxdd[best]))
    if best == s0:
        return s0, {**log, "decision": "S0", "reason": "S0 is the best eligible strategy"}
    mean, se = paired_se(runs[best].equity[:c], runs[s0].equity[:c], int(dates[c].astype("datetime64[D]").astype(int)), draws)
    log.update(diff=mean, se=se)
    if mean > margin * se:
        return best, {**log, "decision": "picked", "reason": f"beats S0 by {mean:.4f} a year, more than {margin:g} standard error ({se:.4f})"}
    return s0, {**log, "decision": "S0", "reason": f"the edge over S0 ({mean:.4f} a year) is not more than {margin:g} standard error ({se:.4f})"}


LOG_COLUMNS = ["cut", "eligible", "s0", "s0_growth", "s0_maxdd", "s0_eligible", "best", "best_growth", "best_maxdd", "diff", "se", "margin", "decision", "reason", "picked", "family"]
REFERENCES = ("Nifty BeES", "Gold BeES", "Liquid fund")


@dataclass(frozen=True)
class Selection:
    log: pd.DataFrame             # one row per cut
    holder: np.ndarray            # T: the index of the run held on each day (S0 before the first cut)
    weights: np.ndarray           # T x 5: the stitched target weights
    first_cut: int | None


def walk_forward(runs: list[Run], weights_of, dates: np.ndarray, cap: float, margin: float, capital: float = 1_000_000.0, first: str = "2013-04-01",
                 draws: int = DRAWS) -> Selection:
    """Pick at every April cut from data before it, hold the pick until the next cut, and stitch the picked runs' weights (S0's before the first cut)."""
    s0s = [i for i, r in enumerate(runs) if r.family == "S0"]
    if len(s0s) != 1:
        raise ValueError(f"there must be exactly one S0 among the runs, not {len(s0s)}")
    cuts = cut_days(dates, first)
    holder = np.full(len(dates), s0s[0])
    rows = []
    for k, c in enumerate(cuts):
        i, row = pick(runs, prefix_stats(runs, dates, c, capital), dates, c, cap, s0s[0], margin, draws)
        holder[c:cuts[k + 1] if k + 1 < len(cuts) else len(dates)] = i
        rows.append({**row, "picked": runs[i].id, "family": runs[i].family})
    weights = np.empty((len(dates), 5))
    for i in np.unique(holder):
        weights[holder == i] = weights_of(int(i))[holder == i]
    return Selection(pd.DataFrame(rows, columns=LOG_COLUMNS), holder, weights, cuts[0] if cuts else None)


def candidates(panel: P.Panel, rules, trials: list, cap: float, progress=None):
    """The full run of every trial that applies at this cap (S0 only its own), and a function that rebuilds the weights of run i."""
    chosen = [t for t in trials if t.cap in (None, cap)]
    runs = []
    for k, t in enumerate(chosen):
        runs.append(run_of_result(t.id, t.family, cap, sim.simulate(panel, t.fn(panel), rules, sim.SimConfig(cap=cap, band=t.band)), t.eligible_from))
        if progress:
            progress(k + 1, len(chosen))
    return runs, lambda i: chosen[i].fn(panel)


def stitched_account(panel: P.Panel, sel: Selection, rules, cap: float, capital: float = 1_000_000.0) -> sim.Result:
    """The stitched weights as ONE fresh account from the first cut, governor on."""
    if sel.first_cut is None:
        raise ValueError("there was no cut, so nothing was stitched")
    return sim.simulate(P.from_day(panel, sel.first_cut), sel.weights[sel.first_cut:], rules, sim.SimConfig(cap=cap, capital=capital))


def references(panel: P.Panel, sel: Selection, s0_weights: np.ndarray, rules, cap: float, capital: float = 1_000_000.0) -> dict[str, sim.Result]:
    """Accounts started fresh on the first cut with the same capital: S0 (its weights from the full history, governor on) and buy and hold of the reference investments."""
    window = P.from_day(panel, sel.first_cut)
    from research import strategies as st
    out = {"S0": sim.simulate(window, s0_weights[sel.first_cut:], rules, sim.SimConfig(cap=cap, capital=capital))}
    for name in REFERENCES:
        out[name] = sim.simulate(window, st.s1_static(baseline.REFERENCE[name], "never")(window), rules, sim.SimConfig(governor=False, capital=capital))
    return out
