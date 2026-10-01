# Intelligent Investment (India)

> If I invested ₹X on date Y, what would I have after every real cost and tax, compared with the main alternatives, and what range could happen if I invest today?

A research system for a resident Indian investor: ETFs and funds on NSE, every transaction charged and taxed by the rules of its own date (Fyers fee schedule,
STT, exchange, SEBI, stamp duty, GST, DP charges, capital gains by holding period, exemptions, grandfathering, slabs, surcharge, cess, rebate), every number traced to
its rule and source. Fyers is the design target only: no account, no keys, no orders are ever sent.

**Not investment advice.** Past results and estimates, never guarantees.

## Status

| # | Part | State |
|---|---|---|
| 1 | Rules and costs engine (`engine/`, `rules/`) | done: dated TOML rule tables from 2010, exact Decimal maths, a trace for every number |
| 2 | Data layer (`data/`) | done: NSE archive and website history, AMFI NAVs, 2010-04-01 to 2026-09-30, gaps documented in `data/gaps.md` |
| 3 | Strategy engine (`research/`) | done: design frozen under tag `frozen-design-v1`, the frozen test run once |
| 4 | Calculator, comparison and projection (`calc/`) | done: the model's signal replayed for any amount, dates and tax profile with exact traced books; eight alternatives through the same engine; projections labelled ESTIMATE |
| 5 | Web app (`site/`) | done locally: every number has an ⓘ that opens its trace; deploy on Vercel waits for a yes |
| 6 | Fyers demo (`site/app/fyers`, `calc/fyers.py`) | done: a past day's orders as Fyers API v3 payloads with fee estimates, preview only |

## Results

The product is a walk-forward selector per risk level (maximum drawdown 10%, 20%, 30%): every April it looks only at the past and keeps same-risk plain holding
(Nifty ETF plus a liquid fund) unless a candidate beats it by more than selection noise. Candidates: equal weight of four ETFs (Nifty, Next 50, Bank, Gold) and a
liquid fund; means of trend, momentum, volatility-targeting and drawdown-aware variants; and a deep-learning position model trained on a Kaggle T4 GPU.

**Frozen test**, the three years nothing was designed on (2023-10-03 to 2026-09-30, ₹10 lakh, after all charges and tax, everything sold at the end, per year):

| Risk level | Product | Same-risk plain holding | Nifty BeES held | Liquid fund held |
|---|---|---|---|---|
| Conservative (10%) | 4.0% (it was plain holding) | 4.0% | 4.3% | 4.0% |
| Balanced (20%) | 6.8%, worst fall 13.1% | 3.9% | 4.3% | 4.0% |
| Aggressive (30%) | 10.9%, worst fall 13.2% | 3.7% | 4.3% | 4.0% |

- The winner in both the design years and the frozen years is the simple equal-weight mix, not the deep model: the deep model earned less than its own equal-weight
  starting point in both periods.
- Three years are one market path (gold rose about 31% a year after tax): weak evidence either way.
- The research tax profile (new regime, other income ₹12 lakh) sits on the ₹12 lakh rebate threshold from FY 2025-26, where slab-taxed gains cost about 43%; the
  liquid-fund figures are as low as they get for this profile. See `research/out/frozen/notes_after_the_run.md`.

Reports: `research/out/frozen/report.md` (frozen test), `research/out/oos.md` (design period, out of sample for the selection), `research/out/baseline.md` (every trial,
in-sample), pre-registration `docs/superpowers/specs/2026-10-01-frozen-test-preregistration.md`, every decision in `docs/superpowers/ledgers/`.

## Run it

```bash
python -m pip install -r requirements-research.txt      # Python 3.13
python -m pytest                                        # about 1,440 tests
python -m research.baseline                             # every trial over the design period -> research/out/trials.csv, baseline.md
python -m research.oos                                  # walk-forward selector, design period -> research/out/oos.md
python -m research.kaggle.s6                            # deep model on a Kaggle GPU (needs the kaggle CLI logged in)
python -m research.frozen                               # the frozen test: refuses to run unless the code equals tag frozen-design-v1
```

## The calculator and the site

```bash
python -m calc.server 8765                 # the calculator API: POST /api/calc, /api/preview
cd site && npm install && LOCAL_API=1 npx next build && LOCAL_API=1 npx next start -p 3100     # the site, forwarding /api to it
npx playwright test                        # browser checks: every number has an ⓘ that opens, inputs recalculate
python -m tools.bundle_site                # before a Vercel deploy: copies code, rules, data and the signal into site/api/_lib
```

The model's signal (`research/out/signal/`) is the frozen design's weights after its reference account's drawdown guard; a user's account follows them, its
orders decided by the fast simulator and booked again exactly by the engine (`calc/replay.py`). Alternatives: Nifty BeES, Junior BeES, Bank BeES, Gold BeES,
HDFC Nifty 50 index fund, ICICI Nifty Next 50 index fund, SBI Arbitrage fund, Nippon India Liquid fund.

## Layout

```
rules/      dated rule tables (tax, charges, Fyers fees), every row with its source, date checked and confidence
engine/     money, traces, charges, tax, FIFO lots, a traced buy-and-hold
data/       downloaders, builders and checks; data/processed/ is committed, raw downloads are not
research/   panel, causal features, fast simulator (numba), strategies, selector, diagnostics, deep model (research/dl), Kaggle pipeline (research/kaggle)
calc/       the calculator: options, product replay, exact books, alternatives, projections, API, Fyers preview, local server
site/       Next.js web app and its Vercel Python functions
tools/      the deploy bundler
docs/       design specs, plans, ledgers, verification notes
tests/      unit, golden, causality and reproducibility tests
```

## The earlier project

`ml/`, `models/`, `web/` and `.github/workflows/etf-daily.yml` belong to the superseded US-ETF and Bitcoin project (DeepTrend); its README is in
`docs/old-project/DeepTrend-README.md`. Its daily job runs only in its own repository (`btc-paper-trader`).
