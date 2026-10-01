# Frozen test: pre-registration

Date: 2026-10-01. Written and committed before any research code loaded a day after 2023-09-30. The git tag `frozen-design-v1` marks the commit the test runs on;
`research/frozen.py` and `research/kaggle/s6.py frozen` refuse to run if any code, rule or data file differs from the tag's (outputs under `research/out/` may).
Spec: `2026-10-01-strategy-engine-design.md` section 6; plans 3A and 3B and their ledgers hold every decision made on the way here.

## 1. What is frozen

| Item | Value |
|---|---|
| Data | `research.panel.load_panel(end="2026-09-30")` built from `data/processed/` (the run records the SHA-256 of the three files it reads) |
| Frozen period | the first trading day on or after 2023-10-01 to 2026-09-30 |
| Risk levels | Conservative, Balanced, Aggressive: maximum drawdown 10%, 20%, 30%, before tax; the governor cuts risk from half the cap and is out at 90% of it |
| Candidates at each level | S0 same-risk plain holding (Nifty ETF and the liquid fund, the largest 5% step whose drawdown so far stayed within the cap); E1 equal weight of the four ETFs and the fund, back to equal each April; E2 mean of the 6 trend-filter variants; E3 mean of the 18 momentum-rotation variants; E4 mean of the 10 volatility-targeting variants; E5 mean of the 6 drawdown-aware variants; S6 the deep model, the mean of 12 committed configurations with 3 seeds each |
| S6 in the frozen years | design-period weights unchanged (`research/out/s6`); new days from models retrained on the Kaggle GPU at the April 2023, 2024, 2025 and 2026 cuts on the data before each cut (`research/out/s6_frozen`); S6 may be picked from 2016-04-01, after three years of its own record |
| Selector (the product) | every first trading day of April from 2013-04-01, data before that day only: eligible = drawdown so far within the cap; best by after-tax growth; held for the year only if its paired edge over S0 exceeds the margin times its block-bootstrap standard error, else S0 |
| Margins | deflated, sqrt(2 ln N) standard errors for the effective number of candidates measured on the design period (`research/out/oos_margins.json`): Conservative 1.3852, Balanced 1.3319, Aggressive 1.3082. The spec's 1 standard error is reported next to it |
| Execution (W1) | harvest: on the 5th-to-last trading day of each financial year, long-term equity gains up to 95% of what is left of the yearly exemption are realised and the units bought back the next day; the hold rule is off |
| Accounts | fresh on the first frozen day with Rs 10 lakh; tax profile new regime, other income Rs 12 lakh; charges, slippage and tax by each transaction's own date. Reference investments bought on day one and held plainly: Nifty BeES, Junior BeES, Bank BeES, Gold BeES, the liquid fund |
| Metrics | after-tax growth a year; after selling all (everything sold on the last day, its charges and tax paid); worst drawdown before tax; Sharpe above the fund; turnover; tax |

## 2. Hypotheses

- **Primary, at each level:** the product (the selector with the deflated margin) has higher after-selling-all growth than S0, and its worst drawdown is within the cap.
- **Secondary, chosen with the design period in view (hindsight, stated as such):** E1 alone beats S0 after selling all at Balanced and at Aggressive; S6 alone beats E1 (does the deep model add anything to its own equal-weight starting point?).
- Everything else in the report is description, not a test.

## 3. What the design period showed (in-sample for these choices)

Fresh accounts from 2013-04-01 to 2023-09-29 with W1 harvesting (`research/out/oos.md`), after selling all and worst drawdown:

| Level | S0 | E1 | E4 | E5 | S6 | Selector (deflated) | Nifty BeES held |
|---|---|---|---|---|---|---|---|
| Conservative (10%) | 7.8%, 9.1% | 7.0%, 10.3% | 7.5%, 9.6% | 7.9%, 10.0% | 5.2%, 9.4% | 7.8%, 9.1% (S0 every year) | 12.9%, 36.3% |
| Balanced (20%) | 8.4%, 17.8% | 9.3%, 17.1% | 8.8%, 16.8% | 8.1%, 17.6% | 5.3%, 18.1% | 8.4%, 17.8% (S0 every year) | 12.9%, 36.3% |
| Aggressive (30%) | 8.9%, 26.0% | 10.9%, 21.1% | 10.1%, 20.6% | 10.1%, 21.8% | 6.3%, 25.6% | 7.6%, 25.9% (E1 in 5 of 11 years) | 12.9%, 36.3% |

The other investments held from the same day: Junior BeES 14.2% after selling all with a 38.7% drawdown, Bank BeES 13.5% and 47.7%, Gold BeES 5.3% and 25.5%, the liquid fund 6.3% and 0.2%. The first design (every one of 2,077 parameter sets as a candidate) lost 4 to 5 points a year to S0 out of
sample; that result is why the candidate list became one ensemble per family, a choice made after seeing it.

## 4. How the run is done

1. `python -m research.kaggle.s6 frozen`: trains S6 for the frozen years on a private Kaggle T4 kernel and verifies the weights against the kernel's hashes.
2. `python -m research.frozen`: writes `research/out/frozen/report.md`, `record.json` (tag, commit, data hashes, margins, run date, all results), the selection logs, and the
   signal artifact per level (`signal_<level>.csv`: the product's target weights after each day's close from 2013-04-01, the strategy they came from, with hashes).
3. The outputs are committed whatever they say. Any later change to the candidates, the selector, the margins or the execution voids this test, and the report will say so.

The fast simulator's charges were replayed order by order through the exact engine on three design accounts (`research/out/replay_design.json`): Rs 8 to Rs 16 apart in
total over ten years, at most Rs 7.51 on one order, about 0.0005% of the final wealth; taxes are the engine's own. The frozen run repeats the check on the product's orders.

## 5. What it cannot show

Three years are one market path: a win or a loss on its own is weak evidence. No instrument in the universe was young or delisted (survivorship does not arise), but the
candidate list, the caps and the margins were fixed with the design years in view. The research capital and tax profile are one investor's; the site will replay the
artifact for any amount, dates and tax profile.
