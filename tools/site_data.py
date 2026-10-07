"""What the website shows before anyone asks the calculator: two real calculator answers (lean: no traces, CSV or projections) and the repository facts the
Evidence pages quote. Rerun after the data, the rules or the model change.

    python -m tools.site_data

site/public/data/lump.json   Rs 10 lakh once, from the Max level's first day: the Overview and the calculator's first one-time answer
site/public/data/sip.json    Rs 5,000 every month over the same years: the calculator's first monthly answer
site/public/data/facts.json  the data, the rules, the cost assumptions and the Max level's selection runs, read from the files that hold them
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from calc import api
from calc.product import DATA_END, rules
from research import costs as C, maxmodel as X

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site" / "public" / "data"
COMMON = {"end": DATA_END.isoformat(), "level": "Max", "compare": ["NIFTYBEES", "GOLDBEES", "MON100", "MOM100", "LIQUID_FUND"], "regime": "new",
          "other_income": 1200000, "lean": True}
RUNS = {"lump": {**COMMON, "mode": "lump", "amount": 1000000, "start": "2017-04-03"},
        "sip": {**COMMON, "mode": "sip", "amount": 5000, "start": "2017-04-03"}}
MIXES = ("mom", "momT", "momT50+gold25+nasdaq25", "momT60+gold20+nasdaq20", "momT70+gold30", "momT50+growth50", "nifty", "gold", "nasdaq")


def mixes(path: Path) -> list[dict]:
    """The rows of research/out/mixes.txt's first table (name, a year, worst fall) that the Evidence page quotes."""
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines()[1:]:
        if line.startswith("---"):
            break
        *name, cagr, fall = line.split()
        if " ".join(name) in MIXES:
            rows.append({"what": " ".join(name), "a_year": float(cagr), "worst_fall": float(fall)})
    return rows


def facts() -> dict:
    stocks = pd.read_parquet(ROOT / "data" / "processed" / "stocks_eq.parquet", columns=["date", "symbol"])
    rows = list(rules().all_rows())
    with (ROOT / "research" / "out" / "stockmom.csv").open(newline="") as f:
        runs = [{"picks": int(r["n"]), "universe": int(r["top"]), "a_year": float(r["cagr_liquidated"]), "worst_fall": float(r["max_dd"]), "orders": int(r["orders"])}
                for r in csv.DictReader(f)]
    return {"stocks": {"symbols": int(stocks.symbol.nunique()), "rows": len(stocks), "from": str(stocks.date.min().date()), "to": str(stocks.date.max().date())},
            "rules": {"rows": len(rows), "from": min(r.valid_from for r in rows).isoformat(), "verified_on": max(r.ref.verified_on for r in rows).isoformat()},
            "max": {"momentum": X.MOMENTUM, "fixed": X.FIXED, "trend_days": X.TREND},
            "costs": {"stock_half_spread": C.STOCK_HALF_SPREAD, "etf_half_spread": {k: C.HALF_SPREAD[k] for k in X.FIXED}, "impact": C.IMPACT,
                      "max_slippage": C.MAX_SLIPPAGE},
            "universe_runs": runs, "mixes": mixes(ROOT / "research" / "out" / "mixes.txt")}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, inputs in RUNS.items():
        a = api.calculate(inputs)
        assert "error" not in a and not a["messages"], a.get("error") or a["messages"]
        (OUT / f"{name}.json").write_text(json.dumps(a, separators=(",", ":")), encoding="utf-8")
        print(f"{name}: " + ", ".join(f"{r['id']} {r['growth']:.1%}" for r in a["results"]))
    (OUT / "facts.json").write_text(json.dumps(facts(), indent=1), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
