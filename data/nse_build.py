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
OUT = {
    "cash": ("nse_etf_daily.csv", ["date", "symbol", "series", "open", "high", "low", "close", "last", "prev_close", "qty", "value", "trades", "isin"],
             ("date", "symbol", "series")),
    "fo": ("nse_index_futures_daily.csv", ["date", "symbol", "expiry", "open", "high", "low", "close", "settle", "prev_close", "contracts",
                                           "value_rs", "open_int", "chg_oi", "lot", "underlying"], ("date", "symbol", "expiry")),
    "index": ("nse_index_daily.csv", ["date", "name", "open", "high", "low", "close", "volume", "turnover_cr", "pe", "pb", "div_yield"],
              ("date", "name")),
}


def build(root: Path = ROOT, etfs=ETFS, futures=FUTURES, indices=INDICES) -> dict[str, int]:
    readers = {"cash": lambda raw: nr.read_cash(raw, etfs), "fo": lambda raw: nr.read_fo(raw, futures), "index": lambda raw: nr.read_index(raw, indices)}
    rows: dict[str, list[dict]] = {k: [] for k in OUT}
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
        for row in readers[r["kind"]](raw):
            if row["date"] != r["date"]:
                raise ValueError(f"{tag}: a row is dated {row['date']}")
            rows[r["kind"]].append(row)
    (root / "processed").mkdir(exist_ok=True)
    for kind, (name, fields, key) in OUT.items():
        with (root / "processed" / name).open("w", newline="") as f:
            w = csv.DictWriter(f, fields, lineterminator="\n")
            w.writeheader()
            w.writerows(sorted(rows[kind], key=lambda x: tuple(x[k] for k in key)))
    return {k: len(v) for k, v in rows.items()}


if __name__ == "__main__":
    print(build())
