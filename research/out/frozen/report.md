# Frozen test: the three years nothing was designed on

Run once on code 1783e36a24f669e95a317e56ba4ca014d2a18586 (tag frozen-design-v1), 2023-10-03 to 2026-09-30. Every account starts fresh on the first trading day with Rs 10 lakh; the strategies and plain holding run with the drawdown governor at the risk level's cap and with W1 harvesting; the reference investments are bought and held plainly. Charges, slippage and tax by each transaction's own date; growth is after tax, and 'after selling all' also sells everything on the last day and pays that tax.

Three years is one market path: a result here, either way, is weak evidence on its own. It is the honest check the design was frozen for, not proof.

## Conservative: drawdown cap 10%

| Account | After-tax growth a year | After selling all | Worst drawdown | Sharpe | Turnover a year | Tax |
|---|---|---|---|---|---|---|
| Selector (deflated margin 1.39 standard errors) | 6.5% | 4.0% | 3.0% | -0.08 | 0.28 | Rs 13,380 |
| Selector, 1 standard error | 6.5% | 4.0% | 3.0% | -0.08 | 0.28 | Rs 13,380 |
| S0 plain holding | 6.5% | 4.0% | 3.0% | -0.08 | 0.28 | Rs 13,380 |
| E1 equal weight | 11.2% | 10.9% | 8.9% | 0.63 | 0.94 | Rs 153,710 |
| E2 trend filters | 9.9% | 9.6% | 8.7% | 0.35 | 7.37 | Rs 151,520 |
| E3 momentum rotation | 19.0% | 17.2% | 13.0% | 0.94 | 2.10 | Rs 177,550 |
| E4 volatility targeting | 5.7% | 5.7% | 8.4% | -0.11 | 1.71 | Rs 39,530 |
| E5 drawdown-aware exposure | 6.6% | 6.6% | 8.7% | 0.00 | 1.47 | Rs 56,280 |
| S6 deep model | 10.0% | 10.0% | 9.2% | 0.56 | 1.40 | Rs 183,210 |
| Nifty BeES held | 6.5% | 4.3% | 15.2% | 0.02 | 0.13 | Rs 0 |
| Junior BeES held | 16.9% | 13.8% | 25.9% | 0.62 | 0.11 | Rs 0 |
| Bank BeES held | 8.1% | 5.8% | 18.1% | 0.15 | 0.14 | Rs 0 |
| Gold BeES held | 36.0% | 31.1% | 24.4% | 1.24 | 0.10 | Rs 0 |
| Liquid fund held | 7.0% | 4.0% | 0.0% | -0.58 | 0.15 | Rs 0 |

The product **is plain holding** in these years after selling all (+0.00 points a year), and its worst drawdown is within the cap.
Held in these years (pick of each April): 2023-04-03: S0|cap=0.1|band=0.01; 2024-04-01: S0|cap=0.1|band=0.01; 2025-04-01: S0|cap=0.1|band=0.01; 2026-04-01: S0|cap=0.1|band=0.01.
Replay of the product's 39 orders through the exact engine: charges differ by Rs 1.59 in total (0.0001% of the final wealth; largest single order Rs 1.00).

## Balanced: drawdown cap 20%

| Account | After-tax growth a year | After selling all | Worst drawdown | Sharpe | Turnover a year | Tax |
|---|---|---|---|---|---|---|
| Selector (deflated margin 1.33 standard errors) | 7.0% | 6.8% | 13.1% | 0.26 | 0.80 | Rs 162,790 |
| Selector, 1 standard error | 10.1% | 10.0% | 13.2% | 0.53 | 0.64 | Rs 163,900 |
| S0 plain holding | 6.1% | 3.9% | 7.0% | -0.08 | 0.39 | Rs 22,000 |
| E1 equal weight | 10.1% | 10.0% | 13.2% | 0.53 | 0.64 | Rs 163,900 |
| E2 trend filters | 11.6% | 11.6% | 11.5% | 0.45 | 9.98 | Rs 164,670 |
| E3 momentum rotation | 19.9% | 19.6% | 16.3% | 0.91 | 1.91 | Rs 182,780 |
| E4 volatility targeting | 3.9% | 3.9% | 12.5% | -0.25 | 1.31 | Rs 29,910 |
| E5 drawdown-aware exposure | 3.3% | 3.3% | 14.2% | -0.26 | 1.05 | Rs 72,750 |
| S6 deep model | 10.7% | 9.9% | 12.8% | 0.51 | 0.94 | Rs 158,060 |
| Nifty BeES held | 6.5% | 4.3% | 15.2% | 0.02 | 0.13 | Rs 0 |
| Junior BeES held | 16.9% | 13.8% | 25.9% | 0.62 | 0.11 | Rs 0 |
| Bank BeES held | 8.1% | 5.8% | 18.1% | 0.15 | 0.14 | Rs 0 |
| Gold BeES held | 36.0% | 31.1% | 24.4% | 1.24 | 0.10 | Rs 0 |
| Liquid fund held | 7.0% | 4.0% | 0.0% | -0.58 | 0.15 | Rs 0 |

The product **beats plain holding** after selling all (+2.87 points a year), and its worst drawdown is within the cap.
Held in these years (pick of each April): 2023-04-03: S0|cap=0.2|band=0.01; 2024-04-01: E1|equal-weight,rebalance=year|band=0.01; 2025-04-01: E1|equal-weight,rebalance=year|band=0.01; 2026-04-01: E1|equal-weight,rebalance=year|band=0.01.
Replay of the product's 47 orders through the exact engine: charges differ by Rs 3.03 in total (0.0002% of the final wealth; largest single order Rs 0.88).

## Aggressive: drawdown cap 30%

| Account | After-tax growth a year | After selling all | Worst drawdown | Sharpe | Turnover a year | Tax |
|---|---|---|---|---|---|---|
| Selector (deflated margin 1.31 standard errors) | 11.6% | 10.9% | 13.2% | 0.63 | 0.41 | Rs 149,620 |
| Selector, 1 standard error | 11.6% | 10.9% | 13.2% | 0.63 | 0.41 | Rs 149,620 |
| S0 plain holding | 5.1% | 3.7% | 11.1% | -0.14 | 0.44 | Rs 47,510 |
| E1 equal weight | 11.6% | 10.9% | 13.2% | 0.63 | 0.41 | Rs 149,620 |
| E2 trend filters | 11.7% | 11.7% | 11.5% | 0.46 | 10.10 | Rs 166,130 |
| E3 momentum rotation | 17.3% | 17.3% | 20.0% | 0.81 | 1.84 | Rs 228,870 |
| E4 volatility targeting | 4.3% | 4.3% | 12.8% | -0.17 | 1.09 | Rs 38,040 |
| E5 drawdown-aware exposure | 3.8% | 3.8% | 14.8% | -0.20 | 0.96 | Rs 65,270 |
| S6 deep model | 10.1% | 9.7% | 12.8% | 0.48 | 0.86 | Rs 169,290 |
| Nifty BeES held | 6.5% | 4.3% | 15.2% | 0.02 | 0.13 | Rs 0 |
| Junior BeES held | 16.9% | 13.8% | 25.9% | 0.62 | 0.11 | Rs 0 |
| Bank BeES held | 8.1% | 5.8% | 18.1% | 0.15 | 0.14 | Rs 0 |
| Gold BeES held | 36.0% | 31.1% | 24.4% | 1.24 | 0.10 | Rs 0 |
| Liquid fund held | 7.0% | 4.0% | 0.0% | -0.58 | 0.15 | Rs 0 |

The product **beats plain holding** after selling all (+7.22 points a year), and its worst drawdown is within the cap.
Held in these years (pick of each April): 2023-04-03: E1|equal-weight,rebalance=year|band=0.01; 2024-04-01: E1|equal-weight,rebalance=year|band=0.01; 2025-04-01: E1|equal-weight,rebalance=year|band=0.01; 2026-04-01: E1|equal-weight,rebalance=year|band=0.01.
Replay of the product's 40 orders through the exact engine: charges differ by Rs 2.65 in total (0.0002% of the final wealth; largest single order Rs 0.91).

