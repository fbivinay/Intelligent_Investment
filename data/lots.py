"""Lot sizes of the index futures, one per contract. The old daily file (before 2024-07-08) does not carry the lot, so it is worked out from the
traded value: value / contracts / price = units per contract, rounded to the nearest multiple of 5 (every NIFTY and BANKNIFTY lot NSE has set is
one). A contract keeps the lot it was listed with (NSE revises a lot for contracts listed after a date), so every day of a contract votes,
weighted by contracts traded, and a wild day is outvoted. The days from 2024-07-08 do carry the lot; `check_published` compares the working-out
with it. `lot_sizes.csv` has one row per contract: the lot and the share of votes that agree.
Run:  python -m data.lots
"""
from __future__ import annotations

import csv
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).parent
MIN_CONTRACTS = 1000            # fewer contracts and value / contracts / price is noise
AGREE = Decimal("0.5")          # more than this share of a contract's votes must agree on one lot, or it gets none


def implied_lot(row: dict) -> Decimal | None:
    c = Decimal(row["contracts"])
    return Decimal(row["value_rs"]) / c / Decimal(row["close"]) if c >= MIN_CONTRACTS else None


def contract_lots(rows: list[dict]) -> dict[tuple[str, str], tuple[int, Decimal]]:
    """{(symbol, expiry): (lot, share of the votes that agree)}"""
    votes: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for r in rows:
        x = implied_lot(r)
        if x is not None:
            votes[(r["symbol"], r["expiry"])][int((x / 5).to_integral_value()) * 5] += int(Decimal(r["contracts"]))
    out = {}
    for key, c in votes.items():
        lot, n = c.most_common(1)[0]
        share = Decimal(n) / Decimal(sum(c.values()))
        if share > AGREE:
            out[key] = (lot, share)
    return out


def history(found: dict) -> list[tuple[str, str, str, int]]:
    """(symbol, first expiry, last expiry, lot) for each run of consecutive expiries with the same lot."""
    runs: list[list] = []
    for (sym, expiry), (lot, _) in sorted(found.items()):
        if runs and runs[-1][0] == sym and runs[-1][3] == lot:
            runs[-1][2] = expiry
        else:
            runs.append([sym, expiry, expiry, lot])
    return [tuple(r) for r in runs]


def check_published(rows: list[dict]) -> dict:
    """For contracts whose rows carry the exchange's own lot, compare it with the working-out."""
    found = contract_lots(rows)
    published: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for r in rows:
        if r["lot"]:
            published[(r["symbol"], r["expiry"])][int(r["lot"])] += 1
    common = sorted(k for k in published if k in found)
    differ = [(s, e, found[(s, e)][0], published[(s, e)].most_common(1)[0][0]) for s, e in common if found[(s, e)][0] != published[(s, e)].most_common(1)[0][0]]
    return {"compared": len(common), "differ": differ}


def build(root: Path = ROOT) -> dict[str, int]:
    with (root / "processed" / "nse_index_futures_daily.csv").open(newline="") as f:
        rows = list(csv.DictReader(f))
    found = contract_lots(rows)
    with (root / "lot_sizes.csv").open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["symbol", "expiry", "lot", "agree"])
        w.writerows((s, e, lot, f"{share:.2f}") for (s, e), (lot, share) in sorted(found.items()))
    return {"contracts": len(found), "runs": len(history(found)), "differ": len(check_published(rows)["differ"])}


if __name__ == "__main__":
    print(build())
    with (ROOT / "processed" / "nse_index_futures_daily.csv").open(newline="") as f:
        for run in history(contract_lots(list(csv.DictReader(f)))):
            print(run)
