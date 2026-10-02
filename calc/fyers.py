"""How it would run on Fyers: PREVIEW ONLY. For a past day, the model's orders as the JSON a Fyers API v3 place-order call takes, with the engine's fee estimate.

No credentials, no network call to Fyers, past days only: a public page of live buy and sell signals may count as investment advice under SEBI rules.

Order fields as Fyers documents them for API v3 (checked 2026-10-01 against the fyers-apiv3 package documentation, https://pypi.org/project/fyers-apiv3/, and Fyers'
SDK documentation): symbol "NSE:<SYMBOL>-EQ"; type 1 limit, 2 market, 3 stop (SL-M), 4 stop-limit; side 1 buy, -1 sell; productType "CNC" for delivery; validity
"DAY"; offlineOrder true for an order placed after the close for the next session (after-market order). The model decides after a day's close, so its orders are
after-market market orders for the next session; the research fills them at that session's average price plus a slippage assumption, an order at the open would
fill at the open. The liquid fund is bought from and sold to the fund house, not on the exchange, so it has no API order.
"""
from __future__ import annotations

from datetime import date

import numpy as np

from calc.product import ProductRun

MARKET, CNC = 2, "CNC"
SIDE = {"buy": 1, "sell": -1}
LABEL = "Preview only: no account, no keys, nothing is sent to Fyers. A past day, replayed."


def payload(trade: dict) -> dict | None:
    if trade["asset"] == "LIQUID_FUND":
        return None
    return {"symbol": f"NSE:{trade['asset']}-EQ", "qty": int(trade["units"]), "type": MARKET, "side": SIDE[trade["side"]], "productType": CNC, "limitPrice": 0,
            "stopPrice": 0, "validity": "DAY", "disclosedQty": 0, "offlineOrder": True, "orderTag": "preview" + trade["date"].replace("-", "")}


def order_days(run: ProductRun) -> list[str]:
    return sorted({t["date"] for t in run.booked.trades})


def preview(run: ProductRun, on: date) -> dict:
    """The fill day `on`: what the model decided at the previous close, what the account held then, and the orders filled on `on`."""
    day = on.isoformat()
    if day not in run.dates:
        raise ValueError(f"{day} is not a trading day of this account")
    i = run.dates.index(day)
    if i == 0:
        raise ValueError("the first day has no decision before it")
    target = run.weights[i - 1]
    trades = [t for t in run.booked.trades if t["date"] == day]
    orders = []
    for t in trades:
        p = payload(t)
        how = "Fyers API v3 place order (after-market, for the next session)" if p else "Not an exchange order: buy or redeem directly with the fund house"
        orders.append({"trade": t, "payload": p, "how": how, "fees": t["charges"], "depository": t["dp"]})
    before = run.units[i - 1]
    value = before * run.prices[i - 1]
    return {"label": LABEL, "decided_on": run.dates[i - 1], "fill_day": day, "targets": {a: float(w) for a, w in zip(run.names, target)},
            "holdings_before": {a: float(u) for a, u in zip(run.names, before)}, "values_before": {a: float(v) for a, v in zip(run.names, value)}, "orders": orders,
            "total_fees": float(sum(float(o["fees"]) for o in orders)), "total_depository": float(sum(float(o["depository"]) for o in orders)),
            "timeline": [f"After the close of {run.dates[i - 1]}: the day's prices are in; the weights for the next session are worked out",
                         "The same evening: the ETF orders are placed as after-market orders; the fund leg goes to the fund house",
                         f"{day}: the orders fill during the session (the research assumes the day's average price plus slippage)",
                         "After that close: the next decision"]}
