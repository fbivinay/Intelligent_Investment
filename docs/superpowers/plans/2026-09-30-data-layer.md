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
- Every day of every file kind is listed in `data/nse_days.csv`: kind, date, status (`ok` or `absent`), bytes, sha256, url, retrieved. Every calendar day is tried (Diwali Muhurat sessions and budget-day or test Saturdays are real trading days on weekends). `absent` means the exchange returned 403 or 404 (a weekend, a holiday, or a file it does not have); a day the exchange says is absent although the ETF traded is a named gap.
- Raw files sit in `data/raw/` (git-ignored); the hashes are in git.
- Universe v1: ETFs NIFTYBEES, JUNIORBEES, BANKBEES, GOLDBEES, LIQUIDBEES; NIFTY and BANKNIFTY index futures; indices Nifty 50, Nifty Next 50, Nifty Bank, Nifty Midcap 100, India VIX; AMFI NAV for the ETFs and a few index, arbitrage and liquid funds.

## Tasks

1. **Archive downloader** `data/nse_archive.py`: URL builders (both layouts, tried in order), day fetch with retry and status classification, threaded sync that resumes from `data/nse_days.csv`, `verify_days`. Tests: injected opener.
2. **Readers**: cash bhavcopy, index-futures rows, index closes (old and new layouts) to typed rows. Tests: real header and rows copied as fixtures.
3. **Build** processed CSVs (`nse_etf_daily.csv`, `nse_index_futures_daily.csv`, `nse_index_daily.csv`) from the raw files, and run the real download 2016-06 to today.
4. **Corporate actions and adjustment**: split and bonus candidates from price gaps, confirmation from AMFI NAV, `data/corporate_actions.csv`, `data/adjust.py`.
5. **AMFI NAV** via mfapi with a check against the AMFI report.
6. **Gaps and cross-check**: trading calendar, gaps report, cross-check against Yahoo (`data/README` table of results).
7. **On hold, owner's decision:** 2010-04 to 2016-05 exact NSE prices through the owner's Chrome (the per-symbol and index and futures history reports work in a real browser; moving the data out of the page to disk was blocked by the safety layer, so it needs the owner's explicit go-ahead or a click on Chrome's download prompt). Fallback: AMFI NAV plus Yahoo, labelled proxy.
