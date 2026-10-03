"""Save one real calculator run as site/public/history.json: the Overview chart and the calculator's first result show it without waiting for the API. Rerun after the data or model changes.

    python -m tools.site_data
"""
from __future__ import annotations

import json
from pathlib import Path

from calc import api

OUT = Path(__file__).resolve().parents[1] / "site" / "public" / "history.json"
INPUTS = {"amount": 1000000, "start": "2017-04-03", "end": "2026-09-30", "level": "Max",
          "compare": ["NIFTYBEES", "GOLDBEES", "MON100", "LIQUID_FUND"], "regime": "new", "other_income": 1200000}

if __name__ == "__main__":
    a = api.calculate(INPUTS)
    assert "error" not in a, a
    out = {k: a[k] for k in ("inputs", "stamps", "results", "messages", "series", "notes")}     # the calculator's own answer, less traces, CSVs and projections
    OUT.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT}: " + ", ".join(f"{r['id']} {r['growth']:.1%}" for r in out["results"]))
