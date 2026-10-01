# Out of sample: the walk-forward selector against plain holding

Each April the selector picks among every strategy using only data before that day; the picks are stitched into one account started on the first April with Rs 10 lakh, the drawdown governor on at the risk level's cap, charges, slippage and tax by each transaction's own date. Plain holding (S0) and the reference investments start the same day with the same money. Everything in this table is out of sample for the selection; the design (candidate list, margins, caps) was fixed with the design period in view, and the last three years stay untouched until the freeze.

## Conservative: drawdown cap 10%

| Account, fresh from 2013-04-01 to 2023-09-29 | After-tax growth a year | After selling all | Worst drawdown | Sharpe | Turnover a year | Tax |
|---|---|---|---|---|---|---|
| Selector, 1 standard error | 3.5% | 3.5% | 12.5% | -0.39 | 1.56 | Rs 70,800 |
| Selector, deflated margin (3.6 standard errors) | 7.8% | 7.7% | 9.1% | 0.21 | 0.24 | Rs 45,460 |
| S0 plain holding | 7.8% | 7.7% | 9.1% | 0.21 | 0.24 | Rs 45,460 |
| Nifty BeES held | 13.4% | 12.9% | 36.3% | 0.48 | 0.02 | Rs 10 |
| Gold BeES held | 5.5% | 5.3% | 25.5% | -0.03 | 0.04 | Rs 0 |
| Liquid fund held | 6.8% | 6.3% | 0.2% | -0.84 | 0.03 | Rs 100 |

- Selector, 1 standard error: edge over S0 out of sample -4.1 points a year (bootstrap standard error 2.1); picked a strategy at 8 of 11 cuts (S1: 8).
- Selector, deflated margin (3.6 standard errors): edge over S0 out of sample +0.0 points a year (bootstrap standard error 0.0); picked a strategy at 0 of 11 cuts (none).

2065 trials, about 620 independent. Probability of backtest overfitting of the candidate set (in-sample, whole design period): 45%. Best in-sample candidate S1|weights=0/0/0.1/0.1/0.8,rebalance=year|band=0.01: deflated Sharpe probability 59% (shown to size the selection effect, not a result). Selector out of sample, deflated for the two margins tried: 2% (spec), 48% (deflated).

## Balanced: drawdown cap 20%

| Account, fresh from 2013-04-01 to 2023-09-29 | After-tax growth a year | After selling all | Worst drawdown | Sharpe | Turnover a year | Tax |
|---|---|---|---|---|---|---|
| Selector, 1 standard error | 3.0% | 3.0% | 18.0% | -0.29 | 1.63 | Rs 18,500 |
| Selector, deflated margin (3.5 standard errors) | 8.4% | 8.3% | 17.8% | 0.22 | 0.30 | Rs 49,230 |
| S0 plain holding | 8.4% | 8.3% | 17.8% | 0.22 | 0.30 | Rs 49,230 |
| Nifty BeES held | 13.4% | 12.9% | 36.3% | 0.48 | 0.02 | Rs 10 |
| Gold BeES held | 5.5% | 5.3% | 25.5% | -0.03 | 0.04 | Rs 0 |
| Liquid fund held | 6.8% | 6.3% | 0.2% | -0.84 | 0.03 | Rs 100 |

- Selector, 1 standard error: edge over S0 out of sample -5.2 points a year (bootstrap standard error 2.7); picked a strategy at 8 of 11 cuts (S1: 5, S3: 3).
- Selector, deflated margin (3.5 standard errors): edge over S0 out of sample +0.0 points a year (bootstrap standard error 0.0); picked a strategy at 0 of 11 cuts (none).

2065 trials, about 522 independent. Probability of backtest overfitting of the candidate set (in-sample, whole design period): 65%. Best in-sample candidate S1|weights=0/0.1/0.1/0.1/0.7,rebalance=year|band=0.01: deflated Sharpe probability 65% (shown to size the selection effect, not a result). Selector out of sample, deflated for the two margins tried: 6% (spec), 54% (deflated).

## Aggressive: drawdown cap 30%

| Account, fresh from 2013-04-01 to 2023-09-29 | After-tax growth a year | After selling all | Worst drawdown | Sharpe | Turnover a year | Tax |
|---|---|---|---|---|---|---|
| Selector, 1 standard error | 3.8% | 3.7% | 26.5% | -0.16 | 1.37 | Rs 25,040 |
| Selector, deflated margin (3.5 standard errors) | 9.1% | 8.9% | 26.0% | 0.24 | 0.31 | Rs 23,560 |
| S0 plain holding | 9.1% | 8.9% | 26.0% | 0.24 | 0.31 | Rs 23,560 |
| Nifty BeES held | 13.4% | 12.9% | 36.3% | 0.48 | 0.02 | Rs 10 |
| Gold BeES held | 5.5% | 5.3% | 25.5% | -0.03 | 0.04 | Rs 0 |
| Liquid fund held | 6.8% | 6.3% | 0.2% | -0.84 | 0.03 | Rs 100 |

- Selector, 1 standard error: edge over S0 out of sample -5.1 points a year (bootstrap standard error 3.3); picked a strategy at 8 of 11 cuts (S1: 3, S3: 5).
- Selector, deflated margin (3.5 standard errors): edge over S0 out of sample +0.0 points a year (bootstrap standard error 0.0); picked a strategy at 0 of 11 cuts (none).

2065 trials, about 487 independent. Probability of backtest overfitting of the candidate set (in-sample, whole design period): 83%. Best in-sample candidate S1|weights=0.1/0.2/0.1/0.2/0.4,rebalance=year|band=0.01: deflated Sharpe probability 66% (shown to size the selection effect, not a result). Selector out of sample, deflated for the two margins tried: 16% (spec), 62% (deflated).

