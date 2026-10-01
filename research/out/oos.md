# Out of sample: the walk-forward selector, each candidate alone, and the other investments

Each April the selector picks among its candidates using only data before that day; the picks are stitched into one account started on the first April with Rs 10 lakh. Every account has the drawdown governor on at the risk level's cap (the reference investments, held without one, are the exception) and pays charges, slippage and tax by each transaction's own date. All start the same day with the same money. The selection is out of sample; the design (candidate lists, margins, caps) was fixed with the design period in view. Design 2 (plain holding plus one ensemble per family) was chosen after design 1's result was seen, so its numbers here are in-sample for that choice: only the last three years, untouched until the freeze, can confirm it.

Execution: harvest = True for every strategy account and S0 (W1: long-term equity gains realised each March up to the yearly exemption and bought back the next day); the reference investments are held plainly.

## Conservative: drawdown cap 10%

| Account, fresh from 2013-04-01 to 2023-09-29 | After-tax growth a year | After selling all | Worst drawdown | Sharpe | Turnover a year | Tax |
|---|---|---|---|---|---|---|
| Selector over the ensembles, 1 standard error | 7.8% | 7.8% | 9.1% | 0.21 | 0.30 | Rs 34,560 |
| Selector over the ensembles, deflated margin (1.4 standard errors) | 7.8% | 7.8% | 9.1% | 0.21 | 0.30 | Rs 34,560 |
| Selector over all 2077 trials, 1 standard error | 3.5% | 3.4% | 12.5% | -0.39 | 1.57 | Rs 70,800 |
| Selector over all 2077 trials, deflated margin (3.6 standard errors) | 7.8% | 7.8% | 9.1% | 0.21 | 0.30 | Rs 34,560 |
| S0 plain holding (Nifty ETF and cash) (alone) | 7.8% | 7.8% | 9.1% | 0.21 | 0.30 | Rs 34,560 |
| E1 equal weight, four ETFs and cash (alone) | 7.1% | 7.0% | 10.3% | 0.08 | 0.96 | Rs 136,060 |
| E2 trend filters (mean of 6) (alone) | 7.3% | 7.3% | 9.0% | 0.12 | 6.98 | Rs 214,620 |
| E3 momentum rotation (mean of 18) (alone) | 5.2% | 5.2% | 10.1% | -0.13 | 2.90 | Rs 150,460 |
| E4 volatility targeting (mean of 10) (alone) | 7.6% | 7.5% | 9.6% | 0.14 | 1.92 | Rs 128,270 |
| E5 drawdown-aware exposure (mean of 6) (alone) | 8.0% | 7.9% | 10.0% | 0.18 | 2.11 | Rs 117,450 |
| S6 deep model (mean of 12 configurations, 3 seeds each) (alone) | 5.3% | 5.2% | 9.4% | -0.16 | 1.76 | Rs 66,080 |
| Nifty BeES held | 13.4% | 12.9% | 36.3% | 0.48 | 0.02 | Rs 10 |
| Junior BeES held | 14.6% | 14.2% | 38.7% | 0.50 | 0.02 | Rs 10 |
| Bank BeES held | 13.9% | 13.5% | 47.7% | 0.40 | 0.02 | Rs 0 |
| Gold BeES held | 5.5% | 5.3% | 25.5% | -0.03 | 0.04 | Rs 0 |
| Liquid fund held | 6.8% | 6.3% | 0.2% | -0.84 | 0.03 | Rs 100 |

- Selector over the ensembles, 1 standard error: edge over S0 +0.0 points a year (bootstrap standard error 0.0); picked a strategy at 0 of 11 cuts (none).
- Selector over the ensembles, deflated margin (1.4 standard errors): edge over S0 +0.0 points a year (bootstrap standard error 0.0); picked a strategy at 0 of 11 cuts (none).
- Selector over all 2077 trials, 1 standard error: edge over S0 -4.1 points a year (bootstrap standard error 2.1); picked a strategy at 8 of 11 cuts (S1: 8).
- Selector over all 2077 trials, deflated margin (3.6 standard errors): edge over S0 +0.0 points a year (bootstrap standard error 0.0); picked a strategy at 0 of 11 cuts (none).

ensembles: 7 candidates, about 3 independent. Probability of backtest overfitting (in-sample, whole design period): 97%. Best in-sample candidate E2|mean of 6 S2|band=0.05: deflated Sharpe probability 45% (sizes the selection effect, not a result).
all trials: 2077 candidates, about 623 independent. Probability of backtest overfitting (in-sample, whole design period): 43%. Best in-sample candidate S1|weights=0/0.1/0/0.1/0.8,rebalance=year|band=0.01: deflated Sharpe probability 59% (sizes the selection effect, not a result).

Selector paths, deflated for the four variants tried: 37% (ensembles, spec), 37% (ensembles, deflated), 1% (all trials, spec), 37% (all trials, deflated).

## Balanced: drawdown cap 20%

| Account, fresh from 2013-04-01 to 2023-09-29 | After-tax growth a year | After selling all | Worst drawdown | Sharpe | Turnover a year | Tax |
|---|---|---|---|---|---|---|
| Selector over the ensembles, 1 standard error | 8.8% | 8.6% | 17.8% | 0.25 | 0.47 | Rs 28,810 |
| Selector over the ensembles, deflated margin (1.3 standard errors) | 8.5% | 8.4% | 17.8% | 0.22 | 0.40 | Rs 25,440 |
| Selector over all 2077 trials, 1 standard error | 2.9% | 2.9% | 18.0% | -0.30 | 1.63 | Rs 20,020 |
| Selector over all 2077 trials, deflated margin (3.5 standard errors) | 8.5% | 8.4% | 17.8% | 0.22 | 0.40 | Rs 25,440 |
| S0 plain holding (Nifty ETF and cash) (alone) | 8.5% | 8.4% | 17.8% | 0.22 | 0.40 | Rs 25,440 |
| E1 equal weight, four ETFs and cash (alone) | 9.5% | 9.3% | 17.1% | 0.33 | 0.39 | Rs 12,530 |
| E2 trend filters (mean of 6) (alone) | 8.3% | 8.2% | 15.1% | 0.21 | 9.31 | Rs 267,180 |
| E3 momentum rotation (mean of 18) (alone) | 6.5% | 6.4% | 17.0% | 0.03 | 2.19 | Rs 143,040 |
| E4 volatility targeting (mean of 10) (alone) | 8.9% | 8.8% | 16.8% | 0.25 | 1.11 | Rs 89,100 |
| E5 drawdown-aware exposure (mean of 6) (alone) | 8.2% | 8.1% | 17.6% | 0.18 | 1.13 | Rs 45,270 |
| S6 deep model (mean of 12 configurations, 3 seeds each) (alone) | 5.4% | 5.3% | 18.1% | -0.11 | 1.35 | Rs 26,870 |
| Nifty BeES held | 13.4% | 12.9% | 36.3% | 0.48 | 0.02 | Rs 10 |
| Junior BeES held | 14.6% | 14.2% | 38.7% | 0.50 | 0.02 | Rs 10 |
| Bank BeES held | 13.9% | 13.5% | 47.7% | 0.40 | 0.02 | Rs 0 |
| Gold BeES held | 5.5% | 5.3% | 25.5% | -0.03 | 0.04 | Rs 0 |
| Liquid fund held | 6.8% | 6.3% | 0.2% | -0.84 | 0.03 | Rs 100 |

- Selector over the ensembles, 1 standard error: edge over S0 +0.3 points a year (bootstrap standard error 0.5); picked a strategy at 3 of 11 cuts (E1: 3).
- Selector over the ensembles, deflated margin (1.3 standard errors): edge over S0 +0.0 points a year (bootstrap standard error 0.0); picked a strategy at 0 of 11 cuts (none).
- Selector over all 2077 trials, 1 standard error: edge over S0 -5.4 points a year (bootstrap standard error 2.7); picked a strategy at 8 of 11 cuts (S1: 5, S3: 3).
- Selector over all 2077 trials, deflated margin (3.5 standard errors): edge over S0 +0.0 points a year (bootstrap standard error 0.0); picked a strategy at 0 of 11 cuts (none).

ensembles: 7 candidates, about 2 independent. Probability of backtest overfitting (in-sample, whole design period): 49%. Best in-sample candidate E1|equal-weight,rebalance=year|band=0.01: deflated Sharpe probability 67% (sizes the selection effect, not a result).
all trials: 2077 candidates, about 524 independent. Probability of backtest overfitting (in-sample, whole design period): 65%. Best in-sample candidate S1|weights=0/0.1/0.1/0.1/0.7,rebalance=year|band=0.01: deflated Sharpe probability 63% (sizes the selection effect, not a result).

Selector paths, deflated for the four variants tried: 46% (ensembles, spec), 43% (ensembles, deflated), 3% (all trials, spec), 43% (all trials, deflated).

## Aggressive: drawdown cap 30%

| Account, fresh from 2013-04-01 to 2023-09-29 | After-tax growth a year | After selling all | Worst drawdown | Sharpe | Turnover a year | Tax |
|---|---|---|---|---|---|---|
| Selector over the ensembles, 1 standard error | 6.8% | 6.7% | 26.0% | 0.06 | 0.60 | Rs 2,110 |
| Selector over the ensembles, deflated margin (1.3 standard errors) | 7.7% | 7.6% | 25.9% | 0.14 | 0.53 | Rs 16,150 |
| Selector over all 2077 trials, 1 standard error | 3.8% | 3.7% | 26.5% | -0.17 | 1.40 | Rs 31,570 |
| Selector over all 2077 trials, deflated margin (3.5 standard errors) | 9.1% | 8.9% | 26.0% | 0.24 | 0.43 | Rs 4,890 |
| S0 plain holding (Nifty ETF and cash) (alone) | 9.1% | 8.9% | 26.0% | 0.24 | 0.43 | Rs 4,890 |
| E1 equal weight, four ETFs and cash (alone) | 11.1% | 10.9% | 21.1% | 0.47 | 0.24 | Rs 6,840 |
| E2 trend filters (mean of 6) (alone) | 7.7% | 7.6% | 20.0% | 0.15 | 9.85 | Rs 240,840 |
| E3 momentum rotation (mean of 18) (alone) | 8.0% | 7.9% | 20.0% | 0.16 | 1.97 | Rs 158,430 |
| E4 volatility targeting (mean of 10) (alone) | 10.2% | 10.1% | 20.6% | 0.35 | 0.99 | Rs 101,470 |
| E5 drawdown-aware exposure (mean of 6) (alone) | 10.3% | 10.1% | 21.8% | 0.32 | 0.91 | Rs 26,250 |
| S6 deep model (mean of 12 configurations, 3 seeds each) (alone) | 6.4% | 6.3% | 25.6% | 0.01 | 1.30 | Rs 26,570 |
| Nifty BeES held | 13.4% | 12.9% | 36.3% | 0.48 | 0.02 | Rs 10 |
| Junior BeES held | 14.6% | 14.2% | 38.7% | 0.50 | 0.02 | Rs 10 |
| Bank BeES held | 13.9% | 13.5% | 47.7% | 0.40 | 0.02 | Rs 0 |
| Gold BeES held | 5.5% | 5.3% | 25.5% | -0.03 | 0.04 | Rs 0 |
| Liquid fund held | 6.8% | 6.3% | 0.2% | -0.84 | 0.03 | Rs 100 |

- Selector over the ensembles, 1 standard error: edge over S0 -2.1 points a year (bootstrap standard error 1.2); picked a strategy at 9 of 11 cuts (E1: 9).
- Selector over the ensembles, deflated margin (1.3 standard errors): edge over S0 -1.3 points a year (bootstrap standard error 0.8); picked a strategy at 5 of 11 cuts (E1: 5).
- Selector over all 2077 trials, 1 standard error: edge over S0 -5.1 points a year (bootstrap standard error 3.3); picked a strategy at 8 of 11 cuts (S1: 3, S3: 5).
- Selector over all 2077 trials, deflated margin (3.5 standard errors): edge over S0 +0.0 points a year (bootstrap standard error 0.0); picked a strategy at 0 of 11 cuts (none).

ensembles: 7 candidates, about 2 independent. Probability of backtest overfitting (in-sample, whole design period): 19%. Best in-sample candidate E1|equal-weight,rebalance=year|band=0.01: deflated Sharpe probability 84% (sizes the selection effect, not a result).
all trials: 2077 candidates, about 489 independent. Probability of backtest overfitting (in-sample, whole design period): 83%. Best in-sample candidate S1|weights=0/0.1/0.1/0.1/0.7,rebalance=year|band=0.01: deflated Sharpe probability 65% (sizes the selection effect, not a result).

Selector paths, deflated for the four variants tried: 34% (ensembles, spec), 44% (ensembles, deflated), 13% (all trials, spec), 57% (all trials, deflated).

