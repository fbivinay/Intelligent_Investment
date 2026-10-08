<p align="center">
  <img src="site/app/icon.svg" width="96" height="96" alt="Intelligent Investment logo">
</p>

<h1 align="center">Intelligent Investment</h1>

<p align="center">
  <b>What would my money have become in India, after every real charge and every tax, next to the normal ways to invest, and how bad could the falls get?</b>
</p>

<p align="center">
  <a href="https://intelligent-investment.vercel.app"><b>Live website</b></a> &nbsp;|&nbsp;
  <a href="#the-website">The website</a> &nbsp;|&nbsp;
  <a href="#the-two-models">The two models</a> &nbsp;|&nbsp;
  <a href="#results">Results</a> &nbsp;|&nbsp;
  <a href="#run-it">Run it</a>
</p>

An algorithmic investing system for an Indian investor, its research, and a website that answers with real numbers. Every rupee of charges and
tax is worked out by the rules of its own date, every trade fills at a price that could really have been had, and no decision ever sees a later
day. Execution is designed for the Fyers broker (its fee schedule is in the maths), but no account is used and no order is ever sent.

**Not investment advice. Everything here is past results and estimates, never a promise.**

---

## In one minute

Rs 10 lakh invested on 3 April 2017, valued on 30 September 2026 (9.5 years), after every charge and every tax (new regime, Rs 12 lakh other
income), everything sold on the last day:

| | Became | A year | Worst fall |
|---|---:|---:|---:|
| **Max strategy** (our model: rules) | **Rs 57.7 lakh** | **20.3%** | **18%** |
| LSTM model (our deep-learning strategy) | Rs 27.4 lakh | 11.2% | 30% |
| Nasdaq 100 ETF | Rs 69.6 lakh | 22.7% | 37% |
| Gold ETF | Rs 41.2 lakh | 16.1% | 24% |
| Nifty 50 ETF | Rs 24.9 lakh | 10.1% | 36% |
| Liquid fund | Rs 16.0 lakh | 5.0% | 0% |

The Max strategy kept most of the growth of the best single asset with half its worst fall. The LSTM, trained only on the years before each
one it invested in, did not beat it; the website says so. The full table of all twelve options is under [Results](#results).

---

## The website

**https://intelligent-investment.vercel.app** (desktop): full-screen slides in three parts, every figure from the calculator below.

| Part | What it shows |
|---|---|
| **Overview** | What Rs 10 lakh invested 9.5 years ago could have become (the years are worked out from the dates), the path of the model next to the Nifty 50, Gold and Nasdaq 100 ETFs, and all twelve options ranked by final value, a year or worst fall. |
| **Performance** | The calculator: one payment or a monthly SIP, any start month and year from April 2017, your tax regime and other income. The Max strategy's final value, return a year and worst fall, and a table of the options you pick, the LSTM model among them, ranked by final value. Then where the money went (charges and tax by kind and year), the path by value, return or fall from the peak, the model's trades (every trading day, its biggest moves, what it holds now), and "if you invest today": what a plan could become at each option's past return, an estimate and never a forecast. |
| **Evidence** | Four slides: how Max and the LSTM work in plain words; the data (source, period, form, records, with real rows); what each model reads; and the two side by side with Rs 10 lakh's growth. |

Answers come from the exact engine, not a lookup: about 2 seconds for a usual question and 4.4 seconds for the largest one (a monthly plan
since 2017 beside every option), measured on the live site. A warm-up call when the site opens loads the data before the first question.

---

## The two models

### Max strategy (rules)

1. **Picks 30 shares.** On the first trading day of each quarter, after the close, it ranks the 500 most traded NSE shares (median daily value
   over six months, a year of prices, traded in the last week) by a trend score, `(6-month return + 12-month return) / 2 / yearly volatility`
   (a published momentum-index method), and holds the 30 highest in equal parts. ETFs trade in the same segment and are left out of the ranking.
2. **Watches the market.** On the first trading day of each month: while the Nifty 50 ETF closes below its 200-day average, the share half waits in
   a liquid fund; back above it, the 30 are picked again.
3. **Spreads the risk.** Half the account in the shares, a quarter in the Gold ETF, a quarter in the Nasdaq 100 ETF, back to those shares on every
   decision day and drifting in between.

Orders go in the next trading day at that day's average price (VWAP) plus slippage (half the spread and a market-impact term), in whole shares.
The 30-of-500 rule was fixed before it was run; the market switch, the two ETFs and the half / quarter / quarter mix were picked after seeing
2017-2026, the same years shown, and the site says so.

### LSTM model (deep learning)

A separate strategy, after Zhang, Zohren and Roberts, *Deep Learning for Portfolio Optimization* (2020): a network that outputs portfolio weights
and is trained to maximise the Sharpe ratio directly.

1. **Reads the recent past.** Each day, the last 63 or 126 days of 43 numbers: for each of the Nifty 50, Gold and Nasdaq 100 ETFs its return over
   1, 5, 21, 63 and 252 days, volatility over 21 and 63 days, fall from the year's high, distance from its 50- and 200-day averages and a volume
   spike (value traded against its 63-day average) (33); for the market India VIX and its 5-day change, the Nifty's P/E and P/B against their history, gold against shares over 63 days and
   the liquid fund's yield (6); and four missing-data flags. All from prices up to that day, scaled with statistics from the training years only.
2. **Remembers patterns.** An LSTM layer (32 or 64 units) reads the sequence; its last state, through one linear layer started at zero (so the
   untrained network holds everything in equal parts), gives softmax weights for the three ETFs and the liquid fund: long only, adding to one.
3. **Learns only from the past.** Trained to maximise the after-cost Sharpe ratio (a cost of 0.3% of every rupee traded), retrained on the first
   trading day of each April from 2017 on every day before it, the settings (sequence length, units) chosen each year on held-out, purged
   validation days, five seeds averaged. Trained on a **Kaggle T4 GPU** (about 2-4 minutes a run); the weights come back checked by their SHA-256.
4. **Invests.** The calculator follows its weights like any strategy, trading only when a holding is more than 5% of the money away from its target.

Two versions were trained and both are reported: v1, written down before any result, on six ETFs (10.8% a year, worst fall 36%; it moved into
Indian shares just before the 2020 crash), and v2 on the three ETFs above (11.2%, 30%), the one the site shows. Even the best fixed mix of these
ETFs, picked with hindsight, makes 18.6% with a 20% fall, so an ETF-only network is unlikely to reach Max. An earlier deep model (GRU, TCN and MLP
position models on four ETFs) was also rejected: it lost to a simple equal mix.

---

## Results

Rs 10 lakh once, 3 April 2017 to 30 September 2026, after every charge and tax, everything sold on the last day (the calculator's saved answer,
`site/public/data/lump.json`):

| Option | Became | A year | Worst fall | Charges | Tax |
|---|---:|---:|---:|---:|---:|
| Nasdaq 100 ETF | Rs 69.6 lakh | 22.7% | 37% | Rs 1,537 | Rs 10.7 lakh |
| **Max strategy** | **Rs 57.7 lakh** | **20.3%** | **18%** | Rs 98,065 | Rs 9.5 lakh |
| Gold ETF | Rs 41.2 lakh | 16.1% | 24% | Rs 1,410 | Rs 5.4 lakh |
| Midcap 100 ETF | Rs 32.3 lakh | 13.1% | 48% | Rs 1,406 | Rs 3.4 lakh |
| **LSTM model** | **Rs 27.4 lakh** | **11.2%** | **30%** | Rs 9,011 | Rs 4.9 lakh |
| Nifty Next 50 ETF | Rs 26.9 lakh | 11.0% | 39% | Rs 1,377 | Rs 2.7 lakh |
| Next 50 index fund | Rs 25.9 lakh | 10.5% | 41% | Rs 28 | Rs 2.6 lakh |
| Nifty 50 ETF | Rs 24.9 lakh | 10.1% | 36% | Rs 1,366 | Rs 2.5 lakh |
| Nifty 50 index fund | Rs 24.5 lakh | 9.9% | 38% | Rs 27 | Rs 2.4 lakh |
| Bank Nifty ETF | Rs 23.9 lakh | 9.6% | 48% | Rs 1,360 | Rs 2.2 lakh |
| Arbitrage fund | Rs 16.3 lakh | 5.3% | 1% | Rs 18 | Rs 1.4 lakh |
| Liquid fund | Rs 16.0 lakh | 5.0% | 0% | Rs 0 | Rs 1.6 lakh |

Rs 5,000 every month over the same years (Rs 5.7 lakh paid in): Max Rs 14.9 lakh (19.3% a year, XIRR), LSTM Rs 9.9 lakh (11.2%). Over those
9.5 years Max placed 1,674 orders on 124 trading days and held 478 different shares at some point; its exact books and the fast simulator agree to
within a few hundred rupees.

### What we tried

| Tried | Result (after tax) |
|---|---|
| Deep learning, first model (GRU, TCN and MLP position networks on four ETFs, Kaggle GPU) | lost to a simple equal mix of ETFs: rejected |
| Trend, momentum and volatility rules on 4 ETFs (chosen on early years, tested on later ones) | about 7-11% a year; a fall guard cut both risk and return |
| Six ETFs in equal parts (adds Midcap 100 and Nasdaq 100) | about 15% a year, worst fall 28% (2013-2026) |
| Stock momentum alone (30 strongest of the 500 most traded shares, ETFs left out) | about 22% a year, worst fall 48% (2017-2026) |
| **Max**: momentum half (with a market switch) + Gold ETF + Nasdaq 100 ETF | **20.3% a year, worst fall 18%** (2017-2026, the same years its switch and mix were chosen on); on the website |
| **LSTM strategy** (deep learning, Kaggle T4 GPU, retrained each April on earlier years only) | 11.2% a year, worst fall 30% (2017-2026), below Max; on the website beside it (v1 on six ETFs: 10.8%, 36%) |
| Nifty futures for leverage; covered calls; insurance puts | added nothing after cost and tax: rejected |
| **About 100 Fyers automations** (1,905 settings of intraday Nifty and Bank Nifty option, futures and signal strategies) | option selling with a stop on every leg wins; buying options on chart signals does not |

### Intraday options research

Risk levels built from the intraday option book (test years 2022-01 to 2026-05, whole lots, one account, new tax regime with Rs 12 lakh other
income; full tables by regime and income in `research/out/intraday/levels_tax.md`):

| Level | Minimum money | Asked | Got after tax | Worst fall | Before tax |
|---|---|---|---|---|---|
| Low | Rs 50 lakh | 15%, fall up to 5% | 12.3% (16.4% with no other income) | 2.5% | 17.5% |
| Medium | Rs 25 lakh | 20%, fall up to 10% | 26.2% | 4.7% | 38.3% |
| High | Rs 10 lakh | 25%, fall up to 15% | 48.3% | 7.9% | 72.3% |

Same years for comparison: Nifty 50 ETF 6.9% (fall 15.7%), Gold ETF 26.3% (24.4%), Nasdaq 100 ETF 23.1% (27.9%), Midcap 100 ETF 15.4% (20.9%),
liquid fund 5.5%, Max 22.1% (15.7%). Option prices inside the day are modelled between the exchange's real open and close (no free minute
option data exists); the levels need daily automated trading and the minimum money above; 4.4 test years are one market path.

---

## How it is built

1. **Rules of charges and tax** (`rules/`, `engine/`). 197 dated rules from 2010 to 2026, each linked to its source and checked on 2 October 2026:
   every Fyers fee, exchange and government charge (STT, stamp duty, GST, SEBI, DP) and every income-tax rule (slabs, old and new regime,
   surcharge, cess, 87A rebate, capital gains, holding periods, exemptions, grandfathering, business income). The engine charges and taxes every
   transaction by the rules of its own date, FIFO lot by lot, with a trace for every number. Checked against hand calculations and the Fyers
   brokerage calculator.
2. **Data** (`data/`, readable copy in `dataset/`). See [Data](#data).
3. **Research** (`research/`). A numba simulator with exact yearly tax, next-day fills with slippage, whole shares and a trade band; strategies,
   walk-forward selection, a frozen final test of the ETF models (2023-10 to 2026-09), stock momentum, the Max level, the LSTM, and intraday options.
   Heavy runs went to Kaggle (GPU for the deep models, CPU for the option grids).
4. **Calculator** (`calc/`). The engine behind the website: the Max and LSTM strategies replayed for any amount, start and monthly plan with exact
   books, next to ten ETFs and funds bought through the same engine; a lean JSON API (`site/api/calc.py` on Vercel, `python -m calc.server` locally).
5. **Website** (`site/`). Next.js 16 and React 19, one slide deck kept across the three routes, motion throughout, Python functions on Vercel.

**Kept honest by:** decisions use prices up to that day's close only and trade the next day (a test cuts the data at several days and checks no
earlier pick changes); every instrument that later stopped trading stays in the data; the momentum ranking holds shares only (a test checks no
fund unit is ever picked); the LSTM is trained only on days before each year it invests in; every choice made with hindsight is said where its
result is shown.

---

## Data

| | |
|---|---|
| **Source** | NSE daily files (every share, ETF, future and option, index closes), the NSE website's history for 2010-2016, AMFI fund values (NAVs), minute-by-minute Nifty 50, Bank Nifty, Fin Nifty and India VIX (2015-2026, Kaggle) |
| **Period** | Shares January 2016 to September 2026; ETFs April 2010 to September 2026; every trading day |
| **Form** | Daily time series: one row per instrument per day (open, high, low, close, previous close, volume, value traded, ISIN) |
| **Records** | 4.6 million daily rows of 3,711 equity-segment instruments (3,213 shares, 498 ETF units); 24,105 rows of the six ETFs the models use; 29 fund schemes from AMFI |
| **Classes** | 9 classes, 36 datasets: share prices, ETF prices, index levels and valuation, mutual fund values, index futures, index options, minute prices, reference data, tax and charge rules; the complete data of each class is one CSV, zipped, in [`classes/`](classes/); every class and its datasets are listed below, in [The 9 classes of data](#the-9-classes-of-data) |
| **Checks** | Gaps and fixes in `data/gaps.md`; a readable copy (raw downloads, cleaned Excel, the tax and charge rules) in `dataset/` |

---

## The 9 classes of data

<!-- classes: written by python -m tools.classes -->
Every dataset the project uses, 36 in all, each counted from its own files. The complete data of each class is one CSV, zipped, in [`classes/`](classes/); the two largest are zipped in parts (each part opens on its own, with the header on top), as GitHub takes no file over 100 MB.

### 1. Share prices (2016–2026)

Every share and ETF unit in NSE's EQ series: open, high, low, close, volume and value, one row per instrument per day.

- Source: NSE daily equity files (bhavcopy)
- Used by: Max strategy (its momentum ranking)
- Complete data: 4,585,946 rows, 363.9 MB as CSV; zipped: [`1_share_prices_part1.zip`](classes/1_share_prices_part1.zip) (73.4 MB), [`1_share_prices_part2.zip`](classes/1_share_prices_part2.zip) (78.0 MB)

| Dataset | Size | Years |
|---|---:|---|
| NSE daily equity files | 2,663 files | 2016–2026 |
| Share prices, every EQ-series instrument | 4,585,946 rows | 2016–2026 |

### 2. ETF prices (2009–2026)

Seven ETFs (Nifty 50, Nifty Next 50, Bank Nifty, Gold, Midcap 100, Nasdaq 100, Liquid BeES): daily prices as published, and a copy adjusted for their four unit splits.

- Source: NSE daily equity files from 2016, the NSE website's history for 2010 to 2015; Yahoo as a cross-check only
- Used by: Max strategy, LSTM model, calculator
- Complete data: 32,574 rows, 4.3 MB as CSV; zipped: [`2_etf_prices.zip`](classes/2_etf_prices.zip) (1.1 MB)

| Dataset | Size | Years |
|---|---:|---|
| ETF daily prices, as published | 28,200 rows | 2010–2026 |
| ETF daily prices, adjusted for splits | 28,200 rows | 2010–2026 |
| NSE website history, 2010 to 2016 (its index and futures rows too) | 3 files |  |
| Nifty 50 ETF from Yahoo, a cross-check only | 4,374 rows | 2009–2026 |
| Yahoo download, as received | 1 file |  |
| Notes on the Yahoo series (split, payouts, hashes) | 1 file |  |
| Bad Yahoo prints left out | 1 file |  |
| Nifty 50 ETF payout of 2012 | 1 row | 2012 |

### 3. Index levels and valuation (2010–2026)

Nifty 50, Nifty Next 50, Nifty Bank, Nifty Midcap 100 and India VIX: daily levels, with P/E, P/B and dividend yield for the four Nifty indices from 2012.

- Source: NSE daily index files from 2012, the NSE website's history before
- Used by: LSTM model (India VIX, P/E, P/B), research
- Complete data: 19,822 rows, 1.8 MB as CSV; zipped: [`3_index_levels_and_valuation.zip`](classes/3_index_levels_and_valuation.zip) (0.6 MB)

| Dataset | Size | Years |
|---|---:|---|
| NSE daily index files | 3,517 files | 2012–2026 |
| Index daily levels and valuation | 19,822 rows | 2010–2026 |

### 4. Mutual fund values (2006–2026)

Daily net asset values (NAVs) of 29 schemes: index funds, liquid and arbitrage funds, gold ETFs and the BeES ETFs' own NAVs.

- Source: AMFI, through api.mfapi.in
- Used by: Liquid fund for Max and the LSTM, the calculator's funds
- Complete data: 100,305 rows, 13.5 MB as CSV; zipped: [`4_mutual_fund_values.zip`](classes/4_mutual_fund_values.zip) (1.1 MB)

| Dataset | Size | Years |
|---|---:|---|
| AMFI scheme histories | 29 files |  |
| Fund NAVs, daily, as published | 100,305 rows | 2006–2026 |
| Fund NAVs, adjusted for unit changes | 100,305 rows | 2006–2026 |
| Scheme list | 29 rows |  |
| Unit changes | 10 rows | 2012–2022 |

### 5. Index futures (2010–2026)

Nifty and Bank Nifty futures: the three contracts traded each day, with settlement price and open interest.

- Source: NSE daily derivatives (F&O) files from 2016, the NSE website's history for 2010 to 2015
- Used by: Research (futures for leverage, rejected)
- Complete data: 24,564 rows, 2.9 MB as CSV; zipped: [`5_index_futures.zip`](classes/5_index_futures.zip) (0.9 MB)

| Dataset | Size | Years |
|---|---:|---|
| NSE daily derivatives files | 2,662 files | 2016–2026 |
| Index futures, daily | 24,564 rows | 2010–2026 |
| Contract re-dates | 2 rows |  |

### 6. Index options (2016–2026)

Nifty and Bank Nifty options: every strike and expiry each day, calls and puts, with open interest.

- Source: NSE daily derivatives (F&O) files
- Used by: Research (covered calls, insurance puts, the intraday option book)
- Complete data: 9,104,303 rows, 622.8 MB as CSV; zipped: [`6_index_options_part1.zip`](classes/6_index_options_part1.zip) (72.2 MB), [`6_index_options_part2.zip`](classes/6_index_options_part2.zip) (46.5 MB)

| Dataset | Size | Years |
|---|---:|---|
| Nifty options, daily | 5,655,622 rows | 2016–2026 |
| Bank Nifty options, daily | 3,448,681 rows | 2016–2026 |
| Lot sizes | 411 rows |  |

### 7. Minute prices (2015–2026)

One-minute bars of the Nifty 50, Nifty Bank, Nifty Financial Services and India VIX, and the option days built from them.

- Source: Kaggle dataset debashis74017/nifty-50-minute-data
- Used by: Intraday research (the Fyers automations)
- Complete data: 4,194,156 rows, 279.5 MB as CSV; zipped: [`7_minute_prices.zip`](classes/7_minute_prices.zip) (47.4 MB)

| Dataset | Size | Years |
|---|---:|---|
| Nifty 50, one minute | 1,048,738 rows | 2015–2026 |
| Nifty Bank, one minute | 1,048,705 rows | 2015–2026 |
| Nifty Financial Services, one minute | 1,048,375 rows | 2015–2026 |
| India VIX, one minute | 1,048,338 rows | 2015–2026 |
| Nifty option days: minute paths, each strike's volatility | 2,558 rows | 2016–2026 |
| Bank Nifty option days: the same | 2,558 rows | 2016–2026 |
| Nifty option prices each minute, modelled | 2,558 rows |  |
| Bank Nifty option prices each minute, modelled | 2,558 rows |  |

### 8. Reference data (2012–2026)

The record of every NSE file asked for and collected, with its hash, the ETF unit splits, and the data quality report.

- Source: Built while downloading and checking
- Used by: Data cleaning and checks
- Complete data: 13,064 rows, 2.5 MB as CSV; zipped: [`8_reference_data.zip`](classes/8_reference_data.zip) (0.5 MB)

| Dataset | Size | Years |
|---|---:|---|
| Every NSE daily file asked for, with its status | 13,057 rows | 2012–2026 |
| NSE website files collected | 3 rows |  |
| ETF unit splits | 4 rows | 2019–2021 |
| Data quality report | 1 file |  |

### 9. Tax and charge rules (2010–2026)

Every Fyers fee, exchange and government charge and income-tax rule from 2010 to 2026, each dated and linked to its source.

- Source: Income Tax Act, Finance Acts, CBDT, NSE, SEBI, Fyers (rules/SOURCES.md)
- Used by: The engine: every charge and tax of every model
- Complete data: 197 rows, 0.1 MB as CSV; zipped: [`9_tax_and_charge_rules.zip`](classes/9_tax_and_charge_rules.zip) (0.0 MB)

| Dataset | Size | Years |
|---|---:|---|
| Dated tax and charge tables | 197 rows | 2010–2026 |
<!-- /classes -->

---

## Folders

```
site/             the website (Next.js 16, Vercel); site/app/icon.svg is the logo; site/public/data the saved answers it shows first
calc/             the calculator behind the website: products, options, exact books, the API
engine/           exact charges, tax, FIFO lots, a trace for every number
rules/            the dated tax and charge tables the engine reads
research/         simulators, strategies, walk-forward selection, stock momentum, the Max level, the LSTM (research/lstm.py), intraday options
research/kaggle/  snapshots and kernels for the Kaggle GPU runs (the deep models, the LSTM)
research/out/     results, reports and signals (signal_max, signal_lstm, lstm, lstm_v2, ...)
data/             downloaders and cleaners; data/raw (downloads), data/processed (cleaned, what the code reads)
dataset/          the data for reading: raw, cleaned (Excel), tax and charge rules
classes/          the complete data, one zipped CSV per class (the two largest in parts, each under GitHub's 100 MB)
tools/            the website's saved data, the Vercel bundle, the dataset export, the classes of data
tests/            1,563 tests
docs/             designs, plans and the record of every decision
```

---

## Run it

Python 3.13 and Node 24.

```bash
# the research and the calculator
python -m pip install -r requirements-research.txt
python -m pytest                                       # 1,563 tests

# the website on this machine: the calculator API on port 8765, the site on port 3000
python -m calc.server 8765                             # or, from site/: npm run api
cd site && npm install && npm run dev                  # http://localhost:3000

# rebuild what the website shows
python -m research.stocks_build                        # the share file (data/processed/stocks_eq.parquet) from the NSE daily files
python -m research.maxmodel                            # the Max level's picks and signal (research/out/signal_max)
python -m research.kaggle.lstm v2                      # train the LSTM on a Kaggle T4 GPU (needs the kaggle CLI, logged in)
python -m research.lstm_result v2                      # its record after every charge and tax
python -m research.lstm_result signal v2               # its weights as the calculator's signal (research/out/signal_lstm)
python -m tools.site_data                              # the saved answers and facts (site/public/data/*.json)

# other research
python -m research.stockmom                            # stock momentum by universe size
python -m research.intraday.levels_tax                 # the intraday risk levels by tax profile
python -m tools.export_dataset                         # rebuild dataset/ from data/ and rules/
python -m tools.classes                                # the complete data of each class, zipped (classes/), and the README's list of classes

# deploy (only from the command line: pushes to GitHub do not deploy)
python -m tools.bundle_site
cd site && npx vercel deploy --prod --yes
```

---

## Limits

- **Hindsight.** The Max strategy's market switch, its two ETFs and its mix were chosen after seeing 2017-2026, the same years shown; there is no
  untouched test period for it. Its record is one path of 9.5 years with strong runs for gold and US shares.
- **The LSTM** is tested year by year on data it never saw, but two versions were tried and the better one is shown (both are reported).
- **Data stand-ins.** A share that stops trading keeps its last price until the next re-pick sells it; a daily move over 50% is read as a missed
  corporate action. Small accounts cannot hold 30 shares in equal parts; whole shares make them follow loosely.
- **Your tax.** Results change with income and regime; Rs 12 lakh of other income sits at the new regime's rebate limit, where the first gains are
  taxed heavily.
- **Not a promise.** Past results, not investment advice. No account is used and no order is ever sent.
