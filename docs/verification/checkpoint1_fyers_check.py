"""Line-by-line check of the engine's order charges against Fyers' own brokerage calculator.

Fyers' calculator page (fyers.in/calculator/brokerage) works out charges in the browser from a table of rates
(assets.fyers.in/Lib/calculators/3.0/brokrage-calc.js). Those rates, read on 2026-09-30, are in
fyers_calculator_params_2026-09-30.json. The formula below is the page's own, transcribed from its script:
brokerage on each leg is the lower of the cap and (rate x turnover); every other line is rate x turnover; GST is
applied to brokerage, transaction charges, SEBI fee and IPFT. Nothing is rounded on the page except when it shows two
decimals, so the engine's rounded lines (STT to the rupee, the rest to the paisa) are expected to differ by rounding.

Run from the repo root:  python docs/verification/checkpoint1_fyers_check.py
"""
import json
import sys
from datetime import date
from decimal import Decimal as D
from pathlib import Path

sys.path.insert(0, ".")
from engine.charges import Order, order_charges  # noqa: E402
from engine.rules import Rules  # noqa: E402

PARAMS = json.loads((Path(__file__).parent / "fyers_calculator_params_2026-09-30.json").read_text())


def page(p, buy_price, sell_price, qty, cap=None):
    """The calculator page's formula. Returns its lines for a buy and a sell of `qty` units."""
    p = {k: D(str(v)) for k, v in p.items() if isinstance(v, (int, float))}
    u = D(cap) if cap is not None else p["brokerage_upper_cap"]
    f, m = D(buy_price) * qty, D(sell_price) * qty
    brokerage = min(u, f * p["brokerage_percentage"]) + min(u, m * p["brokerage_percentage"])
    transaction = f * (p["exch_transaction_charge_buy"] + p["cm_transaction_buy"]) + m * (p["exch_transaction_charge_sell"] + p["cm_transaction_sell"])
    sebi = (f + m) * p["sebi_fees"]
    ipft = (f + m) * p["nse_ipft"]
    stt = f * p["stt_on_buy_side"] + m * p["stt_on_sell_side"]
    stamp = f * p["stamp_duty_buy"] + m * p["stamp_duty_sell"]
    gst = p["gst"] * (brokerage + transaction + sebi + ipft)
    total = brokerage + transaction + gst + sebi + stt + stamp + ipft
    return dict(brokerage=brokerage, transaction=transaction, stt=stt, gst=gst, sebi=sebi, stamp=stamp, ipft=ipft, total=total)


def engine(rules, on, cls, buy_price, sell_price, qty):
    lines = {"brokerage": D(0), "transaction": D(0), "stt": D(0), "gst": D(0), "sebi": D(0), "stamp": D(0), "ipft": D(0)}
    for side, price in (("buy", buy_price), ("sell", sell_price)):
        c = order_charges(rules, Order(on, cls, side, D(qty), D(price)))
        for name, node in c.lines.items():
            lines["transaction" if name in ("exchange_txn", "clearing") else name] += node.value
    lines["total"] = sum(lines.values(), D(0))
    return lines


def table(title, page_lines, engine_lines, note):
    print(f"### {title}\n")
    print("| line | Fyers calculator | engine | difference |\n|---|---:|---:|---:|")
    for k in ("brokerage", "transaction", "stt", "gst", "sebi", "stamp", "ipft", "total"):
        a, b = page_lines[k], engine_lines[k]
        print(f"| {k} | {a:,.4f} | {b:,.2f} | {b - a:+,.4f} |")
    print(f"\n{note}\n")


if __name__ == "__main__":
    rules = Rules.load(Path("rules"))
    on = date(2026, 9, 28)
    q, px = 1567, "260.47"
    table("Nifty ETF, delivery, 1567 units bought and sold at 260.47 (the report's sale price), 2026-09-28",
          page(PARAMS["equity_delivery_nse"], px, px, q), engine(rules, on, "etf_equity", px, px, q),
          "STT differs on purpose: the calculator's equity delivery line is the share rate, 0.1% on both sides, while an "
          "equity-oriented ETF unit pays 0.001% on the sale only (NSE STT table, S23). Every other line agrees to rounding.")
    q, px = 75, "25000"
    table("Index futures, 75 units bought and sold at 25,000, 2026-09-28",
          page(PARAMS["futures_nse"], px, px, q), engine(rules, on, "fut_index", px, px, q),
          "STT for futures agrees (0.05% on the sale, in force from 2026-04-01, NSE circular S23). The other lines agree to rounding.")
