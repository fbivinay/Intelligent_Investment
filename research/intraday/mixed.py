"""The Low level with Nifty and Bank Nifty strategies in one book.

    python -m research.intraday.mixed [k]        # writes research/out/intraday/mixed.md

Pick (training years only, as research/intraday/combine.py): stop-protected settings of both grids by training growth at the 5% fall, at most one per
index-structure-signal, none correlating above 0.7 with one already in; `k` of them in equal shares. Size: one common scale so the training worst fall of the
after-tax balance (flat 31.2%) is 5%, the cautious measure of levels_tax.py. Then whole lots at Rs 50 lakh and Rs 10 lakh on the test years, with the exact
tax of each year by regime and other income.
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd

from engine.rules import Rules
from engine.tax import TaxProfile
from research.intraday import combine as C, engine as E, grid as G, levels_tax as LT, signals as S

ROOT = Path(__file__).resolve().parents[2]
AMOUNTS = (50e5, 10e5)
LIMIT = 0.05


def main(k: int = 8):
    rules = Rules.load(ROOT / "rules")
    specs = {s.name: s for s in G.specs()}
    data, cands = {}, []
    for sym, f in (("NIFTY", "grid.csv"), ("BANKNIFTY", "grid_BANKNIFTY.csv")):
        d = E.load(sym)
        data[sym] = (d, S.build(d.T))
        g = pd.read_csv(G.OUT / f).dropna(subset=["train_cagr"])
        g = g[g.name.map(C.protected)]
        cands += [(r.train_cagr, sym, r.name, r.scale) for r in g.itertuples()]
    cands.sort(reverse=True)
    d0 = data["NIFTY"][0]
    days = d0.T["days"]
    split, D = int(np.searchsorted(days, G.SPLIT)), len(days)
    picked, seen, rets = [], set(), []
    for _, sym, name, scale in cands:
        key = sym + "|" + "|".join(name.split("|")[:3])
        if key in seen:
            continue
        d, sig = data[sym]
        a = E.arrays(d, E.trades(d, specs[name], sig))
        r = pd.Series(E.account_multi([d], [a], [scale], 1e9, 0, split)).pct_change().fillna(0)
        if any(abs(r.corr(x)) > 0.7 for x in rets):
            continue
        picked.append((sym, name, scale, a))
        rets.append(r)
        seen.add(key)
        if len(picked) == k:
            break
    ds = [data[s][0] for s, _, _, _ in picked]
    books = [a for _, _, _, a in picked]
    base = np.array([sc for _, _, sc, _ in picked]) / len(picked)
    run = lambda m, cap, lo, hi, **kw: E.stats_arr(E.account_multi(ds, books, base * m, cap, lo, hi, **kw), days[lo:hi])  # noqa: E731
    m = 1.0
    for _ in range(10):
        m *= LIMIT / run(m, 1e9, 0, split)["worst_fall"]
    lines = ["# Low level with Nifty and Bank Nifty strategies", "", "| Index | Strategy |", "|---|---|", *[f"| {s} | {n} |" for s, n, _, _ in picked], ""]
    for cap in AMOUNTS:
        gross, pre = run(m, cap, split, D, tax=False, charges=False), run(m, cap, split, D, tax=False)
        tr = run(m, cap, 0, split, tax=False)
        lines += [f"## Rs {cap / 1e5:.0f} lakh", "", f"Test: before tax and charges {gross['cagr']:.1%}; before tax {pre['cagr']:.1%}, market fall {pre['worst_fall']:.1%}. "
                  f"Training before tax {tr['cagr']:.1%}.", "", "| Regime | Other income | After tax a year | Worst fall (tax paid included) |", "|---|---|---|---|"]
        for regime in ("new", "old"):
            for inc in LT.INCOMES:
                st = run(m, cap, split, D, tax_fn=LT.tax_fn(rules, TaxProfile(regime, Decimal(int(inc)))))
                lines.append(f"| {regime} | Rs {inc / 1e5:.0f} lakh | {st['cagr']:.1%} | {st['worst_fall']:.1%} |")
                print(f"Rs {cap / 1e5:.0f} lakh", lines[-1], flush=True)
        lines.append("")
    (G.OUT / "mixed.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:4 + k]))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8)
