"""The project's data sorted into its 9 classes. classes/ holds the complete data of each class as one CSV (1_share_prices.csv to
9_tax_and_charge_rules.csv) and the same CSV zipped; git keeps the zips, since three of the CSVs are over GitHub's 100 MB a file.
inventory() measures every dataset of a class (rows, years, files) for the website's list and the README's.

    python -m tools.classes          # writes all nine and the README's list; python -m tools.classes 2 4 writes classes 2 and 4

Needs the data on this machine (data/raw and the largest files are not in git).
"""
from __future__ import annotations

import itertools
import re
import shutil
import subprocess
import sys
import tomllib
import zipfile
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from engine.rules import Rules
from tools.export_dataset import _rows

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


P = ROOT / "data" / "processed"
YAHOO = "yahoo, a cross-check only (split-adjusted)"


def _arrow(parts, path: Path) -> None:
    """Arrow tables of one layout into one CSV, a part at a time; whole-day timestamps are written as days (2016-01-04). Nothing is quoted (Arrow
    stops with an error if a value holds a comma, so none can break a row)."""
    with path.open("wb") as out:
        w = None
        for t in parts:
            for i, f in enumerate(t.schema):
                if pa.types.is_timestamp(f.type):
                    t = t.set_column(i, f.name, t.column(i).cast(pa.date32()))
                elif pa.types.is_dictionary(f.type):
                    t = t.set_column(i, f.name, t.column(i).cast(pa.string()))
            if w is None:
                out.write((",".join(t.schema.names) + "\n").encode())
                w = pacsv.CSVWriter(out, t.schema, write_options=pacsv.WriteOptions(include_header=False, quoting_style="none"))
            w.write_table(t)
        w.close()


def _whole(df: pd.DataFrame) -> pd.DataFrame:
    """Counts that turned decimal when tables were put together (57933.0, from the gaps of another table's rows) are written whole again."""
    for c in df.select_dtypes("float").columns:
        v = df[c].dropna()
        if len(v) and (v % 1 == 0).all():
            df[c] = df[c].astype("Int64")
    return df


def _shares(path: Path) -> None:
    _arrow([pq.read_table(P / "stocks_eq.parquet")], path)


def _etfs(path: Path) -> None:
    """The seven ETFs from NSE (as published, and adjusted for splits), then Nifty BeES from Yahoo with its 2012 payout, marked by source."""
    etf = pd.read_csv(P / "etf_daily_adjusted.csv", low_memory=False)
    yahoo = pd.read_csv(P / "NIFTYBEES.csv").rename(columns={"high": "adj_high", "close": "adj_close"})
    paid = pd.read_csv(P / "NIFTYBEES_dividends.csv").rename(columns={"ex_date": "date", "per_unit": "adj_dividend"})
    yahoo = yahoo.merge(paid, on="date", how="outer").assign(symbol="NIFTYBEES", source=YAHOO)
    _whole(pd.concat([etf, yahoo], ignore_index=True).sort_values(["date", "symbol", "source"], kind="stable")).to_csv(path, index=False, lineterminator="\n")


def _funds(path: Path) -> None:
    """Every NAV as published and on today's unit size, with the scheme's name and ISIN."""
    nav = pd.read_csv(P / "amfi_nav_adjusted.csv", dtype={"code": str})
    schemes = pd.read_csv(ROOT / "data" / "amfi_schemes.csv", dtype={"code": str})[["code", "label", "name", "isin"]]
    nav = nav.merge(schemes.rename(columns={"label": "scheme", "name": "amfi_name"}), on="code", how="left", validate="many_to_one")
    _whole(nav[["date", "code", "scheme", "amfi_name", "isin", "nav", "adj_factor", "adj_nav"]]).to_csv(path, index=False, lineterminator="\n")


def _options(path: Path) -> None:
    def part(symbol: str) -> pa.Table:
        t = pq.read_table(P / f"{symbol.lower()}_options.parquet")
        return t.add_column(0, "symbol", pa.array([symbol] * len(t)))
    _arrow((part(s) for s in ("NIFTY", "BANKNIFTY")), path)


MINUTE = (("Nifty 50", "nifty50_minute.csv"), ("Nifty Bank", "banknifty_minute.csv"), ("Nifty Financial Services", "finnifty_minute.csv"),
          ("India VIX", "vix_minute.csv"))


def _minutes(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as out:
        out.write("index,date,open,high,low,close,volume\n")
        for name, f in MINUTE:
            with (ROOT / "data" / "raw" / "minute" / f).open(encoding="utf-8") as src:
                assert next(src).strip() == "date,open,high,low,close,volume", f
                for line in src:
                    if line.strip():
                        out.write(f"{name},{line.rstrip()}\n")


def _reference(path: Path) -> None:
    """The three record tables one under the other; the first column says which table a row is from."""
    parts = [pd.read_csv(ROOT / "data" / f).assign(table=t) for t, f in (("NSE daily files asked for", "nse_days.csv"),
             ("NSE website files collected", "nse_web_files.csv"), ("ETF unit splits", "corporate_actions.csv"))]
    df = pd.concat(parts, ignore_index=True)
    _whole(df[["table", *[c for c in df.columns if c != "table"]]]).to_csv(path, index=False, lineterminator="\n")


def _rules(path: Path) -> None:
    """Every row of every dated rule table, with its area (tax, charges, fyers) and table; lists and tables inside a row are written as JSON."""
    rows = [_rows(tomllib.loads(f.read_text(encoding="utf-8"))).assign(area=f.parent.name, table=f.stem) for f in sorted((ROOT / "rules").rglob("*.toml"))]
    df = pd.concat(rows, ignore_index=True)
    _whole(df[["area", "table", *[c for c in df.columns if c not in ("area", "table")]]]).to_csv(path, index=False, lineterminator="\n")


def _copy(name: str):
    """A processed CSV as it is, with plain line ends (a git checkout on Windows may have given it CR LF)."""
    return lambda path: path.write_bytes((P / name).read_bytes().replace(b"\r\n", b"\n"))


# the complete data of each class, by class number (the order of CLASSES). Left out: the raw downloads (the same rows before cleaning),
# the NumPy arrays built from the minute prices for the option work, and the text report data/gaps.md
BUILD = {1: _shares, 2: _etfs, 3: _copy("nse_index_daily.csv"), 4: _funds, 5: _copy("nse_index_futures_daily.csv"), 6: _options, 7: _minutes,
         8: _reference, 9: _rules}


def file_name(k: int) -> str:
    return f"{k}_{re.sub(r'[^a-z0-9]+', '_', CLASSES[k - 1][0].lower()).strip('_')}.csv"


LIMIT = 95_000_000                # GitHub refuses a file over 100 MB: a class whose zip comes out bigger is zipped in parts


@contextmanager
def _zipped(z: Path, name: str):
    """A zip holding one file, open for writing. The date inside is fixed, so the zip is byte for byte the same while the data does not change."""
    info = zipfile.ZipInfo(name, date_time=(2026, 9, 30, 0, 0, 0))
    info.compress_type, info.compress_level, info.external_attr = zipfile.ZIP_DEFLATED, 9, 0o644 << 16
    with zipfile.ZipFile(z, "w") as zf, zf.open(info, "w") as dst:
        yield dst


def _zips(stem: str, out: Path) -> list[Path]:
    """A class's zips in order: the one zip, or its parts."""
    return sorted(out.glob(f"{stem}.zip")) + sorted(out.glob(f"{stem}_part*.zip"), key=lambda p: int(p.stem.rsplit("part", 1)[1]))


def _lines(path: Path) -> int:
    with path.open("rb") as f:
        return sum(chunk.count(b"\n") for chunk in iter(lambda: f.read(1 << 24), b""))


def _cuts(src: Path, n: int) -> list[int]:
    """Where parts 2 to n start: the first row at or after each n-th of the rows whose first column (the day, the symbol) differs from the row
    before, so a day or a symbol is never split between two parts."""
    rows = _lines(src) - 1
    targets, cuts, key = [rows * i // n for i in range(1, n)], [], None
    with src.open("rb") as f:
        f.readline()
        for row, line in enumerate(f):
            k = line.split(b",", 1)[0]
            if targets and row >= targets[0] and k != key:
                cuts.append(row)
                targets.pop(0)
            key = k
    return cuts


def _zip(src: Path) -> list[Path]:
    """The CSV zipped. A zip over LIMIT is made again in parts instead (1_share_prices_part1.zip, ...), each with the header on top, so every
    part opens on its own and the parts one after another are the whole CSV."""
    stem, out = src.stem, src.parent
    for old in _zips(stem, out):
        old.unlink()
    whole = out / f"{stem}.zip"
    with _zipped(whole, src.name) as dst, src.open("rb") as f:
        shutil.copyfileobj(f, dst, 1 << 20)
    if whole.stat().st_size <= LIMIT:
        return [whole]
    n = -(-whole.stat().st_size // max(1, int(LIMIT * 0.9)))      # parts, with room to spare
    whole.unlink()
    starts = [0, *_cuts(src, n)]
    with src.open("rb") as f:
        head = f.readline()
        for i, start in enumerate(starts, 1):
            lines = itertools.islice(f, starts[i] - start if i < len(starts) else None)
            with _zipped(out / f"{stem}_part{i}.zip", f"{stem}_part{i}.csv") as dst:
                dst.write(head)
                while chunk := list(itertools.islice(lines, 100_000)):
                    dst.write(b"".join(chunk))
    parts = _zips(stem, out)
    assert all(p.stat().st_size < 100_000_000 for p in parts), [(p.name, p.stat().st_size) for p in parts]
    return parts


def _ours(name: str) -> bool:
    return any(name in (f"{s}.csv", f"{s}.zip") or re.fullmatch(rf"{s}_part\d+\.zip", name) for s in (Path(file_name(k)).stem for k in BUILD))


def write(out: Path = OUT, only=None) -> None:
    """The complete data of each class (or of the classes in only), one CSV per class, numbered in order, and zipped: the zips are what git
    keeps (the CSVs are ignored), each under GitHub's 100 MB a file."""
    out.mkdir(exist_ok=True)
    for old in out.iterdir():                 # a file of an earlier layout of this folder; the classes' own files are made again in place
        if old.is_file() and old.suffix in (".md", ".csv", ".zip") and not _ours(old.name):
            old.unlink()
    for k in only or BUILD:
        path = out / file_name(k)
        BUILD[k](path)
        zips = _zip(path)
        print(f"{path.name}: {path.stat().st_size / 1e6:,.1f} MB, zipped " + ", ".join(f"{z.name} {z.stat().st_size / 1e6:,.1f} MB" for z in zips),
              flush=True)


def _size(d: dict) -> str:
    n, unit = (d["rows"], "row") if isinstance(d["rows"], int) else (d["files"], "file")
    return f"{n:,} {unit}{'' if n == 1 else 's'}"


def _years(a: str, b: str) -> str:
    return "" if not a else a[:4] if a[:4] == b[:4] else f"{a[:4]}–{b[:4]}"


README = ROOT / "README.md"
MARKS = ("<!-- classes: written by python -m tools.classes -->", "<!-- /classes -->")


def readme_section(classes: list[dict], out: Path = OUT) -> str:
    """The classes as the website's pop-up lists them, with each class's complete data: its rows, its size as CSV, and its zip or zipped parts."""
    lines = [f"Every dataset the project uses, {sum(len(c['datasets']) for c in classes)} in all, each counted from its own files. The complete data "
             "of each class is one CSV, zipped, in [`classes/`](classes/); the two largest are zipped in parts (each part opens on its own, with the "
             "header on top), as GitHub takes no file over 100 MB."]
    for c in classes:
        csv_ = out / file_name(c["class"])
        zips = ", ".join(f"[`{z.name}`](classes/{z.name}) ({z.stat().st_size / 1e6:,.1f} MB)" for z in _zips(csv_.stem, out))
        lines += ["", f"### {c['class']}. {c['name']} ({_years(c['from'], c['to'])})", "", c["what"] + ".", "", f"- Source: {c['source']}",
                  f"- Used by: {c['used_by']}", f"- Complete data: {_lines(csv_) - 1:,} rows, {csv_.stat().st_size / 1e6:,.1f} MB as CSV; zipped: {zips}",
                  "", "| Dataset | Size | Years |", "|---|---:|---|",
                  *[f"| {d['dataset']} | {_size(d)} | {_years(d['first'], d['last'])} |" for d in c["datasets"]]]
    return "\n".join(lines)


def update_readme(classes: list[dict], path: Path = README, out: Path = OUT) -> None:
    s = path.read_text(encoding="utf-8")
    a, b = s.index(MARKS[0]) + len(MARKS[0]), s.index(MARKS[1])
    path.write_text(s[:a] + "\n" + readme_section(classes, out) + "\n" + s[b:], encoding="utf-8", newline="\n")


def summary(classes: list[dict]) -> list[dict]:
    """What the website shows: each class, and its datasets with their rows or files and their years."""
    return [{"name": c["name"], "what": c["what"], "source": c["source"], "used_by": c["used_by"], "from": c["from"], "to": c["to"],
             "datasets": [{"name": d["dataset"], "rows": d["rows"] if isinstance(d["rows"], int) else None, "files": d["files"], "from": d["first"],
                           "to": d["last"]} for d in c["datasets"]]} for c in classes]


if __name__ == "__main__":
    write(only=[int(a) for a in sys.argv[1:]] or None)
    update_readme(inventory())
