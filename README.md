# Intelligent Investment (India)

An algorithmic investing system for an Indian investor. It answers one question honestly: **what would my money have become, after every real charge
and every tax, compared with the normal ways to invest, and how bad could the falls get?**

Execution is designed for the Fyers broker (its fee schedule is in the maths), but no account is used and no order is ever sent. Not investment advice:
everything here is past results and estimates, never a promise.

## What we did, step by step

1. **Rules of charges and tax** (`rules/`, `engine/`). Every Fyers fee, exchange and government charge (STT, stamp duty, GST, SEBI, DP) and every income-tax
   rule (slabs, old and new regime, surcharge, cess, 87A rebate, capital gains, holding periods, exemptions, grandfathering, business income) from 2010 to
   2026, each row dated and linked to its source. The engine charges and taxes every transaction by the rules of its own date. Checked against hand
   calculations and the Fyers brokerage calculator.
2. **Data** (`data/`, readable copy in `dataset/`). Every NSE daily file 2016-2026 (all shares, all futures and options, index closes), NSE website history
   2010-2016, mutual fund and ETF NAVs from AMFI, and minute-by-minute Nifty, Bank Nifty and India VIX (2015-2026, Kaggle). Gaps and checks in
   `data/gaps.md`.
3. **Testing strategies without cheating** (`research/`). Every strategy is judged on years it never saw: chosen on the early years, then run unchanged on
   the later ones. Trades fill at the next day's prices with slippage. Nothing uses future data (tested). Heavy runs went to Kaggle (GPU for the deep
   model, CPU for the option grids).
4. **Calculator and website** (`calc/`, `site/`). Enter an amount, once or every month (SIP), a start and your tax profile; it replays the model with exact
   charges and tax and compares it with ETFs and funds. The site is a desktop slide deck in three parts: Overview, Performance (the calculator, the path, the
   model's trades, and what a plan started today could become at each option's past return) and Evidence (the Max model in seven steps: the model, data,
   signals, strategy, testing, costs and tax, limits). Live: https://intelligent-investment.vercel.app

## What we found

| Tried | Result (after tax, years not used to choose it) |
|---|---|
| Deep learning (5 network types, Kaggle GPU) | lost to a simple equal mix of ETFs: rejected |
| Trend, momentum and volatility rules on 4 ETFs | about 7-11% a year; a fall guard cut both risk and return |
| Six ETFs in equal parts (adds Midcap 100 and Nasdaq 100) | about 15% a year, worst fall 28% (2013-2026) |
| Stock momentum (30 strongest of the 500 most traded shares, ETFs left out) | about 22% a year, worst fall 48% (2017-2026) |
| **Max**: momentum half (with a market switch) + gold ETF + Nasdaq 100 ETF | **20.3% a year, worst fall 18%** (2017-2026, the same years its switch and mix were chosen on); on the website |
| Nifty futures for leverage; covered calls; insurance puts | added nothing after cost and tax: rejected |
| **About 100 Fyers automations** (1,905 settings of intraday Nifty and Bank Nifty option, futures and signal strategies) | option selling with a stop on every leg wins; buying options on chart signals does not |

The risk levels built from the intraday option book (test years 2022-01 to 2026-05, whole lots, one account, new tax regime with Rs 12 lakh other income;
full tables by regime and income in `research/out/intraday/levels_tax.md`):

| Level | Minimum money | Asked | Got after tax | Worst fall | Before tax |
|---|---|---|---|---|---|
| Low | Rs 50 lakh | 15%, fall up to 5% | 12.3% (16.4% with no other income) | 2.5% | 17.5% |
| Medium | Rs 25 lakh | 20%, fall up to 10% | 26.2% | 4.7% | 38.3% |
| High | Rs 10 lakh | 25%, fall up to 15% | 48.3% | 7.9% | 72.3% |

Same years for comparison: Nifty 50 ETF 6.9% (fall 15.7%), Gold ETF 26.3% (24.4%), Nasdaq 100 ETF 23.1% (27.9%), Midcap 100 ETF 15.4% (20.9%), liquid
fund 5.5%, Max 22.1% (15.7%).

Limits, said plainly: option prices inside the day are modelled between the exchange's real open and close prices (no free minute option data exists);
the option levels need daily automated trading and the minimum money above (smaller accounts cannot hold the lots); 4.4 test years are one market path.

## Folders

```
dataset/    the data for reading: 1_raw_data (as downloaded), 2_cleaned_data (Excel), 3_tax_and_charges_rules (structured Excel, unstructured notes)
rules/      the dated tax and charge tables the engine reads
engine/     exact charges, tax, FIFO lots, a trace for every number
data/       downloaders and cleaners; data/raw (downloads), data/processed (cleaned, what the code reads)
research/   simulators, strategies, walk-forward selection, deep model, stock momentum, intraday options (research/intraday), reports in research/out
calc/       the calculator behind the website
site/       the website (Next.js, Vercel)
tests/      about 1,500 tests
docs/       designs, plans and the record of every decision
```

## Run it

```bash
python -m pip install -r requirements-research.txt     # Python 3.13
python -m pytest                                       # the tests
python -m research.intraday.levels_tax                 # the risk levels by tax profile
python -m tools.export_dataset                         # rebuild dataset/ from data/ and rules/
python -m tools.site_data                              # the saved runs and facts the website shows first (site/public/data/*.json)
python -m tools.bundle_site                            # then: cd site && npx vercel deploy --prod --yes
```
