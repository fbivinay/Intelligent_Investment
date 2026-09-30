# Strategy engine 3A: research panel, fast simulator, strategies S0 to S5 and W1, CPU baseline

> Executed inline (author and executor are the same session); every task is test first. The Kaggle pipeline, the deep-learning and futures candidates, the selector
> and the freeze are plan 3B, written when 3A is done.

**Goal:** the first visible result of the model work: for each risk level, the after-tax, after-cost, drawdown-governed result of the same-risk plain holding and of every
S1 to S5 strategy (and the W1 wrapper) over the design period, from a fast simulator that agrees with the exact `engine/`.

**Spec:** `docs/superpowers/specs/2026-10-01-strategy-engine-design.md` (sections 2 to 5 and step 1 to 3 of section 8).

**Tech:** Python 3.13, numpy, pandas, numba, pytest. The engine stays exact Decimal; the research code is float and fast and is checked against it.

## Global constraints (from the spec)

- Decision after the close of t, fill at the open of t+1 (the NAV of t+1 for the liquid fund). Holding P&L is open(t+1) to open(t+2).
- Instruments: NIFTYBEES, JUNIORBEES, BANKBEES, GOLDBEES (split-adjusted), the liquid fund as cash (`nav_units.csv` applied, regular plan spliced to direct on 2013-01-01).
- Research capital Rs 10 lakh; research tax profile: new regime, other income Rs 12 lakh; design period 2010-04-01 to 2023-09-30; the frozen years are never loaded by 3A code
  (`load_panel(end=...)` cuts the data, and the default `end` is the design end).
- Risk caps 10%, 20%, 30% of the reference account's close-marked drawdown; governor from half the cap to 90% of it; re-risk after a new high or 60 days without a new low.
- Every strategy and parameter set run is a trial and is written to the ledger (`research/out/trials.csv`).

## Files

```
research/__init__.py
research/panel.py        load_panel(): aligned arrays, cash series, index features; Panel dataclass
research/causal.py       assert_causal(): truncate the data at cut points and compare the decisions up to each cut
research/features.py     causal features from a Panel
research/costs.py        per-day charge rates by instrument class, worked out by calling engine.charges at several order sizes; slippage model
research/taxparams.py    per-day tax parameters by bucket read from the engine's rule tables (rates, holding months, exemption, grandfathering, slab rate)
research/sim.py          numba simulator: next-open fills, whole units, FIFO lots, charges, slippage, yearly tax, governor, metrics
research/governor.py     the drawdown governor as a function of the account's own path
research/strategies.py   S0..S5 and W1: each returns target weights (T x 5) using only data up to each day
research/baseline.py     runs every strategy for every risk level over the design period, writes the ledger and the baseline table
tests/test_research_*.py
```

## Tasks

1. **Panel.** `load_panel(root, end)` returns `Panel(dates, assets, open, high, low, close, value, cash, index)` as float arrays (T x 4 for the ETFs, T for cash and index
   columns, NaN where a source has no value). Tests (synthetic csv in `tmp_path`): dates are the days every ETF has a row; split-adjusted prices are continuous across a
   split; the cash series takes the regular plan to 2012-12-31 and the direct plan after, on daily returns, and is continuous across the splice and across a x100 unit
   change; `end` cuts every array; a missing ETF day is refused.
2. **Causality harness and features.** `assert_causal(fn, panel, cuts)`; a deliberately look-ahead function (centred mean) must fail it. Features: returns over 1, 5, 21, 63,
   252 days, 21 and 63 day volatility, drawdown from the 252 day high, distance from the 50 and 200 day averages, traded value spike, VIX level and change, P/E and P/B
   expanding percentile (NaN until a year of history), gold against equity strength, trailing cash yield. Tests: each feature by hand on a tiny panel, the harness passes
   on all of them, NaN where history is short.
3. **Costs.** `charge_table(rules, days, classes)` gives, per day and class, (rate on the buy value, rate on the sell value, fixed per order) fitted from
   `engine.charges.order_charges` at three order sizes and checked to be linear to a stated tolerance; `slippage(value, adv, instrument)`. Tests: equals the engine on
   recorded orders (a Nifty BeES buy and sell on dates either side of a STT or brokerage change); slippage grows with the order size and is zero for a zero order.
4. **Tax parameters.** `tax_table(rules, fy, bucket, profile)` reads the rule tables: short and long rate, holding months, treatment (special, slab, exempt), yearly exemption,
   grandfathering date, the profile's marginal slab rate with cess. Tests: equal to the rule rows on dates either side of 2018-04-01, 2023-04-01 and 2024-07-23.
5. **Simulator.** `simulate(panel, weights, cfg) -> Result(wealth, drawdown, turnover, costs, tax, units)` in numba. Decision weights at t fill at open t+1; buys and sells in whole
   units after slippage and charges; a trade band (default 1% of wealth) and a minimum trade value; FIFO lots per asset; tax at each financial year end from the year's
   gains (short and long pools, exemption, loss netting within the year, loss carried to the next year), paid from the cash leg; a hypothetical sale of everything at the end
   (the liquidation tax) is reported separately. Tests: (a) value accounting: wealth = sum of holdings at the close, every day; (b) hand-worked two-trade scenario with
   known charges and tax; (c) a buy and hold of one ETF agrees with `engine.scenario.buy_and_hold` within 0.5% of the final wealth and the tax line within Rs 1,000;
   (d) a weight vector never buys more than the cash it has; (e) same input, same output.
6. **Governor.** `apply_governor(weights, equity_path, cap)` inside the simulator loop: risky weights scaled by the drawdown rule, the rest to cash; hysteresis as in the
   spec. Tests: full exposure under half the cap, zero at 90% of it, linear between, stays cut until a new high or 60 days without a new low.
7. **Strategies.** S0 (same-risk plain holding: Nifty share the largest whose training drawdown is within the cap), S1 (static mixes on a 10% grid, yearly or no rebalancing),
   S2 (trend filter: lengths 50, 100, 200; equal or inverse-volatility), S3 (momentum rotation: lookbacks 3, 6, 12 months; k 1 to 3; monthly or quarterly), S4 (volatility
   targeting of the equity sleeve: target 6 to 18%, lookbacks 20 and 60), S5 (drawdown-aware exposure: start and end points), W1 (tax-aware wrapper: hold a lot that is within
   30 or 60 days of turning long term unless the signal is strongly against it; realise gains up to the exemption each financial year). Tests: weights sum to 1 and are
   non-negative; each strategy passes `assert_causal` on random cuts; S0's equity share shrinks as the cap shrinks; W1 reduces the number of short-term sales on a synthetic
   path that crosses the one-year mark.
8. **Baseline.** `python -m research.baseline` runs S0..S5 and W1 for the three risk levels over 2010-04-01 to 2023-09-30 from the start of the design period (one reference
   account per strategy and level), writes `research/out/trials.csv` (every run: id, family, parameters, risk level, dates, after-tax CAGR, liquidation-tax CAGR, max
   drawdown, turnover, costs, tax) and `research/out/baseline.md` (best per family and level against S0). Test: the run is deterministic (same file hash twice), every row is in
   the ledger, and no strategy run reads data after the design end.

## Review focus (inputs the tests above do not exercise, most likely to bite)

- A split or unit-change day inside a holding period (the 2019-12-19 ETF splits, the 2012 and 2013 liquid fund changes): wealth must not jump.
- A day an ETF has no traded value (average traded value zero): slippage must not divide by zero.
- A strategy that wants 100% in an asset whose price exceeds the wealth: no purchase, no crash.
- A financial year with a net loss: loss carried forward, never a negative tax.
- The last day of the design period falling on a non-trading day.
