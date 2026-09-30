# Strategy engine (sub-project 3): Design

Date: 2026-10-01. Status: draft for review. Refines sections 9 and 10 of `2026-09-29-india-algo-system-design.md`; everything decided there still stands
(risk levels, frozen last 3 years, default = plain holding, Kaggle GPU for deep learning and big sweeps).

## 1. What it produces

For each risk level (Conservative, Balanced, Aggressive) a **signal artifact**: target weights by date from 2013-04-01 to today, made only from data
available at the close of each day; the log of which strategy was picked each year and why; the ledger of every strategy tried; and diagnostics (deflated
Sharpe, probability of overfitting, causality test). The artifact is small, hashed, and replayed later through `engine/` for any amount, dates and tax
profile (sub-project 4 and 5). The question it answers: *does anything beat plain holding after every tax and cost, out of sample, at the same risk?*
"No" is a valid answer and is published as such.

## 2. Conventions (fixed before any result is seen)

| Topic | Rule |
|---|---|
| Decision time | After the close of day t. The strategy sees data up to and including t only. |
| Fill | At the open of the next trading day t+1 (funds: the NAV of t+1), with slippage. Profit and loss of the holding is open(t+1) to open(t+2). |
| Instruments | NIFTYBEES, JUNIORBEES, BANKBEES, GOLDBEES (ETFs); a liquid fund as the cash leg (Nippon India Liquid, regular plan to 2012-12, direct from 2013-01, spliced on daily returns; LIQUIDBEES cannot be used, its price is flat); NIFTY and BANKNIFTY index futures (Aggressive only, leverage up to 1.5x). The Midcap 100 index has no instrument in the data: a feature only. |
| Tax classes | `etf_equity`, `etf_gold`, `mf_debt` (cash leg), futures as business income: the engine's own classes and rules by date. |
| Research capital | Rs 10 lakh (slippage and lot rounding bite at this size; the site scales later). |
| Research tax profile | Resident individual, new regime, other income Rs 12 lakh (labelled; the replay uses the user's profile). |
| Slippage | Half-spread by instrument plus an impact term in (order value / 20-day average traded value, past data only). Parameters are assumptions, labelled, and shown in every trace that uses them. |
| Risk caps | Maximum drawdown of the reference account marked at the close, before tax: Conservative 10%, Balanced 20%, Aggressive 30%. Caps are targets, not guarantees. |
| Design period | 2010-04-01 to 2023-09-30. First pick on 2013-04-01 (3 years of training minimum); before that the same-risk plain holding applies and is labelled "no model yet". |
| Frozen test | 2023-10-01 to 2026-09-30, run once after the design is frozen (git tag and hashes). The selector still re-picks each April inside it, from past data only. |
| Young instruments | None in v1: every instrument exists from 2010-04. A future instrument is tradable only after 1 year of history. |
| Weights depend on the date only | The artifact holds the weights of one reference account (research capital, start 2013-04-01), including the cap governor. A user starting on another date gets the same weights; their own drawdown can exceed the cap. Said on the site. |

Data needed (all in `data/`): adjusted ETF open and close (splits from `corporate_actions.csv`), NAVs with unit changes applied (`nav_units.csv`), traded
value for average daily volume, India VIX, index P/E and P/B (from 2012-07; blank before, so features that use them are off before then), futures with
lot sizes.

## 3. Strategies (committed before any evaluation; every one, with every parameter set, is a trial)

| # | Family | Parameters tried |
|---|---|---|
| S0 | **Same-risk plain holding** (the default and the benchmark): Nifty ETF plus the cash leg, equity share the largest whose training-window drawdown is within the cap; it has the governor too, so every comparison is like for like | one per risk level |
| S1 | Static mixes of the four ETFs and cash, rebalanced yearly or never | weights on a 10% grid |
| S2 | Trend filter per asset: hold it while above its moving average, else cash | average length 50, 100, 200; equal or inverse-volatility weights |
| S3 | Momentum rotation: hold the top k assets by past return | lookback 3, 6, 12 months; k 1 to 3; monthly or quarterly |
| S4 | Volatility targeting of the equity sleeve | target 6 to 18%; lookback 20, 60 days |
| S5 | Drawdown-aware exposure (scale down as the account nears its own high-water drawdown) | start and end points |
| S6 | **Deep learning position model** (Deep Momentum Network): LSTM, GRU, TCN, small Transformer, MLP; output = long-only weights over the assets and cash (Aggressive: signed futures weight); loss = negative Sharpe with a turnover penalty; retrained each April on an expanding window; 3 seeds averaged | architecture, sequence length, penalty, 3 seeds |
| S7 | Futures overlay (Aggressive only): hedge when trend is down, lever up to 1.5x when trend is up and volatility is low | thresholds |
| W1 | Tax-aware execution (wraps any of the above): do not sell a lot within 30 days of turning long term unless the signal is strongly against it; each financial year realise gains up to the exemption and buy back | on or off, 30 or 60 days |

Features are causal by construction: returns over 1, 5, 21, 63, 252 days, realised volatility, drawdown, distance from the 50 and 200 day averages, volume
spikes, India VIX level and change, index P/E and P/B percentiles (from 2012-07), gold against equity strength, trailing cash yield, futures basis and open
interest change. Each is computed only from data up to t; a test proves it (section 6).

## 4. Cap governor (live, applies to every strategy at its risk level)

The reference account's drawdown from its high-water mark scales the risky share: full exposure while the drawdown is under half the cap, falling in a
straight line to zero at 90% of the cap, back to full exposure only after a new high-water mark or 60 trading days without a new low. The governor is part
of each strategy in the simulation, so selection sees its cost (sells, tax, missed recovery), not a free insurance.

## 5. Walk-forward selector

Every first trading day of April, from 2013: use only data before that day.

1. Simulate every strategy (with its governor) on the expanding training window, after charges, slippage and tax, from the window start: after-tax wealth,
   maximum drawdown, turnover, tax paid.
2. Eligible: training drawdown within the cap (governor on).
3. Score: after-tax growth (log of ending wealth per year).
4. Keep plain holding unless the best eligible strategy beats it by more than selection noise: the paired difference of the two after-tax wealth paths
   (daily log changes, annualised) must exceed one standard error (stationary block bootstrap, blocks of about a month). Otherwise S0 stays.
5. Write the pick, its score, the runner-up and the reason to the selection log. Hold the pick for the financial year.

The stitched weights over all Aprils are the out-of-sample history the site shows.

## 6. Protection against fooling ourselves

- **Trial ledger**: every strategy and parameter set, every April, every design-time experiment, with its date and metrics (`research/out/trials.csv`). The count
  feeds the deflated Sharpe ratio.
- **Deflated Sharpe ratio** and **probability of backtest overfitting** (combinatorially symmetric cross-validation over strategy by time block) on the
  design period, published next to the result.
- **Purged and embargoed splits** inside training for anything tuned (deep-learning epochs, penalties): train, purge the horizon, embargo, validate.
- **Causality test for every strategy and feature**: cut the data at a random date T, rerun; all decisions up to T must equal the full run. It runs on
  every candidate in the test suite and on the final artifact.
- **Frozen final test** once, after the tag; the run writes its own record (code hash, data hash, date). Any later change to the candidate list or the
  selector voids it and is stated.
- **Design-time hindsight** is disclosed: we know history when choosing the list. The committed list and the frozen years limit it.

## 7. Compute

Everything is tested locally on small grids first. Kaggle GPU (private kernels on a T4, no internet, datasets uploaded by us) does the heavy parts, reusing
the login already on this machine:

| Stage | Where | Work |
|---|---|---|
| Snapshot | local to Kaggle Dataset | `panel`, `features`, rule constants, code package, each with its SHA-256 in `manifest.json` |
| 1 | Kaggle GPU (PyTorch; JAX if the image has it) | pre-tax, after-cost screening of all parameter sets on every training window, vectorised; deep-learning training each April with several seeds and architectures |
| 2 | Kaggle CPU or local, multiprocess | exact after-tax simulation of the survivors (the number fixed by rule before results are seen: best 25 per risk level per April, plus S0) |
| 3 | local | selector, diagnostics, signal artifact; replay through `engine/` and compare with the fast simulator |

Every screened candidate still counts as a trial. GPU training is not bit-for-bit repeatable, so the saved weights are the record; the replay from them is
exact. Kaggle quotas and session limits apply (a T4 session is limited to a few hours; jobs are split by April).

## 8. Order of work ("done when" for each)

1. **Research panel and features**: one aligned daily table with the cash leg and every feature. Done when a causality test passes for every feature and the
   splice and split days are continuous.
2. **Fast simulator** (float, vectorised): next-open fills, costs, slippage, lot rounding, FIFO tax with the engine's rates by date, governor. Done when it
   agrees with the exact `engine/` replay within a stated tolerance on hand-worked and recorded scenarios.
3. **Strategies S0 to S5, W1** with the causality harness. Done when every one passes it and a CPU baseline run gives a first table: each strategy's after-tax
   result and drawdown for each risk level over the design period.
4. **Kaggle pipeline**: snapshot upload, kernel push, poll, pull, verify hashes. Done when a small sweep runs on the GPU and matches the local result.
5. **Deep-learning candidate S6 and futures overlay S7** on Kaggle, with purged validation.
6. **Selector, ledger, diagnostics** and the walk-forward stitched series. Done when it reproduces from data and code alone.
7. **Exact replay and freeze**, then the single frozen-test run and the artifacts.

Each step is a plan task with tests first; the first visible result is the baseline table after step 3.

## 9. Choices made for you (say which to change)

1. Fills at the next open, daily decisions, weights depend on the date only.
2. Universe: the four ETFs, a liquid fund as cash, futures only for Aggressive.
3. Research capital Rs 10 lakh; research tax profile: new regime, other income Rs 12 lakh.
4. Same-risk plain holding is the default for each level (not 100% Nifty for everyone).
5. Selection noise margin: one standard error of the paired after-tax difference (block bootstrap).
6. First pick 2013-04-01 (3 years of training); frozen test 2023-10-01 to 2026-09-30.
7. Governor: half the cap to 90% of the cap, re-risk after a new high or 60 days.
8. Deep learning: five architectures, three seeds, Sharpe loss with a turnover penalty, retrained yearly.

## 10. Honest limits

- One market, about 16 years: 13 yearly selections and a handful of regimes. The deflated Sharpe and overfitting probability exist because this is thin.
- After Indian short-term tax (15% then 20%) and charges, active trading rarely beats holding. A result of "mostly hold, tilt a little" is a good outcome.
- The fast simulator approximates tax for ranking; the exact engine decides the published numbers, and the gap between the two is reported.
- Slippage, the research tax profile and the governor settings are assumptions. Changing them changes the picks; the ledger records which were used.
- Futures margin history is not free: a conservative assumption, labelled (parent spec section 15).
