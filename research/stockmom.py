"""Stock momentum through the exact simulator: charges by the engine (listed shares: STT 0.1% on both sides), slippage, FIFO lots, yearly tax by each
sale's own date, both endings. Data: data/processed/stocks_eq.parquet (python -m research.stocks_build), every EQ instrument 2016-01 to 2026-09.

    python -m research.stockmom

Rule (the published momentum-index method, fixed before this run): on the first trading day of each quarter, after the close, the universe is the `top`
most traded stocks (median daily value over 126 days, a year of history, traded in the last week); the score is the mean of the 6- and 12-month returns over
the yearly volatility; the best `n` are held in equal parts, drifting until the next quarter. Bought at the next day's VWAP. No drawdown guard.
Stocks only: EQ also lists exchange-traded fund units (liquid, gold, silver, index ETFs, an ISIN of INF...). They are left out of the ranking (a liquid
ETF's tiny volatility gave it the top score, and the engine would charge and tax a fund as a share); the Nifty ETF is still read for the market switch.
A stock that stops trading keeps its last price until the next rebalance sells it: a stand-in, a real delisting can pay less.
"""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from engine.rules import Rules
from research import baseline as B, panel as P, sim, strategies as st

ROOT = Path(__file__).resolve().parents[1]
START = "2017-04-01"
PARQUET = ROOT / "data" / "processed" / "stocks_eq.parquet"


@lru_cache(maxsize=1)
def funds() -> frozenset[str]:
    """The exchange-traded fund units in the stock file: symbols with a mutual fund unit's ISIN (INF...). Never ranked."""
    df = pd.read_parquet(PARQUET, columns=["symbol", "isin"])
    return frozenset(df.symbol[df["isin"].astype(str).str.startswith("INF")])


def wide():
    df = pd.read_parquet(PARQUET, columns=["date", "symbol", "high", "low", "close", "prev_close", "qty", "value"])
    r = df.close / df.prev_close - 1
    df["r"] = r.where(r.abs() < 0.5, 0.0)          # a >50% day is a missed corporate action or a relisting, not a return
    f = {c: df.pivot(index="date", columns="symbol", values=c) for c in ("r", "high", "low", "close", "qty", "value")}
    traded = f["r"].notna()
    idx = (1 + f["r"].fillna(0)).cumprod().where(traded.cumsum() > 0).ffill()
    return f, idx, traded


def picks(idx, value, traded, n=30, top=500, start=START, trend=0, safe=()):
    """{decision day: chosen symbols}, decided after that day's close with data up to it. With `trend` (days), the market switch is checked on the first
    trading day of each month: while the Nifty ETF closes below its `trend`-day average the money goes to `safe` (empty: the liquid fund); back above it, the
    stocks are ranked afresh. Without it, only the quarters' first days count."""
    dates = idx.index
    days = pd.Series(dates, index=dates)
    d0 = days[days >= start]
    quarter = set(d0.groupby(d0.dt.to_period("Q")).first().values)
    first = d0.groupby(d0.dt.to_period("M" if trend else "Q")).first().values
    medval = value.fillna(0).rolling(126, min_periods=100).median()
    age = traded.cumsum()
    market = idx["NIFTYBEES"]
    up = market > market.rolling(trend or 1).mean() if trend else pd.Series(True, index=dates)
    out, invested = {}, False
    for d in first:
        p = dates.get_loc(d)
        if not up.iloc[p]:
            if invested or not out:
                out[d] = list(safe)
            invested = False
            continue
        if invested and d not in quarter:
            continue
        out[d] = list(score(idx, medval, age, traded, p, top).dropna().nlargest(n).index)
        invested = True
    return out


def score(idx, medval, age, traded, p, top=500):
    """The trend score of each share in the universe on day index p, from data up to that day: among the `top` most traded shares (median daily value
    over 126 days; fund units left out) with a year of history and a trade in the last week, the mean of the 6- and 12-month returns over the yearly
    volatility."""
    live = (age.iloc[p] >= 252) & traded.iloc[p - 5:p + 1].any() & ~age.columns.isin(funds())
    uni = medval.iloc[p][live].nlargest(top).index
    i = idx[uni]
    vol = np.log(i.iloc[p - 252:p + 1]).diff().std() * np.sqrt(252)
    return ((i.iloc[p] / i.iloc[p - 126] - 1) + (i.iloc[p] / i.iloc[p - 252] - 1)) / 2 / vol


def stock_panel(f, idx, symbols, start=START):
    """A research Panel of the symbols on the trading days from `start`: adjusted prices (the return chain scaled to the last close), the day's VWAP,
    the liquid fund as the cash leg. Days a stock has no row carry its last price (first price before it trades) and no traded value."""
    days = idx.index[idx.index >= start]
    sym = list(symbols)
    scale = (f["close"][sym].ffill().iloc[-1] / idx[sym].iloc[-1])
    adj = (idx[sym] * scale).loc[days]
    ratio = adj / f["close"][sym].loc[days]                               # the adjustment of each published price on its day
    vwap = (f["value"][sym] / f["qty"][sym]).loc[days] * ratio
    hi, lo = f["high"][sym].loc[days] * ratio, f["low"][sym].loc[days] * ratio
    fill = lambda x: x.ffill().bfill().to_numpy()                        # noqa: E731
    close = fill(adj)
    vw = vwap.where((vwap >= lo * 0.99) & (vwap <= hi * 1.01))
    vw = vw.fillna(adj).ffill().bfill().to_numpy()
    d = [x.date() for x in days]
    nan = np.full(len(d), np.nan)
    return P.Panel(dates=np.array(d, dtype="datetime64[D]"), assets=sym, open=close, high=fill(hi.fillna(adj)), low=fill(lo.fillna(adj)), close=close,
                   value=f["value"][sym].loc[days].fillna(0).to_numpy(), vwap=vw, cash=P._cash_index(P.DATA, d), nifty=nan, vix=nan, pe=nan, pb=nan)


def weights(panel, chosen: dict) -> np.ndarray:
    dates = pd.DatetimeIndex(panel.dates.astype("datetime64[ns]"))
    T, n = len(dates), len(panel.assets)
    col = {s: j for j, s in enumerate(panel.assets)}
    target = np.zeros((T, n + 1))
    reset = np.zeros(T, dtype=bool)
    target[:, n] = 1.0                                                     # cash until the first pick
    for d, syms in chosen.items():
        t = dates.get_loc(d)
        target[t:] = 0.0
        if syms:
            target[t:, [col[s] for s in syms]] = 1.0 / len(syms)
        else:
            target[t:, n] = 1.0                                            # the market switch is off: the liquid fund
        reset[t] = True
    return st._drifting(panel, target, reset)


def run(n=30, top=500, capital=1e6, harvest=True, trend=0, safe=()):
    f, idx, traded = wide()
    chosen = picks(idx, f["value"], traded, n, top, trend=trend, safe=safe)
    syms = sorted({s for v in chosen.values() for s in v})
    panel = stock_panel(f, idx, syms)
    w = weights(panel, chosen)
    rules = Rules.load(ROOT / "rules")
    cfg = sim.SimConfig(capital=capital, cap=1.0, governor=False, harvest=harvest, max_orders=200_000)
    res = sim.simulate(panel, w, rules, cfg)
    return panel, res, rules


def main():
    rows = []
    for n, top in ((30, 500), (20, 500), (50, 500), (30, 200)):
        panel, res, rules = run(n, top)
        rows.append(dict(n=n, top=top, **B.measure(panel, res, B.fixed_total(panel, rules), 1e6)))
        print(rows[-1], file=sys.stderr, flush=True)
    pd.DataFrame(rows).to_csv(ROOT / "research" / "out" / "stockmom.csv", index=False)


if __name__ == "__main__":
    main()
