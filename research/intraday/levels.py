"""The risk levels the user asked for, checked: the stop-protected six-strategy Nifty book (combine_6_safe.md) sized on the training years to each worst-fall
limit, then run with whole lots at each amount, on the training and the test years, after tax and charges, before tax, and before tax and charges.

    python -m research.intraday.levels        # writes research/out/intraday/levels.md
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.intraday import capital as K, combine as C, engine as E, grid as G

LIMITS = (0.05, 0.10, 0.15)
AMOUNTS = (10e5, 25e5, 50e5, 100e5)
ASKED = {(50e5, 0.05): 0.15, (25e5, 0.10): 0.20, (10e5, 0.15): 0.25}       # (amount, worst fall) -> the return the user asked for


def main():
    G._init()
    d = G._D
    grid = pd.read_csv(G.OUT / "grid.csv").set_index("name")
    split, D = int(np.searchsorted(d.T["days"], G.SPLIT)), len(d.lot)
    books = [E.arrays(d, E.trades(d, C._spec(n), G._SIG)) for n in K.BOOK]
    base = np.array([grid.at[n, "scale"] for n in K.BOOK]) / len(K.BOOK)
    run = lambda m, cap, lo, hi, **kw: E.stats_arr(E.account_multi([d] * len(books), books, base * m, cap, lo, hi, **kw), d.T["days"][lo:hi])  # noqa: E731
    lines = ["# Risk levels checked (whole lots, one account)", "", "Size fitted on 2016-2021 so the worst fall there is the limit (as if the money were large); "
             "test = 2022-01 to 2026-05, never used for any choice.", "",
             "| Amount | Fall limit | Asked | Test after tax | Test fall | Test before tax | Test before tax and charges | Training after tax | Training fall | Meets it? |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for limit in LIMITS:
        m = 1.0
        for _ in range(10):
            fall = run(m, 1e9, 0, split)["worst_fall"]
            m *= limit / fall
        for cap in AMOUNTS:
            tr, te = run(m, cap, 0, split), run(m, cap, split, D)
            pre, gross = run(m, cap, split, D, tax=False), run(m, cap, split, D, tax=False, charges=False)
            want = ASKED.get((cap, limit))
            ok = "" if want is None else ("yes" if te["cagr"] >= want and te["worst_fall"] <= limit else "no")
            lines.append(f"| Rs {cap / 1e5:.0f} lakh | {limit:.0%} | {'' if want is None else f'{want:.0%}'} | {te['cagr']:.1%} | {te['worst_fall']:.1%} | "
                         f"{pre['cagr']:.1%} | {gross['cagr']:.1%} | {tr['cagr']:.1%} | {tr['worst_fall']:.1%} | {ok} |")
            print(lines[-1], flush=True)
    (G.OUT / "levels.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
