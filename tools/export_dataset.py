"""Build the dataset/ section: the data in readable form, for a person, next to the machine copies the code reads (data/raw, data/processed, rules/).

    python -m tools.export_dataset

dataset/1_raw_data              a link (Windows junction) to data/raw: the files exactly as downloaded, not copied
dataset/2_cleaned_data          the cleaned tables as Excel, one file per table (big tables split by year: an Excel sheet holds about a million rows)
dataset/3_tax_and_charges_rules structured/ (the rule tables as Excel) and unstructured/ (the source list and the checking notes, as text)
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "dataset"
CLEAN = OUT / "2_cleaned_data"
RULES = OUT / "3_tax_and_charges_rules"
MAX_ROWS = 1_000_000


def _xlsx(path: Path, sheets: dict[str, pd.DataFrame]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="xlsxwriter", engine_kwargs={"options": {"constant_memory": True}}) as w:
        for name, df in sheets.items():
            if len(df) > MAX_ROWS:
                raise ValueError(f"{path.name}/{name}: {len(df)} rows is more than a sheet holds")
            df.to_excel(w, sheet_name=name[:31], index=False)
    print(path.relative_to(ROOT), flush=True)


def _by_year(df: pd.DataFrame, folder: Path, stem: str, date_col: str = "date") -> None:
    years = pd.to_datetime(df[date_col]).dt.year
    for y, part in df.groupby(years):
        _xlsx(folder / f"{stem}_{y}.xlsx", {str(y): part})


def raw_link() -> None:
    link = OUT / "1_raw_data"
    if link.exists():
        return
    OUT.mkdir(exist_ok=True)
    subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(DATA / "raw")], check=True, capture_output=True)


def raw_guide() -> None:
    rows = [
        ("nse/cash", "NSE daily equity bhavcopy: every share and ETF, one zip a day", "archives.nseindia.com, nsearchives.nseindia.com", "2016-01 to 2026-09"),
        ("nse/fo", "NSE daily F&O bhavcopy: every future and option contract, one zip a day", "archives.nseindia.com, nsearchives.nseindia.com", "2016-01 to 2026-09"),
        ("nse/index", "NSE daily index closes with P/E, P/B, dividend yield (and India VIX)", "archives.nseindia.com, nsearchives.nseindia.com", "2012-07 to 2026-09"),
        ("nse_web", "NSE website history reports for the years before the archive (ETFs, indices, VIX, index futures), as JSON", "www.nseindia.com (collected in a browser)", "2010-04 to 2016-06"),
        ("amfi", "Mutual fund and ETF NAV history, one JSON per scheme code (names in 2_cleaned_data/05_Fund_scheme_list.xlsx)", "api.mfapi.in (mirror of AMFI)", "2006 to 2026-09"),
        ("minute", "Nifty 50, Nifty Bank, Nifty Financial Services and India VIX, one row a minute", "Kaggle dataset debashis74017/nifty-50-minute-data", "2015-01 to 2026-05"),
        ("yahoo_NIFTYBEES.NS_20260930.json", "Yahoo Finance history of Nifty BeES, used only as a cross-check", "query1.finance.yahoo.com", "2009 to 2026-09"),
    ]
    out = []
    for folder, what, source, period in rows:
        p = DATA / "raw" / folder
        files = [p] if p.is_file() else [f for f in p.rglob("*") if f.is_file()]
        out.append(dict(folder=folder, what=what, source=source, period=period, files=len(files), size_mb=round(sum(f.stat().st_size for f in files) / 1e6, 1)))
    days = pd.read_csv(DATA / "nse_days.csv")
    _xlsx(OUT / "1_raw_data_GUIDE.xlsx", {"What is in 1_raw_data": pd.DataFrame(out), "Every NSE archive day": days,
                                          "NSE website files": pd.read_csv(DATA / "nse_web_files.csv"), "Fund schemes fetched": pd.read_csv(DATA / "amfi_schemes.csv")})


def cleaned() -> None:
    P = DATA / "processed"
    _xlsx(CLEAN / "01_ETF_daily_prices_split_adjusted.xlsx", {"ETF prices": pd.read_csv(P / "etf_daily_adjusted.csv")})
    idx = pd.read_csv(P / "nse_index_daily.csv")
    _xlsx(CLEAN / "02_Index_daily_closes_Nifty_Next50_Bank_Midcap_VIX.xlsx", {n[:31]: g for n, g in idx.groupby("name")})
    fut = pd.read_csv(P / "nse_index_futures_daily.csv")
    _xlsx(CLEAN / "03_Index_futures_daily_Nifty_BankNifty.xlsx", {s: g for s, g in fut.groupby("symbol")})
    schemes = pd.read_csv(DATA / "amfi_schemes.csv", dtype={"code": str})
    nav = pd.read_csv(P / "amfi_nav_adjusted.csv", dtype={"code": str}).merge(schemes[["code", "label"]], on="code", how="left")
    _xlsx(CLEAN / "04_Mutual_fund_and_ETF_NAV_daily.xlsx", {"NAV": nav})
    _xlsx(CLEAN / "05_Fund_scheme_list.xlsx", {"Schemes": schemes})
    _xlsx(CLEAN / "06_Lot_sizes_Nifty_BankNifty.xlsx", {"Lot sizes": pd.read_csv(DATA / "lot_sizes.csv")})
    _xlsx(CLEAN / "07_Corporate_actions_and_unit_changes.xlsx", {"ETF splits": pd.read_csv(DATA / "corporate_actions.csv"), "Fund unit changes": pd.read_csv(DATA / "nav_units.csv"),
                                                                  "Futures re-dated": pd.read_csv(DATA / "contract_redates.csv")})
    _xlsx(CLEAN / "08_NiftyBeES_dividends.xlsx", {"Dividends": pd.read_csv(P / "NIFTYBEES_dividends.csv")})
    stocks = pd.read_parquet(P / "stocks_eq.parquet")
    _by_year(stocks, CLEAN / "09_Stock_prices_every_NSE_share_daily", "Stock_prices")
    for sym in ("nifty", "banknifty"):
        f = P / f"{sym}_options.parquet"
        if f.exists():
            _by_year(pd.read_parquet(f), CLEAN / f"10_{sym.capitalize()}_options_daily", f"{sym.capitalize()}_options")
    minute = DATA / "raw" / "minute"
    names = {"nifty50_minute.csv": "Nifty50", "banknifty_minute.csv": "BankNifty", "vix_minute.csv": "IndiaVIX"}
    frames = {k: pd.read_csv(minute / f, parse_dates=["date"]) for f, k in names.items() if (minute / f).exists()}
    years = sorted(set().union(*[set(df.date.dt.year) for df in frames.values()]))
    for y in years:
        _xlsx(CLEAN / "11_Minute_prices_Nifty_BankNifty_VIX" / f"Minute_prices_{y}.xlsx", {k: df[df.date.dt.year == y] for k, df in frames.items()})
    shutil.copyfile(DATA / "gaps.md", CLEAN / "00_Data_quality_report.md")


def _rows(table: dict) -> pd.DataFrame:
    out = []
    for r in table.get("row", []):
        flat = {}
        for k, v in r.items():
            flat[k] = json.dumps(v) if isinstance(v, (list, dict)) else v
        out.append(flat)
    return pd.DataFrame(out)


def rules() -> None:
    S = RULES / "structured"
    for area, title in (("tax", "Income_tax_rules_by_year"), ("charges", "Exchange_and_government_charges_by_date"), ("fyers", "Fyers_brokerage_and_fees_by_date")):
        sheets = {f.stem: _rows(tomllib.loads(f.read_text(encoding="utf-8"))) for f in sorted((ROOT / "rules" / area).glob("*.toml"))}
        _xlsx(S / f"{title}.xlsx", sheets)
    text = (ROOT / "rules" / "SOURCES.md").read_text(encoding="utf-8")
    src = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in text.splitlines() if re.match(r"^\| S\d+", ln)]
    _xlsx(S / "Sources_of_every_rule.xlsx", {"Sources": pd.DataFrame(src, columns=["id", "document", "url", "retrieved", "supports"])})
    U = RULES / "unstructured"
    U.mkdir(parents=True, exist_ok=True)
    for src_path, name in ((ROOT / "rules" / "SOURCES.md", "Sources_of_every_rule.md"),
                           (ROOT / "docs" / "verification" / "rulings.md", "Rulings_on_unclear_tax_points.md"),
                           (ROOT / "docs" / "verification" / "assumed-rows.md", "Rules_assumed_without_a_primary_source.md"),
                           (ROOT / "docs" / "verification" / "checkpoint-1.md", "Tax_and_charges_checked_against_hand_calculations.md"),
                           (ROOT / "docs" / "verification" / "mutation-sweeps.md", "Tests_that_catch_wrong_rules.md"),
                           (ROOT / "docs" / "verification" / "fyers_calculator_params_2026-09-30.json", "Fyers_calculator_check_2026-09-30.json")):
        if src_path.exists():
            shutil.copyfile(src_path, U / name)
            print((U / name).relative_to(ROOT))


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    if step in ("all", "raw"):
        raw_link()
        raw_guide()
    if step in ("all", "rules"):
        rules()
    if step in ("all", "cleaned"):
        cleaned()
