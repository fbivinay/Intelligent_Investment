"""What the website shows before anyone asks the calculator: two real calculator answers (lean: no traces, CSV or projections), the invest-today table
and the repository facts the Evidence pages quote. Rerun after the data, the rules or the model change.

    python -m tools.site_data

site/public/data/lump.json    Rs 10 lakh once, from the Max level's first day, beside every alternative: the Overview and the calculator's first answer
site/public/data/sip.json     Rs 5,000 every month over the same years: the calculator's first monthly answer
site/public/data/future.json  each option's yearly return after charges and tax over those years, and the invest-today factors (calc.future)
site/public/data/facts.json   the data (counts, periods, real sample rows), the Max level's latest ranking and the LSTM strategy's record, read from the files
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from calc import api, future, options as O
from calc.product import DATA_END
from research import lstm as L, maxmodel as X, panel as P, stockmom as M
from research.kaggle import lstm as KL

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site" / "public" / "data"
START = "2017-04-03"                                     # the Max level's first day: every option is measured over the same years from it
ALTERNATIVES = [o.id for o in O.OPTIONS if o.kind != "product"]
COMMON = {"end": DATA_END.isoformat(), "level": "Max", "levels": ["Max", "LSTM"], "compare": ALTERNATIVES, "regime": "new", "other_income": 1200000, "lean": True}
SAMPLE = ("RELIANCE", "HDFCBANK", "INFY")
LSTM_VERSION = "v2"                                      # the LSTM strategy the Evidence shows (research/kaggle/lstm.py names the versions)
RUNS = {"lump": {**COMMON, "mode": "lump", "amount": 1000000, "start": START},
        "sip": {**COMMON, "mode": "sip", "amount": 5000, "start": START}}


def ranking() -> dict:
    """The Max level's latest ranking, by its own code: the day, the shares it could rank, the trend score of the best ones (with the 6- and 12-month
    returns and the yearly volatility the score is made of), checked against the 30 the model picked that day."""
    f, idx, traded = M.wide()
    chosen = M.picks(idx, f["value"], traded, 30, 500, trend=X.TREND)
    key = max(d for d, v in chosen.items() if v)
    day = pd.Timestamp(key)
    p = idx.index.get_loc(day)
    medval = f["value"].fillna(0).rolling(126, min_periods=100).median()
    s = M.score(idx, medval, traded.cumsum(), traded, p, 500).dropna()
    s = s.nlargest(len(s))                                                    # the order picks() takes its 30 from
    assert list(s.index[:30]) == list(chosen[key]), "the ranking does not give the model's picks"
    i = idx[s.index[:12]]
    r6, r12 = i.iloc[p] / i.iloc[p - 126] - 1, i.iloc[p] / i.iloc[p - 252] - 1
    vol = np.log(i.iloc[p - 252:p + 1]).diff().std() * np.sqrt(252)
    top = [{"symbol": k, "score": round(float(s[k]), 4), "r6": round(float(r6[k]), 4), "r12": round(float(r12[k]), 4), "vol": round(float(vol[k]), 4)}
           for k in s.index[:12]]
    return {"day": str(day.date()), "ranked": int(len(s)), "held": 30, "top": top,
            "decisions": len(chosen), "switch_days": sum(1 for v in chosen.values() if not v)}


def sample() -> list[dict]:
    """Real rows of the share file on its last day: the form the data is in."""
    df = pd.read_parquet(M.PARQUET, columns=["date", "symbol", "open", "high", "low", "close", "qty", "value"])
    last = df[df.date == df.date.max()].set_index("symbol").loc[list(SAMPLE)]
    return [{"date": str(r.date.date()), "symbol": k, "open": float(r.open), "high": float(r.high), "low": float(r.low), "close": float(r.close), "qty": int(r.qty),
             "value": float(r.value)} for k, r in last.iterrows()]


def lstm(version: str = LSTM_VERSION) -> dict:
    """The LSTM strategy's record (research/lstm_result.py, from the Kaggle kernel's weights) and the facts of its design (research/lstm.py), for the
    version the site shows."""
    res = json.loads((KL.out_dir(version) / "result.json").read_text(encoding="utf-8"))
    assets = KL.VERSIONS[version]
    return {**res, "inputs": len(L.PER_ASSET) * len(assets) + len(L.MARKET) + len(L.MAY_BE_MISSING), "per_asset": len(L.PER_ASSET),
            "market": len(L.MARKET), "flags": len(L.MAY_BE_MISSING), "assets": [*assets, "LIQUID_FUND"],
            "seq_lens": sorted({c["seq_len"] for c in L.CONFIGS}), "hidden": sorted({c["hidden"] for c in L.CONFIGS}), "seeds": len(L.SEEDS), "cost": L.COST,
            "tried": [{"version": v, "etfs": len(KL.VERSIONS[v]), **{k: r[k] for k in ("cagr", "worst_fall")}}
                      for v in KL.VERSIONS if (r := _result(v))]}


def _result(version: str) -> dict | None:
    path = KL.out_dir(version) / "result.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def facts() -> dict:
    stocks = pd.read_parquet(M.PARQUET, columns=["date", "symbol"])
    fields = [c for c in pq.read_schema(M.PARQUET).names if c not in ("date", "symbol")]
    etf = pd.read_csv(ROOT / "data" / "processed" / "etf_daily_adjusted.csv", usecols=["date", "symbol"])
    etf = etf[etf.symbol.isin(P.GROWTH)]
    return {"stocks": {"symbols": int(stocks.symbol.nunique()), "funds": len(M.funds()), "rows": len(stocks), "from": str(stocks.date.min().date()),
                       "to": str(stocks.date.max().date()), "fields": fields},
            "etfs": {"symbols": [a for a in P.GROWTH], "rows": len(etf), "from": etf.date.min(), "to": etf.date.max()},
            "max": {"momentum": X.MOMENTUM, "fixed": X.FIXED, "trend_days": X.TREND},
            "ranking": ranking(), "sample": sample(), "lstm": lstm()}


def projections(lump: dict) -> dict:
    """Each option's yearly return after charges and tax over the same years (Rs 10 lakh once from the Max level's first day), and the invest-today
    factors made from them."""
    rates = {r["id"]: {"rate": r["growth"], "worst_fall": r["worst_fall"]} for r in lump["results"]}
    return {"label": future.LABEL, "from": START, "to": DATA_END.isoformat(), "amount": RUNS["lump"]["amount"], "regime": "new", "other_income": 1200000,
            "rates": rates, "factors": future.factors({k: v["rate"] for k, v in rates.items()})}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    saved = {}
    for name, inputs in RUNS.items():
        a = api.calculate(inputs)
        assert "error" not in a and not a["messages"], a.get("error") or a["messages"]
        (OUT / f"{name}.json").write_text(json.dumps(a, separators=(",", ":")), encoding="utf-8")
        saved[name] = a
        print(f"{name}: " + ", ".join(f"{r['id']} {r['growth']:.1%}" for r in a["results"]))
    (OUT / "future.json").write_text(json.dumps(projections(saved["lump"]), separators=(",", ":")), encoding="utf-8")
    (OUT / "facts.json").write_text(json.dumps(facts(), indent=1), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
