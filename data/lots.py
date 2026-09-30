"""Lot sizes of the index futures, one per contract. Two sources publish the lot: the website file (to 2016-06) and the new daily file (from
2024-07-08). The old daily file (2016-01 to 2024-07-05) does not, so there the lot is worked out from the traded value: value / contracts / price =
units per contract, rounded to the nearest multiple of 5 (every NIFTY and BANKNIFTY lot NSE has set is one). A contract keeps the lot it was
listed with (NSE revises a lot for contracts listed after a date), so every day of a contract votes, weighted by contracts traded, and a wild day is
outvoted. Website rows are never used for the working-out (their contract counts were made from the lot); `check_published` compares the
working-out with the published lot wherever a contract has both. `lot_sizes.csv` has one row per contract: the lot, the share of votes that
agree, and whether it is `published` (used as it is, preferred) or `inferred`.
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
        if r.get("source", "archive") == "web":
            continue
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


def published_lots(rows: list[dict]) -> dict[tuple[str, str], tuple[int, Decimal]]:
    """{(symbol, expiry): (lot, share of the rows that carry it)} for contracts whose rows carry the lot the exchange published."""
    votes: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for r in rows:
        if r.get("lot"):
            votes[(r["symbol"], r["expiry"])][int(r["lot"])] += 1
    return {k: (c.most_common(1)[0][0], Decimal(c.most_common(1)[0][1]) / Decimal(sum(c.values()))) for k, c in votes.items()}


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
    """For contracts that have both a published lot and a working-out, compare them."""
    found, pub = contract_lots(rows), published_lots(rows)
    common = sorted(k for k in pub if k in found)
    differ = [(s, e, found[(s, e)][0], pub[(s, e)][0]) for s, e in common if found[(s, e)][0] != pub[(s, e)][0]]
    return {"compared": len(common), "differ": differ}


def table(rows: list[dict]) -> dict[tuple[str, str], tuple[int, Decimal, str]]:
    """{(symbol, expiry): (lot, agree, basis)}: the published lot where there is one, else the working-out."""
    found, pub = contract_lots(rows), published_lots(rows)
    return {k: (*pub[k], "published") if k in pub else (*found[k], "inferred") for k in sorted(set(found) | set(pub))}


def build(root: Path = ROOT) -> dict[str, int]:
    with (root / "processed" / "nse_index_futures_daily.csv").open(newline="") as f:
        rows = list(csv.DictReader(f))
    t = table(rows)
    with (root / "lot_sizes.csv").open("w", newline="") as f:
        w = csv.writer(f, lineterminator=chr(10))
        w.writerow(["symbol", "expiry", "lot", "agree", "basis"])
        w.writerows((s, e, lot, f"{share:.2f}", basis) for (s, e), (lot, share, basis) in t.items())
    n_pub = sum(1 for v in t.values() if v[2] == "published")
    return {"contracts": len(t), "runs": len(history({k: v[:2] for k, v in t.items()})), "differ": len(check_published(rows)["differ"]),
            "published": n_pub, "inferred": len(t) - n_pub}


if __name__ == "__main__":
    print(build())
    with (ROOT / "processed" / "nse_index_futures_daily.csv").open(newline="") as f:
        for run in history({k: v[:2] for k, v in table(list(csv.DictReader(f))).items()}):
            print(run)
