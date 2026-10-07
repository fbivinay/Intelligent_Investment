"""A value through time, read for the charts: the days of a monthly plan, a growth index that leaves out the money paid in (so a payment is not a gain),
its drawdowns, calendar-year returns, the deepest fall, and the yearly rate of a plan's payments (XIRR). No money is worked out here: the values come from
the product's books or the alternatives' engine runs.
"""
from __future__ import annotations

from datetime import date

import numpy as np

from engine.tax import add_months


def schedule(start: date, end: date) -> list[date]:
    """A monthly plan's payment days: the start, then the same day of each month after it, up to the end."""
    out, k = [], 0
    while (d := add_months(start, k)) <= end:
        out.append(d)
        k += 1
    return out


def growth_index(values, paid) -> np.ndarray:
    """1 on the first day, then each day's change with that day's payment taken out: what one rupee kept in all along would be worth."""
    v, p = np.asarray(values, dtype=float), np.asarray(paid, dtype=float)
    r = np.ones(len(v))
    prev = v[:-1]
    r[1:] = np.where(prev > 0, (v[1:] - p[1:]) / np.where(prev > 0, prev, 1.0), 1.0)
    return np.cumprod(r)


def drawdown(index) -> np.ndarray:
    """How far below its highest point so far, as a share (0.18 is 18% down)."""
    i = np.asarray(index, dtype=float)
    return 1.0 - i / np.maximum.accumulate(i)


def years(dates: list[str], index) -> list[dict]:
    """The index's change over each calendar year, from the last day of the year before (or the first day); the first and last years are marked partial
    when they do not cover the whole year."""
    out, base = [], float(index[0])
    for i, d in enumerate(dates):
        if i < len(dates) - 1 and dates[i + 1][:4] == d[:4]:
            continue
        partial = (not out and dates[0][5:] > "01-07") or (i == len(dates) - 1 and d[5:] < "12-24")
        out.append({"year": int(d[:4]), "value": round(float(index[i]) / base - 1.0, 6), "partial": bool(partial)})
        base = float(index[i])
    return out


def deepest_fall(dates: list[str], index) -> dict | None:
    """The deepest fall, highest point to lowest, and the first day the index was back at that high (None if it has not got back)."""
    i = np.asarray(index, dtype=float)
    dd = drawdown(i)
    if dd.max() <= 0:
        return None
    trough = int(dd.argmax())
    peak = trough - int(np.argmax(i[trough::-1] >= i[:trough + 1].max()))         # the last day at the high the fall started from
    back = np.nonzero(i[trough:] >= i[peak])[0]
    rec = trough + int(back[0]) if len(back) else None
    end = date.fromisoformat(dates[rec] if rec is not None else dates[-1])
    return {"peak": dates[peak], "trough": dates[trough], "recovered": dates[rec] if rec is not None else None, "depth": round(float(dd[trough]), 6),
            "days": (end - date.fromisoformat(dates[peak])).days}


def xirr(flows: list[tuple[date, float]]) -> float:
    """The yearly rate at which the payments (negative) grow into the final amount (positive), days counted as 365.25 a year like the growth figures.
    With one payment it is the plain growth a year. -1 when nothing is left."""
    if sum(a for _, a in flows if a > 0) <= 0:
        return -1.0
    t0 = flows[0][0]
    yrs = np.array([(d - t0).days / 365.25 for d, _ in flows])
    amt = np.array([a for _, a in flows], dtype=float)
    npv = lambda r: float((amt / (1.0 + r) ** yrs).sum())                    # noqa: E731
    lo, hi = -0.9999, 1.0
    while npv(hi) > 0 and hi < 1e6:
        hi *= 2
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if npv(mid) > 0 else (lo, mid)
    return (lo + hi) / 2


if __name__ == "__main__":
    ix = growth_index([100, 210, 189, 231], [100, 100, 0, 0])
    assert np.allclose(ix, [1, 1.1, 0.99, 1.21]), ix
    assert abs(drawdown(ix).max() - 0.1) < 1e-12
    assert abs(xirr([(date(2020, 1, 1), -100.0), (date(2022, 1, 1), 121.0)]) - (1.21 ** (365.25 / 731) - 1)) < 1e-9
    print("paths checks done")
