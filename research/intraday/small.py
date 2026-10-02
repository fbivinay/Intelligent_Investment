"""Books for small accounts, whole lots, one shared account: Rs 1 lakh at a 5% worst fall and Rs 3 lakh at a 12% worst fall.

    python -m research.intraday.small        # reads the grids, writes research/out/intraday/small.md

Candidates: the best 150 settings of each index's grid by training growth. Greedy on the training years (2016-01 to 2021-12) only: the best single
(setting, size) whose training worst fall stays within 80% of the limit (a margin for unseen years, fixed before any run), then up to four more, each the
addition that raises training growth most within that fall. Size: the share of the equity whose margin a strategy may use, from SIZES. The book then runs
unchanged on the test years (2022-01 to 2026-05).
"""
from __future__ import annotations

import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

from research.intraday import engine as E, grid as G, signals as S

TARGETS = {"low": (1e5, 0.05), "medium": (3e5, 0.12)}
SIZES = (0.1, 0.2, 0.35, 0.5, 0.75, 1.0)
BUFFER = 0.8
MIN_ACTIVE = 0.5                # the book trades at least one lot on half the training days: a book that cannot afford its lots is not a result
TOP = 150
_C = None


def _load():
    out = []
    for sym, f in (("NIFTY", "grid.csv"), ("BANKNIFTY", "grid_BANKNIFTY.csv")):
        d = E.load(sym)
        sig = S.build(d.T)
        g = pd.read_csv(G.OUT / f).dropna(subset=["train_cagr"]).sort_values("train_cagr", ascending=False).head(TOP)
        specs = {s.name: s for s in G.specs()}
        for n in g.name:
            out.append((f"{sym}:{n}", d, E.arrays(d, E.trades(d, specs[n], sig))))
    return out


def _try(args):
    base, k, size, capital, split = args
    ds = [_C[j][1] for j, _ in base] + [_C[k][1]]
    bs = [_C[j][2] for j, _ in base] + [_C[k][2]]
    sc = [s for _, s in base] + [size]
    v, active = E.account_multi(ds, bs, sc, capital, 0, split, count=True)
    return k, size, {**E.stats_arr(v, ds[0].T["days"][:split]), "active": active / split}


def _init(c):
    global _C
    _C = c


def search(cands, capital, limit, split, workers=8):
    base, best = [], None
    with Pool(workers, initializer=_init, initargs=(cands,)) as pool:
        for _ in range(5):
            jobs = [(base, k, s, capital, split) for k in range(len(cands)) if k not in [j for j, _ in base] for s in SIZES]
            res = [r for r in pool.map(_try, jobs, chunksize=8) if r[2]["worst_fall"] <= limit * BUFFER and r[2]["active"] >= MIN_ACTIVE]
            if not res:
                break
            k, s, st = max(res, key=lambda r: r[2]["cagr"])
            if best is not None and st["cagr"] <= best["cagr"] + 0.002:
                break
            base, best = base + [(k, s)], st
            print(f"  + {cands[k][0]} size {s}: training {st['cagr']:.1%}, fall {st['worst_fall']:.1%}, trading days {st['active']:.0%}", file=sys.stderr, flush=True)
    return base, best


def main():
    cands = _load()
    split = int(np.searchsorted(cands[0][1].T["days"], G.SPLIT))
    days = cands[0][1].T["days"]
    lines = ["# Small-account books, whole lots", ""]
    for level, (capital, limit) in TARGETS.items():
        print(level, file=sys.stderr)
        base, tr = search(cands, capital, limit, split)
        if not base:
            lines += [f"## {level}: Rs {capital:,.0f}, worst fall limit {limit:.0%}", "", f"No book trades on half the training days within {limit * BUFFER:.0%}: the account cannot hold its lots at that risk.", ""]
            continue
        ds, bs, sc = [cands[k][1] for k, _ in base], [cands[k][2] for k, _ in base], [s for _, s in base]
        te = E.stats_arr(E.account_multi(ds, bs, sc, capital, split, len(days)), days[split:])
        full = E.stats_arr(E.account_multi(ds, bs, sc, capital, 0, len(days)), days)
        lines += [f"## {level}: Rs {capital:,.0f}, worst fall limit {limit:.0%}", "", "| Strategy | Size |", "|---|---|",
                  *[f"| {cands[k][0]} | {s} |" for k, s in base], "",
                  "| Window | Growth a year after tax | Worst fall |", "|---|---|---|",
                  f"| training 2016-2021 | {tr['cagr']:.1%} | {tr['worst_fall']:.1%} |", f"| test 2022-2026 | {te['cagr']:.1%} | {te['worst_fall']:.1%} |",
                  f"| whole period (one account) | {full['cagr']:.1%} | {full['worst_fall']:.1%} |", ""]
    (G.OUT / "small.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
