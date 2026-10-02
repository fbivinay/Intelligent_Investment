"""One table of trading days for the intraday option work: the Nifty and India VIX minute paths (09:15 to 15:29, 375 bars) and, for the nearest and next
NIFTY option expiries, each strike's implied volatility at the open and at the close, backed out of the exchange's own open and close prices.

    python -m research.intraday.prep      # writes data/processed/intraday_days.npz

Sources: data/raw/minute/*.csv (Kaggle dataset debashis74017/nifty-50-minute-data, 2015-01 to 2026-05) and data/processed/nifty_options.parquet (the F&O
bhavcopies). Each strike's volatility comes from its out-of-the-money option (the liquid side) and prices both the call and the put. The option open is paired
with the Nifty at 09:15, the close with the Nifty at 15:29. A strike with no trade that day or a price outside the no-arbitrage range has no volatility (NaN).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from research.intraday import pricing as BS

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "minute"
OUT = ROOT / "data" / "processed" / "intraday_days.npz"
BARS = 375                      # 09:15 to 15:29
STEP = 50
OFFS = np.arange(-20, 21)       # strikes around the 09:15 at-the-money strike, in steps of 50
R = 0.065                       # assumed rupee rate for pricing (labelled)


def minutes(name: str) -> pd.DataFrame:
    d = pd.read_csv(RAW / name, parse_dates=["date"])
    d["day"] = d.date.dt.normalize()
    d["bar"] = (d.date.dt.hour * 60 + d.date.dt.minute) - (9 * 60 + 15)
    d = d[(d.bar >= 0) & (d.bar < BARS)]
    return d.pivot_table(index="day", columns="bar", values="close").reindex(columns=range(BARS)).ffill(axis=1).bfill(axis=1)


def years_left(day: pd.Timestamp, expiry: pd.Timestamp, bar: int) -> float:
    """Calendar time from the bar's minute to 15:30 on the expiry day, in years."""
    now = day + pd.Timedelta(minutes=9 * 60 + 15 + bar)
    return max((expiry + pd.Timedelta(hours=15, minutes=30) - now).total_seconds(), 60.0) / (365.25 * 86400)


def build(out: Path = OUT) -> None:
    spot = minutes("nifty50_minute.csv")
    vix = minutes("vix_minute.csv").reindex(spot.index).ffill()
    o = pd.read_parquet(ROOT / "data" / "processed" / "nifty_options.parquet")
    o = o[o.date.isin(spot.index)]
    days = sorted(set(spot.index) & set(o.date))
    D, K = len(days), len(OFFS)
    exp = np.zeros((D, 2), dtype="datetime64[D]")
    atm = np.zeros(D)
    iv = np.full((D, 2, 2, K), np.nan)            # day, expiry slot (nearest, next), open/close, strike
    px = np.full((D, 2, 2, 2, K), np.nan)         # day, slot, open/close, CE/PE, strike: the exchange's prices, for checks
    hl = np.full((D, 2, 2, 2, K), np.nan)         # day, slot, high/low, CE/PE, strike
    by_day = dict(tuple(o.groupby("date")))
    for i, d in enumerate(days):
        s0, s1 = spot.at[d, 0], spot.at[d, BARS - 1]
        atm[i] = round(s0 / STEP) * STEP
        g = by_day[d]
        expiries = sorted(e for e in g.expiry.unique() if e >= d)[:2]
        for slot, e in enumerate(expiries):
            exp[i, slot] = np.datetime64(e.date())
            c = g[(g.expiry == e) & (g.contracts > 0)].set_index(["type", "strike"])
            strikes = atm[i] + OFFS * STEP
            for t, side in enumerate(("CE", "PE")):
                for j, k in enumerate(strikes):
                    if (side, k) in c.index:
                        row = c.loc[(side, k)]
                        row = row.iloc[0] if isinstance(row, pd.DataFrame) else row
                        px[i, slot, 0, t, j], px[i, slot, 1, t, j] = row.open, row.close
                        hl[i, slot, 0, t, j], hl[i, slot, 1, t, j] = row.high, row.low
            for when, (s, bar) in enumerate(((s0, 0), (s1, BARS - 1))):
                T = years_left(pd.Timestamp(d), pd.Timestamp(e), bar)
                otm_put = strikes < s
                price = np.where(otm_put, px[i, slot, when, 1], px[i, slot, when, 0])
                iv[i, slot, when] = BS.implied(price, s, strikes, T, R, np.where(otm_put, -1, 1))
        if i % 250 == 0:
            print(f"\r{i}/{D}", end="", file=sys.stderr)
    np.savez_compressed(out, days=np.array(days, dtype="datetime64[D]"), spot=spot.loc[days].to_numpy(), vix=vix.loc[days].to_numpy(), expiry=exp, atm=atm,
                        offs=OFFS, iv=iv, px=px, hl=hl)
    print(f"\n{D} days, {days[0].date()} to {days[-1].date()}", file=sys.stderr)


def load(path: Path = OUT) -> dict:
    z = np.load(path)
    return {k: z[k] for k in z.files}


if __name__ == "__main__":
    build()
