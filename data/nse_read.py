"""Readers for the NSE daily files (see nse_archive.py): rows for the instruments we use, exactly as published.

Numbers stay text so nothing is rounded on the way in. Every reader knows the old and the new (from 2024-07-08) file layouts and refuses a
layout it does not know, so a format change shows up as an error instead of an empty result.
"""
from __future__ import annotations

import csv
import io
import zipfile
from decimal import Decimal

MON = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}
# index names NSE has changed over the years, read under one name
ALIASES = {"S&P CNX Nifty": "Nifty 50", "CNX Nifty": "Nifty 50"}


def _text(raw: bytes) -> str:
    if raw[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            return z.read(z.namelist()[0]).decode("utf-8-sig", "replace")
    return raw.decode("utf-8-sig", "replace")


def _table(raw: bytes):
    r = csv.DictReader(io.StringIO(_text(raw)))
    head = {h.strip() for h in (r.fieldnames or []) if h is not None}
    rows = ({(k or "").strip(): (v or "").strip() for k, v in row.items() if k is not None} for row in r)
    return head, rows


def _need(head: set, what: str, needed: set) -> None:
    if not needed <= head:
        raise ValueError(f"unknown layout for {what}: expected columns {sorted(needed)}, found {sorted(head)[:8]}")


def _dmy_name(s: str) -> str:
    """01-JUN-2016 or 30-Jun-2016 to 2016-06-01."""
    d, m, y = s.split("-")
    return f"{int(y):04d}-{MON[m.upper()]:02d}-{int(d):02d}"


def _dmy_num(s: str) -> str:
    """31-01-2018 to 2018-01-31."""
    d, m, y = s.split("-")
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


def read_cash(raw: bytes, symbols: set[str]) -> list[dict]:
    head, rows = _table(raw)
    old = {"SYMBOL", "SERIES", "OPEN", "HIGH", "LOW", "CLOSE", "LAST", "PREVCLOSE", "TOTTRDQTY", "TOTTRDVAL", "TIMESTAMP", "TOTALTRADES", "ISIN"}
    new = {"TradDt", "TckrSymb", "SctySrs", "OpnPric", "HghPric", "LwPric", "ClsPric", "LastPric", "PrvsClsgPric", "TtlTradgVol", "TtlTrfVal",
           "TtlNbOfTxsExctd", "ISIN"}
    out = []
    if "TckrSymb" in head:
        _need(head, "cash bhavcopy", new)
        for r in rows:
            if r["TckrSymb"] in symbols:
                out.append(dict(date=r["TradDt"], symbol=r["TckrSymb"], series=r["SctySrs"], open=r["OpnPric"], high=r["HghPric"], low=r["LwPric"],
                                close=r["ClsPric"], last=r["LastPric"], prev_close=r["PrvsClsgPric"], qty=r["TtlTradgVol"], value=r["TtlTrfVal"],
                                trades=r["TtlNbOfTxsExctd"], isin=r["ISIN"]))
    else:
        _need(head, "cash bhavcopy", old)
        for r in rows:
            if r["SYMBOL"] in symbols:
                out.append(dict(date=_dmy_name(r["TIMESTAMP"]), symbol=r["SYMBOL"], series=r["SERIES"], open=r["OPEN"], high=r["HIGH"], low=r["LOW"],
                                close=r["CLOSE"], last=r["LAST"], prev_close=r["PREVCLOSE"], qty=r["TOTTRDQTY"], value=r["TOTTRDVAL"],
                                trades=r["TOTALTRADES"], isin=r["ISIN"]))
    return out


def read_fo(raw: bytes, symbols: set[str]) -> list[dict]:
    """Index futures rows (not options, not stock futures). New layout: contracts, value in rupees, lot size and the underlying come as
    published; old layout: value is in lakhs and is turned into rupees, and no lot size or underlying is published."""
    head, rows = _table(raw)
    out = []
    if "FinInstrmTp" in head:
        _need(head, "F&O bhavcopy", {"TradDt", "FinInstrmTp", "TckrSymb", "XpryDt", "OpnPric", "HghPric", "LwPric", "ClsPric", "PrvsClsgPric",
                                     "UndrlygPric", "SttlmPric", "OpnIntrst", "ChngInOpnIntrst", "TtlTradgVol", "TtlTrfVal", "NewBrdLotQty"})
        for r in rows:
            if r["FinInstrmTp"] == "IDF" and r["TckrSymb"] in symbols:
                out.append(dict(date=r["TradDt"], symbol=r["TckrSymb"], expiry=r["XpryDt"], open=r["OpnPric"], high=r["HghPric"], low=r["LwPric"],
                                close=r["ClsPric"], settle=r["SttlmPric"], prev_close=r["PrvsClsgPric"], contracts=r["TtlTradgVol"],
                                value_rs=r["TtlTrfVal"], open_int=r["OpnIntrst"], chg_oi=r["ChngInOpnIntrst"], lot=r["NewBrdLotQty"],
                                underlying=r["UndrlygPric"]))
    else:
        _need(head, "F&O bhavcopy", {"INSTRUMENT", "SYMBOL", "EXPIRY_DT", "OPEN", "HIGH", "LOW", "CLOSE", "SETTLE_PR", "CONTRACTS", "VAL_INLAKH",
                                     "OPEN_INT", "CHG_IN_OI", "TIMESTAMP"})
        for r in rows:
            if r["INSTRUMENT"] == "FUTIDX" and r["SYMBOL"] in symbols:
                out.append(dict(date=_dmy_name(r["TIMESTAMP"]), symbol=r["SYMBOL"], expiry=_dmy_name(r["EXPIRY_DT"]), open=r["OPEN"], high=r["HIGH"],
                                low=r["LOW"], close=r["CLOSE"], settle=r["SETTLE_PR"], prev_close="", contracts=r["CONTRACTS"],
                                value_rs=str((Decimal(r["VAL_INLAKH"]) * 100000).quantize(Decimal("0.01"))), open_int=r["OPEN_INT"],
                                chg_oi=r["CHG_IN_OI"], lot="", underlying=""))
    return out


def read_index(raw: bytes, names: set[str]) -> list[dict]:
    head, rows = _table(raw)
    _need(head, "index closes", {"Index Name", "Index Date", "Open Index Value", "High Index Value", "Low Index Value", "Closing Index Value",
                                 "Volume", "Turnover (Rs. Cr.)", "P/E", "P/B", "Div Yield"})
    blank = lambda s: "" if s in ("-", "") else s  # noqa: E731
    ours = {n.casefold(): n for n in names}     # NSE has spelled the same index NIFTY and Nifty; we keep our spelling
    out = []
    for r in rows:
        name = ours.get(ALIASES.get(r["Index Name"], r["Index Name"]).casefold())
        if name is not None:
            out.append(dict(date=_dmy_num(r["Index Date"]), name=name, open=blank(r["Open Index Value"]), high=blank(r["High Index Value"]),
                            low=blank(r["Low Index Value"]), close=blank(r["Closing Index Value"]), volume=blank(r["Volume"]),
                            turnover_cr=blank(r["Turnover (Rs. Cr.)"]), pe=blank(r["P/E"]), pb=blank(r["P/B"]), div_yield=blank(r["Div Yield"])))
    return out
