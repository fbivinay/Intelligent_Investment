"""Freeze one Yahoo Finance daily series as CSV plus a hashed manifest entry.

Yahoo's chart API is unofficial: fine for a first checkpoint, not a system of record.
Sub-project 2 replaces it with NSE files. Run:  python data/fetch_yahoo.py NIFTYBEES.NS
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).parent
URL = ("https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
       "?period1=0&period2={now}&interval=1d&events=div%7Csplit")


def fetch(symbol: str) -> bytes:
    req = urllib.request.Request(URL.format(symbol=symbol, now=int(time.time())),
                                 headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(3):
        try:
            return urllib.request.urlopen(req, timeout=30).read()
        except OSError:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))


def parse(raw: bytes) -> tuple[list[tuple[date, Decimal, Decimal]], dict[date, Decimal]]:
    """(bars of date, high, close), dividends per unit by ex-date.

    Refuses a reply that LISTS split events, because its prices are then adjusted in a way this layer does not handle. It cannot see
    a series adjusted without listing a split (Yahoo's NIFTYBEES.NS is one: see `adjusted` in data/corrections.json and the manifest)."""
    chart = json.loads(raw)["chart"]
    if not chart.get("result"):
        raise ValueError(f"Yahoo returned no data: {chart.get('error')}")
    r = chart["result"][0]
    events = r.get("events", {})
    if events.get("splits"):
        raise ValueError("split events present: prices are adjusted, handle in the data layer first")
    tz = timezone(timedelta(seconds=r["meta"]["gmtoffset"]))
    q = r["indicators"]["quote"][0]
    bars = [(datetime.fromtimestamp(t, tz).date(), Decimal(f"{h:.2f}"), Decimal(f"{c:.2f}"))
            for t, h, c in zip(r["timestamp"], q["high"], q["close"]) if h is not None and c is not None]
    divs = {datetime.fromtimestamp(v["date"], tz).date(): Decimal(f"{v['amount']:.4f}")
            for v in events.get("dividends", {}).values()}
    return bars, divs


def save(symbol: str, raw: bytes, retrieved: date, root: Path = ROOT, corrections: dict | None = None) -> Path:
    """Write the CSVs and the manifest entry. `corrections` (from data/corrections.json) can name bars to leave out, each with
    the reason, and dividends to add by hand, each with its source; both are recorded in the manifest."""
    bars, divs = parse(raw)
    if not bars:
        raise ValueError(f"no price rows in the Yahoo reply for {symbol}")
    corrections = corrections or {}
    excluded = dict(corrections.get("exclude", {}))
    for day in excluded:
        if not any(b[0].isoformat() == day for b in bars):
            raise ValueError(f"exclusion {day} matches no bar in the {symbol} series")
    bars = [b for b in bars if b[0].isoformat() not in excluded]
    if not bars:
        raise ValueError(f"every bar of {symbol} was excluded")
    manual = {}
    for day, entry in corrections.get("dividends", {}).items():
        if date.fromisoformat(day) in divs:
            raise ValueError(f"the dividend on {day} is already in the Yahoo series")
        divs[date.fromisoformat(day)] = Decimal(entry["per_unit"])
        manual[day] = entry["source"]
    (root / "raw").mkdir(exist_ok=True)
    (root / "processed").mkdir(exist_ok=True)
    (root / "raw" / f"yahoo_{symbol}_{retrieved:%Y%m%d}.json").write_bytes(raw)
    out = root / "processed" / f"{symbol.split('.')[0]}.csv"
    with out.open("w", newline="") as f:  # LF line ends on every system, so the hash below is the same everywhere
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["date", "high", "close"])
        w.writerows(bars)
    div_out = root / "processed" / f"{symbol.split('.')[0]}_dividends.csv"
    with div_out.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["ex_date", "per_unit"])
        w.writerows(sorted(divs.items()))
    mpath = root / "manifest.json"
    manifest = json.loads(mpath.read_text()) if mpath.exists() else {}
    manifest[out.name] = {"source": URL.format(symbol=symbol, now="<retrieval time>"), "retrieved": retrieved.isoformat(),
                          "raw_sha256": hashlib.sha256(raw).hexdigest(),
                          "csv_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
                          "rows": len(bars), "first": bars[0][0].isoformat(), "last": bars[-1][0].isoformat(),
                          "dividend_events": len(divs), "excluded": excluded, "manual_dividends": manual,
                          "dividends_csv": div_out.name, "dividends_csv_sha256": hashlib.sha256(div_out.read_bytes()).hexdigest(),
                          "adjusted": dict(corrections.get("adjusted", {}))}
    mpath.write_bytes((json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode())
    return out


def verify(root: Path = ROOT) -> list[str]:
    """Problems found by checking each processed CSV against its manifest entry (hash, row count, first and last date)."""
    problems = []
    for name, m in json.loads((root / "manifest.json").read_text()).items():
        path = root / "processed" / name
        if not path.exists():
            problems.append(f"{name}: file is missing")
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != m["csv_sha256"]:
            problems.append(f"{name}: hash differs from the manifest")
        with path.open(newline="") as f:
            rows = list(csv.DictReader(f))
        if len(rows) != m["rows"] or rows[0]["date"] != m["first"] or rows[-1]["date"] != m["last"]:
            problems.append(f"{name}: rows or dates differ from the manifest")
        div_name = m.get("dividends_csv")
        if not div_name or "dividends_csv_sha256" not in m:
            problems.append(f"{name}: the manifest has no hash for its dividends file")
            continue
        div_path = root / "processed" / div_name
        if not div_path.exists():
            problems.append(f"{div_name}: file is missing")
        elif hashlib.sha256(div_path.read_bytes()).hexdigest() != m["dividends_csv_sha256"]:
            problems.append(f"{div_name}: hash differs from the manifest")
        else:
            with div_path.open(newline="") as f:
                if len(list(csv.DictReader(f))) != m["dividend_events"]:
                    problems.append(f"{div_name}: rows differ from the manifest")
    return problems


def load_bars(path: Path):
    from engine.scenario import Bar
    with Path(path).open(newline="") as f:
        return [Bar(date.fromisoformat(r["date"]), Decimal(r["high"]), Decimal(r["close"])) for r in csv.DictReader(f)]


def load_dividends(path: Path) -> dict[date, Decimal]:
    with Path(path).open(newline="") as f:
        return {date.fromisoformat(r["ex_date"]): Decimal(r["per_unit"]) for r in csv.DictReader(f)}


if __name__ == "__main__":
    sym = sys.argv[1]
    cpath = ROOT / "corrections.json"
    fixes = json.loads(cpath.read_text()).get(sym, {}) if cpath.exists() else {}
    print(save(sym, fetch(sym), date.today(), corrections=fixes))
