"""Lot sizes of the index futures over time. The old daily file (before 2024-07-08) does not carry the lot, so it is worked out from the traded value:
value / contracts / price = units per contract, rounded to the nearest multiple of 5 (every NIFTY and BANKNIFTY lot NSE has set is one). The days
from 2024-07-08 do carry the lot, and `check_published` compares the working-out with it. `lot_sizes.csv` lists runs of days with the same lot:
the change happened between one run's last_seen and the next run's first_seen.
Run:  python -m data.lots
"""
from __future__ import annotations

import csv
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).parent
MIN_CONTRACTS = 1000            # fewer contracts and value / contracts / price is noise
AGREE = Decimal("0.5")          # more than this share of a day's contracts must agree on one lot, or the day gets no lot


def implied_lot(row: dict) -> Decimal | None:
    c = Decimal(row["contracts"])
    return Decimal(row["value_rs"]) / c / Decimal(row["close"]) if c >= MIN_CONTRACTS else None


def daily_lots(rows: list[dict]) -> dict[tuple[str, str], int]:
    votes: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for r in rows:
        x = implied_lot(r)
        if x is not None:
            votes[(r["symbol"], r["date"])][int((x / 5).to_integral_value()) * 5] += int(Decimal(r["contracts"]))
    out = {}
    for key, c in votes.items():
        lot, n = c.most_common(1)[0]
        if n > sum(c.values()) * AGREE:
            out[key] = lot
    return out


def history(daily: dict[tuple[str, str], int]) -> list[tuple[str, str, str, int]]:
    """(symbol, first day seen, last day seen, lot) for each run of days with the same lot."""
    runs: list[list] = []
    for (sym, day), lot in sorted(daily.items()):
        if runs and runs[-1][0] == sym and runs[-1][3] == lot:
            runs[-1][2] = day
        else:
            runs.append([sym, day, day, lot])
    return [tuple(r) for r in runs]


def check_published(rows: list[dict]) -> dict:
    """On days that carry the exchange's own lot, compare it with the working-out."""
    inferred = daily_lots(rows)
    published: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for r in rows:
        if r["lot"]:
            published[(r["symbol"], r["date"])][int(r["lot"])] += 1
    common = sorted(k for k in published if k in inferred)
    differ = [(s, d, inferred[(s, d)], published[(s, d)].most_common(1)[0][0]) for s, d in common if inferred[(s, d)] != published[(s, d)].most_common(1)[0][0]]
    return {"compared": len(common), "differ": differ}


def build(root: Path = ROOT) -> dict[str, int]:
    with (root / "processed" / "nse_index_futures_daily.csv").open(newline="") as f:
        rows = list(csv.DictReader(f))
    daily = daily_lots(rows)
    runs = history(daily)
    with (root / "lot_sizes.csv").open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["symbol", "first_seen", "last_seen", "lot"])
        w.writerows(runs)
    return {"runs": len(runs), "days": len(daily), "differ": len(check_published(rows)["differ"])}


if __name__ == "__main__":
    print(build())
