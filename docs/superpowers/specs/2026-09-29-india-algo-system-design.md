# India Algo System: Design (v3, fresh start)

Date: 2026-09-29. Status: draft for review.
Replaces all earlier work (Bitcoin ETF model, Deep Momentum Network). Old code is archived in git, not reused.

## 1. What we are building

One product that answers:

> "If I invested ₹X on date Y, what would I have after every real cost and tax, compared with the main alternatives, and what range could happen if I invest today?"

Six parts:

1. A rules engine: Indian tax and Fyers costs, by transaction date.
2. A data layer: free, reproducible, point-in-time.
3. A strategy engine that picks its own approach, walk-forward, tested against overfitting.
4. A comparison and projection engine.
5. A public website: live controls, an ⓘ trace on every number.
6. A demo of how the orders would go through Fyers (no real connection).

## 2. Ground rules

1. Genuine results only. No look-ahead, data leakage, survivorship bias, cherry-picking or unrealistic fills.
2. Every transaction is taxed and charged by the rules of its own date. The same holds for every comparison.
3. Every number has a trace: exact inputs, formula, rule used, source link.
4. Actual history and future estimates are always labelled. An estimate is never a promise.
5. Optimise after-tax, after-charge, risk-adjusted return, not headline return.
6. No real orders are ever sent. Fyers is the design target. We show how it would work; we do not connect to it.

## 3. Decisions agreed in chat

| Topic | Decision |
|---|---|
| Deep learning | Evidence decides. DL is one candidate. It wins only if it beats simpler methods after tax and cost, out-of-sample. |
| v1 universe | Index ETFs and funds, index futures, gold, liquid/arbitrage funds. Single stocks and options come later (stocks need point-in-time index membership and corporate-action data). |
| Start dates | 2010-04-01 onward. Earlier needs more rule research. |
| Engine | One Python engine. The website calls it through a thin API. The same code makes each number and its trace. |
| End convention | Sell everything on the end date and pay the tax. "Still holding" is shown beside it. |
| Strategy choice | Walk-forward selector, re-picking once a year. The default is plain index holding. A candidate replaces it only if it beats it after tax by more than selection noise. |
| Risk levels | Conservative: max drawdown 10%, long only, no leverage. Balanced: 20%, long only, no leverage. Aggressive: 30%, futures allowed, leverage up to 1.5x. |
| Frozen test | The last 3 years stay untouched until the design is final, then run once. |
| Fyers | Demo only. No account, keys or orders. Fyers fees are still used in the cost maths. |
| Compute | Kaggle GPU for deep learning and large sweeps. TPU only if a sweep is big enough to need it. |
| Hosting | Vercel: Next.js site plus a Python API. |

## 4. Scope

In v1:
- Resident individual taxpayer, under 60, old and new regime, other income as an input.
- Daily bars. Fills at the next open with a slippage model.
- Lump-sum investing (₹X at date Y).
- Comparison set: Nifty 50 ETF, Nifty 50 index fund (direct plan), Sensex, Nifty Next 50, midcap index, gold ETF, liquid or arbitrage fund, FD, and active funds picked by a fixed rule at the start date (largest in category).

Not in v1: intraday strategies, single stocks, options, SIP, NRI/HUF/company tax, tick data, live or alert orders, tax filing.

## 5. Sub-projects, in build order

Each gets its own plan and build cycle.

| # | Sub-project | Done when |
|---|---|---|
| 1 | Rules and costs engine | Golden tests pass on both sides of every rule-change date from 2010. A ₹1L Nifty ETF example matches a hand calculation and an independent calculator. |
| 2 | Data layer | The v1 universe has clean, adjusted daily data with gaps documented. Rebuilding from the manifest gives identical hashes. |
| 3 | Backtest and strategy search | Causality test passes. Trial ledger, deflated Sharpe and overfitting probability are published. An out-of-sample series exists for all three risk levels. |
| 4 | Comparison and projection | At least 8 alternatives run through the engine. Projection fans exist for each. |
| 5 | Web app | All controls recalculate. Every displayed number has an ⓘ. Deployed on Vercel. |
| 6 | Fyers demo | A replayed past date shows target, orders, Fyers-format payloads and estimated fees. No credentials in code. |

First visible checkpoint (end of sub-project 1): ₹1 lakh in a Nifty ETF, 2014 to today, after every cost and tax, with ⓘ traces. It uses one ETF's daily prices and dividends. The full data layer follows.

## 6. Architecture

```
rules/     dated TOML tables (tax, charges, Fyers fees) + source list
engine/    money, trace, charges, tax, lots, portfolio simulator
data/      manifest.json (source, date, SHA-256 per file), raw (ignored), processed (small)
research/  candidate list, walk-forward, overfit tests, Kaggle packaging
api/       Vercel Python function: replays a signal artifact through engine/
web/       Next.js UI
tests/     golden cases, causality, reproducibility, trace balance
```

Data flow:

```
data snapshot -> research (Kaggle) -> signal artifact (target weights by date,
selection log, trial ledger, diagnostics) -> api replays it through engine/
for the user's amount, dates and tax profile -> web shows result + traces
```

Heavy research runs offline. The website only replays a saved artifact, so recalculation is fast and deterministic.

### 6.1 Rule table format (`rules/*.toml`)

Every row: `from`, `to`, `value` (string, parsed as Decimal), `source` (URL or Act section), `verified_on`, `confidence` (`primary` = official text, `secondary` = broker or reputable explainer, `assumed` = stand-in), `note`. The engine never hard-codes a rate. Any `secondary` or `assumed` row shows a flag in every trace that uses it.

### 6.2 Trace format

Each computed value is a node: `label`, `value` (exact Decimal), `formula`, `inputs` (child nodes or constants), `rules` (row ids with from/to, source, confidence). A test checks that every node equals its formula applied to its children. The UI renders the tree. There is no separate explanation text, so it cannot drift from the result.

### 6.3 Money

Decimal arithmetic, exact. Rounding is display-only. The ⓘ shows the exact value. Where the law or a contract note rounds (for example, tax to the nearest rupee), that rounding is its own trace step.

## 7. Rules and costs engine (sub-project 1)

Costs, each by date and segment:
- Fyers brokerage (delivery, intraday, futures, options), DP charges, other account fees.
- STT and CTT.
- Exchange transaction charges (NSE, BSE), SEBI turnover fee, IPFT, clearing charges.
- Stamp duty (state-wise before July 2020, uniform after; one default state before that, labelled).
- Service tax, then GST, on brokerage and exchange charges.
- Mutual fund items: STT on redemption, stamp duty on purchase, exit load. Expense ratio is already in NAV and is shown as information only.

Tax, each by financial year and sale date:
- Capital gains on listed equity and equity-oriented funds: short and long term, rates, holding period, exemption, 31 Jan 2018 grandfathering.
- Capital gains on other assets (gold ETF, debt funds): holding period, rate, indexation with the cost inflation index while it applied, section 50AA.
- F&O gains and losses as business income, deductible costs, audit threshold.
- Loss set-off and carry-forward.
- Dividend tax (company-paid era, then slab) and interest income.
- Slabs for old and new regime, surcharge tiers and caps, cess, section 87A rebate, marginal relief.
- The user's other income is an input. Tax on investment income is the tax with it minus the tax without it.

Conventions:
- FIFO lots. Tax for each financial year is settled at year end from portfolio cash (labelled assumption).
- Advance-tax interest is ignored (labelled).
- The user starts with no carried-forward losses.
- Future years use today's rules (labelled on every projection).

Research method: for each rule row, use the official text first (Finance Acts, CBDT and SEBI circulars, exchange circulars, Fyers pages and Wayback snapshots). A row needs one primary source or two independent secondary sources. Otherwise it is `assumed` and flagged. Fyers likely has no fee history before about 2015 to 2016; earlier years use a labelled stand-in.

Verification: hand-worked golden cases on both sides of each rule-change date (for example, a sale one day before and one day after a rate change). Charges are compared with Fyers' own calculator. Property tests: tax is never negative, lots are conserved, every trace node balances.

## 8. Data layer (sub-project 2)

Sources (free): NSE and BSE archives (equity and F&O end-of-day files, index history, total-return indices), AMFI NAV history, Yahoo Finance as a cross-check, and Fyers' historical API only if a gap needs it.

Rules:
- Point in time. The tradable set on date t is what existed and was liquid on t, including instruments that later closed. No fund is chosen by today's performance.
- Adjust for splits, bonuses and dividends in one documented place.
- Every raw file is listed in `data/manifest.json` with URL, retrieval date and SHA-256.
- An instrument that did not exist at the start shows "n/a", never back-filled.

Feasibility gates, each with a fallback, checked first:

| Gate | Fallback |
|---|---|
| Scripted access to NSE F&O history from 2010 | Drop futures from v1 |
| AMFI NAV history for direct plans | Use Yahoo or mfapi |
| Total-return index history | Compare against investable ETFs and funds only |
| Fyers fee history via Wayback | Use the earliest known schedule, labelled assumed |
| Historical lot sizes and margins | Conservative margin assumption, labelled |
| Historical exchange charges | Broker-published tables via Wayback, labelled secondary |

## 9. Strategy engine (sub-project 3)

A strategy maps data up to the close of day t to a target exposure per instrument. It fills at the next open.

Candidate list (committed before any evaluation):
- static mixes
- trend filters
- sector and factor momentum rotation
- volatility targeting
- a deep-learning position model
- futures hedge or leverage
- tax-aware execution: holding-period-aware exits, yearly LTCG harvesting up to the exemption

The system is a walk-forward selector. Once a year (first trading day of the financial year) it sees only past data, simulates every candidate after tax and cost including the tax of switching, and picks the best under the risk cap. The stitched result is the history the site shows. Minimum training window and the treatment of young instruments are fixed in the sub-project 3 spec.

Objective: maximum after-tax CAGR under the drawdown cap of the chosen risk level. The cap is enforced by selection and by a live governor that cuts exposure as drawdown nears the cap. Caps are targets, not guarantees; gaps can break them.

Anti-overfit:
- Every candidate and window tried is counted as a trial.
- Deflated Sharpe and overfitting probability are computed and published.
- Purged and embargoed splits inside training.
- Plain index holding is the default. A candidate must beat it by more than selection noise.
- Frozen last 3 years, run once after design freeze.
- An automated causality test: cut off future data and confirm past decisions do not change.
- Design-time hindsight is disclosed: we know history when writing the candidate list. The committed list and the frozen years limit it.

Execution realism: slippage grows with order size against average daily volume, fills are capped at a share of volume, futures use real lot sizes and margin, leverage pays interest, dividends are included.

## 10. Compute on Kaggle

The tax-aware simulator is sequential and lot-based, so it does not run well on a GPU. The heavy work is split into a funnel:

1. Data snapshot is published as a private Kaggle Dataset. Kernels run offline from it.
2. Stage 1 (GPU): screen very many parameter sets with a fast pre-tax simulator written in JAX (runs on CPU, GPU or TPU unchanged), and train the deep-learning candidate walk-forward in PyTorch.
3. Stage 2 (CPU, multiprocess): run the exact tax-aware simulation on the survivors. The survivor count is fixed by rule before results are seen. Every screened candidate still counts as a trial.
4. Stage 3: the selector writes the signal artifact. It is small and committed with its hash.

TPU is optional. Our models are small, so GPU is the default. We measure first. GPU training is not bit-for-bit repeatable, so the saved artifact is the record. The after-tax replay from the artifact is exactly reproducible. Kaggle weekly quotas and session limits apply. The existing Kaggle CLI login on this machine is reused.

## 11. Comparison and projection (sub-project 4)

Comparison: every alternative goes through the same engine, on its own dated rules. Each card shows gross, charges, tax, net, and "if still holding". Active funds are picked by a fixed rule at the start date, never by later performance.

Projection: block-bootstrap of each option's own past daily returns, thousands of paths from today to the chosen end date. Each path goes through the tax engine on today's rules. Output: P10, P50, P90, chance of loss. The chart shows a solid line for actual history and a dashed fan for the estimate with an ESTIMATE badge. Notes on every projection: rules assumed unchanged; the past 15 years were a strong bull run, so history may flatter the future.

## 12. Web app (sub-project 5)

Controls: amount, start, end, option, tax profile (regime and other income), risk level, assumptions (slippage, fee plan, end convention). Any change recalculates.

Every result has an ⓘ that opens the trace: initial capital, trades or investment returns, gross profit, brokerage, STT, GST, exchange and SEBI charges, stamp duty, DP charges, tax (financial year, holding period, rule, rate, exemption used), surcharge, cess, other deductions, final net. Each rule links to its source and verified-on date. A CSV export lists every trade and tax line. Pages show "data as of" and "rules verified on" stamps.

Edge cases: start before an instrument existed, end before start, an amount too small to buy one unit or lot. Each shows a clear message.

Not investment advice: the site says it is for information. Numbers are past results or estimates, never guarantees.

## 13. Fyers demo (sub-project 6)

A page called "How it would run on Fyers". For a selected past date it shows: target weights, current holdings, the order list, each order as the JSON the Fyers API v3 would receive (verified against Fyers docs at build time), and the estimated Fyers fees. It also shows the daily timeline (close, compute, next-open fill). It is labelled preview only. There are no credentials, no network calls to Fyers, and no live or alert modes.

It replays past dates on purpose. A public page of live buy and sell signals may count as investment advice under SEBI rules. Check with someone qualified before ever publishing live signals.

## 14. Testing and reproducibility

- Golden tax and charge cases on both sides of every rule-change date.
- Property tests: no negative tax, lot conservation, every trace node balances.
- Causality test for every strategy.
- Rebuild from `data/manifest.json` gives identical hashes.
- Same artifact plus same data gives identical replay results.
- UI test: every displayed number has a trace id and the ⓘ opens.

## 15. Limits and honest caveats

- Daily bars only. No order book. Fills are modelled, not observed.
- Fyers fees before about 2015 to 2016: stand-in, labelled.
- Stamp duty before July 2020 was state-wise: one default state, labelled.
- Futures margin history is not free: conservative assumption, labelled.
- Future tax rules are assumed equal to today's.
- The past 15 years were a strong Indian bull run. Projections from it can be too rosy.
- Design-time hindsight cannot be removed. It is limited and disclosed.
- After Indian tax and charges, active trading rarely beats simple holding. The system may mostly hold ETFs. That is a valid result.
- Data gates in section 8 may shrink v1 (for example, no futures).

## 16. Rule catalogue to research first

- Fyers: brokerage by segment and date, DP and account charges, launch date.
- Statutory and exchange: STT and CTT, exchange charges (NSE and BSE), SEBI fee, IPFT, stamp duty, service tax and GST, DP charges, mutual fund STT and stamp duty.
- Tax: capital gains rates, holding periods, exemptions and grandfathering by asset class and date; cost inflation index; section 50AA; F&O business income and audit threshold; loss rules; slabs, surcharge, cess and rebate by financial year and regime; dividend and interest tax.
- Comparators: FD and PPF rate history, fund expense ratios.
- Data: NSE and BSE file formats, AMFI NAV format, lot-size and margin history.
