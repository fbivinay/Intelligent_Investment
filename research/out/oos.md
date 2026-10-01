# Out of sample: the walk-forward selector, each candidate alone, and the other investments

Each April the selector picks among its candidates using only data before that day; the picks are stitched into one account started on the first April with Rs 10 lakh. Every account has the drawdown governor on at the risk level's cap (the reference investments, held without one, are the exception) and pays charges, slippage and tax by each transaction's own date. All start the same day with the same money. The selection is out of sample; the design (candidate lists, margins, caps) was fixed with the design period in view. Design 2 (plain holding plus one ensemble per family) was chosen after design 1's result was seen, so its numbers here are in-sample for that choice: only the last three years, untouched until the freeze, can confirm it.

## Conservative: drawdown cap 10%

| Account, fresh from 2013-04-01 to 2023-09-29 | After-tax growth a year | After selling all | Worst drawdown | Sharpe | Turnover a year | Tax |
|---|---|---|---|---|---|---|
| Selector over the ensembles, 1 standard error | 7.8% | 7.7% | 9.1% | 0.21 | 0.24 | Rs 45,460 |
| Selector over the ensembles, deflated margin (1.3 standard errors) | 7.8% | 7.7% | 9.1% | 0.21 | 0.24 | Rs 45,460 |
| Selector over all 2065 trials, 1 standard error | 3.5% | 3.5% | 12.5% | -0.39 | 1.56 | Rs 70,800 |
| Selector over all 2065 trials, deflated margin (3.6 standard errors) | 7.8% | 7.7% | 9.1% | 0.21 | 0.24 | Rs 45,460 |
| S0 plain holding (Nifty ETF and cash) (alone) | 7.8% | 7.7% | 9.1% | 0.21 | 0.24 | Rs 45,460 |
| E1 equal weight, four ETFs and cash (alone) | 7.1% | 7.0% | 10.3% | 0.08 | 0.93 | Rs 136,410 |
| E2 trend filters (mean of 6) (alone) | 7.3% | 7.3% | 9.0% | 0.12 | 6.98 | Rs 214,620 |
| E3 momentum rotation (mean of 18) (alone) | 5.2% | 5.2% | 10.1% | -0.13 | 2.90 | Rs 150,460 |
| E4 volatility targeting (mean of 10) (alone) | 7.6% | 7.5% | 9.6% | 0.14 | 1.92 | Rs 128,270 |
| E5 drawdown-aware exposure (mean of 6) (alone) | 8.0% | 7.9% | 10.0% | 0.18 | 2.11 | Rs 117,450 |
| Nifty BeES held | 13.4% | 12.9% | 36.3% | 0.48 | 0.02 | Rs 10 |
| Gold BeES held | 5.5% | 5.3% | 25.5% | -0.03 | 0.04 | Rs 0 |
| Liquid fund held | 6.8% | 6.3% | 0.2% | -0.84 | 0.03 | Rs 100 |

- Selector over the ensembles, 1 standard error: edge over S0 +0.0 points a year (bootstrap standard error 0.0); picked a strategy at 0 of 11 cuts (none).
- Selector over the ensembles, deflated margin (1.3 standard errors): edge over S0 +0.0 points a year (bootstrap standard error 0.0); picked a strategy at 0 of 11 cuts (none).
- Selector over all 2065 trials, 1 standard error: edge over S0 -4.1 points a year (bootstrap standard error 2.1); picked a strategy at 8 of 11 cuts (S1: 8).
- Selector over all 2065 trials, deflated margin (3.6 standard errors): edge over S0 +0.0 points a year (bootstrap standard error 0.0); picked a strategy at 0 of 11 cuts (none).

ensembles: 6 candidates, about 2 independent. Probability of backtest overfitting (in-sample, whole design period): 97%. Best in-sample candidate E2|mean of 6 S2|band=0.05: deflated Sharpe probability 47% (sizes the selection effect, not a result).
all trials: 2065 candidates, about 620 independent. Probability of backtest overfitting (in-sample, whole design period): 45%. Best in-sample candidate S1|weights=0/0/0.1/0.1/0.8,rebalance=year|band=0.01: deflated Sharpe probability 59% (sizes the selection effect, not a result).

Selector paths, deflated for the four variants tried: 37% (ensembles, spec), 37% (ensembles, deflated), 1% (all trials, spec), 37% (all trials, deflated).

## Balanced: drawdown cap 20%

| Account, fresh from 2013-04-01 to 2023-09-29 | After-tax growth a year | After selling all | Worst drawdown | Sharpe | Turnover a year | Tax |
|---|---|---|---|---|---|---|
| Selector over the ensembles, 1 standard error | 8.7% | 8.5% | 17.8% | 0.24 | 0.34 | Rs 63,390 |
| Selector over the ensembles, deflated margin (1.2 standard errors) | 8.4% | 8.3% | 17.8% | 0.22 | 0.30 | Rs 49,230 |
| Selector over all 2065 trials, 1 standard error | 3.0% | 3.0% | 18.0% | -0.29 | 1.63 | Rs 18,500 |
| Selector over all 2065 trials, deflated margin (3.5 standard errors) | 8.4% | 8.3% | 17.8% | 0.22 | 0.30 | Rs 49,230 |
| S0 plain holding (Nifty ETF and cash) (alone) | 8.4% | 8.3% | 17.8% | 0.22 | 0.30 | Rs 49,230 |
| E1 equal weight, four ETFs and cash (alone) | 9.4% | 9.1% | 17.1% | 0.32 | 0.31 | Rs 49,050 |
| E2 trend filters (mean of 6) (alone) | 8.3% | 8.2% | 15.1% | 0.21 | 9.31 | Rs 267,180 |
| E3 momentum rotation (mean of 18) (alone) | 6.5% | 6.4% | 17.0% | 0.03 | 2.19 | Rs 143,040 |
| E4 volatility targeting (mean of 10) (alone) | 9.0% | 8.9% | 16.8% | 0.25 | 1.08 | Rs 93,270 |
| E5 drawdown-aware exposure (mean of 6) (alone) | 8.2% | 8.1% | 17.7% | 0.17 | 1.07 | Rs 53,520 |
| Nifty BeES held | 13.4% | 12.9% | 36.3% | 0.48 | 0.02 | Rs 10 |
| Gold BeES held | 5.5% | 5.3% | 25.5% | -0.03 | 0.04 | Rs 0 |
| Liquid fund held | 6.8% | 6.3% | 0.2% | -0.84 | 0.03 | Rs 100 |

- Selector over the ensembles, 1 standard error: edge over S0 +0.3 points a year (bootstrap standard error 0.5); picked a strategy at 3 of 11 cuts (E1: 3).
- Selector over the ensembles, deflated margin (1.2 standard errors): edge over S0 +0.0 points a year (bootstrap standard error 0.0); picked a strategy at 0 of 11 cuts (none).
- Selector over all 2065 trials, 1 standard error: edge over S0 -5.2 points a year (bootstrap standard error 2.7); picked a strategy at 8 of 11 cuts (S1: 5, S3: 3).
- Selector over all 2065 trials, deflated margin (3.5 standard errors): edge over S0 +0.0 points a year (bootstrap standard error 0.0); picked a strategy at 0 of 11 cuts (none).

ensembles: 6 candidates, about 2 independent. Probability of backtest overfitting (in-sample, whole design period): 53%. Best in-sample candidate E1|equal-weight,rebalance=year|band=0.01: deflated Sharpe probability 70% (sizes the selection effect, not a result).
all trials: 2065 candidates, about 522 independent. Probability of backtest overfitting (in-sample, whole design period): 65%. Best in-sample candidate S1|weights=0/0.1/0.1/0.1/0.7,rebalance=year|band=0.01: deflated Sharpe probability 65% (sizes the selection effect, not a result).

Selector paths, deflated for the four variants tried: 46% (ensembles, spec), 43% (ensembles, deflated), 3% (all trials, spec), 43% (all trials, deflated).

## Aggressive: drawdown cap 30%

| Account, fresh from 2013-04-01 to 2023-09-29 | After-tax growth a year | After selling all | Worst drawdown | Sharpe | Turnover a year | Tax |
|---|---|---|---|---|---|---|
| Selector over the ensembles, 1 standard error | 6.9% | 6.8% | 26.0% | 0.06 | 0.50 | Rs 800 |
| Selector over the ensembles, deflated margin (1.2 standard errors) | 7.4% | 7.2% | 25.9% | 0.11 | 0.47 | Rs 56,060 |
| Selector over all 2065 trials, 1 standard error | 3.8% | 3.7% | 26.5% | -0.16 | 1.37 | Rs 25,040 |
| Selector over all 2065 trials, deflated margin (3.5 standard errors) | 9.1% | 8.9% | 26.0% | 0.24 | 0.31 | Rs 23,560 |
| S0 plain holding (Nifty ETF and cash) (alone) | 9.1% | 8.9% | 26.0% | 0.24 | 0.31 | Rs 23,560 |
| E1 equal weight, four ETFs and cash (alone) | 11.1% | 10.7% | 21.1% | 0.46 | 0.15 | Rs 24,980 |
| E2 trend filters (mean of 6) (alone) | 7.7% | 7.6% | 20.0% | 0.15 | 9.85 | Rs 240,840 |
| E3 momentum rotation (mean of 18) (alone) | 8.0% | 7.9% | 20.0% | 0.16 | 1.97 | Rs 158,430 |
| E4 volatility targeting (mean of 10) (alone) | 10.2% | 10.1% | 20.6% | 0.36 | 0.93 | Rs 106,100 |
| E5 drawdown-aware exposure (mean of 6) (alone) | 10.3% | 10.2% | 21.8% | 0.32 | 0.84 | Rs 34,800 |
| Nifty BeES held | 13.4% | 12.9% | 36.3% | 0.48 | 0.02 | Rs 10 |
| Gold BeES held | 5.5% | 5.3% | 25.5% | -0.03 | 0.04 | Rs 0 |
| Liquid fund held | 6.8% | 6.3% | 0.2% | -0.84 | 0.03 | Rs 100 |

- Selector over the ensembles, 1 standard error: edge over S0 -2.1 points a year (bootstrap standard error 1.2); picked a strategy at 9 of 11 cuts (E1: 9).
- Selector over the ensembles, deflated margin (1.2 standard errors): edge over S0 -1.6 points a year (bootstrap standard error 1.0); picked a strategy at 7 of 11 cuts (E1: 7).
- Selector over all 2065 trials, 1 standard error: edge over S0 -5.1 points a year (bootstrap standard error 3.3); picked a strategy at 8 of 11 cuts (S1: 3, S3: 5).
- Selector over all 2065 trials, deflated margin (3.5 standard errors): edge over S0 +0.0 points a year (bootstrap standard error 0.0); picked a strategy at 0 of 11 cuts (none).

ensembles: 6 candidates, about 2 independent. Probability of backtest overfitting (in-sample, whole design period): 20%. Best in-sample candidate E1|equal-weight,rebalance=year|band=0.01: deflated Sharpe probability 84% (sizes the selection effect, not a result).
all trials: 2065 candidates, about 487 independent. Probability of backtest overfitting (in-sample, whole design period): 83%. Best in-sample candidate S1|weights=0.1/0.2/0.1/0.2/0.4,rebalance=year|band=0.01: deflated Sharpe probability 66% (sizes the selection effect, not a result).

Selector paths, deflated for the four variants tried: 36% (ensembles, spec), 41% (ensembles, deflated), 14% (all trials, spec), 58% (all trials, deflated).

