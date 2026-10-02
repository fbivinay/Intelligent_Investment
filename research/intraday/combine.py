"""A book of several intraday strategies, picked and sized on the training years only, then run on the test years.

    python -m research.intraday.combine [k] [safe]      # reads research/out/intraday/grid.csv, writes combine_<k>[_safe].md; safe: protected() only

Pick: the best `k` settings by training growth at the 5% fall (from the grid), at most one per structure-and-signal pair so the book is not one idea k
times, and none whose daily results correlate above 0.7 with one already picked (training years). Weights: equal shares of the money, each strategy at its own
5% size; then one common scale fitted so the book's training worst fall is 5%. The test years see that book unchanged.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from research.intraday import engine as E, grid as G


def _spec(name: str) -> E.Spec:
    return next(s for s in G.specs() if s.name == name)


def daily(d, spec, scale, lo, hi):
    tr = E.trades(d, spec, G._SIG)
    eq = E.account(d, tr, scale=scale, lo=lo, hi=hi).equity
    return eq.pct_change().fillna(0)


NAKED = ("straddle", "strangle2", "strangle3")


def protected(name: str) -> bool:
    """Every sold option has a stop of its own or a bought option behind it (condors, butterflies, spreads)."""
    parts = name.split("|")
    return not (parts[0] == "theta" and parts[1] in NAKED and "legsl=None" in parts)


def main(k: int = 6, safe: bool = False):
    G._init()
    d = G._D
    grid = pd.read_csv(G.OUT / "grid.csv").dropna(subset=["train_cagr"]).sort_values("train_cagr", ascending=False)
    if safe:
        grid = grid[grid.name.map(protected)]
    split = int(np.searchsorted(d.T["days"], G.SPLIT))
    picked, rets, seen = [], {}, set()
    for _, row in grid.iterrows():
        key = "|".join(row["name"].split("|")[:3])
        if key in seen:
            continue
        r = daily(d, _spec(row["name"]), row.scale, 0, split)
        if any(abs(r.corr(rets[p])) > 0.7 for p in picked):
            continue
        picked.append(row["name"])
        rets[row["name"]] = r
        seen.add(key)
        if len(picked) == k:
            break
    cash = pd.Series(d.cash * (1 - E.TAX), index=pd.DatetimeIndex(d.T["days"].astype("datetime64[ns]")))

    def book(lo, hi, m):
        rs = pd.concat([daily(d, _spec(n), grid.set_index("name").at[n, "scale"] * m, lo, hi) for n in picked], axis=1)
        c = cash.iloc[lo:hi]
        excess = rs.sub(c, axis=0).mean(axis=1)                  # each strategy's return over the liquid fund, in equal shares
        return (1 + c + excess).cumprod()

    m = 1.0
    for _ in range(8):
        e = book(0, split, m)
        dd = (1 - e / e.cummax()).max()
        m *= 0.05 / dd
    tr, te = book(0, split, m), book(split, len(d.lot), m)
    lines = ["# A book of intraday strategies at a 5% worst fall", "", f"Picked on 2016-01 to 2021-12 (training), run unchanged on 2022-01 to 2026-05 (test). Common scale {m:.2f}.", "",
             "| Strategy |", "|---|", *[f"| {n} |" for n in picked], "",
             "| Window | Growth a year after tax | Worst fall |", "|---|---|---|"]
    for name, e in (("training", tr), ("test", te)):
        y = (e.index[-1] - e.index[0]).days / 365.25
        lines.append(f"| {name} | {e.iloc[-1] ** (1 / y) - 1:.1%} | {(1 - e / e.cummax()).max():.1%} |")
    (G.OUT / f"combine_{k}{'_safe' if safe else ''}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 6, "safe" in sys.argv[2:])
