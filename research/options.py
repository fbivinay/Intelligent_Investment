"""Monthly NIFTY option strategies, per rupee of Nifty exposure, 2016-2026 (data/processed/nifty_options.parquet from research.options_build).

    python -m research.options

Each month, at the close of the first trading day after a monthly expiry, an option of the next monthly expiry is bought or sold at its close (a contract
with no trade that day: none is taken, the month is skipped), at the strike nearest to `moneyness` x the Nifty close, and held to expiry, where it is worth
its intrinsic value on the Nifty close. Notional: one rupee of Nifty per rupee of account. Costs (assumed, labelled): `slip` index points a side, STT on
the option's sale value (0.05% to 2023-03, 0.0625% to 2024-09, 0.1% to 2026-03, 0.15% after) and on the intrinsic value at expiry for a bought option
(0.125%), exchange and other charges 0.06% of premium. Before tax: option income is business income, taxed at slab rates by the caller.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def _stt_sell(d):
    return 0.0005 if d < pd.Timestamp("2023-04-01") else 0.000625 if d < pd.Timestamp("2024-10-01") else 0.001 if d < pd.Timestamp("2026-04-01") else 0.0015


def load():
    o = pd.read_parquet(ROOT / "data" / "processed" / "nifty_options.parquet")
    n = pd.read_csv(ROOT / "data" / "processed" / "nse_index_daily.csv", parse_dates=["date"])
    nifty = n[n.name == "Nifty 50"].set_index("date").close
    fut = pd.read_csv(ROOT / "data" / "processed" / "nse_index_futures_daily.csv", parse_dates=["date", "expiry"])
    monthly = sorted(set(fut[fut.symbol == "NIFTY"].groupby("date").expiry.min()))
    return o, nifty, [e for e in monthly if e <= nifty.index[-1]]


def monthly(o, nifty, expiries, kind="PE", moneyness=1.0, side=-1, slip=1.0):
    """Rows per month: entry day, expiry, strike, premium, payoff, P&L per rupee of Nifty (side -1 sells, +1 buys)."""
    days = nifty.index
    rows = []
    for prev, nxt in zip(expiries[:-1], expiries[1:]):
        k = days.searchsorted(prev, side="right")
        if k >= len(days) or days[k] >= nxt:
            continue
        d = days[k]
        s = nifty.iloc[k]
        chain = o[(o.date == d) & (o.expiry == nxt) & (o.type == kind) & (o.contracts > 0)]
        if chain.empty:
            continue
        row = chain.iloc[(chain.strike - moneyness * s).abs().argmin()]
        prem = float(row.close)
        st = nifty.asof(nxt)
        intrinsic = max(row.strike - st, 0.0) if kind == "PE" else max(st - row.strike, 0.0)
        cost = slip + 0.0006 * prem
        if side < 0:
            cost += _stt_sell(d) * prem
            pnl = prem - intrinsic - cost
        else:
            cost += 0.00125 * intrinsic
            pnl = intrinsic - prem - cost
        rows.append(dict(entry=d, expiry=nxt, spot=s, strike=row.strike, premium=prem, intrinsic=intrinsic, pnl=pnl / s))
    return pd.DataFrame(rows)


def main():
    o, nifty, ex = load()
    out = []
    for kind, side, m in (("PE", -1, 1.0), ("PE", -1, 0.97), ("PE", -1, 0.95), ("CE", -1, 1.02), ("CE", -1, 1.05), ("PE", 1, 0.95), ("PE", 1, 0.90)):
        df = monthly(o, nifty, ex, kind, m, side)
        yrs = (df.expiry.iloc[-1] - df.entry.iloc[0]).days / 365.25
        out.append(dict(strategy=f"{'sell' if side < 0 else 'buy'} {kind} {m:g}", months=len(df), pnl_a_year=df.pnl.sum() / yrs, worst_month=df.pnl.min(),
                        best_month=df.pnl.max(), win=(df.pnl > 0).mean()))
        df.to_csv(ROOT / "research" / "out" / f"opt_{'sell' if side < 0 else 'buy'}_{kind}_{m:g}.csv", index=False)
    print(pd.DataFrame(out).round(4).to_string(index=False))


if __name__ == "__main__":
    main()
