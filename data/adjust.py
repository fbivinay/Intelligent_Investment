"""Splits: found from the price gaps, confirmed against a second source (the fund's NAV), listed with the evidence in data/corporate_actions.csv,
and applied only here. The published prices are never touched: `adjust` adds adj_* columns (prices before a split's ex-date divided by its factor,
quantities multiplied by it, a factor of 1 leaves the published text as it is).
Run:  python -m data.adjust     (writes data/processed/etf_daily_adjusted.csv; stops when a big gap has no listed action, or an action has no gap)
"""
from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).parent
LOW, HIGH = Decimal("0.6"), Decimal("1.7")     # a close that moves outside this band from one day to the next is a candidate: no ETF here moves 40% in a day
SAME = Decimal("0.25")                          # a listed factor and the gap seen on its ex-date may differ this much (that day's market move)
ADJ = ["adj_factor", "adj_open", "adj_high", "adj_low", "adj_close", "adj_qty"]


def _plain(x: Decimal) -> str:
    return format(x.normalize(), "f")


def load_actions(path: Path = ROOT / "corporate_actions.csv") -> list[dict]:
    out, seen = [], set()
    with path.open(newline="") as f:
        for r in csv.DictReader(f):
            tag = f"{r['symbol']} {r['ex_date']}"
            if r["kind"] != "split":
                raise ValueError(f"{tag}: kind {r['kind']!r} is not handled (only split)")
            factor = Decimal(r["factor"])
            if factor <= 0:
                raise ValueError(f"{tag}: the factor must be above zero")
            if not r["evidence"].strip():
                raise ValueError(f"{tag}: no evidence given")
            if (r["symbol"], r["ex_date"]) in seen:
                raise ValueError(f"{tag}: listed twice")
            seen.add((r["symbol"], r["ex_date"]))
            out.append({"symbol": r["symbol"], "ex_date": date.fromisoformat(r["ex_date"]), "factor": factor, "evidence": r["evidence"]})
    return sorted(out, key=lambda a: (a["symbol"], a["ex_date"]))


def adjust(rows: list[dict], actions: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        day = date.fromisoformat(r["date"])
        factor = Decimal(1)
        for a in actions:
            if a["symbol"] == r["symbol"] and a["ex_date"] > day:
                factor *= a["factor"]
        if factor == 1:
            px = {k: r[k] for k in ("open", "high", "low", "close")}
            qty = r["qty"]
        else:
            px = {k: _plain(Decimal(r[k]) / factor) for k in ("open", "high", "low", "close")}
            qty = _plain(Decimal(r["qty"]) * factor)
        out.append(r | {"adj_factor": _plain(factor), "adj_open": px["open"], "adj_high": px["high"], "adj_low": px["low"], "adj_close": px["close"], "adj_qty": qty})
    return out


def candidates(rows: list[dict], low: Decimal = LOW, high: Decimal = HIGH) -> list[dict]:
    """Days a symbol's close moved outside the band from its previous listed day (same series). ratio = previous close / close."""
    last: dict[tuple, dict] = {}
    out = []
    for r in sorted(rows, key=lambda r: (r["symbol"], r["series"], r["date"])):
        key = (r["symbol"], r["series"])
        p = last.get(key)
        if p is not None:
            move = Decimal(r["close"]) / Decimal(p["close"])
            if move < low or move > high:
                out.append({"symbol": r["symbol"], "date": r["date"], "prev_date": p["date"], "prev_close": Decimal(p["close"]),
                            "close": Decimal(r["close"]), "ratio": Decimal(p["close"]) / Decimal(r["close"])})
        last[key] = r
    return out


def unexplained(rows: list[dict], actions: list[dict]) -> list[dict]:
    listed = {(a["symbol"], a["ex_date"].isoformat()) for a in actions}
    return [c for c in candidates(rows) if (c["symbol"], c["date"]) not in listed]


def unconfirmed(rows: list[dict], actions: list[dict]) -> list[dict]:
    """Listed actions whose ex-date shows no gap in the prices, or a gap of a different size than the factor."""
    seen = {(c["symbol"], c["date"]): c["ratio"] for c in candidates(rows)}
    return [a for a in actions if (a["symbol"], a["ex_date"].isoformat()) not in seen
            or abs(seen[(a["symbol"], a["ex_date"].isoformat())] / a["factor"] - 1) > SAME]


def build(root: Path = ROOT) -> int:
    with (root / "processed" / "nse_etf_daily.csv").open(newline="") as f:
        rd = csv.DictReader(f)
        fields, rows = list(rd.fieldnames), list(rd)
    actions = load_actions(root / "corporate_actions.csv")
    bad = [f"{c['symbol']} {c['date']} (close {c['prev_close']} to {c['close']}, ratio {c['ratio']:.2f}) has no listed action" for c in unexplained(rows, actions)]
    bad += [f"{a['symbol']} {a['ex_date']} (factor {a['factor']}) shows no matching gap in the prices" for a in unconfirmed(rows, actions)]
    if bad:
        raise ValueError("; ".join(bad))
    with (root / "processed" / "etf_daily_adjusted.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fields + ADJ, lineterminator="\n")
        w.writeheader()
        w.writerows(adjust(rows, actions))
    return len(rows)


if __name__ == "__main__":
    print(f"{build()} rows")
