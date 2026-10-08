# The 9 classes of data

Every dataset the project uses, 36 in all, sorted into 9 classes and measured from the files by `python -m tools.classes` (the same list as [`datasets.csv`](datasets.csv)). The raw downloads and the largest files are not in git (the last column says which); `python -m tools.export_dataset` writes readable Excel copies into `dataset/`.

| # | Class | What it holds | Period | Datasets | Used by |
|---|---|---|---|---:|---|
| 1 | **Share prices** | Every share and ETF unit in NSE's EQ series: open, high, low, close, volume and value, one row per instrument per day | 2016 to 2026 | 2 | Max strategy (its momentum ranking) |
| 2 | **ETF prices** | Seven ETFs (Nifty 50, Nifty Next 50, Bank Nifty, Gold, Midcap 100, Nasdaq 100, Liquid BeES): daily prices as published, and a copy adjusted for their four unit splits | 2009 to 2026 | 8 | Max strategy, LSTM model, calculator |
| 3 | **Index levels and valuation** | Nifty 50, Nifty Next 50, Nifty Bank, Nifty Midcap 100 and India VIX: daily levels, with P/E, P/B and dividend yield for the four Nifty indices from 2012 | 2010 to 2026 | 2 | LSTM model (India VIX, P/E, P/B), research |
| 4 | **Mutual fund values** | Daily net asset values (NAVs) of 29 schemes: index funds, liquid and arbitrage funds, gold ETFs and the BeES ETFs' own NAVs | 2006 to 2026 | 5 | Liquid fund for Max and the LSTM, the calculator's funds |
| 5 | **Index futures** | Nifty and Bank Nifty futures: the three contracts traded each day, with settlement price and open interest | 2010 to 2026 | 3 | Research (futures for leverage, rejected) |
| 6 | **Index options** | Nifty and Bank Nifty options: every strike and expiry each day, calls and puts, with open interest | 2016 to 2026 | 3 | Research (covered calls, insurance puts, the intraday option book) |
| 7 | **Minute prices** | One-minute bars of the Nifty 50, Nifty Bank, Nifty Financial Services and India VIX, and the option days built from them | 2015 to 2026 | 8 | Intraday research (the Fyers automations) |
| 8 | **Reference data** | The record of every NSE file asked for and collected, with its hash, the ETF unit splits, and the data quality report | 2012 to 2026 | 4 | Data cleaning and checks |
| 9 | **Tax and charge rules** | Every Fyers fee, exchange and government charge and income-tax rule from 2010 to 2026, each dated and linked to its source | 2010 to 2026 | 1 | The engine: every charge and tax of every model |

## 1. Share prices

Every share and ETF unit in NSE's EQ series: open, high, low, close, volume and value, one row per instrument per day.

Source: NSE daily equity files (bhavcopy). Used by: Max strategy (its momentum ranking).

| Dataset | File | Format | Rows | Files | From | To | In git |
|---|---|---|---:|---:|---|---|---|
| NSE daily equity files | `data/raw/nse/cash` | folder of daily ZIP (CSV inside) |  | 2,663 | 2016-01-01 | 2026-09-30 | no |
| Share prices, every EQ-series instrument | `data/processed/stocks_eq.parquet` | PARQUET | 4,585,946 | 1 | 2016-01-01 | 2026-09-30 | no |

## 2. ETF prices

Seven ETFs (Nifty 50, Nifty Next 50, Bank Nifty, Gold, Midcap 100, Nasdaq 100, Liquid BeES): daily prices as published, and a copy adjusted for their four unit splits.

Source: NSE daily equity files from 2016, the NSE website's history for 2010 to 2015; Yahoo as a cross-check only. Used by: Max strategy, LSTM model, calculator.

| Dataset | File | Format | Rows | Files | From | To | In git |
|---|---|---|---:|---:|---|---|---|
| ETF daily prices, as published | `data/processed/nse_etf_daily.csv` | CSV | 28,200 | 1 | 2010-04-01 | 2026-09-30 | yes |
| ETF daily prices, adjusted for splits | `data/processed/etf_daily_adjusted.csv` | CSV | 28,200 | 1 | 2010-04-01 | 2026-09-30 | yes |
| NSE website history, 2010 to 2016 (its index and futures rows too) | `data/raw/nse_web` | folder of JSON |  | 3 |  |  | no |
| Nifty 50 ETF from Yahoo, a cross-check only | `data/processed/NIFTYBEES.csv` | CSV | 4,374 | 1 | 2009-01-02 | 2026-09-30 | yes |
| Yahoo download, as received | `data/raw/yahoo_NIFTYBEES.NS_20260930.json` | JSON |  | 1 |  |  | no |
| Notes on the Yahoo series (split, payouts, hashes) | `data/manifest.json` | JSON |  | 1 |  |  | yes |
| Bad Yahoo prints left out | `data/corrections.json` | JSON |  | 1 |  |  | yes |
| Nifty 50 ETF payout of 2012 | `data/processed/NIFTYBEES_dividends.csv` | CSV | 1 | 1 | 2012-03-12 | 2012-03-12 | yes |

## 3. Index levels and valuation

Nifty 50, Nifty Next 50, Nifty Bank, Nifty Midcap 100 and India VIX: daily levels, with P/E, P/B and dividend yield for the four Nifty indices from 2012.

Source: NSE daily index files from 2012, the NSE website's history before. Used by: LSTM model (India VIX, P/E, P/B), research.

| Dataset | File | Format | Rows | Files | From | To | In git |
|---|---|---|---:|---:|---|---|---|
| NSE daily index files | `data/raw/nse/index` | folder of daily CSV |  | 3,517 | 2012-07-02 | 2026-09-30 | no |
| Index daily levels and valuation | `data/processed/nse_index_daily.csv` | CSV | 19,822 | 1 | 2010-04-01 | 2026-09-30 | yes |

## 4. Mutual fund values

Daily net asset values (NAVs) of 29 schemes: index funds, liquid and arbitrage funds, gold ETFs and the BeES ETFs' own NAVs.

Source: AMFI, through api.mfapi.in. Used by: Liquid fund for Max and the LSTM, the calculator's funds.

| Dataset | File | Format | Rows | Files | From | To | In git |
|---|---|---|---:|---:|---|---|---|
| AMFI scheme histories | `data/raw/amfi` | folder of JSON |  | 29 |  |  | no |
| Fund NAVs, daily, as published | `data/processed/amfi_nav_daily.csv` | CSV | 100,305 | 1 | 2006-04-02 | 2026-09-30 | yes |
| Fund NAVs, adjusted for unit changes | `data/processed/amfi_nav_adjusted.csv` | CSV | 100,305 | 1 | 2006-04-02 | 2026-09-30 | yes |
| Scheme list | `data/amfi_schemes.csv` | CSV | 29 | 1 |  |  | yes |
| Unit changes | `data/nav_units.csv` | CSV | 10 | 1 | 2012-08-05 | 2022-01-10 | yes |

## 5. Index futures

Nifty and Bank Nifty futures: the three contracts traded each day, with settlement price and open interest.

Source: NSE daily derivatives (F&O) files from 2016, the NSE website's history for 2010 to 2015. Used by: Research (futures for leverage, rejected).

| Dataset | File | Format | Rows | Files | From | To | In git |
|---|---|---|---:|---:|---|---|---|
| NSE daily derivatives files | `data/raw/nse/fo` | folder of daily ZIP (CSV inside) |  | 2,662 | 2016-01-01 | 2026-09-30 | no |
| Index futures, daily | `data/processed/nse_index_futures_daily.csv` | CSV | 24,564 | 1 | 2010-04-01 | 2026-09-30 | yes |
| Contract re-dates | `data/contract_redates.csv` | CSV | 2 | 1 |  |  | yes |

## 6. Index options

Nifty and Bank Nifty options: every strike and expiry each day, calls and puts, with open interest.

Source: NSE daily derivatives (F&O) files. Used by: Research (covered calls, insurance puts, the intraday option book).

| Dataset | File | Format | Rows | Files | From | To | In git |
|---|---|---|---:|---:|---|---|---|
| Nifty options, daily | `data/processed/nifty_options.parquet` | PARQUET | 5,655,622 | 1 | 2016-01-01 | 2026-09-30 | no |
| Bank Nifty options, daily | `data/processed/banknifty_options.parquet` | PARQUET | 3,448,681 | 1 | 2016-01-01 | 2026-09-30 | no |
| Lot sizes | `data/lot_sizes.csv` | CSV | 411 | 1 |  |  | yes |

## 7. Minute prices

One-minute bars of the Nifty 50, Nifty Bank, Nifty Financial Services and India VIX, and the option days built from them.

Source: Kaggle dataset debashis74017/nifty-50-minute-data. Used by: Intraday research (the Fyers automations).

| Dataset | File | Format | Rows | Files | From | To | In git |
|---|---|---|---:|---:|---|---|---|
| Nifty 50, one minute | `data/raw/minute/nifty50_minute.csv` | CSV | 1,048,738 | 1 | 2015-01-09 | 2026-05-15 | no |
| Nifty Bank, one minute | `data/raw/minute/banknifty_minute.csv` | CSV | 1,048,705 | 1 | 2015-01-09 | 2026-05-15 | no |
| Nifty Financial Services, one minute | `data/raw/minute/finnifty_minute.csv` | CSV | 1,048,375 | 1 | 2015-01-09 | 2026-05-15 | no |
| India VIX, one minute | `data/raw/minute/vix_minute.csv` | CSV | 1,048,338 | 1 | 2015-01-09 | 2026-05-15 | no |
| Nifty option days: minute paths, each strike's volatility | `data/processed/intraday_days.npz` | NumPy arrays, a row a day | 2,558 | 1 | 2016-01-01 | 2026-05-15 | no |
| Bank Nifty option days: the same | `data/processed/intraday_days_BANKNIFTY.npz` | NumPy arrays, a row a day | 2,558 | 1 | 2016-01-01 | 2026-05-15 | no |
| Nifty option prices each minute, modelled | `data/processed/intraday_paths.npy` | NumPy array, a row a day | 2,558 | 1 |  |  | no |
| Bank Nifty option prices each minute, modelled | `data/processed/intraday_paths_BANKNIFTY.npy` | NumPy array, a row a day | 2,558 | 1 |  |  | no |

## 8. Reference data

The record of every NSE file asked for and collected, with its hash, the ETF unit splits, and the data quality report.

Source: Built while downloading and checking. Used by: Data cleaning and checks.

| Dataset | File | Format | Rows | Files | From | To | In git |
|---|---|---|---:|---:|---|---|---|
| Every NSE daily file asked for, with its status | `data/nse_days.csv` | CSV | 13,057 | 1 | 2012-07-01 | 2026-09-30 | yes |
| NSE website files collected | `data/nse_web_files.csv` | CSV | 3 | 1 |  |  | yes |
| ETF unit splits | `data/corporate_actions.csv` | CSV | 4 | 1 | 2019-12-19 | 2021-06-17 | yes |
| Data quality report | `data/gaps.md` | Markdown |  | 1 |  |  | yes |

## 9. Tax and charge rules

Every Fyers fee, exchange and government charge and income-tax rule from 2010 to 2026, each dated and linked to its source.

Source: Income Tax Act, Finance Acts, CBDT, NSE, SEBI, Fyers (rules/SOURCES.md). Used by: The engine: every charge and tax of every model.

| Dataset | File | Format | Rows | Files | From | To | In git |
|---|---|---|---:|---:|---|---|---|
| Dated tax and charge tables | `rules` | TOML tables | 197 | 25 | 2010-04-01 | 2026-10-02 | yes |
