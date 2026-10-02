# The wider universe: six ETFs, walk-forward

The Midcap 100 ETF and the Nasdaq 100 ETF join the four ETFs (their NAV, scaled to the exchange price, stands in before 2016). Read every number with this in mind: **these two were added after their 2013-2026 history was known to be strong**. The yearly picks use only data before each April, but the menu they pick from was chosen with hindsight, and no unseen years are left to test it. The Nasdaq ETF is taxed as a non-equity ETF (as gold ETFs are) and has traded above its NAV since 2022 (13% at the end): a buyer pays that premium.

What it shows: with a drawdown guard the walk-forward selector stays near 7-11% a year after tax whatever the cap, because the guard sells after falls and the selector keeps plain holding unless a candidate's edge is large. Without a guard, the plain equal mix of the six ETFs made about 15% a year after selling all, with a worst fall near 28%; 18-19% needed a mix picked knowing which ETFs did best.

## Fixed mixes, no guard

Bought on 2013-04-01 with Rs 10 lakh, back to the mix's weights each April, harvesting as above, no governor; to 2026-09-30.

| Mix | After-tax growth a year | After selling all | Worst drawdown | Sharpe | Turnover a year | Tax |
|---|---|---|---|---|---|---|
| Equal six ETFs, no cash (the product's Growth level) | 16.0% | 15.4% | 28.0% | 0.75 | 0.14 | Rs 313,150 |
| Equal six ETFs and cash (E1) | 14.8% | 14.3% | 24.3% | 0.75 | 0.14 | Rs 276,060 |
| Junior 25 / Midcap 25 / Nasdaq 25 / Gold 25 | 17.8% | 17.1% | 23.2% | 0.89 | 0.13 | Rs 369,000 |
| Midcap 40 / Nasdaq 40 / Gold 20 (picked with hindsight) | 19.1% | 18.4% | 23.8% | 0.89 | 0.15 | Rs 583,890 |
| Nasdaq 50 / Midcap 25 / Gold 25 (picked with hindsight) | 19.6% | 18.8% | 21.9% | 0.90 | 0.14 | Rs 577,310 |

Each April the selector picks among its candidates using only data before that day; the picks are stitched into one account started on the first April with Rs 10 lakh. Every account has the drawdown governor on at the risk level's cap (the reference investments, held without one, are the exception) and pays charges, slippage and tax by each transaction's own date. All start the same day with the same money. The selection is out of sample; the design (candidate lists, margins, caps) was fixed with the design period in view. Design 2 (plain holding plus one ensemble per family) was chosen after design 1's result was seen, so its numbers here are in-sample for that choice: only the last three years, untouched until the freeze, can confirm it.

Execution: harvest = True for every strategy account and S0 (W1: long-term equity gains realised each March up to the yearly exemption and bought back the next day); the reference investments are held plainly.

## Conservative: drawdown cap 10%

| Account, fresh from 2013-04-01 to 2026-09-30 | After-tax growth a year | After selling all | Worst drawdown | Sharpe | Turnover a year | Tax |
|---|---|---|---|---|---|---|
| Selector over the ensembles, 1 standard error | 7.4% | 7.0% | 9.1% | 0.14 | 0.30 | Rs 97,990 |
| Selector over the ensembles, deflated margin (1.3 standard errors) | 7.4% | 7.0% | 9.1% | 0.14 | 0.30 | Rs 97,990 |
| Selector over all 987 trials, 1 standard error | 8.6% | 8.6% | 10.0% | 0.25 | 1.41 | Rs 663,260 |
| Selector over all 987 trials, deflated margin (3.5 standard errors) | 7.4% | 7.0% | 9.1% | 0.14 | 0.30 | Rs 97,990 |
| S0 plain holding (Nifty ETF and cash) (alone) | 7.4% | 7.0% | 9.1% | 0.14 | 0.30 | Rs 97,990 |
| E1 equal weight, six ETFs and cash (alone) | 9.8% | 9.8% | 10.0% | 0.40 | 1.14 | Rs 486,100 |
| E2 trend filters (mean of 6) (alone) | 9.3% | 9.3% | 9.7% | 0.33 | 6.19 | Rs 661,290 |
| E3 momentum rotation (mean of 18) (alone) | 9.8% | 9.6% | 12.4% | 0.32 | 2.83 | Rs 654,660 |
| E4 volatility targeting (mean of 10) (alone) | 6.9% | 6.9% | 9.6% | 0.05 | 1.83 | Rs 218,530 |
| E5 drawdown-aware exposure (mean of 6) (alone) | 7.4% | 7.4% | 10.0% | 0.10 | 1.91 | Rs 236,130 |
| Nifty BeES held | 11.8% | 11.0% | 36.3% | 0.39 | 0.01 | Rs 10 |
| Junior BeES held | 15.0% | 14.2% | 38.7% | 0.52 | 0.01 | Rs 10 |
| Bank BeES held | 12.5% | 11.8% | 47.7% | 0.35 | 0.01 | Rs 0 |
| Gold BeES held | 11.4% | 10.4% | 25.5% | 0.36 | 0.02 | Rs 0 |
| Midcap 100 ETF held | 16.8% | 15.9% | 48.4% | 0.58 | 0.01 | Rs 10 |
| Nasdaq 100 ETF held | 24.9% | 23.4% | 36.6% | 0.84 | 0.01 | Rs 360 |
| Liquid fund held | 6.8% | 6.0% | 0.2% | -0.74 | 0.02 | Rs 100 |

- Selector over the ensembles, 1 standard error: edge over S0 +0.0 points a year (bootstrap standard error 0.0); picked a strategy at 0 of 14 cuts (none).
- Selector over the ensembles, deflated margin (1.3 standard errors): edge over S0 +0.0 points a year (bootstrap standard error 0.0); picked a strategy at 0 of 14 cuts (none).
- Selector over all 987 trials, 1 standard error: edge over S0 +1.3 points a year (bootstrap standard error 2.6); picked a strategy at 14 of 14 cuts (S1: 14).
- Selector over all 987 trials, deflated margin (3.5 standard errors): edge over S0 +0.0 points a year (bootstrap standard error 0.0); picked a strategy at 0 of 14 cuts (none).

ensembles: 6 candidates, about 2 independent. Probability of backtest overfitting (in-sample, whole design period): 70%. Best in-sample candidate E2|mean of 6 S2|band=0.05: deflated Sharpe probability 72% (sizes the selection effect, not a result).
all trials: 987 candidates, about 404 independent. Probability of backtest overfitting (in-sample, whole design period): 45%. Best in-sample candidate S1|weights=0/0/0/0/0/0.2/0.8,rebalance=year|band=0.01: deflated Sharpe probability 63% (sizes the selection effect, not a result).

Selector paths, deflated for the four variants tried: 62% (ensembles, spec), 62% (ensembles, deflated), 75% (all trials, spec), 62% (all trials, deflated).

## Balanced: drawdown cap 20%

| Account, fresh from 2013-04-01 to 2026-09-30 | After-tax growth a year | After selling all | Worst drawdown | Sharpe | Turnover a year | Tax |
|---|---|---|---|---|---|---|
| Selector over the ensembles, 1 standard error | 9.2% | 9.0% | 18.0% | 0.28 | 0.62 | Rs 262,690 |
| Selector over the ensembles, deflated margin (1.3 standard errors) | 8.4% | 8.2% | 18.0% | 0.21 | 0.70 | Rs 263,300 |
| Selector over all 987 trials, 1 standard error | 11.1% | 11.0% | 18.7% | 0.37 | 0.91 | Rs 616,880 |
| Selector over all 987 trials, deflated margin (3.4 standard errors) | 7.3% | 7.1% | 18.0% | 0.11 | 0.46 | Rs 147,540 |
| S0 plain holding (Nifty ETF and cash) (alone) | 7.3% | 7.1% | 18.0% | 0.11 | 0.46 | Rs 147,540 |
| E1 equal weight, six ETFs and cash (alone) | 12.0% | 11.7% | 17.7% | 0.56 | 0.34 | Rs 324,140 |
| E2 trend filters (mean of 6) (alone) | 10.8% | 10.8% | 15.8% | 0.47 | 7.90 | Rs 852,300 |
| E3 momentum rotation (mean of 18) (alone) | 9.5% | 9.5% | 17.5% | 0.27 | 2.54 | Rs 674,190 |
| E4 volatility targeting (mean of 10) (alone) | 7.5% | 7.5% | 16.8% | 0.12 | 1.09 | Rs 249,290 |
| E5 drawdown-aware exposure (mean of 6) (alone) | 7.2% | 7.2% | 17.6% | 0.09 | 1.08 | Rs 164,660 |
| Nifty BeES held | 11.8% | 11.0% | 36.3% | 0.39 | 0.01 | Rs 10 |
| Junior BeES held | 15.0% | 14.2% | 38.7% | 0.52 | 0.01 | Rs 10 |
| Bank BeES held | 12.5% | 11.8% | 47.7% | 0.35 | 0.01 | Rs 0 |
| Gold BeES held | 11.4% | 10.4% | 25.5% | 0.36 | 0.02 | Rs 0 |
| Midcap 100 ETF held | 16.8% | 15.9% | 48.4% | 0.58 | 0.01 | Rs 10 |
| Nasdaq 100 ETF held | 24.9% | 23.4% | 36.6% | 0.84 | 0.01 | Rs 360 |
| Liquid fund held | 6.8% | 6.0% | 0.2% | -0.74 | 0.02 | Rs 100 |

- Selector over the ensembles, 1 standard error: edge over S0 +1.8 points a year (bootstrap standard error 1.1); picked a strategy at 8 of 14 cuts (E1: 8).
- Selector over the ensembles, deflated margin (1.3 standard errors): edge over S0 +1.1 points a year (bootstrap standard error 0.9); picked a strategy at 4 of 14 cuts (E1: 4).
- Selector over all 987 trials, 1 standard error: edge over S0 +3.6 points a year (bootstrap standard error 4.2); picked a strategy at 14 of 14 cuts (S1: 14).
- Selector over all 987 trials, deflated margin (3.4 standard errors): edge over S0 +0.0 points a year (bootstrap standard error 0.0); picked a strategy at 0 of 14 cuts (none).

ensembles: 6 candidates, about 2 independent. Probability of backtest overfitting (in-sample, whole design period): 26%. Best in-sample candidate E1|equal-weight,rebalance=year|band=0.01: deflated Sharpe probability 90% (sizes the selection effect, not a result).
all trials: 987 candidates, about 352 independent. Probability of backtest overfitting (in-sample, whole design period): 34%. Best in-sample candidate S1|weights=0/0/0/0.2/0.2/0.2/0.4,rebalance=year|band=0.01: deflated Sharpe probability 71% (sizes the selection effect, not a result).

Selector paths, deflated for the four variants tried: 73% (ensembles, spec), 64% (ensembles, deflated), 82% (all trials, spec), 49% (all trials, deflated).

## Aggressive: drawdown cap 30%

| Account, fresh from 2013-04-01 to 2026-09-30 | After-tax growth a year | After selling all | Worst drawdown | Sharpe | Turnover a year | Tax |
|---|---|---|---|---|---|---|
| Selector over the ensembles, 1 standard error | 10.8% | 10.5% | 26.0% | 0.39 | 0.40 | Rs 189,480 |
| Selector over the ensembles, deflated margin (1.3 standard errors) | 10.8% | 10.5% | 26.0% | 0.39 | 0.40 | Rs 189,480 |
| Selector over all 987 trials, 1 standard error | 11.5% | 11.2% | 26.5% | 0.36 | 0.82 | Rs 435,550 |
| Selector over all 987 trials, deflated margin (3.4 standard errors) | 8.2% | 7.9% | 26.0% | 0.18 | 0.33 | Rs 125,600 |
| S0 plain holding (Nifty ETF and cash) (alone) | 8.2% | 7.9% | 26.0% | 0.18 | 0.33 | Rs 125,600 |
| E1 equal weight, six ETFs and cash (alone) | 13.7% | 13.3% | 22.4% | 0.69 | 0.20 | Rs 272,510 |
| E2 trend filters (mean of 6) (alone) | 10.5% | 10.5% | 21.0% | 0.43 | 8.19 | Rs 809,780 |
| E3 momentum rotation (mean of 18) (alone) | 11.0% | 11.0% | 22.7% | 0.36 | 2.30 | Rs 759,460 |
| E4 volatility targeting (mean of 10) (alone) | 8.6% | 8.6% | 20.6% | 0.22 | 0.92 | Rs 285,090 |
| E5 drawdown-aware exposure (mean of 6) (alone) | 8.6% | 8.6% | 21.8% | 0.21 | 0.81 | Rs 231,620 |
| Nifty BeES held | 11.8% | 11.0% | 36.3% | 0.39 | 0.01 | Rs 10 |
| Junior BeES held | 15.0% | 14.2% | 38.7% | 0.52 | 0.01 | Rs 10 |
| Bank BeES held | 12.5% | 11.8% | 47.7% | 0.35 | 0.01 | Rs 0 |
| Gold BeES held | 11.4% | 10.4% | 25.5% | 0.36 | 0.02 | Rs 0 |
| Midcap 100 ETF held | 16.8% | 15.9% | 48.4% | 0.58 | 0.01 | Rs 10 |
| Nasdaq 100 ETF held | 24.9% | 23.4% | 36.6% | 0.84 | 0.01 | Rs 360 |
| Liquid fund held | 6.8% | 6.0% | 0.2% | -0.74 | 0.02 | Rs 100 |

- Selector over the ensembles, 1 standard error: edge over S0 +2.5 points a year (bootstrap standard error 1.0); picked a strategy at 6 of 14 cuts (E1: 6).
- Selector over the ensembles, deflated margin (1.3 standard errors): edge over S0 +2.5 points a year (bootstrap standard error 1.0); picked a strategy at 6 of 14 cuts (E1: 6).
- Selector over all 987 trials, 1 standard error: edge over S0 +3.2 points a year (bootstrap standard error 5.0); picked a strategy at 12 of 14 cuts (S1: 12).
- Selector over all 987 trials, deflated margin (3.4 standard errors): edge over S0 +0.0 points a year (bootstrap standard error 0.0); picked a strategy at 0 of 14 cuts (none).

ensembles: 6 candidates, about 2 independent. Probability of backtest overfitting (in-sample, whole design period): 18%. Best in-sample candidate E1|equal-weight,rebalance=year|band=0.01: deflated Sharpe probability 96% (sizes the selection effect, not a result).
all trials: 987 candidates, about 331 independent. Probability of backtest overfitting (in-sample, whole design period): 31%. Best in-sample candidate S1|weights=0/0/0/0.2/0.2/0.2/0.4,rebalance=year|band=0.01: deflated Sharpe probability 77% (sizes the selection effect, not a result).

Selector paths, deflated for the four variants tried: 84% (ensembles, spec), 84% (ensembles, deflated), 82% (all trials, spec), 61% (all trials, deflated).

## Capped 40%: drawdown cap 40%

| Account, fresh from 2013-04-01 to 2026-09-30 | After-tax growth a year | After selling all | Worst drawdown | Sharpe | Turnover a year | Tax |
|---|---|---|---|---|---|---|
| Selector over the ensembles, 1 standard error | 11.3% | 11.1% | 31.6% | 0.39 | 0.35 | Rs 335,230 |
| Selector over the ensembles, deflated margin (1.3 standard errors) | 10.0% | 9.9% | 31.6% | 0.32 | 0.34 | Rs 279,550 |
| Selector over all 987 trials, 1 standard error | 12.9% | 12.3% | 33.9% | 0.41 | 0.57 | Rs 434,380 |
| Selector over all 987 trials, deflated margin (3.4 standard errors) | 9.7% | 9.3% | 31.6% | 0.28 | 0.24 | Rs 100,340 |
| S0 plain holding (Nifty ETF and cash) (alone) | 9.7% | 9.3% | 31.6% | 0.28 | 0.24 | Rs 100,340 |
| E1 equal weight, six ETFs and cash (alone) | 14.3% | 13.8% | 24.2% | 0.72 | 0.16 | Rs 276,540 |
| E2 trend filters (mean of 6) (alone) | 10.4% | 10.4% | 24.3% | 0.42 | 8.34 | Rs 797,930 |
| E3 momentum rotation (mean of 18) (alone) | 11.7% | 11.7% | 24.2% | 0.40 | 2.18 | Rs 812,980 |
| E4 volatility targeting (mean of 10) (alone) | 8.8% | 8.8% | 21.8% | 0.24 | 0.91 | Rs 295,100 |
| E5 drawdown-aware exposure (mean of 6) (alone) | 9.5% | 9.5% | 23.5% | 0.27 | 0.76 | Rs 283,660 |
| Nifty BeES held | 11.8% | 11.0% | 36.3% | 0.39 | 0.01 | Rs 10 |
| Junior BeES held | 15.0% | 14.2% | 38.7% | 0.52 | 0.01 | Rs 10 |
| Bank BeES held | 12.5% | 11.8% | 47.7% | 0.35 | 0.01 | Rs 0 |
| Gold BeES held | 11.4% | 10.4% | 25.5% | 0.36 | 0.02 | Rs 0 |
| Midcap 100 ETF held | 16.8% | 15.9% | 48.4% | 0.58 | 0.01 | Rs 10 |
| Nasdaq 100 ETF held | 24.9% | 23.4% | 36.6% | 0.84 | 0.01 | Rs 360 |
| Liquid fund held | 6.8% | 6.0% | 0.2% | -0.74 | 0.02 | Rs 100 |

- Selector over the ensembles, 1 standard error: edge over S0 +1.5 points a year (bootstrap standard error 0.8); picked a strategy at 2 of 14 cuts (E1: 2).
- Selector over the ensembles, deflated margin (1.3 standard errors): edge over S0 +0.6 points a year (bootstrap standard error 0.5); picked a strategy at 1 of 14 cuts (E1: 1).
- Selector over all 987 trials, 1 standard error: edge over S0 +3.0 points a year (bootstrap standard error 5.7); picked a strategy at 12 of 14 cuts (S1: 12).
- Selector over all 987 trials, deflated margin (3.4 standard errors): edge over S0 +0.0 points a year (bootstrap standard error 0.0); picked a strategy at 0 of 14 cuts (none).

ensembles: 6 candidates, about 2 independent. Probability of backtest overfitting (in-sample, whole design period): 15%. Best in-sample candidate E1|equal-weight,rebalance=year|band=0.01: deflated Sharpe probability 97% (sizes the selection effect, not a result).
all trials: 987 candidates, about 323 independent. Probability of backtest overfitting (in-sample, whole design period): 32%. Best in-sample candidate S1|weights=0/0/0/0.2/0.2/0.4/0.2,rebalance=year|band=0.01: deflated Sharpe probability 83% (sizes the selection effect, not a result).

Selector paths, deflated for the four variants tried: 88% (ensembles, spec), 83% (ensembles, deflated), 89% (all trials, spec), 78% (all trials, deflated).

## No guard: no cap, governor off

| Account, fresh from 2013-04-01 to 2026-09-30 | After-tax growth a year | After selling all | Worst drawdown | Sharpe | Turnover a year | Tax |
|---|---|---|---|---|---|---|
| Selector over the ensembles, 1 standard error | 11.5% | 11.0% | 36.3% | 0.37 | 0.11 | Rs 97,210 |
| Selector over the ensembles, deflated margin (1.3 standard errors) | 11.5% | 11.0% | 36.3% | 0.37 | 0.11 | Rs 97,210 |
| Selector over all 987 trials, 1 standard error | 17.4% | 16.4% | 47.0% | 0.55 | 0.15 | Rs 262,390 |
| Selector over all 987 trials, deflated margin (3.4 standard errors) | 11.5% | 11.0% | 36.3% | 0.37 | 0.11 | Rs 97,210 |
| S0 plain holding (Nifty ETF and cash) (alone) | 11.5% | 11.0% | 36.3% | 0.37 | 0.11 | Rs 97,210 |
| E1 equal weight, six ETFs and cash (alone) | 14.8% | 14.3% | 24.3% | 0.75 | 0.14 | Rs 276,060 |
| E2 trend filters (mean of 6) (alone) | 10.4% | 10.4% | 25.2% | 0.42 | 8.42 | Rs 799,950 |
| E3 momentum rotation (mean of 18) (alone) | 12.0% | 12.0% | 24.3% | 0.41 | 2.16 | Rs 852,380 |
| E4 volatility targeting (mean of 10) (alone) | 8.9% | 8.9% | 21.8% | 0.24 | 0.91 | Rs 297,240 |
| E5 drawdown-aware exposure (mean of 6) (alone) | 9.6% | 9.6% | 23.8% | 0.28 | 0.78 | Rs 287,100 |
| Nifty BeES held | 11.8% | 11.0% | 36.3% | 0.39 | 0.01 | Rs 10 |
| Junior BeES held | 15.0% | 14.2% | 38.7% | 0.52 | 0.01 | Rs 10 |
| Bank BeES held | 12.5% | 11.8% | 47.7% | 0.35 | 0.01 | Rs 0 |
| Gold BeES held | 11.4% | 10.4% | 25.5% | 0.36 | 0.02 | Rs 0 |
| Midcap 100 ETF held | 16.8% | 15.9% | 48.4% | 0.58 | 0.01 | Rs 10 |
| Nasdaq 100 ETF held | 24.9% | 23.4% | 36.6% | 0.84 | 0.01 | Rs 360 |
| Liquid fund held | 6.8% | 6.0% | 0.2% | -0.74 | 0.02 | Rs 100 |

- Selector over the ensembles, 1 standard error: edge over S0 +0.0 points a year (bootstrap standard error 0.0); picked a strategy at 0 of 14 cuts (none).
- Selector over the ensembles, deflated margin (1.3 standard errors): edge over S0 +0.0 points a year (bootstrap standard error 0.0); picked a strategy at 0 of 14 cuts (none).
- Selector over all 987 trials, 1 standard error: edge over S0 +5.2 points a year (bootstrap standard error 6.2); picked a strategy at 12 of 14 cuts (S1: 12).
- Selector over all 987 trials, deflated margin (3.4 standard errors): edge over S0 +0.0 points a year (bootstrap standard error 0.0); picked a strategy at 0 of 14 cuts (none).

ensembles: 6 candidates, about 2 independent. Probability of backtest overfitting (in-sample, whole design period): 11%. Best in-sample candidate E1|equal-weight,rebalance=year|band=0.01: deflated Sharpe probability 98% (sizes the selection effect, not a result).
all trials: 987 candidates, about 317 independent. Probability of backtest overfitting (in-sample, whole design period): 32%. Best in-sample candidate S1|weights=0/0/0/0.2/0.2/0.6/0,rebalance=year|band=0.01: deflated Sharpe probability 86% (sizes the selection effect, not a result).

Selector paths, deflated for the four variants tried: 85% (ensembles, spec), 85% (ensembles, deflated), 95% (all trials, spec), 85% (all trials, deflated).

