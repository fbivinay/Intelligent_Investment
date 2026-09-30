"""The causality harness: cut the data at a day T, rerun, and require every decision up to T to be what the full run made.

A feature or strategy that peeks at the future (a centred window, a normalisation over the whole sample, a next-day value) gives a different answer on the
truncated data. `assert_causal` runs the function on the full panel and on the panel cut after each of several days, and compares all rows up to the cut.
"""
from __future__ import annotations

import dataclasses

import numpy as np

from research.panel import Panel


def truncate(panel: Panel, n: int) -> Panel:
    """The panel with only its first n days."""
    cut = {f.name: (getattr(panel, f.name)[:n] if isinstance(getattr(panel, f.name), np.ndarray) else getattr(panel, f.name)) for f in dataclasses.fields(panel)}
    return Panel(**cut)


def cut_points(T: int, n_cuts: int = 8, seed: int = 0) -> list[int]:
    """Indices t to cut after (the run sees days 0..t): the second day, the second to last day, and random days in between. Reproducible."""
    rng = np.random.default_rng(seed)
    mid = rng.choice(np.arange(2, T - 2), size=max(0, n_cuts - 2), replace=False)
    return sorted({1, T - 2, *[int(x) for x in mid]})


def assert_causal(fn, panel: Panel, cuts: list[int] | None = None, n_cuts: int = 8, seed: int = 0, atol: float = 1e-12) -> None:
    """fn(panel) returns one row per day (any trailing shape). For each cut t, fn(truncate(panel, t + 1))[:t + 1] must equal fn(panel)[:t + 1]."""
    T = len(panel.dates)
    full = np.asarray(fn(panel), dtype=float)
    assert full.shape[0] == T, f"the function must return one row per day ({T}), it returned {full.shape}"
    for t in (cuts if cuts is not None else cut_points(T, n_cuts, seed)):
        part = np.asarray(fn(truncate(panel, t + 1)), dtype=float)
        assert part.shape[0] == t + 1, f"one row per day expected on the cut data ({t + 1}), got {part.shape}"
        a, b = part, full[:t + 1]
        same = (np.isclose(a, b, atol=atol, rtol=0, equal_nan=True))
        if not same.all():
            bad = np.argwhere(~same)[0]
            raise AssertionError(f"look-ahead: cutting the data after day {t} changed the value on day {int(bad[0])} ({a[tuple(bad)]} against {b[tuple(bad)]} on the full data)")
