"""Turn the listed raw NSE files into three processed CSVs (ETF daily, index-futures daily, index daily). Nothing is adjusted.

Every raw file is checked against the hash in data/nse_days.csv first, and every row must carry the date of the file it came from, so a
wrong or duplicated file cannot slip in. The CSVs are sorted and use LF line ends, so building twice gives the same bytes.
The file collected from the NSE website's own history reports (data/nse_web.py, listed in data/nse_web_files.csv) adds the rows the archive files
do not have (2010 to 2015); where both have a row the archive row is kept. The Midcap 100 and Nasdaq 100 ETFs are not in that file: before their first
archive row their NAV stands in (processed/amfi_nav_daily.csv, so run data/amfi_nav.py build first), scaled by the median price over NAV of their first
archive days so the series does not jump where the two meet. The `source` column says which one each row came from (archive, web or nav).
Run:  python -m data.nse_build
"""
from __future__ import annotations

import csv
import hashlib
from bisect import bisect_right
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path
from statistics import median

from data import nse_archive as na
from data import nse_read as nr
from data import nse_web as nw

ROOT = Path(__file__).parent
ETFS = {"NIFTYBEES", "JUNIORBEES", "BANKBEES", "GOLDBEES", "LIQUIDBEES", "MOM100", "MON100"}
RENAMED = {"M100": "MOM100", "N100": "MON100"}        # the exchange renamed both on 2021-06-16 (same ISINs); rows are listed under today's ticker
STAND_IN = {"MOM100": "114456", "MON100": "114984"}   # their AMFI scheme codes: the NAV stands in before their first archive row
JUNCTION = 20                                          # archive days the price over NAV ratio is taken from
LIQUIDITY = 250                                        # archive days the stand-in's traded value is taken from (their median)
CALENDAR = "NIFTYBEES"                                 # a stand-in row is made for each day this ETF traded: every full session, none of the gold-only ones
FUTURES = {"NIFTY", "BANKNIFTY"}
INDICES = {"Nifty 50", "Nifty Next 50", "Nifty Bank", "Nifty Midcap 100", "India VIX"}
MAX_PROBLEMS = 50    # stop reading after this many bad files: something systematic is wrong
OUT = {
    "cash": ("nse_etf_daily.csv", ["date", "symbol", "series", "open", "high", "low", "close", "last", "prev_close", "qty", "value", "trades", "isin", "source"],
             ("date", "symbol", "series")),
    "fo": ("nse_index_futures_daily.csv", ["date", "symbol", "expiry", "open", "high", "low", "close", "settle", "prev_close", "contracts",
                                           "value_rs", "open_int", "chg_oi", "lot", "underlying", "source"], ("date", "symbol", "expiry")),
    "index": ("nse_index_daily.csv", ["date", "name", "open", "high", "low", "close", "volume", "turnover_cr", "pe", "pb", "div_yield", "source"],
              ("date", "name")),
}


def build(root: Path = ROOT, etfs=ETFS, futures=FUTURES, indices=INDICES) -> dict[str, int]:
    old = {o: n for o, n in RENAMED.items() if n in etfs}
    readers = {"cash": lambda raw, day: [x | {"symbol": old.get(x["symbol"], x["symbol"])} for x in nr.read_cash(raw, etfs | set(old))],
               "fo": lambda raw, day: nr.read_fo(raw, futures),
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
                rows[r["kind"]].extend(dict(x, source="archive") for x in got)
                if r["kind"] == "index" and any(a["date"] != b["date"] for a, b in zip(got, nr.read_index(raw, indices))):
                    month_first += 1
        if len(problems) >= MAX_PROBLEMS:
            break
    if problems:      # every bad file at once, so a fix does not cost one full build per file
        raise ValueError(f"{len(problems)} files disagree with the list or are in a layout the reader does not know: " + "; ".join(problems[:20]))
    web = nw.read_listed(root)
    in_universe = {"cash": ("symbol", etfs), "fo": ("symbol", futures), "index": ("name", indices)}
    web_added = {k: 0 for k in OUT}
    for kind, (name, fields, key) in OUT.items():
        have = {tuple(x[k] for k in key) for x in rows[kind]}
        field, allowed = in_universe[kind]
        for x in web[kind]:
            if x[field] in allowed and tuple(x[k] for k in key) not in have:
                rows[kind].append(dict(x, source="web"))
                web_added[kind] += 1
    stand_ins = nav_stand_ins(rows["cash"], root, etfs)
    rows["cash"] += stand_ins
    for kind, (name, fields, key) in OUT.items():
        seen = Counter(tuple(x[k] for k in key) for x in rows[kind])
        twice = [k for k, n in seen.items() if n > 1]
        if twice:
            raise ValueError(f"{name}: {len(twice)} keys would be listed twice, first {twice[:5]}")
    (root / "processed").mkdir(exist_ok=True)
    for kind, (name, fields, key) in OUT.items():
        with (root / "processed" / name).open("w", newline="") as f:
            w = csv.DictWriter(f, fields, lineterminator="\n")
            w.writeheader()
            w.writerows(sorted(rows[kind], key=lambda x: tuple(x[k] for k in key)))
    return {k: len(v) for k, v in rows.items()} | {"index_month_first": month_first} | {f"{k}_web": n for k, n in web_added.items()} | {"cash_nav": len(stand_ins)}


def nav_stand_ins(cash: list[dict], root: Path, etfs) -> list[dict]:
    """Rows for the CALENDAR ETF's days before a STAND_IN ETF's first archive row, from its NAV of the day (or the last one before it) times the
    median price over NAV of its first JUNCTION archive days. Open, high, low and close are that price; the units are the median traded value of its first
    LIQUIDITY archive days over the price, so a fill's size can be compared with a normal day. Nothing before the NAV's first day."""
    out = []
    for sym in sorted(s for s in etfs if s in STAND_IN):
        mine = sorted((x for x in cash if x["symbol"] == sym and x["source"] == "archive"), key=lambda x: x["date"])
        days = sorted({x["date"] for x in cash if mine and x["symbol"] == CALENDAR and x["date"] < mine[0]["date"]})
        if not days:
            continue
        with (root / "processed" / "amfi_nav_daily.csv").open(newline="") as f:
            nav = sorted((r["date"], Decimal(r["nav"])) for r in csv.DictReader(f) if r["code"] == STAND_IN[sym])
        on = [d for d, _ in nav]

        def at(day: str) -> Decimal | None:
            k = bisect_right(on, day)
            return nav[k - 1][1] if k else None
        premium = median(Decimal(x["close"]) / at(x["date"]) for x in mine[:JUNCTION])
        value = median(Decimal(x["value"]) for x in mine[:LIQUIDITY])
        for day in days:
            v = at(day)
            if v is None:
                continue
            px = (v * premium).quantize(Decimal("0.0001"))
            units = max(int((value / px).to_integral_value()), 1)
            out.append(dict(date=day, symbol=sym, series="EQ", open=str(px), high=str(px), low=str(px), close=str(px), last="", prev_close="", qty=str(units),
                            value=str(units * px), trades="", isin="", source="nav"))
    return out


if __name__ == "__main__":
    print(build())
