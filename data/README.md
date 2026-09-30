# Data layer

Daily end-of-day data for the v1 universe, kept exactly as the source published it. Counts, date ranges and cross-check results are in
[`gaps.md`](gaps.md), which `python -m data.gaps` computes from these files (nothing in it is typed by hand).

## Rules

- **Unadjusted.** Published prices are never edited. A split is listed once, with its evidence, in `corporate_actions.csv` and applied only in
  `adjust.py` (extra `adj_*` columns in `processed/etf_daily_adjusted.csv`). `python -m data.adjust` stops if a day-to-day gap of more than
  40% has no listed action, or a listed action has no gap.
- **Every archive day is listed.** `nse_days.csv` has one row per file kind and calendar day: `ok` (hash of the raw file), `absent` (the exchange
  said 404: a weekend or holiday), or `denied` (403 while it served us other files). A day that failed for another reason is not listed, so the
  next run tries it again. When the cash file is absent the other two are listed absent without being asked for (url empty): the market was closed.
- **Two sources, marked on every row.** The `source` column of the three NSE files says `archive` (the exchange's daily files: cash and F&O from
  2016-01, index closes from 2012-07) or `web` (the NSE website's own history reports, for the years before: 2010-04 to 2015-12). Where both have a
  row the archive row is kept, and `gaps.md` compares the two field by field on the days both have (the overlap, 2016-01 to 2016-06).
- **Raw files** are in `raw/` (git-ignored); their hashes are in git (`nse_days.csv`, `nse_web_files.csv`, `amfi_schemes.csv`). `processed/` is committed.
- **Nothing is back-filled.** An instrument has no row before it existed; a value a source does not have is blank (index P/E before 2012-07,
  ISIN and trade counts in the website rows).

## Sources

| Data | Where | Notes |
|---|---|---|
| Cash bhavcopy (ETF prices) | `archives.nseindia.com/content/historical/EQUITIES/YYYY/MON/cmDDMONYYYYbhav.csv.zip`; from 2024-07-08 `nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv.zip` | from 2016-01; both layouts exist for a few days around the switch |
| F&O bhavcopy (index futures) | same pattern under `DERIVATIVES/fo...` and `content/fo/BhavCopy_NSE_FO...` | from 2016-01; old layout has no lot size and no underlying, value is in lakhs |
| Index closes with P/E, P/B, yield | `content/indices/ind_close_all_DDMMYYYY.csv`, old host until 2023-11-16, `nsearchives` after | from 2012-07; price indices only, no total-return index; India VIX only from 2014-05 |
| Website history reports | `www.nseindia.com/api/historicalOR/...` (what its Historical Data pages call: `generateSecurityWiseHistoricalData`, `indicesHistory`, `vixhistory`, `foCPV`) | only from a real browser (script access is refused); 2010-04 to 2016-06; see below |
| Mutual fund and ETF NAV | `api.mfapi.in/mf/<scheme code>` (mirror of AMFI), checked against `portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx` | `amfi_schemes.csv` lists every scheme with its hash |

The exchange's firewall blocks fast downloads: it answered every request with 403 "Access Denied" after a few minutes at six requests a
second, files that exist included. `nse_archive.py` therefore paces itself (one request per 0.6 s), tells a block from a missing file by asking
for a file that certainly exists, waits and carries on. A 403 is never taken to mean "no such file". The website reports refuse scripts outright,
so `nse_web_collect.js` runs inside the owner's Chrome tab on nseindia.com (same origin, the site's own cookies), one request at a time with a
pause, keeps every reply exactly as received, and stops by itself when the site refuses. After about 270 requests in 7 minutes the browser's own
connection to `www.nseindia.com` was refused for a long time (the archive host stayed reachable): hence the collection may come in parts.

## Files

| File | What |
|---|---|
| `nse_days.csv` | the archive day list above |
| `nse_web_files.csv` | the website files collected: file, bytes, sha256, rows per kind, the collector script and its hash; the JSON itself is in `raw/nse_web/` |
| `amfi_schemes.csv` | the AMFI schemes fetched, rows, first and last date, hash of the raw history |
| `processed/nse_etf_daily.csv` | NIFTYBEES, JUNIORBEES, BANKBEES, GOLDBEES, LIQUIDBEES: date, symbol, series, open, high, low, close, last, prev_close, qty, value, trades, isin, source |
| `processed/etf_daily_adjusted.csv` | the same rows plus `adj_factor, adj_open, adj_high, adj_low, adj_close, adj_qty` (splits only) |
| `processed/nse_index_futures_daily.csv` | NIFTY and BANKNIFTY index futures, every expiry: date, symbol, expiry, open, high, low, close, settle, prev_close, contracts, value_rs (rupees), open_int, chg_oi, lot, underlying, source (lot: published in the website rows and from 2024-07-08; underlying likewise) |
| `processed/nse_index_daily.csv` | Nifty 50, Nifty Next 50, Nifty Bank, Nifty Midcap 100, India VIX: date, name, open, high, low, close, volume, turnover_cr, pe, pb, div_yield, source |
| `processed/amfi_nav_daily.csv` | date, code, nav (as published) |
| `lot_sizes.csv` | index futures lot per contract: symbol, expiry, lot, agree, basis (`published`, or `inferred` from traded value, see below) |
| `corporate_actions.csv` | splits with evidence; `nav_ex_date` is the day AMFI's NAV switches to the new unit size |
| `gaps.md` | generated: day list, calendar and price cross-checks, website against archive, coverage of the years before the archive |
| `nse_web_collect.js`, `nse_web.py` | the browser collector and the reader of what it collected |

## Rebuild

```
python data/nse_archive.py 2016-01-01 2026-09-30 cash,fo,index   # archive download (resumable, paced, slow)
python data/nse_archive.py 2012-07-01 2015-12-31 index            # index closes before the F&O and cash files start
# in Chrome on nseindia.com: paste data/nse_web_collect.js, await c.step(25) until done, c.download('nse_web_....json')
python -m data.nse_web register <the downloaded file>             # copy into raw/nse_web/ and list its hash
python -m data.nse_build                                          # raw files to processed/nse_*.csv
python -m data.adjust                                             # splits to processed/etf_daily_adjusted.csv
python -m data.amfi_nav sync; python -m data.amfi_nav build       # NAV histories
python -m data.amfi_nav check                                     # compare with AMFI's own report on 18 sample days
python -m data.lots; python -m data.gaps
```

Building twice gives the same bytes; every raw file is checked against its listed hash first.

## What the data is not

- **Before 2010-04** there is nothing exact. The five ETFs have no AMFI NAV either from 2011-08-18 to 2016-11-06 (the schemes were
  re-registered under new codes). Continuous stand-ins exist (Nifty 50, Next 50, gold, arbitrage and liquid funds) and are listed in
  `amfi_nav.py`, but they are proxies, not the ETFs.
- **Index futures before 2016** are only as complete as `gaps.md` (Coverage section) says: the website file may have been collected in parts,
  and the site stopped answering the browser before all contracts were fetched.
- **Nifty Midcap 100 before 2012-07** is not available: the website report returns nothing for any spelling of its name.
- **India VIX** starts 2010-07 (website) and is continuous from there; the archive files carry it only from 2014-05.
- **LIQUIDBEES** trades and reports its NAV at Rs 1,000 all the time: its return is a daily cash dividend that no file carries. For a cash
  return use a liquid fund's growth NAV.
- **Dividends** are not in any file here. The three equity ETFs (Nifty, Junior, Bank BeES) do not pay them out in 2016 to 2026: `gaps.md` sets each
  NAV against its index, finds no payout step, and the ratio drifts up (dividends kept in the NAV), so their prices already carry them. Gold BeES
  pays none. Liquid BeES is the exception (above).
- **Lot sizes** are per contract (NSE revises a lot for contracts listed after a date). The website rows and the new daily file (from
  2024-07-08) publish the lot; for the old daily file (2016-01 to 2024-07-05) each contract's lot is worked out from traded value / contracts /
  close, nearest multiple of 5, every day of the contract voting. The working-out agrees with every published lot where a contract has both
  (`python -m data.lots` prints the count of differences).
- **Margins, total-return indices, index constituents** are not here.
- **Special sessions** on weekends are tried and listed (every calendar day is asked for), so a Diwali evening or a Saturday session is not missed.

## Source quirks the readers handle (each has a test)

- One cash file (2020-07-13) writes the year with two digits (`13-Jul-20`).
- Three index files (2023-04-06, 2023-04-10, 2023-04-11) write the date month first; they are read as the day they were asked for, and the build
  counts them. 59 index files (2014-06-09 to 2015-06-10) write the date with slashes (`09/06/2014`).
- Index names before 2015-11-09 were `S&P CNX Nifty` / `CNX Nifty`, `CNX Nifty Junior`, `CNX Bank`, `CNX Midcap`; the Midcap 100 is
  `Nifty Free Float Midcap 100` in the files from 2016-04 to 2018-03. Closes are continuous across every renaming (checked on the days either
  side). `Nifty Full Midcap 100` is a different index and is not read.
- The Nifty BeES, Bank BeES and Gold BeES splits of 2019-12-19 show in AMFI's NAV two trading days later than in the exchange price.
- Website replies: a reply is cut off at the newest 70 rows (the collector asks for windows of 90 days and halves any window that fills the cap);
  on 2011-05-06, 2011-08-09 and 2011-10-24 a reply holds the same row twice (read once; two different rows with the same key are an error);
  a listed futures contract nobody traded on a day comes as a row with no values (left out, counted by `python -m data.nse_web describe`);
  futures quantity is in units and value in lakhs (contracts = quantity / lot).
- Index futures: near-month settle against the index stays within about 1% on every day (checked, nothing odd), three contracts a day.
