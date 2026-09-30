"""Daily NSE archive files: cash and F&O bhavcopy (end-of-day prices) and the index closes file.

Download, hash, list every day in data/nse_days.csv, and keep the raw files in data/raw/nse/ (git-ignored). Prices stay exactly as the
exchange published them. Statuses in the list:
  ok      the file came, its hash is listed
  absent  every address said 404: no such file (a weekend, a holiday). On a day the cash file is absent the other files are listed absent
          without being asked for (url left empty): the market was closed
  denied  a 403 while the exchange was serving other files to us (a file it does not give out)
A day that failed for any other reason is not listed, so the next run tries it again. A 403 while a file that certainly exists is refused too is
the exchange's firewall (Akamai) blocking us, not a fact about the file: the run waits and carries on, and never calls those days absent.
Run:  python data/nse_archive.py 2016-06-01 2026-09-30
"""
from __future__ import annotations

import csv
import hashlib
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
NEW_LAYOUT_FROM = date(2024, 7, 8)   # cash and F&O bhavcopy changed file layout and address here
INDEX_NEW_FROM = date(2023, 11, 17)  # the index closes file moved to the new address here (the old address gave its last file on 2023-11-16)
AROUND = 10                          # both addresses are tried this many days either side of a switch, one address everywhere else
KINDS = ["cash", "fo", "index"]      # cash first: on a day it has no file the market was closed
EXT = {"cash": ".zip", "fo": ".zip", "index": ".csv"}
FIELDS = ["kind", "date", "status", "bytes", "sha256", "url", "retrieved"]
MONTHS = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()
# One file per address that certainly exists. When it is refused as well, a 403 elsewhere is the firewall, not the file.
CANARY = {"archives.nseindia.com": "https://archives.nseindia.com/content/historical/EQUITIES/2016/JUN/cm03JUN2016bhav.csv.zip",
          "nsearchives.nseindia.com": "https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_20241001_F_0000.csv.zip"}


class Blocked(Exception):
    """The exchange's firewall is refusing us. Wait, then run again."""


def _order(d: date, switch: date) -> list[str]:
    if d < switch - timedelta(days=AROUND):
        return ["old"]
    if d >= switch + timedelta(days=AROUND):
        return ["new"]
    return ["new", "old"] if d >= switch else ["old", "new"]


def urls(kind: str, d: date) -> list[str]:
    """The addresses a day's file can be at, the likelier first (both only around a switch)."""
    mon = MONTHS[d.month - 1]
    if kind == "index":
        old = f"https://archives.nseindia.com/content/indices/ind_close_all_{d:%d%m%Y}.csv"
        new = f"https://nsearchives.nseindia.com/content/indices/ind_close_all_{d:%d%m%Y}.csv"
        switch = INDEX_NEW_FROM
    elif kind == "cash":
        old = f"https://archives.nseindia.com/content/historical/EQUITIES/{d.year}/{mon}/cm{d:%d}{mon}{d.year}bhav.csv.zip"
        new = f"https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{d:%Y%m%d}_F_0000.csv.zip"
        switch = NEW_LAYOUT_FROM
    elif kind == "fo":
        old = f"https://archives.nseindia.com/content/historical/DERIVATIVES/{d.year}/{mon}/fo{d:%d}{mon}{d.year}bhav.csv.zip"
        new = f"https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{d:%Y%m%d}_F_0000.csv.zip"
        switch = NEW_LAYOUT_FROM
    else:
        raise ValueError(f"unknown kind {kind!r}: cash, fo or index")
    return [{"old": old, "new": new}[w] for w in _order(d, switch)]


def days(start: date, end: date):
    """Every calendar day: special sessions (Diwali Muhurat, budget-day and test Saturdays) are real trading days on weekends."""
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def default_opener(url: str) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception:  # noqa: BLE001  (a timeout or a dropped connection: worth another try)
        return 0, b""


def paced(opener, gap: float = 0.6, clock=time.monotonic, sleep=time.sleep):
    """The same opener, but never two requests starting less than `gap` seconds apart, however many threads ask (the firewall blocked 6 a second)."""
    lock, last = threading.Lock(), [-1e9]

    def slow(url):
        with lock:
            wait = last[0] + gap - clock()
            if wait > 0:
                sleep(wait)
            last[0] = clock()
        return opener(url)

    return slow


def is_blocked(url: str, opener) -> bool:
    return opener(CANARY[url.split("/")[2]])[0] != 200


def fetch_day(kind: str, d: date, opener=default_opener, sleep=time.sleep, tries: int = 4):
    """(status, body, url): ok, absent (every address says 404), denied (a 403 while the exchange serves us other files), or error (the server
    kept failing, so we do not know). Raises Blocked when the exchange refuses even a file that certainly exists."""
    last, denied = "", False
    for url in urls(kind, d):
        last = url
        for attempt in range(tries):
            status, body = opener(url)
            if status == 200:
                return "ok", body, url
            if status == 404:
                break
            if status == 403:
                if is_blocked(url, opener):
                    raise Blocked(url)
                denied = True
                break
            if attempt < tries - 1:
                sleep(1.5 * (attempt + 1))
        else:
            return "error", None, url
    return ("denied" if denied else "absent"), None, last


def raw_path(root: Path, kind: str, d: date) -> Path:
    return root / "raw" / "nse" / kind / f"{d.isoformat()}{EXT[kind]}"


def load_days(root: Path = ROOT) -> list[dict]:
    path = root / "nse_days.csv"
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def append_days(rows: list[dict], root: Path = ROOT) -> None:
    if not rows:
        return
    path = root / "nse_days.csv"
    new = not path.exists()
    with path.open("a", newline="") as f:
        w = csv.DictWriter(f, FIELDS, lineterminator="\n")
        if new:
            w.writeheader()
        w.writerows(rows)


def sync(kinds, start: date, end: date, root: Path = ROOT, **kw) -> dict[str, int]:
    """One download at a time: two runs at once both list the same days (that happened once), so a lock file keeps the second one out."""
    lock = root / "nse_days.lock"
    try:
        lock.open("x").close()
    except FileExistsError:
        raise RuntimeError(f"another download seems to be running ({lock.name} exists); if none is, delete that file") from None
    try:
        return _sync(kinds, start, end, root, **kw)
    finally:
        lock.unlink(missing_ok=True)


def _sync(kinds, start: date, end: date, root: Path, opener=default_opener, sleep=time.sleep, workers: int = 3,
          retrieved: date | None = None, chunk: int = 60, max_waits: int = 8) -> dict[str, int]:
    """Fetch every day from start to end that the list does not have yet. Progress is written after every chunk. When the exchange blocks us the
    run waits (2, 4, 8 ... minutes, at most 30) and tries the same days again; after max_waits waits it raises Blocked, and a later run carries on."""
    retrieved = (retrieved or date.today()).isoformat()
    kinds = [k for k in KINDS if k in kinds]
    status_of = {(r["kind"], r["date"]): r["status"] for r in load_days(root)}
    todo = [d for d in days(start, end) if any((k, d.isoformat()) not in status_of for k in kinds)]
    counts = {"ok": 0, "absent": 0, "denied": 0, "error": 0}

    def one_day(d: date):
        """(day, rows, errors, blocked): the day's kinds in order, the others only when the cash file exists."""
        rows, errors, cash = [], 0, status_of.get(("cash", d.isoformat()))
        for k in kinds:
            if (k, d.isoformat()) in status_of:
                continue
            if k != "cash" and cash == "absent":
                rows.append({"kind": k, "date": d.isoformat(), "status": "absent", "bytes": 0, "sha256": "", "url": "", "retrieved": retrieved})
                continue
            try:
                status, body, url = fetch_day(k, d, opener, sleep)
            except Blocked:
                return d, rows, errors, True
            if k == "cash":
                cash = status
            if status == "error":
                errors += 1
                if k == "cash":
                    break
                continue
            if status == "ok":
                path = raw_path(root, k, d)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(body)
            rows.append({"kind": k, "date": d.isoformat(), "status": status, "bytes": len(body) if body else 0,
                         "sha256": hashlib.sha256(body).hexdigest() if body else "", "url": url, "retrieved": retrieved})
        return d, rows, errors, False

    for i in range(0, len(todo), chunk):
        pending, wait, waited = todo[i:i + chunk], 120, 0
        while pending:
            rows, again = [], []
            with ThreadPoolExecutor(workers) as ex:
                for d, day_rows, errors, blocked in ex.map(one_day, pending):
                    rows += day_rows
                    counts["error"] += errors
                    if blocked:
                        again.append(d)
            append_days(rows, root)
            for r in rows:
                status_of[(r["kind"], r["date"])] = r["status"]
                counts[r["status"]] += 1
            if not again:
                break
            if waited == max_waits:
                raise Blocked(f"the exchange is still blocking us after {max_waits} waits; run the same command again later (finished days are kept)")
            print(f"  the exchange is blocking us: waiting {wait} s ({waited + 1}/{max_waits})", flush=True)
            sleep(wait)
            wait, waited, pending = min(wait * 2, 1800), waited + 1, again
        print(f"  {min(i + chunk, len(todo))}/{len(todo)} days done: {counts}", flush=True)
    return counts


def verify_days(root: Path = ROOT, need_raw: bool = False) -> list[str]:
    """Problems in the day list: a day listed twice, a bad status or hash, and (for raw files that exist) a hash that differs."""
    problems, seen = [], set()
    for r in load_days(root):
        tag = f"{r['kind']} {r['date']}"
        if (r["kind"], r["date"]) in seen:
            problems.append(f"{tag} is listed twice")
        seen.add((r["kind"], r["date"]))
        if r["status"] not in ("ok", "absent", "denied"):
            problems.append(f"{tag}: status {r['status']!r} is not ok, absent or denied")
        elif r["status"] != "ok":
            if r["sha256"]:
                problems.append(f"{tag}: a {r['status']} day has a hash")
        elif not re.fullmatch(r"[0-9a-f]{64}", r["sha256"]):
            problems.append(f"{tag}: sha256 is not a 64-digit hex hash")
        else:
            path = raw_path(root, r["kind"], date.fromisoformat(r["date"]))
            if path.exists():
                if hashlib.sha256(path.read_bytes()).hexdigest() != r["sha256"]:
                    problems.append(f"{tag}: raw file hash differs from the list")
            elif need_raw:
                problems.append(f"{tag}: raw file is missing")
    return problems


if __name__ == "__main__":
    a, z = date.fromisoformat(sys.argv[1]), date.fromisoformat(sys.argv[2])
    kinds = sys.argv[3].split(",") if len(sys.argv) > 3 else ["cash", "fo", "index"]
    print(sync(kinds, a, z, opener=paced(default_opener)))
