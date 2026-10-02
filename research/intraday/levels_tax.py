"""The risk levels after the exact tax of each year, by regime and other income: research/intraday/levels.py's book and sizes, taxed by engine.tax.

    python -m research.intraday.levels_tax        # writes research/out/intraday/levels_tax.md

Option income is business income (slab rates, surcharge, cess, the 87A rebate where it applies, losses carried for business income only); the liquid fund's
gain is taxed each year at slab rates as if redeemed (a simplification: a real holding defers it). Other income is the taxpayer's own income besides this.
No dividends: options pay none and the liquid fund is a growth plan. Before 2020-21 there was only the old regime, so a new-regime taxpayer is taxed by it then.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd

from engine.rules import Rules
from engine.tax import Business, Carry, TaxProfile, investment_tax
from engine.trace import const
from research.intraday import capital as K, combine as C, engine as E, grid as G

ROOT = Path(__file__).resolve().parents[2]
LEVELS = {"Low (Rs 50 lakh, 5%)": (50e5, 0.05), "Low with Rs 10 lakh (5%)": (10e5, 0.05), "Medium (Rs 25 lakh, 10%)": (25e5, 0.10),
          "High (Rs 10 lakh, 15%)": (10e5, 0.15)}
INCOMES = (0, 12e5, 25e5, 60e5, 150e5)


def tax_fn(rules, profile):
    def f(fy, pnl, interest, state):
        carry = state or Carry()
        it = investment_tax(rules, fy, profile, [], carry, interest=const("Liquid fund gain", Decimal(repr(round(float(max(interest, 0.0)), 2)))),
                            business=Business(const("Option income after charges", Decimal(repr(round(float(pnl), 2)))), const("Costs", Decimal(0))))
        return float(it.extra.value), it.with_items.carry_out
    return f


def main():
    rules = Rules.load(ROOT / "rules")
    G._init()
    d = G._D
    grid = pd.read_csv(G.OUT / "grid.csv").set_index("name")
    split, D = int(np.searchsorted(d.T["days"], G.SPLIT)), len(d.lot)
    books = [E.arrays(d, E.trades(d, C._spec(n), G._SIG)) for n in K.BOOK]
    base = np.array([grid.at[n, "scale"] for n in K.BOOK]) / len(K.BOOK)
    days = d.T["days"]
    run = lambda m, cap, lo, hi, **kw: E.stats_arr(E.account_multi([d] * len(books), books, base * m, cap, lo, hi, **kw), days[lo:hi])  # noqa: E731
    sizes = {}
    for limit in {v[1] for v in LEVELS.values()}:
        m = 1.0
        for _ in range(10):
            # The fall is measured on the after-tax balance (the yearly tax payment counts as a drop). Sizing to the market's own fall (before tax) gave
            # 100-280% a year at 5-14% falls: the account then uses its whole margin (about 8 times its money), and the modelled minute paths are smoother
            # than real markets on crash days, so that risk is understated. This stricter measure keeps a buffer against that model error.
            m *= limit / run(m, 1e9, 0, split)["worst_fall"]
        sizes[limit] = m
    lines = ["# Risk levels after the exact tax, by regime and other income", "", "Sizes fitted on 2016-2021 so the worst fall of the after-tax balance (flat 31.2% tax) is the limit: a buffer, see the code. "
             "Test years 2022-01 to 2026-05, whole lots, one account. Before tax and charges, and before tax, do not depend on the taxpayer.", ""]
    for name, (cap, limit) in LEVELS.items():
        m = sizes[limit]
        gross, pre = run(m, cap, split, D, tax=False, charges=False), run(m, cap, split, D, tax=False)
        trp = run(m, cap, 0, split, tax=False)
        lines += [f"## {name}", "", f"Test: before tax and charges {gross['cagr']:.1%} a year; before tax {pre['cagr']:.1%}; worst fall (before tax) {pre['worst_fall']:.1%}. "
                  f"Training: before tax {trp['cagr']:.1%}, worst fall {trp['worst_fall']:.1%}.", "",
                  "| Regime | Other income a year | After tax a year | Worst fall of the after-tax balance (tax payments included) |", "|---|---|---|---|"]
        for regime in ("new", "old"):
            for inc in INCOMES:
                st = run(m, cap, split, D, tax_fn=tax_fn(rules, TaxProfile(regime, Decimal(int(inc)))))
                lines.append(f"| {regime} | Rs {inc / 1e5:.0f} lakh | {st['cagr']:.1%} | {st['worst_fall']:.1%} |")
                print(name, lines[-1], flush=True)
        lines.append("")
    (G.OUT / "levels_tax.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
