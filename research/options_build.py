"""NIFTY index options from the F&O bhavcopies on disk (2016-01 to 2026-09) into one parquet: date, expiry, strike, type (CE/PE), close, settle, contracts,
open_int, underlying (new layout only).

    python -m research.options_build
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd

from data.nse_read import _dmy_name

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "nse" / "fo"
OUT = ROOT / "data" / "processed" / "nifty_options.parquet"


def one(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as z:
        text = z.read(z.namelist()[0]).decode("utf-8-sig", "replace")
    head, _, body = text.partition("\n")
    keep = [ln for ln in body.splitlines() if ",NIFTY," in ln and ("OPTIDX" in ln or ",IDO," in ln)]
    df = pd.read_csv(io.StringIO(head + "\n" + "\n".join(keep)), skipinitialspace=True)
    df.columns = [c.strip() for c in df.columns]
    if "FinInstrmTp" in df.columns:
        df = df[(df.FinInstrmTp == "IDO") & (df.TckrSymb == "NIFTY")]
        out = pd.DataFrame(dict(expiry=pd.to_datetime(df.XpryDt), strike=df.StrkPric, type=df.OptnTp, close=df.ClsPric, settle=df.SttlmPric,
                                contracts=df.TtlTradgVol, open_int=df.OpnIntrst, underlying=df.UndrlygPric))
    else:
        df = df[(df.INSTRUMENT == "OPTIDX") & (df.SYMBOL == "NIFTY")]
        out = pd.DataFrame(dict(expiry=pd.to_datetime([_dmy_name(x) for x in df.EXPIRY_DT]), strike=df.STRIKE_PR, type=df.OPTION_TYP.str.strip(),
                                close=df.CLOSE, settle=df.SETTLE_PR, contracts=df.CONTRACTS, open_int=df.OPEN_INT, underlying=float("nan")))
    out.insert(0, "date", pd.Timestamp(path.stem))
    return out


def main() -> None:
    files = sorted(RAW.glob("*.zip"))
    df = pd.concat([one(p) for p in files], ignore_index=True)
    df.to_parquet(OUT, index=False)
    print(len(files), "files,", len(df), "rows,", df.expiry.nunique(), "expiries")


if __name__ == "__main__":
    main()
