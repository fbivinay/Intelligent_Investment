"""Reader for the file collected from the NSE website's own history reports (data/nse_web_collect.js), for the years before the archive files.

The collector keeps every reply exactly as the site sent it, each with the request that got it. This module turns those replies into rows in the
same layout the archive readers give (data/nse_read.py), refusing any reply that does not belong to its request (another symbol, a day outside the
asked window, another expiry). A file may be one part of a collection (paused, or stopped by the site): its rows are good, `describe` says what it
lacks, and whether the files together cover what they should is checked on the rows (data/gaps.py). Numbers are read with their own digits.
`register` copies a downloaded file into data/raw/nse_web/ and lists it, with its hash, in data/nse_web_files.csv.
Run:  python -m data.nse_web register <downloaded file>     (or: describe <file>)
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

from data.nse_read import _dmy_name

ROOT = Path(__file__).parent
SCRIPT = ROOT / "nse_web_collect.js"
LISTING = "nse_web_files.csv"
FIELDS = ["file", "bytes", "sha256", "collected", "requests", "rows_cash", "rows_fo", "rows_index", "script", "script_sha256", "registered"]
INDEX_NAMES = {"NIFTY 50": "Nifty 50", "NIFTY NEXT 50": "Nifty Next 50", "NIFTY BANK": "Nifty Bank"}   # as asked of the site -> as we name them
CASH_KEYS = ["CH_SYMBOL", "CH_SERIES", "mTIMESTAMP", "CH_PREVIOUS_CLS_PRICE", "CH_OPENING_PRICE", "CH_TRADE_HIGH_PRICE", "CH_TRADE_LOW_PRICE",
             "CH_LAST_TRADED_PRICE", "CH_CLOSING_PRICE", "CH_TOT_TRADED_QTY", "CH_TOT_TRADED_VAL", "CH_TOTAL_TRADES"]
FO_KEYS = ["FH_INSTRUMENT", "FH_SYMBOL", "FH_EXPIRY_DT", "FH_TIMESTAMP", "FH_OPENING_PRICE", "FH_TRADE_HIGH_PRICE", "FH_TRADE_LOW_PRICE", "FH_CLOSING_PRICE",
           "FH_PREV_CLS", "FH_SETTLE_PRICE", "FH_TOT_TRADED_QTY", "FH_TOT_TRADED_VAL", "FH_OPEN_INT", "FH_CHANGE_IN_OI", "FH_MARKET_LOT", "FH_UNDERLYING_VALUE"]
FO_TRADE_KEYS = ["FH_OPENING_PRICE", "FH_TRADE_HIGH_PRICE", "FH_TRADE_LOW_PRICE", "FH_CLOSING_PRICE", "FH_PREV_CLS", "FH_SETTLE_PRICE", "FH_TOT_TRADED_QTY",
                 "FH_TOT_TRADED_VAL", "FH_OPEN_INT", "FH_CHANGE_IN_OI", "FH_MARKET_LOT"]     # all null together on a day a listed contract did not trade
INDEX_KEYS = ["EOD_TIMESTAMP", "EOD_OPEN_INDEX_VAL", "EOD_HIGH_INDEX_VAL", "EOD_LOW_INDEX_VAL", "EOD_CLOSE_INDEX_VAL", "HIT_TURN_OVER", "HIT_TRADED_QTY"]
VIX_KEYS = ["EOD_TIMESTAMP", "EOD_OPEN_INDEX_VAL", "EOD_HIGH_INDEX_VAL", "EOD_LOW_INDEX_VAL", "EOD_CLOSE_INDEX_VAL"]


def _day(text: str) -> str:
    """30-Jun-2010 or 30-JUN-2010 or 2010-06-30 to 2010-06-30."""
    if len(text) == 10 and text[4] == "-":
        date.fromisoformat(text)
        return text
    return _dmy_name(text)


def _txt(v) -> str:
    if v is None:
        return ""
    return format(v, "f") if isinstance(v, Decimal) else str(v)


def _need(row: dict, keys: list[str], where: str) -> None:
    missing = [k for k in keys if k not in row]
    if missing:
        raise ValueError(f"{where}: a reply row lacks {missing}")


def _inside(day: str, it: dict, where: str) -> str:
    if not it["from"] <= day <= it["to"]:
        raise ValueError(f"{where}: a row dated {day} is outside the requested window {it['from']} to {it['to']}")
    return day


def _cash(it: dict) -> list[dict]:
    sym = it["symbol"]
    where = f"etf {sym} {it['from']}..{it['to']}"
    out = []
    for r in it["data"]:
        _need(r, CASH_KEYS, where)
        if r["CH_SYMBOL"] != sym:
            raise ValueError(f"{where}: a row is for symbol {r['CH_SYMBOL']}")
        day = _inside(_day(r["mTIMESTAMP"]), it, where)
        out.append(dict(date=day, symbol=sym, series=r["CH_SERIES"], open=_txt(r["CH_OPENING_PRICE"]), high=_txt(r["CH_TRADE_HIGH_PRICE"]),
                        low=_txt(r["CH_TRADE_LOW_PRICE"]), close=_txt(r["CH_CLOSING_PRICE"]), last=_txt(r["CH_LAST_TRADED_PRICE"]),
                        prev_close=_txt(r["CH_PREVIOUS_CLS_PRICE"]), qty=_txt(r["CH_TOT_TRADED_QTY"]), value=_txt(r["CH_TOT_TRADED_VAL"]),
                        trades=_txt(r["CH_TOTAL_TRADES"]), isin=""))
    return out


def _fo(it: dict) -> list[dict]:
    sym = it["symbol"]
    where = f"fo {sym} {it['expiry']}"
    out = []
    for r in it["data"]:
        _need(r, FO_KEYS, where)
        if all(r[k] is None for k in FO_TRADE_KEYS):
            continue                                   # a contract that is listed but nobody traded that day: the site sends the day with no values
        gone = [k for k in FO_TRADE_KEYS if r[k] is None]
        if gone:
            raise ValueError(f"{where}: a row dated {r['FH_TIMESTAMP']} lacks {gone} but has other values")
        if r["FH_INSTRUMENT"] != "FUTIDX":
            raise ValueError(f"{where}: a row is for instrument {r['FH_INSTRUMENT']}, expected FUTIDX")
        if r["FH_SYMBOL"] != sym:
            raise ValueError(f"{where}: a row is for symbol {r['FH_SYMBOL']}")
        if _day(r["FH_EXPIRY_DT"]) != it["expiry"]:
            raise ValueError(f"{where}: a row has expiry {_day(r['FH_EXPIRY_DT'])}")
        day = _inside(_day(r["FH_TIMESTAMP"]), it, where)
        lot, qty = Decimal(r["FH_MARKET_LOT"]), Decimal(r["FH_TOT_TRADED_QTY"])
        contracts, rest = divmod(qty, lot)
        if rest != 0:
            raise ValueError(f"{where} {day}: traded quantity {qty} is not a whole number of lots of {lot}")
        out.append(dict(date=day, symbol=sym, expiry=it["expiry"], open=_txt(r["FH_OPENING_PRICE"]), high=_txt(r["FH_TRADE_HIGH_PRICE"]),
                        low=_txt(r["FH_TRADE_LOW_PRICE"]), close=_txt(r["FH_CLOSING_PRICE"]), settle=_txt(r["FH_SETTLE_PRICE"]),
                        prev_close=_txt(r["FH_PREV_CLS"]), contracts=str(int(contracts)),
                        value_rs=_txt((Decimal(r["FH_TOT_TRADED_VAL"]) * 100000).quantize(Decimal("0.01"))),   # the site gives lakhs
                        open_int=_txt(r["FH_OPEN_INT"]), chg_oi=_txt(r["FH_CHANGE_IN_OI"]), lot=_txt(r["FH_MARKET_LOT"]), underlying=_txt(r["FH_UNDERLYING_VALUE"])))
    return out


def _index(it: dict) -> list[dict]:
    if it["kind"] == "vix":
        name, keys, where = "India VIX", VIX_KEYS, f"vix {it['from']}..{it['to']}"
    else:
        if it["index"] not in INDEX_NAMES:
            raise ValueError(f"index {it['index']!r} is not one this reader names (known: {sorted(INDEX_NAMES)})")
        name, keys, where = INDEX_NAMES[it["index"]], INDEX_KEYS, f"index {it['index']} {it['from']}..{it['to']}"
    out = []
    for r in it["data"]:
        _need(r, keys, where)
        day = _inside(_day(r["EOD_TIMESTAMP"]), it, where)
        out.append(dict(date=day, name=name, open=_txt(r["EOD_OPEN_INDEX_VAL"]), high=_txt(r["EOD_HIGH_INDEX_VAL"]), low=_txt(r["EOD_LOW_INDEX_VAL"]),
                        close=_txt(r["EOD_CLOSE_INDEX_VAL"]), volume=_txt(r.get("HIT_TRADED_QTY")), turnover_cr=_txt(r.get("HIT_TURN_OVER")),
                        pe="", pb="", div_yield=""))
    return out


def _document(raw: bytes) -> tuple[dict, list]:
    try:
        doc = json.loads(raw, parse_float=Decimal)
        meta, items = doc["meta"], doc["items"]
        if not isinstance(meta, dict) or not isinstance(items, list):
            raise TypeError("meta or items has the wrong type")
    except (ValueError, KeyError, TypeError) as e:
        raise ValueError(f"unexpected shape of the web history file ({e!r})") from e
    return meta, items


KEYS = {"cash": ("date", "symbol", "series"), "fo": ("date", "symbol", "expiry"), "index": ("date", "name")}


def _read(raw: bytes) -> tuple[dict[str, list[dict]], int]:
    """(rows, how many repeated identical rows were dropped). The site sometimes sends the same row twice; the same key with different values is
    a conflict and an error."""
    meta, items = _document(raw)
    got: dict[str, list[dict]] = {"cash": [], "fo": [], "index": []}
    for it in items:
        kind = it.get("kind")
        if kind == "etf":
            got["cash"] += _cash(it)
        elif kind == "fo":
            got["fo"] += _fo(it)
        elif kind in ("index", "vix"):
            got["index"] += _index(it)
        else:
            raise ValueError(f"an item of kind {kind!r} is not one this reader knows")
    out: dict[str, list[dict]] = {}
    dropped = 0
    for kind, rows in got.items():
        seen: dict[tuple, dict] = {}
        for r in rows:
            key = tuple(r[k] for k in KEYS[kind])
            if key in seen:
                if seen[key] != r:
                    raise ValueError(f"{kind} {key}: two rows with the same key and different values (conflict)")
                dropped += 1
                continue
            seen[key] = r
        out[kind] = list(seen.values())
    return out, dropped


def read_web(raw: bytes) -> dict[str, list[dict]]:
    """{'cash': [...], 'fo': [...], 'index': [...]} in the archive readers' row layout (the caller adds what it needs, such as a source)."""
    return _read(raw)[0]


def describe(raw: bytes) -> str:
    meta, items = _document(raw)
    rows, dropped = _read(raw)
    lines = [f"collected {meta.get('collected')}, {len(items)} replies"]
    if meta.get("status") not in (None, "finished"):
        lines.append(f"status {meta['status']}: this file is one part of the collection")
    for f in meta.get("failed", []):
        when = f"{f['year']}-{int(f['month']) + 1:02d}" if f.get("year") is not None else f"{f.get('from')} to {f.get('to')}"
        lines.append(f"not collected: {f['kind']} {f['key']} {when}")
    for kind, rs in rows.items():
        days = sorted(r["date"] for r in rs)
        lines.append(f"{kind} {len(rs)} rows" + (f", {days[0]} to {days[-1]}" if days else ""))
    if dropped:
        lines.append(f"{dropped} repeated identical rows dropped")
    empty = sum(1 for it in items if it.get("kind") == "fo" for r in it["data"] if all(r.get(k) is None for k in FO_TRADE_KEYS))
    if empty:
        lines.append(f"{empty} futures rows without trades left out")
    for m in meta.get("missing", []):
        lines.append(f"no contract found: {m['symbol']} {m['year']}-{int(m['month']):02d}")
    return "\n".join(lines)


def load_files(root: Path = ROOT) -> list[dict]:
    path = root / LISTING
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def register(src: Path, root: Path = ROOT, script: Path = SCRIPT, registered: date | None = None) -> dict:
    """Copy a downloaded file to data/raw/nse_web/ and list it. The file is read first: one the reader refuses is neither copied nor listed."""
    src = Path(src)
    raw = src.read_bytes()
    rows = read_web(raw)
    meta, items = _document(raw)
    dest = root / "raw" / "nse_web" / src.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(raw)
    row = {"file": src.name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "collected": meta.get("collected", ""), "requests": len(items),
           "rows_cash": len(rows["cash"]), "rows_fo": len(rows["fo"]), "rows_index": len(rows["index"]), "script": "data/nse_web_collect.js",
           "script_sha256": hashlib.sha256(Path(script).read_bytes()).hexdigest() if Path(script).exists() else "",
           "registered": (registered or date.today()).isoformat()}
    listed = sorted([r for r in load_files(root) if r["file"] != row["file"]] + [row], key=lambda r: r["file"])
    with (root / LISTING).open("w", newline="") as f:
        w = csv.DictWriter(f, FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(listed)
    return row


def verify_files(root: Path = ROOT, need_raw: bool = False) -> list[str]:
    problems, seen = [], set()
    for r in load_files(root):
        if r["file"] in seen:
            problems.append(f"{r['file']} is listed twice")
        seen.add(r["file"])
        path = root / "raw" / "nse_web" / r["file"]
        if path.exists():
            if hashlib.sha256(path.read_bytes()).hexdigest() != r["sha256"]:
                problems.append(f"{r['file']}: raw file hash differs from the list")
        elif need_raw:
            problems.append(f"{r['file']}: raw file is missing")
    return problems


def read_listed(root: Path = ROOT) -> dict[str, list[dict]]:
    """Rows of every listed file, each checked against its listed hash first."""
    out: dict[str, list[dict]] = {"cash": [], "fo": [], "index": []}
    for r in load_files(root):
        path = root / "raw" / "nse_web" / r["file"]
        if not path.exists():
            raise ValueError(f"{r['file']}: raw file is missing (download it again and register it)")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != r["sha256"]:
            raise ValueError(f"{r['file']}: raw file hash differs from the list")
        for kind, rows in read_web(raw).items():
            out[kind] += rows
    return out


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "register":
        print(register(Path(sys.argv[2])))
    elif len(sys.argv) == 3 and sys.argv[1] == "describe":
        print(describe(Path(sys.argv[2]).read_bytes()))
    else:
        sys.exit(__doc__)
