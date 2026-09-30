"""Turn the listed raw NSE files into three processed CSVs (ETF daily, index-futures daily, index daily). Nothing is adjusted.

Every raw file is checked against the hash in data/nse_days.csv first, and every row must carry the date of the file it came from, so a
wrong or duplicated file cannot slip in. The CSVs are sorted and use LF line ends, so building twice gives the same bytes.
Run:  python -m data.nse_build
"""
from __future__ import annotations

import csv
import hashlib
from datetime import date
from pathlib import Path

from data import nse_archive as na
from data import nse_read as nr

ROOT = Path(__file__).parent
ETFS = {"NIFTYBEES", "JUNIORBEES", "BANKBEES", "GOLDBEES", "LIQUIDBEES"}
FUTURES = {"NIFTY", "BANKNIFTY"}
INDICES = {"Nifty 50", "Nifty Next 50", "Nifty Bank", "Nifty Midcap 100", "India VIX"}
MAX_PROBLEMS = 50    # stop reading after this many bad files: something systematic is wrong
OUT = {
    "cash": ("nse_etf_daily.csv", ["date", "symbol", "series", "open", "high", "low", "close", "last", "prev_close", "qty", "value", "trades", "isin"],
             ("date", "symbol", "series")),
    "fo": ("nse_index_futures_daily.csv", ["date", "symbol", "expiry", "open", "high", "low", "close", "settle", "prev_close", "contracts",
                                           "value_rs", "open_int", "chg_oi", "lot", "underlying"], ("date", "symbol", "expiry")),
    "index": ("nse_index_daily.csv", ["date", "name", "open", "high", "low", "close", "volume", "turnover_cr", "pe", "pb", "div_yield"],
              ("date", "name")),
}


def build(root: Path = ROOT, etfs=ETFS, futures=FUTURES, indices=INDICES) -> dict[str, int]:
    readers = {"cash": lambda raw, day: nr.read_cash(raw, etfs), "fo": lambda raw, day: nr.read_fo(raw, futures),
               "index": lambda raw, day: nr.read_index(raw, indices, day)}
    rows: dict[str, list[dict]] = {k: [] for k in OUT}
    problems: list[str] = []
    month_first = 0      # index files that write their date month first (3 in 2023): read as the day they were asked for, and counted
    for r in sorted(na.load_days(root), key=lambda r: (r["date"], r["kind"])):
        if r["status"] != "ok":
            continue
        tag = f"{r['kind']} {r['date']}"
        path = na.raw_path(root, r["kind"], date.fromisoformat(r["date"]))
        if not path.exists():
            raise ValueError(f"{tag}: raw file is missing (run data/nse_archive.py again for this day)")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != r["sha256"]:
            raise ValueError(f"{tag}: raw file hash differs from the list")
        try:
            got = readers[r["kind"]](raw, r["date"])
        except ValueError as e:
            problems.append(f"{tag}: {e}")
        else:
            wrong = [x["date"] for x in got if x["date"] != r["date"]]
            if wrong:
                problems.append(f"{tag}: a row is dated {wrong[0]}")
            else:
                rows[r["kind"]].extend(got)
                if r["kind"] == "index" and any(a["date"] != b["date"] for a, b in zip(got, nr.read_index(raw, indices))):
                    month_first += 1
        if len(problems) >= MAX_PROBLEMS:
            break
    if problems:      # every bad file at once, so a fix does not cost one full build per file
        raise ValueError(f"{len(problems)} files disagree with the list or are in a layout the reader does not know: " + "; ".join(problems[:20]))
    (root / "processed").mkdir(exist_ok=True)
    for kind, (name, fields, key) in OUT.items():
        with (root / "processed" / name).open("w", newline="") as f:
            w = csv.DictWriter(f, fields, lineterminator="\n")
            w.writeheader()
            w.writerows(sorted(rows[kind], key=lambda x: tuple(x[k] for k in key)))
    return {k: len(v) for k, v in rows.items()} | {"index_month_first": month_first}


if __name__ == "__main__":
    print(build())
