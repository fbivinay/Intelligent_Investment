# Data layer (sub-project 2) Plan

**Goal:** clean, unadjusted, point-in-time daily data for the v1 universe, rebuildable from a manifest of hashes, with every gap named.

**Spec:** `docs/superpowers/specs/2026-09-29-india-algo-system-design.md` section 8 (data rules and feasibility gates).

**Tech:** Python 3.13 standard library only, pytest. Data code lives in `data/`. Network is never touched by tests (an injected opener stands in).

## What was found (tested from this machine on 2026-09-30) and the gate outcomes

| Gate (spec section 8) | Result | What we do |
|---|---|---|
| Scripted NSE F&O and cash history | Works from 2016-06 (`archives.nseindia.com` old layout, `nsearchives.nseindia.com` new layout from mid 2024). 2010 to 2016-05 returns 403. NSE web APIs and niftyindices API are blocked for scripts. | Script the archives from 2016-06. 2010-04 to 2016-05 needs the browser route: **on hold for the owner's decision** (see Task 7). |
| AMFI NAV history | Works (`portal.amfiindia.com` report, and mfapi.in per scheme). | mfapi per scheme, checked against the AMFI report on sample dates. |
| Total-return index | Not reachable. | Compare against investable ETFs and index funds only (spec fallback). |
| Index P/E, P/B, yield, India VIX | `ind_close_all_DDMMYYYY.csv` works from 2012-08. | Script it. |

## Global rules

- Prices stay exactly as the exchange published them (unadjusted). Splits and dividends are found from the data, confirmed against a second source, listed in `data/corporate_actions.csv` with the evidence, and applied in one place (`data/adjust.py`).
- Every day of every file kind is listed in `data/nse_days.csv`: kind, date, status (`ok`, `absent` or `denied`), bytes, sha256, url, retrieved. Every calendar day is tried (Diwali Muhurat sessions and budget-day or test Saturdays are real trading days on weekends). `absent` means every address answered 404 (a weekend or a holiday). **Correction after the first run:** a 403 is NOT "no file". NSE's firewall (Akamai) answered 403 "Access Denied" to everything, existing files included, once the first run reached six requests a second, and that run listed about 4,600 real trading days as absent. The downloader now paces itself (one request per 0.6 s), asks for a file that certainly exists to tell a block from a missing file, waits and retries on a block, and lists a 403 as `denied` only when the exchange is serving other files. On a day the cash file is absent the other two are listed absent without being asked for (the market was closed). A lock file keeps two downloads from running at once (two overlapping runs once listed 1,155 days twice).
- Raw files sit in `data/raw/` (git-ignored); the hashes are in git.
- Universe v1: ETFs NIFTYBEES, JUNIORBEES, BANKBEES, GOLDBEES, LIQUIDBEES; NIFTY and BANKNIFTY index futures; indices Nifty 50, Nifty Next 50, Nifty Bank, Nifty Midcap 100, India VIX; AMFI NAV for the ETFs and a few index, arbitrage and liquid funds.

## Tasks

Status 2026-10-01: tasks 1 to 7 DONE (code, tests, real data, committed on `v3/data-layer`). Task 7 was done through the owner's Brave browser in the end (Chrome's connection to the site was refused). Results are in `data/gaps.md` (generated) and `data/README.md`.

1. **Archive downloader** `data/nse_archive.py`: URL builders (both layouts, tried in order), day fetch with retry and status classification, threaded sync that resumes from `data/nse_days.csv`, `verify_days`. Tests: injected opener. DONE, with the firewall handling above.
2. **Readers**: cash bhavcopy, index-futures rows, index closes (old and new layouts) to typed rows. Tests: real header and rows copied as fixtures. DONE; also handles a two-digit year (one 2020 file), three 2023 index files that write the date month first, and the Midcap 100 renaming.
3. **Build** processed CSVs (`nse_etf_daily.csv`, `nse_index_futures_daily.csv`, `nse_index_daily.csv`) from the raw files, and run the real download 2016-06 to today. DONE: 2,562 cash days, 2,561 F&O and index days, every raw file matches its listed hash.
4. **Corporate actions and adjustment**: split and bonus candidates from price gaps, confirmation from AMFI NAV, `data/corporate_actions.csv`, `data/adjust.py`. DONE: three splits, all on 2019-12-19 (Nifty BeES 1:10, Bank BeES 1:10, Gold BeES 1:100), each confirmed by the fund's NAV, which switches two trading days later (`nav_ex_date`). The equity ETFs pay no dividends out (checked in `gaps.md`).
5. **AMFI NAV** via mfapi with a check against the AMFI report. DONE: 27 schemes, 352 NAVs compared with AMFI's own report, no difference.
6. **Gaps and cross-check**: trading calendar, gaps report, cross-check against Yahoo (`data/README` table of results). DONE, plus futures lot sizes per contract (`data/lots.py`).
7. **2010-04 to 2015-12 from the website's history reports** through the owner's browser: DONE. `data/nse_web_collect.js` (tested under node against a fake site) collected ETFs, Nifty 50, Next 50, Bank, India VIX and both index futures, one request at a time; the owner let the browser download each file to Downloads; `data/nse_web.py` reads them; the website rows equal the archive rows on every overlap day (615 ETF rows, all fields; index rows except India VIX by at most 0.04%; futures except a rounding of value). The earlier route (sending the data from the page to a local server) was refused by the safety layer and was never retried.
