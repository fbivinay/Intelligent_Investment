"""Daily NAV of the mutual-fund schemes we use, from mfapi.in (a mirror of AMFI's NAV file), checked against AMFI's own report on sample days.

The ETFs are here to confirm splits and to stand in before 2016-06 (AMFI has no NAV for them from 2011-08-18 to 2016-11-06, because the ETF schemes
were re-registered under new codes). The Midcap 100 and Nasdaq 100 ETFs have one code all along; their NAV stands in for the exchange price before 2016,
where no exchange file of ours has them (data/nse_build.py). The funds are what an ordinary investor could hold instead: Nifty 50 index, Nifty Next 50 index, gold, arbitrage
and liquid. NAVs stay exactly as published (text), unadjusted.
Run:  python -m data.amfi_nav sync | build | check [YYYY-MM-DD ...]
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from data.nse_read import MON

ROOT = Path(__file__).parent
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
FIELDS = ["code", "label", "name", "isin", "rows", "first", "last", "bytes", "sha256", "url", "retrieved"]
REPORT_HEAD = "Scheme Code;NAV Name;Plan;Option;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Net Asset Value;Date"
SCHEMES = {
    "101325": "Nifty BeES ETF, old code (to 2011-08-18)", "140084": "Nifty BeES ETF, new code (from 2016-11-07)",
    "101621": "Junior BeES ETF, old code", "140085": "Junior BeES ETF, new code",
    "101296": "Bank BeES ETF, old code", "140087": "Bank BeES ETF, new code",
    "105085": "Gold BeES ETF, old code", "140088": "Gold BeES ETF, new code",
    "101884": "Liquid BeES ETF, old code", "140086": "Liquid BeES ETF, new code",
    "101525": "HDFC Nifty 50 index fund, regular", "119063": "HDFC Nifty 50 index fund, direct",
    "101349": "ICICI Prudential Nifty 50 index fund, regular", "120620": "ICICI Prudential Nifty 50 index fund, direct",
    "112957": "ICICI Prudential Nifty Next 50 index fund, regular", "120684": "ICICI Prudential Nifty Next 50 index fund, direct",
    "107693": "Quantum Gold ETF", "111954": "SBI Gold ETF", "113049": "HDFC Gold ETF",
    "104457": "SBI Arbitrage fund, regular", "119574": "SBI Arbitrage fund, direct",
    "113345": "Nippon India Arbitrage fund, regular", "118585": "Nippon India Arbitrage fund, direct",
    "100851": "Nippon India Liquid fund, regular", "118701": "Nippon India Liquid fund, direct",
    "100835": "Kotak Liquid fund, regular", "119766": "Kotak Liquid fund, direct",
    "114456": "Motilal Oswal Midcap 100 ETF (MOM100, was M100)", "114984": "Motilal Oswal Nasdaq 100 ETF (MON100, was N100)",
}
# Days the report is compared on: spread over the history, plus the Nifty BeES split day (2019-12-19) and both neighbours.
SAMPLE_DAYS = [date(2006, 9, 15), date(2008, 3, 14), date(2010, 12, 15), date(2011, 8, 18), date(2013, 6, 14), date(2016, 11, 7), date(2017, 6, 15),
               date(2018, 3, 15), date(2019, 12, 18), date(2019, 12, 19), date(2019, 12, 20), date(2020, 3, 23), date(2021, 6, 15),
               date(2022, 6, 14), date(2023, 6, 15), date(2024, 6, 14), date(2025, 6, 13), date(2026, 6, 15)]


def default_opener(url: str) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception:  # noqa: BLE001  (a timeout or a dropped connection: worth another try)
        return 0, b""


def _get(url: str, opener, sleep, tries: int = 4) -> bytes:
    for attempt in range(tries):
        status, body = opener(url)
        if status == 200:
            return body
        if attempt < tries - 1:
            sleep(2 * (attempt + 1))
    raise RuntimeError(f"{url}: the server did not give a file (last status {status})")


def _iso(s: str) -> str:
    """15-Jan-2020 or 15-01-2020 to 2020-01-15."""
    d, m, y = s.split("-")
    return f"{int(y):04d}-{int(m) if m.isdigit() else MON[m.upper()]:02d}-{int(d):02d}"


def _stamp(d: date) -> str:
    """15-Jan-2020, with English month names whatever language the computer is set to."""
    return f"{d.day:02d}-{list(MON)[d.month - 1].title()}-{d.year}"


def parse_history(raw: bytes) -> tuple[dict, list[tuple[str, str]]]:
    """(meta, rows) of one mfapi history, oldest row first. The NAV stays the text that was published."""
    try:
        d = json.loads(raw)
        meta = {"code": str(d["meta"]["scheme_code"]), "name": d["meta"]["scheme_name"], "isin": d["meta"].get("isin_growth") or ""}
        rows = sorted((_iso(r["date"]), r["nav"]) for r in d["data"])
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        raise ValueError(f"unexpected shape of a NAV history ({e!r})") from e
    for day, nav in rows:
        try:
            ok = Decimal(nav) > 0
        except InvalidOperation:
            ok = False
        if not ok:
            raise ValueError(f"scheme {meta['code']} on {day}: NAV {nav!r} is not a positive number")
    return meta, rows


def parse_report(text: str) -> dict[tuple[str, str], str]:
    """{(scheme code, ISO date): NAV text} from AMFI's NAV report. Rows without a number (N.A.) are left out."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != REPORT_HEAD:
        raise ValueError(f"unknown header of the AMFI report: {lines[:1]}")
    out = {}
    for line in lines[1:]:
        f = line.split(";")
        if len(f) == 8 and f[0].isdigit():
            try:
                Decimal(f[6])
            except InvalidOperation:
                continue
            out[(f[0], _iso(f[7]))] = f[6]
    return out


def _listed(root: Path) -> list[dict]:
    path = root / "amfi_schemes.csv"
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def sync(schemes: dict[str, str], root: Path = ROOT, opener=default_opener, sleep=time.sleep, retrieved: date | None = None) -> None:
    """Fetch every scheme's full history. Nothing is written unless all of them arrived, so raw files and the list always agree."""
    retrieved = retrieved or date.today()
    got = {}
    for code, label in schemes.items():
        url = f"https://api.mfapi.in/mf/{code}"
        try:
            raw = _get(url, opener, sleep)
            meta, rows = parse_history(raw)
            if meta["code"] != code:
                raise ValueError(f"asked for scheme {code}, got {meta['code']}")
        except (RuntimeError, ValueError) as e:
            raise RuntimeError(f"scheme {code} ({label}): {e}") from e
        got[code] = dict(code=code, label=label, name=meta["name"], isin=meta["isin"], rows=len(rows), first=rows[0][0] if rows else "",
                         last=rows[-1][0] if rows else "", bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), url=url, retrieved=retrieved.isoformat())
        (root / "raw" / "amfi").mkdir(parents=True, exist_ok=True)
        (root / "raw" / "amfi" / f"{code}.json").write_bytes(raw)
    merged = {r["code"]: r for r in _listed(root)} | got
    with (root / "amfi_schemes.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(merged[c] for c in sorted(merged))


def _navs(root: Path) -> list[tuple[str, str, str]]:
    """(date, code, nav) of every listed scheme, after each raw file is checked against the hash in the list."""
    out = []
    for r in _listed(root):
        path = root / "raw" / "amfi" / f"{r['code']}.json"
        if not path.exists():
            raise ValueError(f"scheme {r['code']}: raw file is missing (run: python -m data.amfi_nav sync)")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != r["sha256"]:
            raise ValueError(f"scheme {r['code']}: raw file hash differs from the list")
        meta, rows = parse_history(raw)
        if meta["code"] != r["code"]:
            raise ValueError(f"scheme {r['code']}: the file holds scheme {meta['code']}")
        out.extend((day, r["code"], nav) for day, nav in rows)
    return sorted(out)


def build(root: Path = ROOT) -> int:
    rows = _navs(root)
    (root / "processed").mkdir(exist_ok=True)
    with (root / "processed" / "amfi_nav_daily.csv").open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["date", "code", "nav"])
        w.writerows(rows)
    return len(rows)


def check(root: Path, days: list[date], opener=default_opener, sleep=time.sleep) -> dict:
    """Compare our NAVs with AMFI's own report for each day: which differ, which the report lacks, and which we lack."""
    ours: dict[str, dict[str, str]] = {}
    for day, code, nav in _navs(root):
        ours.setdefault(day, {})[code] = nav
    listed = {r["code"] for r in _listed(root)}
    compared, differ, missing_in_report, missing_in_ours = 0, [], [], []
    for d in days:
        stamp = _stamp(d)
        report = parse_report(_get(f"https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx?frmdt={stamp}&todt={stamp}", opener, sleep).decode("utf-8", "replace"))
        day = d.isoformat()
        for code, nav in sorted(ours.get(day, {}).items()):
            theirs = report.get((code, day))
            if theirs is None:
                missing_in_report.append((code, day))
                continue
            compared += 1
            if Decimal(nav) != Decimal(theirs):
                differ.append((code, day, nav, theirs))
        missing_in_ours += [(code, day) for (code, dd) in sorted(report) if dd == day and code in listed and code not in ours.get(day, {})]
    return {"compared": compared, "differ": differ, "missing_in_report": missing_in_report, "missing_in_ours": missing_in_ours}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "sync":
        sync(SCHEMES)
        print(f"listed {len(_listed(ROOT))} schemes")
    elif cmd == "build":
        print(f"{build()} NAV rows")
    elif cmd == "check":
        res = check(ROOT, [date.fromisoformat(a) for a in sys.argv[2:]] or SAMPLE_DAYS)
        print({k: (v if k == "compared" else len(v)) for k, v in res.items()})
        for k in ("differ", "missing_in_report", "missing_in_ours"):
            for x in res[k]:
                print(" ", k, x)
    else:
        sys.exit(__doc__)
