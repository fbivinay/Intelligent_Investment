"""Every EQ-series instrument from the cash bhavcopies on disk (2016-01 to 2026-09) into one parquet: date, symbol, high, low, close, prev_close, qty, value
(rupees traded), isin. EQ holds exchange-traded fund units too; their ISIN is a mutual fund unit's (INF...), so research/stockmom.py can rank shares only.

    python -m research.stocks_build

NSE writes prev_close adjusted for the day's corporate action (split, bonus, rights), so close / prev_close chains into a return series without a
separate action list. Stocks that stopped trading just stop: nothing is filled, no survivorship.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "nse" / "cash"
OUT = ROOT / "data" / "processed" / "stocks_eq.parquet"
OLD = {"SYMBOL": "symbol", "SERIES": "series", "HIGH": "high", "LOW": "low", "CLOSE": "close", "PREVCLOSE": "prev_close", "TOTTRDQTY": "qty", "TOTTRDVAL": "value",
       "ISIN": "isin"}
NEW = {"TckrSymb": "symbol", "SctySrs": "series", "HghPric": "high", "LwPric": "low", "ClsPric": "close", "PrvsClsgPric": "prev_close", "TtlTradgVol": "qty",
       "TtlTrfVal": "value", "ISIN": "isin"}


def one(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as z:
        df = pd.read_csv(io.BytesIO(z.read(z.namelist()[0])), skipinitialspace=True)
    df.columns = [c.strip() for c in df.columns]
    cols = NEW if "TckrSymb" in df.columns else OLD
    if not set(cols) <= set(df.columns):
        raise ValueError(f"unknown layout in {path.name}")
    df = df[list(cols)].rename(columns=cols)
    df = df[df.series.astype(str).str.strip() == "EQ"].drop(columns="series")
    df.insert(0, "date", pd.Timestamp(path.stem))
    return df


def main() -> None:
    files = sorted(RAW.glob("*.zip"))
    df = pd.concat([one(p) for p in files], ignore_index=True)
    df["symbol"] = df.symbol.astype(str).str.strip()
    df["isin"] = df["isin"].astype(str).str.strip().astype("category")
    df = df.drop_duplicates(["date", "symbol"]).sort_values(["date", "symbol"])
    df.to_parquet(OUT, index=False)
    print(len(files), "files,", len(df), "rows,", df.symbol.nunique(), "symbols")


if __name__ == "__main__":
    main()
