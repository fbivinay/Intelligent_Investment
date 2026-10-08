"""The project's data sorted into its classes: what each class holds, where it came from, over which years, how many rows, in which files, and
which part of the project reads it. Every count and period is measured from the files themselves.

    python -m tools.classes          # writes classes/README.md and classes/datasets.csv

Needs the data on this machine (data/raw and the largest files are not in git); the files it writes are the record for everyone else.
"""
from __future__ import annotations

import csv
import io
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from engine.rules import Rules

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "classes"

# class: (name, what it holds, source, who reads it, [(dataset, path, kind)]); kind: csv, parquet, json, md, zipdir (a folder of daily zip files),
# csvdir (a folder of daily csv files), jsondir, minute (a large one-minute csv), npz, npy, rules
CLASSES = [
    ("Share prices", "Every share and ETF unit in NSE's EQ series: open, high, low, close, volume and value, one row per instrument per day",
     "NSE daily equity files (bhavcopy)", "Max strategy (its momentum ranking)", [
         ("NSE daily equity files", "data/raw/nse/cash", "zipdir"),
         ("Share prices, every EQ-series instrument", "data/processed/stocks_eq.parquet", "parquet"),
     ]),
    ("ETF prices", "Seven ETFs (Nifty 50, Nifty Next 50, Bank Nifty, Gold, Midcap 100, Nasdaq 100, Liquid BeES): daily prices as published, and a copy "
     "adjusted for their four unit splits", "NSE daily equity files from 2016, the NSE website's history for 2010 to 2015; Yahoo as a cross-check only",
     "Max strategy, LSTM model, calculator", [
         ("ETF daily prices, as published", "data/processed/nse_etf_daily.csv", "csv"),
         ("ETF daily prices, adjusted for splits", "data/processed/etf_daily_adjusted.csv", "csv"),
         ("NSE website history, 2010 to 2016 (its index and futures rows too)", "data/raw/nse_web", "jsondir"),
         ("Nifty 50 ETF from Yahoo, a cross-check only", "data/processed/NIFTYBEES.csv", "csv"),
         ("Yahoo download, as received", "data/raw/yahoo_NIFTYBEES.NS_20260930.json", "json"),
         ("Notes on the Yahoo series (split, payouts, hashes)", "data/manifest.json", "json"),
         ("Bad Yahoo prints left out", "data/corrections.json", "json"),
         ("Nifty 50 ETF payout of 2012", "data/processed/NIFTYBEES_dividends.csv", "csv"),
     ]),
    ("Index levels and valuation", "Nifty 50, Nifty Next 50, Nifty Bank, Nifty Midcap 100 and India VIX: daily levels, with P/E, P/B and dividend yield "
     "for the four Nifty indices from 2012", "NSE daily index files from 2012, the NSE website's history before", "LSTM model (India VIX, P/E, P/B), research", [
         ("NSE daily index files", "data/raw/nse/index", "csvdir"),
         ("Index daily levels and valuation", "data/processed/nse_index_daily.csv", "csv"),
     ]),
    ("Mutual fund values", "Daily net asset values (NAVs) of 29 schemes: index funds, liquid and arbitrage funds, gold ETFs and the BeES ETFs' own NAVs",
     "AMFI, through api.mfapi.in", "Liquid fund for Max and the LSTM, the calculator's funds", [
         ("AMFI scheme histories", "data/raw/amfi", "jsondir"),
         ("Fund NAVs, daily, as published", "data/processed/amfi_nav_daily.csv", "csv"),
         ("Fund NAVs, adjusted for unit changes", "data/processed/amfi_nav_adjusted.csv", "csv"),
         ("Scheme list", "data/amfi_schemes.csv", "csv"),
         ("Unit changes", "data/nav_units.csv", "csv"),
     ]),
    ("Index futures", "Nifty and Bank Nifty futures: the three contracts traded each day, with settlement price and open interest",
     "NSE daily derivatives (F&O) files from 2016, the NSE website's history for 2010 to 2015", "Research (futures for leverage, rejected)", [
         ("NSE daily derivatives files", "data/raw/nse/fo", "zipdir"),
         ("Index futures, daily", "data/processed/nse_index_futures_daily.csv", "csv"),
         ("Contract re-dates", "data/contract_redates.csv", "csv"),
     ]),
    ("Index options", "Nifty and Bank Nifty options: every strike and expiry each day, calls and puts, with open interest",
     "NSE daily derivatives (F&O) files", "Research (covered calls, insurance puts, the intraday option book)", [
         ("Nifty options, daily", "data/processed/nifty_options.parquet", "parquet"),
         ("Bank Nifty options, daily", "data/processed/banknifty_options.parquet", "parquet"),
         ("Lot sizes", "data/lot_sizes.csv", "csv"),
     ]),
    ("Minute prices", "One-minute bars of the Nifty 50, Nifty Bank, Nifty Financial Services and India VIX, and the option days built from them",
     "Kaggle dataset debashis74017/nifty-50-minute-data", "Intraday research (the Fyers automations)", [
         ("Nifty 50, one minute", "data/raw/minute/nifty50_minute.csv", "minute"),
         ("Nifty Bank, one minute", "data/raw/minute/banknifty_minute.csv", "minute"),
         ("Nifty Financial Services, one minute", "data/raw/minute/finnifty_minute.csv", "minute"),
         ("India VIX, one minute", "data/raw/minute/vix_minute.csv", "minute"),
         ("Nifty option days: minute paths, each strike's volatility", "data/processed/intraday_days.npz", "npz"),
         ("Bank Nifty option days: the same", "data/processed/intraday_days_BANKNIFTY.npz", "npz"),
         ("Nifty option prices each minute, modelled", "data/processed/intraday_paths.npy", "npy"),
         ("Bank Nifty option prices each minute, modelled", "data/processed/intraday_paths_BANKNIFTY.npy", "npy"),
     ]),
    ("Reference data", "The record of every NSE file asked for and collected, with its hash, the ETF unit splits, and the data quality report",
     "Built while downloading and checking", "Data cleaning and checks", [
         ("Every NSE daily file asked for, with its status", "data/nse_days.csv", "csv"),
         ("NSE website files collected", "data/nse_web_files.csv", "csv"),
         ("ETF unit splits", "data/corporate_actions.csv", "csv"),
         ("Data quality report", "data/gaps.md", "md"),
     ]),
    ("Tax and charge rules", "Every Fyers fee, exchange and government charge and income-tax rule from 2010 to 2026, each dated and linked to its source",
     "Income Tax Act, Finance Acts, CBDT, NSE, SEBI, Fyers (rules/SOURCES.md)", "The engine: every charge and tax of every model", [
         ("Dated tax and charge tables", "rules", "rules"),
     ]),
]

FORMAT = {"zipdir": "folder of daily ZIP (CSV inside)", "csvdir": "folder of daily CSV", "jsondir": "folder of JSON", "minute": "CSV", "md": "Markdown",
          "npz": "NumPy arrays, a row a day", "npy": "NumPy array, a row a day", "rules": "TOML tables"}
DATE_COLUMNS = ("date", "ex_date")


def _period(series: pd.Series) -> tuple[str, str]:
    s = series.dropna().astype(str).str[:10]
    return (s.min(), s.max()) if len(s) else ("", "")


def _day(name: str) -> str:
    stem = Path(name).stem
    return stem if stem[:2] in ("19", "20") else ""


def measure(path: str, kind: str) -> dict:
    """Rows (or files), first and last day, and size of one dataset."""
    p = ROOT / path
    if kind in ("zipdir", "csvdir", "jsondir"):
        files = sorted(x for x in p.iterdir() if x.is_file())
        return {"rows": "", "files": len(files), "first": _day(files[0].name), "last": _day(files[-1].name), "bytes": sum(x.stat().st_size for x in files)}
    if kind == "rules":
        rows = list(Rules.load(p).all_rows())
        return {"rows": len(rows), "files": len(list(p.rglob("*.toml"))), "first": min(r.valid_from for r in rows).isoformat(),
                "last": max(r.ref.verified_on for r in rows).isoformat(), "bytes": sum(x.stat().st_size for x in p.rglob("*") if x.is_file())}
    out = {"rows": "", "files": 1, "bytes": p.stat().st_size, "first": "", "last": ""}
    if kind == "parquet":
        meta = pq.ParquetFile(p)
        out["rows"] = meta.metadata.num_rows
        if "date" in meta.schema_arrow.names:
            out["first"], out["last"] = _period(pd.read_parquet(p, columns=["date"])["date"])
    elif kind == "csv":
        df = pd.read_csv(p, low_memory=False)
        out["rows"] = len(df)
        col = next((c for c in DATE_COLUMNS if c in df.columns), None)
        if col:
            out["first"], out["last"] = _period(df[col])
    elif kind == "minute":
        with p.open(encoding="utf-8") as f:
            next(f)
            first = last = next(f)
            n = 1
            for last in f:
                n += 1
        out.update(rows=n, first=first.split(",")[0][:10], last=last.split(",")[0][:10])
    elif kind == "npz":
        days = np.load(p, allow_pickle=False)["days"]
        out.update(rows=len(days), first=str(days[0]), last=str(days[-1]))
    elif kind == "npy":
        out["rows"] = np.load(p, mmap_mode="r").shape[0]
    return out


def tracked() -> set[str]:
    return set(subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines())


def in_git(path: str, files: set[str]) -> bool:
    return path in files or any(f.startswith(path + "/") for f in files)


def inventory() -> list[dict]:
    """One entry per class, with its datasets measured."""
    git = tracked()
    classes = []
    for k, (name, what, source, used, sets) in enumerate(CLASSES, 1):
        rows = [{"class": k, "dataset": d, "path": path, "format": FORMAT.get(kind, kind.upper()), "in_git": in_git(path, git), **measure(path, kind)}
                for d, path, kind in sets]
        firsts = [r["first"] for r in rows if r["first"]]
        lasts = [r["last"] for r in rows if r["last"]]
        classes.append({"class": k, "name": name, "what": what, "source": source, "used_by": used, "from": min(firsts) if firsts else "",
                        "to": max(lasts) if lasts else "", "datasets": rows})
    return classes


def _n(x) -> str:
    return f"{x:,}" if isinstance(x, int) else str(x)


def write(classes: list[dict], out: Path = OUT) -> None:
    out.mkdir(exist_ok=True)
    cols = ["class", "class_name", "dataset", "path", "format", "rows", "files", "first", "last", "bytes", "in_git", "source", "used_by"]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n")
    w.writeheader()
    for c in classes:
        for d in c["datasets"]:
            w.writerow({**{k: d[k] for k in cols if k in d}, "in_git": "yes" if d["in_git"] else "no", "class_name": c["name"], "source": c["source"],
                        "used_by": c["used_by"]})
    (out / "datasets.csv").write_text(buf.getvalue(), encoding="utf-8")
    n = sum(len(c["datasets"]) for c in classes)
    lines = [f"# The {len(classes)} classes of data", "",
             f"Every dataset the project uses, {n} in all, sorted into {len(classes)} classes and measured from the files by `python -m tools.classes` "
             "(the same list as [`datasets.csv`](datasets.csv)). The raw downloads and the largest files are not in git (the last column says which); "
             "`python -m tools.export_dataset` writes readable Excel copies into `dataset/`.", "",
             "| # | Class | What it holds | Period | Datasets | Used by |", "|---|---|---|---|---:|---|"]
    for c in classes:
        period = f"{c['from'][:4]} to {c['to'][:4]}" if c["from"] else ""
        lines.append(f"| {c['class']} | **{c['name']}** | {c['what']} | {period} | {len(c['datasets'])} | {c['used_by']} |")
    for c in classes:
        lines += ["", f"## {c['class']}. {c['name']}", "", c["what"] + ".", "", f"Source: {c['source']}. Used by: {c['used_by']}.", "",
                  "| Dataset | File | Format | Rows | Files | From | To | In git |", "|---|---|---|---:|---:|---|---|---|"]
        for d in c["datasets"]:
            lines.append(f"| {d['dataset']} | `{d['path']}` | {d['format']} | {_n(d['rows'])} | {_n(d['files'])} | {d['first']} | {d['last']} | "
                         f"{'yes' if d['in_git'] else 'no'} |")
    (out / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def summary(classes: list[dict]) -> list[dict]:
    """What the website shows: each class, and its datasets with their rows or files and their years."""
    return [{"name": c["name"], "what": c["what"], "source": c["source"], "used_by": c["used_by"], "from": c["from"], "to": c["to"],
             "datasets": [{"name": d["dataset"], "rows": d["rows"] if isinstance(d["rows"], int) else None, "files": d["files"], "from": d["first"],
                           "to": d["last"]} for d in c["datasets"]]} for c in classes]


if __name__ == "__main__":
    inv = inventory()
    write(inv)
    for c in inv:
        print(c["class"], c["name"], c["from"], c["to"], len(c["datasets"]))
