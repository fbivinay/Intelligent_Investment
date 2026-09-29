"""What ₹1,00,000 put in on IBIT's launch day is worth in hand today -- in rupees,
after every Indian tax and charge -- across the choices an Indian investor has.

  Bank FD          1-year SBI FD, renewed; interest taxed at slab every year
  Nifty 50 ETF     NIFTYBEES on NSE; 20% tax under 12 months, 12.5% after, first ₹1.25 lakh
                   of long-term gain per year tax-free
  Gold ETF (India) GOLDBEES on NSE; slab under 12 months, 12.5% after
  Bitcoin in India on an Indian exchange (VDA): 30% + cess on gains, 0.2% fee + GST each way
  IBIT, held       US spot Bitcoin ETF via LRS; 1.5% forex each way; slab under 24 months,
                   12.5% + cess after
  Our model        the ETF model via LRS, simulated in rupees so the rupee's fall
                   against the dollar is taxed as the gain it legally is

Every value is liquidation value: sell everything that day, pay the tax, keep the rest.
FD rates are approximate published SBI 1-year rates. Tax rules as understood in 2026 --
confirm with a Chartered Accountant.

    python ml/india_compare.py
"""

from functools import cache

import numpy as np
import pandas as pd

from etf_data import IBIT_START, load, yahoo
from etf_model import signals
from etf_tax_sim import EtfCosts, run

CAPITAL = 100_000.0
FD_RATE = {2024: 0.068, 2025: 0.065, 2026: 0.0625}     # SBI 1-year FD, approximate
CESS = 1.04


@cache
def nse(ticker: str) -> pd.Series:
    s = yahoo(ticker, start=1704067200)["close"]
    s.index = s.index + pd.Timedelta(days=1)       # NSE bars are dated the previous day in New York time
    return s


def held(price: pd.Series, days: pd.DatetimeIndex, st_rate, lt_rate, lt_days, cost=0.0,
         exempt=0.0, fx=0.0) -> pd.Series:
    """Buy once on day one, then the in-hand value if sold on each later day."""
    p = price.reindex(days, method="ffill")
    put = CAPITAL * (1 - fx)
    units = put * (1 - cost) / p.iloc[0]
    gross = units * p * (1 - cost)
    gain = gross - put
    age = (days - days[0]).days
    rate = np.where(age >= lt_days, lt_rate, st_rate)
    taxable = np.where(age >= lt_days, np.maximum(gain - exempt, 0), np.maximum(gain, 0))
    return pd.Series((gross - rate * taxable) * (1 - fx), index=days)


def fd(days: pd.DatetimeIndex, slab: float) -> pd.Series:
    daily = np.array([FD_RATE.get(d.year, 0.0625) * (1 - slab) / 365 for d in days])
    gap = np.r_[0, np.diff((days - days[0]).days)]
    return pd.Series(CAPITAL * np.cumprod(1 + daily * gap), index=days)


@cache
def market():
    """Fetched once per run: (btc, gold, tbill, usdinr, BTC in rupees)."""
    return (*load(), yahoo("BTC-INR", start=1704067200)["close"])


def model_in_rupees(slab: float, w: dict | None = None) -> tuple:
    """The ETF model and IBIT buy & hold, with every price turned into rupees first.
    `w` overrides the model weights {"BTC", "GLD", "TB"} (e.g. the recorded decisions)."""
    btc, gold, tbill, usdinr, _ = market()
    s = signals(btc["close"], gold["close"])
    days = btc.loc[IBIT_START:].index
    fx = usdinr.reindex(days, method="ffill")
    rate = tbill.reindex(days, method="ffill").fillna(0)
    bill = (1 + rate * np.r_[0, np.diff((days - days[0]).days)] / 365).cumprod()   # T-bill ETF, in dollars
    px = {"BTC": btc.loc[days, ["open", "close"]].mul(fx, axis=0),
          "GLD": gold.loc[days, ["open", "close"]].mul(fx, axis=0),
          "TB": pd.DataFrame({"open": bill * fx, "close": bill * fx})}
    w = w or {"BTC": s["w_btc"], "GLD": s["w_gold"], "TB": s["w_cash"]}
    c = EtfCosts(slab=slab, cash_fee=0.0)
    model = run(px, w, None, costs=c, capital=CAPITAL).equity
    hold = run(px, {"BTC": pd.Series(1.0, days)}, None, costs=c, capital=CAPITAL).equity
    return model, hold, days, fx


def compare(slab: float = 0.312, w: dict | None = None) -> pd.DataFrame:
    model, hold, days, fx = model_in_rupees(slab, w)
    btc_inr = market()[4]
    return pd.DataFrame({
        "Our model (IBIT + gold, via LRS)": model,
        "IBIT, bought and held (via LRS)": hold,
        "Gold ETF in India (GOLDBEES)": held(nse("GOLDBEES.NS"), days, slab, 0.125 * CESS, 365),
        "Nifty 50 ETF (NIFTYBEES)": held(nse("NIFTYBEES.NS"), days, 0.20 * CESS, 0.125 * CESS, 365,
                                         exempt=125_000),
        "Bitcoin on an Indian exchange": held(btc_inr, days, 0.30 * CESS, 0.30 * CESS, 10**6,
                                              cost=0.002 * 1.18),
        "Bank FD (SBI, 1 year, renewed)": fd(days, slab),
    })


def main() -> None:
    for slab in (0.312, 0.104):
        t = compare(slab)
        yrs = (t.index[-1] - t.index[0]).days / 365.25
        print(f"\n₹1,00,000 from {t.index[0]:%d %b %Y} to {t.index[-1]:%d %b %Y}, in hand after tax "
              f"(your slab {slab:.1%} incl. cess)")
        for name, v in t.iloc[-1].sort_values(ascending=False).items():
            dd = (t[name] / t[name].cummax() - 1).min()
            print(f"  {name:<36} ₹{v:>10,.0f}   {((v / CAPITAL) ** (1 / yrs) - 1):+6.1%}/yr   worst drop {dd:.0%}")


if __name__ == "__main__":
    main()
