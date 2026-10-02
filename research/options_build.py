"""NIFTY index options from the F&O bhavcopies on disk (2016-01 to 2026-09) into one parquet: date, expiry, strike, type (CE/PE), open, high, low, close, settle, contracts,
open_int, underlying (new layout only).

    python -m research.options_build [SYMBOL]      # NIFTY (default) or BANKNIFTY
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd

from data.nse_read import _dmy_name

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "nse" / "fo"
SYMBOL = "NIFTY"


def out_path(symbol: str = "NIFTY") -> Path:
    return ROOT / "data" / "processed" / f"{symbol.lower()}_options.parquet"


def one(path: Path, symbol: str = "NIFTY") -> pd.DataFrame:
    with zipfile.ZipFile(path) as z:
        text = z.read(z.namelist()[0]).decode("utf-8-sig", "replace")
    head, _, body = text.partition("\n")
    keep = [ln for ln in body.splitlines() if f",{symbol}," in ln and ("OPTIDX" in ln or ",IDO," in ln)]
    df = pd.read_csv(io.StringIO(head + "\n" + "\n".join(keep)), skipinitialspace=True)
    df.columns = [c.strip() for c in df.columns]
    if "FinInstrmTp" in df.columns:
        df = df[(df.FinInstrmTp == "IDO") & (df.TckrSymb == symbol)]
        out = pd.DataFrame(dict(expiry=pd.to_datetime(df.XpryDt), strike=df.StrkPric, type=df.OptnTp, open=df.OpnPric, high=df.HghPric, low=df.LwPric, close=df.ClsPric, settle=df.SttlmPric,
                                contracts=df.TtlTradgVol, open_int=df.OpnIntrst, underlying=df.UndrlygPric))
    else:
        df = df[(df.INSTRUMENT == "OPTIDX") & (df.SYMBOL == symbol)]
        out = pd.DataFrame(dict(expiry=pd.to_datetime([_dmy_name(x) for x in df.EXPIRY_DT]), strike=df.STRIKE_PR, type=df.OPTION_TYP.str.strip(),
                                open=df.OPEN, high=df.HIGH, low=df.LOW, close=df.CLOSE, settle=df.SETTLE_PR, contracts=df.CONTRACTS, open_int=df.OPEN_INT, underlying=float("nan")))
    out.insert(0, "date", pd.Timestamp(path.stem))
    return out


def main(symbol: str = "NIFTY") -> None:
    files = sorted(RAW.glob("*.zip"))
    df = pd.concat([one(p, symbol) for p in files], ignore_index=True)
    df.to_parquet(out_path(symbol), index=False)
    print(len(files), "files,", len(df), "rows,", df.expiry.nunique(), "expiries")


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else "NIFTY")
