"""One call for the web app: `calculate(params) -> dict`, plain JSON.

Inputs: amount, start, end, model ("six" ETFs, the default, or "four", the frozen-test model), level (its risk level), compare (alternatives to show), regime, other_income, slippage, end_convention (sell or hold), horizon
(projection years). Output: the model and each alternative with net, gross end value, charges, tax and "if still holding", each figure with the id of its trace;
charges by kind and tax by financial year; daily values for the chart; projections; the model's trades and tax lines as CSV; stamps and notes. A bad input
returns {"error": ...} only; an option that cannot run on these dates (the model before its first pick, a fund that did not exist yet) is a message beside the rest.
"""
from __future__ import annotations

import json
import zlib
from datetime import date
from decimal import Decimal

import numpy as np

from calc import compare as CP, options as O, product as PR, project as PJ, replay as R
from engine.tax import TaxProfile, fy_label
from engine.trace import Node, flags
from research.sim import classes

DATA_START, DATA_END = date(2010, 4, 1), PR.DATA_END
MAX_CHILDREN = 12
MAX_DEPTH = 5
SERIES_POINTS = 500
RESEARCH_AMOUNT = Decimal(1000000)
MODEL_NAMES = {"six": ", six ETFs", "four": ", four ETFs (frozen test)"}
PLANS = {"six": "replay of the six-ETF model's signal", "four": "replay of the frozen model's signal"}
SIGNALS = {"six": "six-ETF model (research/out/signal_growth): yearly picks out of sample, the Midcap 100 and Nasdaq 100 ETFs added with hindsight",
           "four": "frozen design frozen-design-v1 (research/out/signal)"}
NOTES = [
    "Past results, not a promise; not investment advice.",
    "The model follows the weights of one reference account that has the drawdown guard; your own fall can exceed the cap if you start on another day.",
    "The model decides at a day's close and buys or sells the next day at that day's average price plus an assumed slippage; the alternatives are bought at the "
    "start day's close (ETFs) or NAV (funds) and held.",
    "ETFs sit in a demat account (opening, yearly and depository fees); funds are held with the fund house (no demat fees). Exit loads are not modelled.",
    "Dividends are added as cash, not reinvested. Cash earns nothing.",
    "Projections resample each option's own past daily returns and tax the value at the horizon on today's rules: an estimate, never a forecast.",
]


class _Traces:
    """Collects depth-limited trace trees by id; long input lists are cut to MAX_CHILDREN with one line saying how many more and their sum."""
    def __init__(self):
        self.trees: dict[str, dict] = {}

    def add(self, n: Node, depth: int = MAX_DEPTH) -> str:
        tid = f"t{len(self.trees)}"
        tree = self._dict(n, depth)
        tree["flags"] = [{"id": r.rule_id, "confidence": r.confidence, "note": r.note, "source": r.source} for r in flags(n)]
        self.trees[tid] = tree
        return tid

    def _dict(self, n: Node, depth: int) -> dict:
        d = {"label": n.label, "value": str(n.value), "op": n.op, "formula": n.formula}
        if n.note:
            d["note"] = n.note
        if n.rules:
            d["rules"] = [{"id": r.rule_id, "from": r.valid_from.isoformat(), "to": r.valid_to.isoformat() if r.valid_to else None, "source": r.source,
                           "verified_on": r.verified_on.isoformat(), "confidence": r.confidence} for r in n.rules]
        if depth > 0 and n.inputs:
            kids = [self._dict(i, depth - 1) for i in n.inputs[:MAX_CHILDREN]]
            rest = n.inputs[MAX_CHILDREN:]
            if rest:
                kids.append({"label": f"... and {len(rest)} more lines", "value": str(sum((i.value for i in rest), Decimal(0))), "op": "more", "formula": "sum"})
            d["inputs"] = kids
        return d


def _fig(n: Node, traces: _Traces, depth: int = MAX_DEPTH) -> dict:
    return {"value": float(n.value), "exact": str(n.value), "trace": traces.add(n, depth)}


def _thin(dates: list[str], values: list[float]) -> dict:
    step = max(1, int(np.ceil(len(dates) / SERIES_POINTS)))
    keep = list(range(0, len(dates), step))
    if keep[-1] != len(dates) - 1:
        keep.append(len(dates) - 1)
    return {"dates": [dates[i] for i in keep], "values": [round(values[i], 2) for i in keep]}


def _parse(params: dict) -> dict:
    def day(key):
        try:
            return date.fromisoformat(str(params[key]))
        except (KeyError, ValueError):
            raise ValueError(f"{key} must be a date like 2016-04-01")
    try:
        amount = Decimal(str(params.get("amount")))
    except Exception:
        raise ValueError("the amount must be a number of rupees")
    if not amount.is_finite() or amount <= 0 or amount > Decimal(10) ** 9:
        raise ValueError("the amount must be more than Rs 0 and at most Rs 100 crore")
    start, end = day("start"), day("end")
    if start < DATA_START:
        raise ValueError(f"the data starts {DATA_START.isoformat()}")
    if end > DATA_END:
        raise ValueError(f"the data ends {DATA_END.isoformat()}")
    if end <= start:
        raise ValueError("the end date must be after the start date")
    model = params.get("model", "six")
    if model not in PR.MODELS:
        raise ValueError(f"the model must be one of {', '.join(PR.MODELS)}")
    level = params.get("level", "Balanced")
    if level not in PR.MODELS[model][2]:
        raise ValueError(f"the risk level must be one of {', '.join(PR.MODELS[model][2])}")
    regime = params.get("regime", "new")
    if regime not in ("new", "old"):
        raise ValueError("the tax regime must be new or old")
    try:
        income = Decimal(str(params.get("other_income", 1200000)))
    except Exception:
        raise ValueError("other income must be a number of rupees")
    if not income.is_finite() or income < 0:
        raise ValueError("other income must be zero or more")
    horizon = params.get("horizon", 5)
    if not isinstance(horizon, int) or not 1 <= horizon <= 20:
        raise ValueError("the projection horizon must be 1 to 20 years")
    compare = params.get("compare", [o.id for o in O.OPTIONS if o.kind != "product"])
    for c in compare:
        O.get(c) if c in {o.id for o in O.OPTIONS} else (_ for _ in ()).throw(ValueError(f"unknown option {c!r}"))
    end_conv = params.get("end_convention", "sell")
    if end_conv not in ("sell", "hold"):
        raise ValueError("the end convention must be sell or hold")
    return dict(amount=amount, start=start, end=end, model=model, level=level, profile=TaxProfile(regime, income), compare=list(compare), slippage=bool(params.get("slippage", True)),
                headline="sold" if end_conv == "sell" else "held", horizon=horizon)


def _figures(sold_w: dict, held_w: dict, traces: _Traces) -> dict:
    """The headline figures: their own traces are shallow (the parts have traces of their own), the tax ones deep enough to show the rates and the exemption."""
    return {"net": _fig(sold_w["net"], traces, 2), "gross_end": _fig(sold_w["gross_end"], traces, 3), "charges": _fig(sold_w["charges"], traces, 2),
            "tax": _fig(sold_w["tax"], traces, 2), "held_net": _fig(held_w["net"], traces, 2), "held_tax": _fig(held_w["tax"], traces, 2)}


def _seed(option_id: str, years: int) -> int:
    return zlib.crc32(option_id.encode()) ^ years


def calculate(params: dict) -> dict:
    try:
        p = _parse(params)
    except (ValueError, KeyError) as e:
        return {"error": str(e).strip("'\"")}
    traces, results, messages, series, projections = _Traces(), [], [], {}, {}
    csv = {"trades": "", "tax_lines": ""}
    check = {}
    pid = f"PRODUCT_{p['level']}"
    try:
        run = PR.run(p["level"], p["amount"], p["start"], p["end"], p["profile"], p["slippage"], p["model"])
    except ValueError as e:
        messages.append({"id": pid, "text": str(e)})
    else:
        b = run.booked
        results.append({"id": pid, "name": O.get(pid).name + MODEL_NAMES[p["model"]], "kind": "product", "plan": PLANS[p["model"]], "headline": p["headline"],
                        **_figures(b.waterfall["sold"], b.waterfall["held"], traces),
                        "charges_by_kind": [{"label": R.KIND_LABELS.get(k, k), **_fig(n, traces, 3)} for k, n in b.charges_by_kind["sold"].items()],
                        "tax_by_fy": [{"fy": fy_label(fy), **_fig(n, traces, 6)} for fy, n in sorted(b.tax_by_fy.items())],
                        "growth": run.growth_sold, "growth_held": run.growth_held, "worst_fall": run.worst_fall, "orders": len(b.trades),
                        "strategies": sorted(set(run.strategy))})
        series[pid] = _thin(run.dates, run.equity)
        csv = {"trades": R.csv_text(b.trades), "tax_lines": R.csv_text(b.tax_lines)}
        check["product_books_less_fast_simulator_rupees"] = round(run.gap, 2)
        hist = PR.run(p["level"], RESEARCH_AMOUNT, PR.start_of(p["level"]), p["end"], p["profile"], p["slippage"], p["model"])
        split = {}
        for c, x in zip(classes(run.names[:-1]), run.weights[-1]):
            split[c] = split.get(c, 0.0) + float(x)
        rets = np.diff(np.asarray(hist.pretax)) / np.asarray(hist.pretax[:-1])
        projections[pid] = PJ.project(rets, b.sold.value if p["headline"] == "sold" else b.held.value, split, p["horizon"], p["profile"], _seed(pid, p["horizon"]))
    for oid in p["compare"]:
        o = O.get(oid)
        try:
            r = CP.run_option(o, p["amount"], p["start"], p["end"], p["profile"])
        except ValueError as e:
            messages.append({"id": oid, "text": str(e)})
            continue
        charges = {"Buy charges": r.sold.waterfall["buy_charges"], "Sale charges": r.sold.waterfall["sale_charges"],
                   "Account opening fee": r.sold.waterfall["account_opening"], "Yearly demat fees": r.sold.waterfall["amc"]}
        results.append({"id": oid, "name": o.name, "kind": o.kind, "plan": r.plan, "headline": p["headline"], **_figures(r.sold.waterfall, r.held.waterfall, traces),
                        "charges_by_kind": [{"label": k, **_fig(n, traces)} for k, n in charges.items()], "tax_by_fy": [],
                        "growth": r.growth_sold, "growth_held": r.growth_held, "worst_fall": r.worst_fall, "orders": 2 if p["headline"] == "sold" else 1})
        series[oid] = _thin(r.dates, r.values)
        bars, _, _ = O.history(o, O.first_day(o, p["start"]))
        closes = np.array([float(b.close) for b in bars if b.on <= p["end"]])
        projections[oid] = PJ.project(closes[1:] / closes[:-1] - 1, r.sold.net.value if p["headline"] == "sold" else r.held.net.value, {o.instrument_class: 1.0},
                                      p["horizon"], p["profile"], _seed(oid, p["horizon"]))
    return {"inputs": {**{k: v for k, v in params.items()}, "start": p["start"].isoformat(), "end": p["end"].isoformat(), "level": p["level"], "model": p["model"]},
            "stamps": {"data_as_of": DATA_END.isoformat(), "rules_verified_on": max(r.ref.verified_on for r in PR.rules().all_rows()).isoformat(),
                       "signal": SIGNALS[p["model"]] + ("; Max level: research/out/signal_max (stock momentum, gold and Nasdaq ETFs)" if p["level"] == "Max" else "")},
            "results": results, "messages": messages, "traces": traces.trees, "series": series, "projections": projections, "csv": csv, "check": check, "notes": NOTES}


def preview(params: dict) -> dict:
    """The Fyers preview of one fill day of the model's account (the first day with orders if no date is given), and the days that have orders."""
    from calc import fyers as F
    try:
        p = _parse({**params, "compare": []})
        run = PR.run(p["level"], p["amount"], p["start"], p["end"], p["profile"], p["slippage"], p["model"])
        days = F.order_days(run)
        on = date.fromisoformat(str(params.get("date", days[0] if days else run.dates[1])))
        return {"order_days": days, "preview": F.preview(run, on)}
    except (ValueError, KeyError) as e:
        return {"error": str(e).strip("'\"")}


if __name__ == "__main__":
    import sys
    print(json.dumps(calculate(json.loads(sys.argv[1]) if len(sys.argv) > 1 else {"amount": 1000000, "start": "2016-04-01", "end": "2026-09-30"}))[:2000])
