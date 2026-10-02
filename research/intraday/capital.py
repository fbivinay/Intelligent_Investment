"""The safe six-strategy book with whole lots: what the money needs to be for the fractional-lot result to hold.

    python -m research.intraday.capital
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.intraday import combine as C, engine as E, grid as G

BOOK = ["theta|strangle2|entry=15|legsl=0.25|tgt=0.5|sl=1.0|days=nonexpiry|vix=(-3.0, 3.0)",
        "theta|strangle3|entry=15|legsl=0.25|tgt=None|sl=None|days=nonexpiry|vix=None",
        "dir|debit_spread|signal=orb_reversal|tgt=None|sl=None|days=all",
        "theta|butterfly4|entry=5|legsl=0.4|tgt=0.5|sl=1.0|days=nonexpiry|vix=(-3.0, 3.0)",
        "dir|buy_atm|signal=rsi_momentum|tgt=None|sl=None|days=all",
        "theta|strangle2|entry=105|legsl=0.5|tgt=0.5|sl=1.0|days=nonexpiry|vix=(-3.0, 3.0)"]
COMMON = 1.23                     # the book's common scale (combine_6_safe.md)


def main():
    G._init()
    d = G._D
    grid = pd.read_csv(G.OUT / "grid.csv").set_index("name")
    split = int(np.searchsorted(d.T["days"], G.SPLIT))
    trades = {n: E.trades(d, C._spec(n), G._SIG) for n in BOOK}
    for capital in (1e6, 2.5e6, 5e6, 1e7, 2.5e7):
        for name, lo, hi in (("training", 0, split), ("test", split, len(d.lot))):
            parts = [E.account(d, trades[n], capital=capital / len(BOOK), scale=grid.at[n, "scale"] * COMMON, lo=lo, hi=hi, whole=True).equity for n in BOOK]
            eq = sum(parts)
            y = (eq.index[-1] - eq.index[0]).days / 365.25
            print(f"Rs {capital / 1e5:.0f} lakh {name}: {(eq.iloc[-1] / eq.iloc[0]) ** (1 / y) - 1:.1%} a year, worst fall {(1 - eq / eq.cummax()).max():.1%}")


if __name__ == "__main__":
    main()
