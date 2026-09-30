"""Where the data has holes, and how it compares with a second source. Writes data/gaps.md: every number in it is computed here, none is typed.
Run:  python -m data.gaps
"""
from __future__ import annotations

import csv
import json
import statistics
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from data import adjust
from data import nse_archive as na
from data import nse_web as nw

ROOT = Path(__file__).parent
YAHOO_TOL, NAV_TOL = Decimal("0.5"), Decimal("1")   # percent: a close that differs from Yahoo by more than 0.5%, or from the NAV by more than 1%, is listed
SHOWN = 40


def calendar_gaps(nse: set[str], other: set[str], start: str, end: str) -> dict[str, list[str]]:
    a, b = {d for d in nse if start <= d <= end}, {d for d in other if start <= d <= end}
    return {"only_nse": sorted(a - b), "only_other": sorted(b - a)}


def price_diffs(nse: dict[str, Decimal], other: dict[str, Decimal]) -> list[tuple[str, Decimal, Decimal, Decimal]]:
    """(day, ours, theirs, percent difference from theirs) for every day both have."""
    return [(d, nse[d], other[d], (nse[d] / other[d] - 1) * 100) for d in sorted(nse.keys() & other.keys())]


def summary(diffs: list, tol: Decimal) -> dict:
    over = sorted(((d, pct) for d, _, _, pct in diffs if abs(pct) > tol), key=lambda x: (-abs(x[1]), x[0]))
    big = max(diffs, key=lambda x: (abs(x[3]), x[0]), default=None)
    mid = Decimal(str(statistics.median(abs(x[3]) for x in diffs))) if diffs else Decimal(0)
    return {"days": len(diffs), "over": len(over), "median_abs": mid, "max_abs": abs(big[3]) if big else Decimal(0), "max_day": big[0] if big else None, "worst": over[:5]}


def nav_vs_index(nav: dict[str, Decimal], index: dict[str, Decimal], step: Decimal) -> dict:
    """NAV / index day by day (the NAV already on one unit size). A dividend paid out lowers the NAV and not the index: a one-day step down of the
    ratio. Dividends kept in the NAV push the ratio up over the years (the index is a price index). A drop over more than 5 calendar days is not
    taken for a payout: too many things can happen in that time."""
    common = sorted(nav.keys() & index.keys())
    ratio = {d: nav[d] / index[d] for d in common}
    years = (date.fromisoformat(common[-1]) - date.fromisoformat(common[0])).days / 365.25 if common else 0
    drift = Decimal(str((float(ratio[common[-1]] / ratio[common[0]]) ** (1 / years) - 1) * 100)) if years else Decimal(0)
    steps = [(a, b, (ratio[b] / ratio[a] - 1) * 100) for a, b in zip(common, common[1:])
             if (date.fromisoformat(b) - date.fromisoformat(a)).days <= 5 and (ratio[b] / ratio[a] - 1) * 100 < -step]
    return {"days": len(common), "first": common[0] if common else None, "last": common[-1] if common else None, "drift": drift, "steps": steps}


WEB_FIELDS = {"cash": ["open", "high", "low", "close", "last", "prev_close", "qty", "value"],
              "fo": ["open", "high", "low", "close", "settle", "prev_close", "contracts", "value_rs", "open_int", "chg_oi"],
              "index": ["open", "high", "low", "close", "volume", "turnover_cr"]}
WEB_KEYS = {"cash": ("date", "symbol", "series"), "fo": ("date", "symbol", "expiry"), "index": ("date", "name")}
WEB_FILES = {"cash": "nse_etf_daily.csv", "fo": "nse_index_futures_daily.csv", "index": "nse_index_daily.csv"}


def compare_sources(web: list[dict], archive: list[dict], key: tuple, fields: list[str]) -> dict:
    """For the rows both sources have (same key): per field, how many values differ, and the largest difference in percent of the archive value.
    A value either source leaves blank is not compared."""
    arc = {tuple(r[k] for k in key): r for r in archive}
    both = [(w, arc[tuple(w[k] for k in key)]) for w in web if tuple(w[k] for k in key) in arc]
    out = {}
    for f in fields:
        compared = differ = 0
        worst, where = Decimal(0), None
        for w, a in both:
            if w[f] == "" or a[f] == "":
                continue
            compared += 1
            x, y = Decimal(w[f]), Decimal(a[f])
            if x != y:
                differ += 1
                pct = abs(x - y) / abs(y) * 100 if y else Decimal(100)
                if pct > worst:
                    worst, where = pct, tuple(w[k] for k in key)
        out[f] = {"compared": compared, "differ": differ, "worst_pct": worst, "worst_key": where}
    return {"both": len(both), "fields": out}


def missing_days(reference: list[str], have: dict[str, set[str]], start: str, end: str) -> dict[str, list[str]]:
    """{name: the reference days inside the window that the set of days `have[name]` lacks}"""
    days = [d for d in reference if start <= d <= end]
    return {name: [d for d in days if d not in s] for name, s in have.items()}


def thin_days(reference: list[str], per_day: dict[str, int], minimum: int) -> list[str]:
    """The reference days on which fewer than `minimum` things were counted (a day not in `per_day` counts zero)."""
    return [d for d in reference if per_day.get(d, 0) < minimum]


ARCHIVE_FIRST = "2016-01-04"     # the first day the archive files have cash and F&O; the website file covers the days before
WEB_START = "2010-04-01"


def _nav_on_latest_scale(nav: dict[str, Decimal], actions: list[dict]) -> dict[str, Decimal]:
    """NAV divided by each split's factor for the days before the NAV series itself switched (its `nav_ex_date`, else the exchange's `ex_date`)."""
    out = {}
    for d, v in nav.items():
        f = Decimal(1)
        for a in actions:
            if (a["nav_ex_date"] or a["ex_date"]).isoformat() > d:
                f *= a["factor"]
        out[d] = v / f
    return out


def _read(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def _dates(days: list[str]) -> str:
    return ", ".join(days[:SHOWN]) + (f" and {len(days) - SHOWN} more" if len(days) > SHOWN else "") if days else "none"


def _line(what: str, s: dict, tol: Decimal) -> list[str]:
    tail = f", median {s['median_abs']:.2f}%, largest {s['max_abs']:.2f}% ({s['max_day']})" if s["days"] else ""
    out = [f"- {what}: {s['days']} days compared, {s['over']} differ by more than {tol}%{tail}"]
    if s["worst"]:
        out.append("  - worst: " + ", ".join(f"{d} {pct:+.2f}%" for d, pct in s["worst"]))
    return out


def report(root: Path = ROOT, symbol: str = "NIFTYBEES", code: str = "140084", yahoo: str = "NIFTYBEES.csv", start: str = "2016-06-01", end: str | None = None,
           nav_pairs: dict[str, str] | None = None, index_pairs: dict[str, str] | None = None) -> str:
    """`symbol` is compared with the Yahoo file `yahoo`; every symbol in `nav_pairs` ({symbol: AMFI scheme code}) is compared with its NAV, and
    every symbol in `index_pairs` ({symbol: index name}) has its NAV set against that index to see whether it pays dividends out."""
    nav_pairs = {sym: (c,) if isinstance(c, str) else tuple(c) for sym, c in (nav_pairs or {symbol: code}).items()}   # one or more scheme codes per ETF
    listed = na.load_days(root)
    end = end or max(r["date"] for r in listed)
    out = ["# Data gaps and cross-checks", "", "Generated by `python -m data.gaps` from the files in `data/`; every number is computed, none typed.", "",
           "## Day list (`data/nse_days.csv`)", ""]
    for kind in na.KINDS:
        c = Counter(r["status"] for r in listed if r["kind"] == kind)
        out.append(f"- {kind}: " + ", ".join(f"{s} {c[s]}" for s in ("ok", "absent", "denied") if c[s]))
    cash_ok = sorted(r["date"] for r in listed if r["kind"] == "cash" and r["status"] == "ok" and start <= r["date"] <= end)
    by_year = Counter(d[:4] for d in cash_ok)
    out += ["- cash days by year: " + ", ".join(f"{y}: {n}" for y, n in sorted(by_year.items())),
            "- `absent`: every address said 404 (a weekend or a holiday); on a day the cash file is absent the other files are listed absent without asking (url empty). "
            "`denied`: a 403 while the exchange served us other files. A day that failed for any other reason is not listed; run the download again.", ""]

    adjusted = root / "processed" / "etf_daily_adjusted.csv"
    adj_rows = _read(adjusted) if adjusted.exists() else []
    adj_of = lambda sym: {r["date"]: r for r in adj_rows if r["symbol"] == sym and start <= r["date"] <= end}  # noqa: E731
    ypath = root / "processed" / yahoo
    if ypath.exists():
        manifest = json.loads((root / "manifest.json").read_text()) if (root / "manifest.json").exists() else {}
        left_out = manifest.get(yahoo, {}).get("excluded", {})
        ycl = {r["date"]: Decimal(r["close"]) for r in _read(ypath)}
        cal = calendar_gaps(set(cash_ok), set(ycl), start, end)
        only_nse = [d + (f" (left out of the Yahoo file on purpose: {left_out[d]})" if d in left_out else "") for d in cal["only_nse"]]
        out += [f"## Trading calendar against Yahoo ({symbol}), {start} to {end}", "",
                f"- NSE cash days {len(cash_ok)}; Yahoo days {len([d for d in ycl if start <= d <= end])}",
                f"- days the NSE cash list has and Yahoo does not: {_dates(only_nse)}",
                f"- days Yahoo has and the NSE cash list does not: {_dates(cal['only_other'])}", ""]
    out += ["## Prices against a second source", "",
            "The NAV is put on the unit size of the adjusted close: divided by each split's factor for the days before the day the NAV series itself "
            "switched (`nav_ex_date` in `corporate_actions.csv`; AMFI's NAV can lag the exchange price by days).", ""]
    if ypath.exists():
        out += _line(f"{symbol} close, NSE split-adjusted against Yahoo (split-adjusted)",
                     summary(price_diffs({d: Decimal(r["adj_close"]) for d, r in adj_of(symbol).items()}, ycl), YAHOO_TOL), YAHOO_TOL)
    navs = root / "processed" / "amfi_nav_daily.csv"
    nav_rows = _read(navs) if navs.exists() else []
    cpath = root / "corporate_actions.csv"
    actions = adjust.load_actions(cpath) if cpath.exists() else []
    for sym, codes in nav_pairs.items():
        c = "+".join(codes)
        nav = _nav_on_latest_scale({r["date"]: Decimal(r["nav"]) for r in nav_rows if r["code"] in codes}, [a for a in actions if a["symbol"] == sym])
        out += _line(f"{sym} split-adjusted close against AMFI NAV (scheme {c})",
                     summary(price_diffs({d: Decimal(r["adj_close"]) for d, r in adj_of(sym).items()}, nav), NAV_TOL), NAV_TOL)
    out.append("")

    if index_pairs:
        ipath = root / "processed" / "nse_index_daily.csv"
        idx_rows = _read(ipath) if ipath.exists() else []
        out += ["## Do the equity ETFs pay dividends out?", "",
                "An ETF's NAV set against the price index it follows. A payout lowers the NAV and not the index: a one-day step down. Dividends kept in the NAV "
                "push the ratio up over the years. Days inside a split's switch are put on one unit size first.", ""]
        for sym, name in index_pairs.items():
            codes = nav_pairs.get(sym, (code,))
            c = "+".join(codes)
            nav = _nav_on_latest_scale({r["date"]: Decimal(r["nav"]) for r in nav_rows if r["code"] in codes and start <= r["date"] <= end},
                                       [a for a in actions if a["symbol"] == sym])
            got = nav_vs_index(nav, {r["date"]: Decimal(r["close"]) for r in idx_rows if r["name"] == name}, Decimal("0.25"))
            steps = ", ".join(f"{b} {pct:.2f}%" for _, b, pct in got["steps"][:10])
            out.append(f"- {sym} NAV against {name} (scheme {c}): {got['days']} days, ratio drift {got['drift']:+.2f}% a year, {len(got['steps'])} one-day step down over 0.25%"
                       + (f": {steps}" if steps else ""))
        out.append("")

    if nw.load_files(root):
        web = nw.read_listed(root)
        out += ["## Website file against the archive files", "",
                "The file collected from the NSE website's own history reports (`nse_web_files.csv`) covers the years before the archive; on the days both have "
                "a row the two are compared field by field, exactly (the build keeps the archive row).", ""]
        for kind in ("cash", "fo", "index"):
            path = root / "processed" / WEB_FILES[kind]
            arc = [r for r in _read(path) if r.get("source", "archive") == "archive"] if path.exists() else []
            res = compare_sources(web[kind], arc, WEB_KEYS[kind], WEB_FIELDS[kind])
            diffs = [f"{f} {v['differ']} of {v['compared']} (largest {v['worst_pct']:.2f}%, {' '.join(v['worst_key'])})" for f, v in res["fields"].items() if v["differ"]]
            same = "all compared fields equal" if not diffs else "differ: " + "; ".join(diffs)
            out.append(f"- {kind}: {res['both']} rows in both; {same}")
        out.append("")

    if nw.load_files(root):
        end_web = (date.fromisoformat(ARCHIVE_FIRST) - timedelta(days=1)).isoformat()
        def rows_of(kind):
            path = root / "processed" / WEB_FILES[kind]
            return _read(path) if path.exists() else []

        idx_rows = rows_of("index")
        ref = sorted({r["date"] for r in idx_rows if r["name"] == "Nifty 50" and WEB_START <= r["date"] <= end_web})
        out += [f"## Coverage of the years before the archive ({WEB_START} to {end_web})", "",
                f"Measured against the {len(ref)} days on which the Nifty 50 has a close (from the index file, whichever source), so a hole shows as a day.", ""]
        etf_days: dict[str, set[str]] = {}
        for r in rows_of("cash"):
            etf_days.setdefault(r["symbol"], set()).add(r["date"])
        for sym, miss in sorted(missing_days(ref, etf_days, WEB_START, end_web).items()):
            out.append(f"- {sym}: {len(ref) - len(miss)} of {len(ref)} Nifty 50 days have a row; missing: {_dates(miss)}")
        vix_days = {r["date"] for r in idx_rows if r["name"] == "India VIX"}
        if vix_days:
            after = [d for d in ref if d >= min(vix_days)]
            miss = [d for d in after if d not in vix_days]
            out.append(f"- India VIX (from its first day, {min(vix_days)}): {len(after) - len(miss)} of {len(after)} Nifty 50 days have a row; missing: {_dates(miss)}")
        per: dict[str, dict[str, int]] = {}
        for r in rows_of("fo"):
            per.setdefault(r["symbol"], Counter())[r["date"]] += 1
        for sym, counts in sorted(per.items()):
            thin = thin_days(ref, counts, 3)
            out.append(f"- {sym} futures: {len(ref) - len(thin)} of {len(ref)} days have 3 contracts; first day without: {thin[0] if thin else 'none'}")
        out.append("")

    out += ["## Processed files", ""]
    for name, col in (("nse_etf_daily.csv", "symbol"), ("nse_index_futures_daily.csv", "symbol"), ("nse_index_daily.csv", "name"), ("amfi_nav_daily.csv", "code")):
        path = root / "processed" / name
        if path.exists():
            rows = _read(path)
            per = Counter(r[col] for r in rows)
            out.append(f"- `{name}`: {len(rows)} rows, {rows[0]['date']} to {rows[-1]['date']}; " + ", ".join(f"{k} {v}" for k, v in sorted(per.items())))
    return "\n".join(out) + "\n"


# AMFI has each ETF under two scheme codes: the old one to 2011-08-18, the new one from 2016-11 (nothing in between)
ETF_NAVS = {"NIFTYBEES": ("101325", "140084"), "JUNIORBEES": ("101621", "140085"), "BANKBEES": ("101296", "140087"),
            "GOLDBEES": ("105085", "140088"), "LIQUIDBEES": ("101884", "140086")}

EQUITY_ETF_INDEX = {"NIFTYBEES": "Nifty 50", "JUNIORBEES": "Nifty Next 50", "BANKBEES": "Nifty Bank"}

if __name__ == "__main__":
    text = report(start=WEB_START, nav_pairs=ETF_NAVS, index_pairs=EQUITY_ETF_INDEX)
    (ROOT / "gaps.md").write_text(text, newline="\n")
    print(text)
