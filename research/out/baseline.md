# Baseline: plain holding against the first strategy families

Design period 2010-04-01 to 2023-09-29; one reference account per run (Rs 10 lakh, new tax regime, other income Rs 12 lakh); charges, slippage and tax by each transaction's own date; the drawdown governor on at the risk level's cap. Every number is a row of `research/out/trials.csv`.

**All of this is in-sample.** The ledger holds 6231 runs; the best of many beating plain holding is what chance alone produces. The walk-forward selector and the deflated Sharpe ratio decide, not this table. Worst drawdown is before tax, like the cap. Dividends the ETFs paid are not added back.

## Other investments (bought on day one and held, no governor)

| Strategy | After-tax growth a year | After selling all | Worst drawdown | From 2013-04: growth | From 2013-04: drawdown | Turnover a year | Tax | |
|---|---|---|---|---|---|---|---|---|
| Nifty BeES | 10.9% | 10.5% | 36.3% | 13.5% | 36.3% | 0.02 | Rs 0 |  |
| Junior BeES | 11.5% | 11.2% | 39.1% | 14.7% | 38.7% | 0.02 | Rs 0 |  |
| Bank BeES | 12.1% | 11.8% | 47.6% | 14.0% | 47.6% | 0.02 | Rs 10 |  |
| Gold BeES | 8.5% | 8.0% | 27.1% | 5.5% | 25.5% | 0.02 | Rs 80 |  |
| Liquid fund | 7.1% | 6.8% | 0.2% | 6.8% | 0.2% | 0.02 | Rs 70 |  |

## Conservative: drawdown cap 10%

| Strategy | After-tax growth a year | After selling all | Worst drawdown | From 2013-04: growth | From 2013-04: drawdown | Turnover a year | Tax | vs S0 (points) |
|---|---|---|---|---|---|---|---|---|
| S0|cap=0.1|band=0.01 (plain holding) | 6.9% | 6.9% | 9.1% | 8.0% | 9.1% | 0.31 | Rs 39,120 | +0.0 |
| S1|weights=0/0.1/0.1/0.1/0.7,rebalance=year|band=0.01 (best of 1267 within the cap, of 2002) | 8.4% | 8.2% | 7.4% | 8.4% | 7.4% | 0.08 | Rs 32,900 | +1.5 |
| S2|length=100,weighting=equal|band=0.01 (best of 10 within the cap, of 12) | 6.9% | 6.9% | 8.5% | 7.7% | 8.5% | 7.14 | Rs 269,990 | -0.0 |
| S3|lookback=126,k=1,every=month|band=0.01 (best of 4 within the cap, of 18) | 7.1% | 7.1% | 9.6% | 7.2% | 9.6% | 3.64 | Rs 425,670 | +0.1 |
| S4|target=0.06,lookback=60|band=0.05 (best of 20 within the cap, of 20) | 7.3% | 7.3% | 9.1% | 7.6% | 9.1% | 0.85 | Rs 194,490 | +0.4 |
| S5|start=0.15,end=0.35|band=0.05 (best of 12 within the cap, of 12) | 6.6% | 6.6% | 10.0% | 8.0% | 10.0% | 2.21 | Rs 154,710 | -0.3 |
| S6|tcn-L63-c20|band=0.05 (best of 8 within the cap, of 12) | 6.5% | 6.4% | 9.5% | 6.9% | 9.5% | 1.62 | Rs 137,310 | -0.4 |

585 of 2076 other trials beat S0 after tax, 513 of them within the cap.

## Balanced: drawdown cap 20%

| Strategy | After-tax growth a year | After selling all | Worst drawdown | From 2013-04: growth | From 2013-04: drawdown | Turnover a year | Tax | vs S0 (points) |
|---|---|---|---|---|---|---|---|---|
| S0|cap=0.2|band=0.01 (plain holding) | 6.6% | 6.5% | 17.8% | 8.7% | 17.8% | 0.42 | Rs 44,020 | +0.0 |
| S1|weights=0/0.2/0.2/0.4/0.2,rebalance=year|band=0.01 (best of 2002 within the cap, of 2002) | 9.7% | 9.5% | 15.2% | 9.3% | 15.2% | 0.19 | Rs 75,420 | +3.0 |
| S2|length=200,weighting=invvol|band=0.01 (best of 12 within the cap, of 12) | 7.4% | 7.3% | 16.8% | 8.3% | 16.8% | 8.63 | Rs 365,810 | +0.8 |
| S3|lookback=126,k=2,every=quarter|band=0.01 (best of 18 within the cap, of 18) | 9.3% | 9.2% | 16.6% | 11.0% | 16.0% | 1.85 | Rs 203,440 | +2.6 |
| S4|target=0.09,lookback=60|band=0.05 (best of 20 within the cap, of 20) | 8.1% | 8.0% | 16.3% | 9.0% | 16.3% | 1.09 | Rs 133,810 | +1.5 |
| S5|start=0.05,end=0.35|band=0.01 (best of 12 within the cap, of 12) | 6.8% | 6.7% | 17.3% | 8.3% | 17.3% | 2.19 | Rs 81,550 | +0.2 |
| S6|gru-L63-c5|band=0.05 (best of 12 within the cap, of 12) | 6.9% | 6.9% | 17.6% | 7.0% | 17.6% | 1.16 | Rs 135,420 | +0.3 |

1909 of 2076 other trials beat S0 after tax, 1909 of them within the cap.

## Aggressive: drawdown cap 30%

| Strategy | After-tax growth a year | After selling all | Worst drawdown | From 2013-04: growth | From 2013-04: drawdown | Turnover a year | Tax | vs S0 (points) |
|---|---|---|---|---|---|---|---|---|
| S0|cap=0.3|band=0.01 (plain holding) | 6.8% | 6.6% | 25.9% | 9.3% | 25.9% | 0.41 | Rs 37,290 | +0.0 |
| S1|weights=0/0.4/0.2/0.4/0,rebalance=year|band=0.01 (best of 2002 within the cap, of 2002) | 10.7% | 10.4% | 21.3% | 11.1% | 21.3% | 0.21 | Rs 67,500 | +3.9 |
| S2|length=100,weighting=equal|band=0.05 (best of 12 within the cap, of 12) | 7.3% | 7.2% | 13.9% | 8.4% | 13.9% | 8.77 | Rs 255,530 | +0.5 |
| S3|lookback=126,k=2,every=quarter|band=0.01 (best of 18 within the cap, of 18) | 10.8% | 10.7% | 21.4% | 12.9% | 18.6% | 1.60 | Rs 282,750 | +4.0 |
| S4|target=0.15,lookback=20|band=0.05 (best of 20 within the cap, of 20) | 8.8% | 8.7% | 22.1% | 10.9% | 22.1% | 1.59 | Rs 119,340 | +2.0 |
| S5|start=0.15,end=0.25|band=0.05 (best of 12 within the cap, of 12) | 8.0% | 7.7% | 22.6% | 10.4% | 22.4% | 0.81 | Rs 25,520 | +1.2 |
| S6|gru-L63-c5|band=0.05 (best of 12 within the cap, of 12) | 7.6% | 7.6% | 22.5% | 7.5% | 22.5% | 1.11 | Rs 142,090 | +0.8 |

2012 of 2076 other trials beat S0 after tax, 2012 of them within the cap.

