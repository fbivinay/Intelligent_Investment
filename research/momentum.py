"""Stock momentum screen on every NSE EQ stock, 2016-2026 (data/processed/stocks_eq.parquet from research.stocks_build).

    python -m research.momentum

Each rebalance day d (after the close): universe = the `top` most traded stocks by median daily value over the past 126 days, with a full year of
history; score = return from d-252 to d-21 (12-1 momentum) or a variant; hold the best `n` equal weight, bought at the next day's close, held to the next
rebalance's next close. A stock that stops trading is sold at its last close. Costs: `cost` per rupee traded each way (STT, charges, slippage).
Before tax: a screen to see if there is an edge worth the exact engine, not a result.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    df = pd.read_parquet(ROOT / "data" / "processed" / "stocks_eq.parquet")
    df["r"] = df.close / df.prev_close - 1
    ret = df.pivot(index="date", columns="symbol", values="r")
    val = df.pivot(index="date", columns="symbol", values="value")
    ret = ret.where(ret.abs() < 0.5)              # a >50% day is almost always a missed corporate action, not a return
    idx = (1 + ret.fillna(0)).cumprod().where(ret.notna().cumsum() > 0)
    traded = ret.notna()
    return idx.ffill(), val.fillna(0), traded


def backtest(idx, val, traded, n=20, top=200, freq="M", score="12-1", cost=0.0025, start="2017-04-01"):
    dates = idx.index
    days = pd.Series(dates, index=dates)
    rebal = days[days >= start].groupby(days[days >= start].dt.to_period(freq)).first().values   # first trading day of each period (decision at its close)
    pos = np.searchsorted(dates, rebal)
    medval = val.rolling(126, min_periods=100).median()
    age = traded.cumsum()
    equity = [1.0]
    eq_dates = [dates[pos[0] + 1]]
    held = pd.Series(dtype=float)
    turn = 0.0
    for k, p in enumerate(pos[:-1]):
        if p < 252:
            continue
        live = (age.iloc[p] >= 252) & traded.iloc[p - 5:p + 1].any()
        uni = medval.iloc[p][live].nlargest(top).index
        i = idx[uni]
        if score == "12-1":
            s = i.iloc[p - 21] / i.iloc[p - 252] - 1
        elif score == "6-1":
            s = i.iloc[p - 21] / i.iloc[p - 126] - 1
        elif score == "12":
            s = i.iloc[p] / i.iloc[p - 252] - 1
        elif score == "riskadj":   # Nifty momentum-index style: mean of 6m and 12m returns over yearly volatility
            vol = np.log(i.iloc[p - 252:p + 1]).diff().std() * np.sqrt(252)
            s = ((i.iloc[p] / i.iloc[p - 126] - 1) + (i.iloc[p] / i.iloc[p - 252] - 1)) / 2 / vol
        else:
            raise ValueError(score)
        pick = s.dropna().nlargest(n).index if n else uni
        new = pd.Series(1 / len(pick), index=pick)
        # weights drifted from last buy, versus the new equal weights
        t = new.subtract(held, fill_value=0).abs().sum()
        turn += t
        a, b = p + 1, pos[k + 1] + 1
        seg = idx[pick].iloc[a:b + 1]
        path = (seg / seg.iloc[0]).ffill().mean(axis=1).values
        base = equity[-1] * (1 - cost * t)
        equity += list(base * path[1:])
        eq_dates += list(seg.index[1:])
        end_w = (seg.iloc[-1] / seg.iloc[0]).ffill()
        held = end_w / end_w.sum()
        equity[-1] *= 1  # sold at the end only if dropped next time
    eq = pd.Series(equity, index=eq_dates)
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    dd = (eq / eq.cummax() - 1).min()
    return dict(cagr=cagr, maxdd=dd, turnover_yr=turn / yrs, years=yrs), eq


def main():
    idx, val, traded = load()
    rows = []
    for top in (100, 200, 500):
        for n in (0, 10, 20, 30, 50):
            for score in (("12-1", "6-1", "12", "riskadj") if n else ("12-1",)):
                for freq in ("M", "Q"):
                    m, _ = backtest(idx, val, traded, n=n, top=top, freq=freq, score=score)
                    rows.append(dict(top=top, n=n or "all", score=score if n else "equal", freq=freq, **m))
                    print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(ROOT / "research" / "out" / "momentum_screen.csv", index=False)


if __name__ == "__main__":
    main()
