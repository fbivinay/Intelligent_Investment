# Checkpoint 1: Rs 1 lakh in Nifty BeES, checked

Report: `python -m engine.report --income 1500000 --regime new --end 2026-09-28` (writes `out/checkpoint1.html`; the
`--income 0` run writes `out/checkpoint1_no_other_income.html`). `--end 2026-09-28` is the last full trading day in the frozen data.

## 1. Fyers calculator cross-check

Fyers' brokerage calculator (fyers.in/calculator/brokerage) is a page that works out charges in the browser from a table of
rates it loads from `assets.fyers.in/Lib/calculators/3.0/brokrage-calc.js`. I read that table on 2026-09-30 without a browser
(`fyers_calculator_params_2026-09-30.json`), applied the page's own formula (transcribed in `checkpoint1_fyers_check.py`) and
compared it with `engine.charges.order_charges` for the same orders on 2026-09-28. Standard plan.

Nifty ETF, delivery, 1567 units bought and sold at 260.47 (the report's sale price):

| line | Fyers calculator | engine | difference |
|---|---:|---:|---:|
| brokerage | 40.0000 | 40.00 | +0.0000 |
| transaction (exchange + clearing) | 25.0600 | 25.06 | +0.0000 |
| STT | 816.3130 | 4.00 | -812.3130 |
| GST | 11.8579 | 11.86 | +0.0021 |
| SEBI | 0.8163 | 0.82 | +0.0037 |
| stamp duty | 61.2235 | 61.22 | -0.0035 |
| NSE IPFT | 0.0008 | 0.00 | -0.0008 |
| total | 955.2715 | 142.96 | -812.3115 |

The STT difference is on purpose, not an error. The calculator's equity-delivery row is the share rate (0.1% on both sides).
A unit of an equity-oriented ETF pays STT only on the sale, at 0.001% (NSE STT table, `rules/SOURCES.md` S23). Every other
line agrees to within rounding (the engine rounds each line, per leg, to the paisa).

Index futures, 75 units bought and sold at 25,000:

| line | Fyers calculator | engine | difference |
|---|---:|---:|---:|
| brokerage | 40.0000 | 40.00 | +0.0000 |
| transaction | 87.3712 | 87.38 | +0.0088 |
| STT | 937.5000 | 938.00 | +0.5000 |
| GST | 23.6025 | 23.60 | -0.0025 |
| SEBI | 3.7500 | 3.76 | +0.0100 |
| stamp duty | 37.5000 | 37.50 | +0.0000 |
| NSE IPFT | 0.0038 | 0.00 | -0.0038 |
| total | 1,129.7275 | 1,130.24 | +0.5125 |

The STT difference is the rule that STT is rounded to the nearest rupee (Securities Transaction Tax Rules 2004, rule 4, S24);
the calculator shows the unrounded figure. No other line differs by more than Rs 0.05.

What this confirms: the 2026 rates in the rule tables (delivery brokerage Rs 20 or 0.3%, exchange 0.0030699%, SEBI Rs 10 per
crore, IPFT Rs 0.01 per crore, stamp duty 0.015% on the buy side, GST 18%, futures STT 0.05% on the sale, futures clearing
0.0005%) are the numbers Fyers' own calculator uses today. It does not confirm earlier years: the archived calculator
scripts of 2018 to 2020 were used when the rule tables were built (`rules/SOURCES.md` S31).

## 2. Hand check of the sale-year tax

`checkpoint1_tax_check.py` recomputes the sale-year tax with plain arithmetic and no engine tax code. Rs 1 lakh bought on
2014-01-01 at 63.72 gives 1567 units; sold 2026-09-28 at 260.47. Tax year 2026-27, new regime, other income Rs 15 lakh:

| step | Rs |
|---|---:|
| cost of acquisition (price plus buy charges, without STT) | 99,975.26 |
| value on 31 Jan 2018 (1567 units at the day's high of 113.85) | 178,402.95 |
| sale value | 408,156.49 |
| sale costs without STT (including the depository fee) | 53.62 |
| cost used: the higher of cost and the lower of the 2018 value and the sale value | 178,402.95 |
| long-term gain: 408,156.49 - 53.62 - 178,402.95 | 229,699.92 |
| after the Rs 1,25,000 yearly exemption | 104,699.92 |
| tax at 12.5% | 13,087.49 |
| slab tax on Rs 15 lakh, new regime (4 lakh nil, 5% to 8, 10% to 12, 15% to 15 lakh) | 105,000.00 |
| tax with the sale: (105,000 + 13,087.49) x 1.04, to Rs 10 | 122,810.00 |
| tax without the sale: 105,000 x 1.04, to Rs 10 | 109,200.00 |
| **tax caused by the sale** | **13,610.00** |

The engine reports Rs 13,610.00. Total income (Rs 15 lakh plus the whole gain of Rs 2.30 lakh) is under the Rs 50 lakh surcharge
line and over the Rs 12 lakh rebate limit, so neither applies.

## 3. Sanity checks

* Tax is zero in every year with no sale (14 financial years, only FY2026-27 has tax) and the source has no taxable dividend.
* "Still holding" beats "sold" by exactly the sale charges plus the tax: 405,420.35 - 391,752.73 = 13,667.62 = 57.62 + 13,610.00.
* Other income Rs 0 pays no tax (the unused basic exemption shelters the gain); Rs 15 lakh pays Rs 13,610. The old and new regimes
  give the same extra tax here because the gain is taxed at a special rate in both.

## 4. Data caveats

* Source: Yahoo Finance daily prices for NIFTYBEES.NS, retrieved 2026-09-30 (`data/manifest.json` has the hash of the raw reply).
  An unofficial source; sub-project 2 replaces it. Prices are close-of-day; the fill model is the close.
* **Splits.** The 1-for-10 unit split (face value Rs 10 to Rs 1, ex-date 2019-12-19, Trendlyne) is already applied to every earlier
  price in Yahoo's series, although Yahoo lists no split event. Earlier prices are therefore a tenth of what the units really
  traded at. Units bought before 2019-12-19 are counted in post-split units. The rupee results are the same to within whole-unit
  rounding, which is smaller here than it was in real life (a real unit cost Rs 500 to Rs 1,300 before the split).
* **Bad bars left out** (`data/corrections.json`, recorded in the manifest): 2010-10-06 (close 15% below both neighbours and
  below the same day's high) and 2019-12-19 and 2019-12-20 (prices a tenth of their neighbours': the split adjusted twice).
* **Dividends.** Yahoo has no dividend records for this ETF, but the scheme did pay them. Trendlyne lists seven, the last on
  2012-03-12 (Rs 10 per pre-split unit, i.e. Rs 1.00 per post-split unit). Its first, Rs 3 with record date 2003-08-21, is
  confirmed by Value Research, which says the scheme pays out income to keep the NAV near one tenth of the Nifty. Only the 2012
  payment falls inside the study window (from 2010-04-01), so it is the one added by hand. It rests on Trendlyne alone.
* The last bar in the file (2026-09-30) is the day of retrieval and may be a live price, so the reports end on 2026-09-28.
* Demat costs: the account is taken as opened on the purchase day for this investment. For the 2014 purchase that means the
  legacy demat AMC of Rs 400 a year plus GST until 2019-11-14 (Rs 2,760.88 over the years). That value is `assumed` in
  `rules/fyers/amc.toml` (seen on Fyers pages only from 2018-09) and is listed on the report.
