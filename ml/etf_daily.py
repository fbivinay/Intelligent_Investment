"""The daily automation: decide after the US close, execute after the next open.

    python ml/etf_daily.py decide              # ~22:30 UTC Mon-Fri
    python ml/etf_daily.py execute             # ~14:45 UTC Mon-Fri, market open in any season
    python ml/etf_daily.py decide --dry-run    # compute and print, write nothing
    python ml/etf_daily.py check               # offline self-check

No database. The job writes two things into the repository, and GitHub Actions
commits them; the website is rebuilt from them:
  web/data/decisions.csv  one row per US session, APPEND-ONLY. Git history
                          timestamps every row, so the live record cannot be
                          edited after the fact without it showing.
  web/data/site.json      everything the website shows, rebuilt each run

decide
  1. fetch real daily prices; refuse stale, missing or absurd data
  2. run the model on the latest finished session and append the decision
  3. rebuild the portfolio from IBIT's launch, following the decisions as
     recorded: in dollars before and after tax, at every Indian slab, and in
     rupees next to FD, Nifty 50, Indian gold and Bitcoin on an Indian exchange
  4. phone alert (ntfy.sh) when the split moved enough to be worth a trade
execute
  5. only when broker keys exist AND the SEND_ORDERS switch is 'on': move the
     account to the last decision (broker.py enforces the safety rules)
"""

import argparse
import csv
import json
import os
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from etf_data import IBIT_START, check, load
from etf_model import signals
from etf_tax_sim import GROSS, EtfCosts, run

SITE = Path(__file__).resolve().parent.parent / "web" / "data"
DECISIONS, ALERTS = SITE / "decisions.csv", SITE / "alerts.csv"
CAPITAL = 10_000.0                                    # the model portfolio's virtual dollars
SLABS = (0.312, 0.26, 0.208, 0.156, 0.104, 0.052)     # Indian slab rates incl. 4% cess
DASHBOARD = "https://btc-paper-trader-fbivinays-projects.vercel.app"
FIELDS = ["date", "recorded_at", "live", "model", "dl_btc", "dl_gold", "btc_votes", "btc_vol",
          "gold_votes", "gold_vol", "w_btc", "w_gold", "w_cash", "btc_close", "gold_close", "tbill", "usdinr"]
MODEL = "dmn-transformer+votes"      # the live model's name in the log


def read_rows(path: Path) -> list:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def append_rows(path: Path, rows: list, fields: list) -> None:
    """Append only. Existing rows are never rewritten."""
    new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerows(rows)


def is_live(session: pd.Timestamp) -> bool:
    """True while the session's decision can still be acted on: before the next open."""
    ny = pd.Timestamp.now(tz="America/New_York").tz_localize(None)
    return ny < (session + pd.offsets.BDay(1)).replace(hour=9, minute=30)


def stats(e: pd.Series, capital: float) -> dict:
    yrs = (e.index[-1] - e.index[0]).days / 365.25
    ye = e.groupby(e.index.year).last()
    prev = pd.concat([pd.Series([capital], index=[ye.index[0] - 1]), ye]).shift(1).dropna()
    return {"end": round(float(e.iloc[-1]), 2), "total": round(float(e.iloc[-1] / capital - 1), 4),
            "per_year": round(float((e.iloc[-1] / capital) ** (1 / yrs) - 1), 4),
            "worst_drop": round(float((e / e.cummax() - 1).min()), 4),
            "years": {str(y): round(float(ye[y] / prev[y] - 1), 4) for y in ye.index}}


def thin(e: pd.Series) -> list:
    """Every 5th day plus the last: plenty for a chart, a fifth of the bytes."""
    idx = list(range(0, len(e), 5)) + ([len(e) - 1] if (len(e) - 1) % 5 else [])
    return [round(float(e.iloc[i]), 1) for i in idx]


def portfolio(btc, gold, tbill, w: pd.DataFrame, costs: EtfCosts = EtfCosts()) -> tuple:
    """(model, buy & hold IBIT) in dollars from IBIT's launch under the given tax and charges."""
    px = {"BTC": btc.loc[IBIT_START:], "GLD": gold.loc[IBIT_START:]}
    model = {"BTC": w["w_btc"], "GLD": w["w_gold"]}
    hold = {"BTC": pd.Series(1.0, w.index)}
    return (run(px, model, tbill, costs=costs, capital=CAPITAL),
            run(px, hold, tbill, costs=costs, capital=CAPITAL))


def alert(history: list, day: pd.Timestamp, s: pd.Series) -> dict | None:
    """Phone alert for people who place the trades by hand, in any broker app.

    Compares the new split with the last one alerted -- what such a person now
    holds -- using the ledger's own band, so it fires exactly when a trade is due.
    Returns the alert row to record, or None.
    """
    new = {k: round(float(s[k]), 4) for k in ("w_btc", "w_gold", "w_cash")}
    old = {k: float(v) for k, v in history[-1].items() if k in new} if history else None
    band = EtfCosts().band
    if old and not any((new[k] == 0) != (old[k] == 0) or abs(new[k] - old[k]) >= band
                       for k in ("w_btc", "w_gold")):
        return None
    was = (lambda k: f"{old[k]:.0%} -> ") if old else (lambda k: "")
    msg = (f"Move to: IBIT {was('w_btc')}{new['w_btc']:.0%}, gold (GLD) {was('w_gold')}{new['w_gold']:.0%}, "
           f"T-bills {was('w_cash')}{new['w_cash']:.0%}. From the {day:%d %b} close; trade at the next US open.")
    return {"date": f"{day:%Y-%m-%d}", **new, "message": msg}


def send_alert(msg: str) -> bool:
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        return False
    req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=msg.encode(), method="POST",
                                 headers={"Title": "ETF model: rebalance", "Click": DASHBOARD,
                                          "Tags": "chart_with_upwards_trend"})
    urllib.request.urlopen(req, timeout=20).close()
    return True


def decide(write: bool) -> str:
    from etf_dl import dl_signal
    from india_compare import compare
    btc, gold, tbill, usdinr = load()
    check(btc, gold)
    sig = signals(btc["close"], gold["close"], dl_signal(btc["close"], gold["close"]))
    day = btc.index[-1]
    now = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ")

    known = {pd.Timestamp(r["date"]): r for r in read_rows(DECISIONS)}
    new = []
    for d in sig.loc[IBIT_START:].index:
        if d in known:
            continue
        s = sig.loc[d]
        new.append({"date": f"{d:%Y-%m-%d}", "recorded_at": now, "live": int(d == day and is_live(d)),
                    "model": MODEL, "dl_btc": round(float(s.dl_btc), 4), "dl_gold": round(float(s.dl_gold), 4),
                    "btc_votes": int(s.btc_votes), "btc_vol": round(float(s.btc_vol), 4),
                    "gold_votes": int(s.gold_votes), "gold_vol": round(float(s.gold_vol), 4),
                    "w_btc": round(float(s.w_btc), 4), "w_gold": round(float(s.w_gold), 4),
                    "w_cash": round(float(s.w_cash), 4),
                    "btc_close": round(float(btc.loc[d, "close"]), 4),
                    "gold_close": round(float(gold.loc[d, "close"]), 4),
                    "tbill": round(float(tbill.asof(d)), 5), "usdinr": round(float(usdinr.asof(d)), 3)})
        known[d] = new[-1]

    # The portfolio follows the decisions as recorded, not as recomputed today.
    rec = pd.DataFrame(known.values()).assign(date=lambda x: pd.to_datetime(x["date"]))
    rec = rec.set_index("date").sort_index()[["w_btc", "w_gold", "w_cash", "live"]].astype(float)

    usd = {}
    for slab in SLABS:
        m, h = portfolio(btc, gold, tbill, rec, EtfCosts(slab=slab))
        usd[str(slab)] = {"model": thin(m.equity), "hold": thin(h.equity),
                          "model_stats": stats(m.equity, CAPITAL), "hold_stats": stats(h.equity, CAPITAL)}
        if slab == SLABS[0]:
            net, trades = m, m.trades
    mg, hg = portfolio(btc, gold, tbill, rec, GROSS)
    dates = net.equity.index

    india = {}
    w_inr = {"BTC": rec["w_btc"], "GLD": rec["w_gold"], "TB": rec["w_cash"]}
    for slab in SLABS:
        t = compare(slab, w_inr)
        india[str(slab)] = {name: {"values": thin(col), **stats(col, 100_000.0)} for name, col in t.items()}

    history = read_rows(ALERTS)
    # Alerts and the summary follow the decision AS RECORDED for that day (it may have been
    # recorded by an earlier run), never a recomputation.
    s = pd.Series({k: float(v) for k, v in known[day].items() if k in ("w_btc", "w_gold", "w_cash",
                                                                        "btc_votes", "gold_votes")})
    fired = alert(history, day, s) if is_live(day) else None

    site = {
        "generated_at": now,
        "last_close": f"{day:%Y-%m-%d}",
        "first_live": next((f"{d:%Y-%m-%d}" for d, r in rec.iterrows() if r["live"]), None),
        "decision": {k: (v if k in ("date", "model") else bool(int(v)) if k == "live"
                         else float(v) if v not in ("", None) else None)
                     for k, v in known[day].items() if k != "recorded_at"},
        "last_alert": fired or (history[-1] if history else None),
        "dates": [f"{dates[i]:%Y-%m-%d}" for i in range(0, len(dates), 5)]
                 + ([f"{dates[-1]:%Y-%m-%d}"] if (len(dates) - 1) % 5 else []),
        "usd": usd,
        "usd_gross": {"model": thin(mg.equity), "hold": thin(hg.equity),
                      "model_stats": stats(mg.equity, CAPITAL), "hold_stats": stats(hg.equity, CAPITAL)},
        "india": india,
        "trades": [{"date": f"{r.date:%Y-%m-%d}", "etf": "IBIT" if r.etf == "BTC" else r.etf,
                    "side": r.side, "units": round(r.units, 3), "price": round(r.price, 2),
                    "value": round(r.units * r.price, 0), "gain": round(r.gain, 0)}
                   for r in trades.iloc[::-1].head(30).itertuples()],
    }
    summary = (f"{day:%Y-%m-%d} close -> IBIT {s.w_btc:.0%} (votes {int(s.btc_votes)}/8), "
               f"gold {s.w_gold:.0%} (votes {int(s.gold_votes)}/8), T-bills {s.w_cash:.0%}; "
               f"{'live' if is_live(day) else 'after the next open, recorded as history'}")
    if not write:
        return summary + f" | {len(new)} decision(s) would be appended"

    append_rows(DECISIONS, new, FIELDS)
    if fired:
        fired["delivered"] = int(send_alert(fired["message"]))
        append_rows(ALERTS, [fired], ["date", "w_btc", "w_gold", "w_cash", "message", "delivered"])
        summary += f" | alert: {fired['message']}"
    (SITE / "site.json").write_text(json.dumps(site, separators=(",", ":")))
    return summary


def execute(write: bool) -> str:
    if os.environ.get("SEND_ORDERS", "off").lower() != "on":
        return "skipped: the SEND_ORDERS switch is off"
    import broker
    b = broker.from_env()
    if b is None:
        return "skipped: no broker keys configured"
    last = read_rows(DECISIONS)[-1]
    age = (pd.Timestamp.now() - pd.Timestamp(last["date"])).days
    if age > 5:
        raise RuntimeError(f"newest decision is {age} days old; refusing to trade on it")
    if not write:
        return f"dry run: would rebalance the {b.mode} account to decision {last['date']}"
    if b.already_sent(f"etf-{last['date']}-"):
        return f"skipped: decision {last['date']} was already executed"
    if not b.clock()["is_open"]:
        return "skipped: market closed today"
    orders = broker.rebalance(b, {"BTC": float(last["w_btc"]), "GLD": float(last["w_gold"]),
                                  "CASH": float(last["w_cash"])}, EtfCosts().band, last["date"],
                              lambda o: None)
    bad = [o for o in orders if o["status"] != "filled"]
    if bad:
        raise RuntimeError(f"{len(bad)} order(s) not filled: " + ", ".join(f"{o['symbol']} {o['status']}" for o in bad))
    return f"{b.mode}: {len(orders)} order(s) for decision {last['date']} filled"


def _self_check() -> None:
    """Alerts fire when a hand-trader must act, and stay quiet otherwise. Offline."""
    history, day = [], pd.Timestamp("2026-09-25")
    split = lambda b, g: pd.Series({"w_btc": b, "w_gold": g, "w_cash": 1 - b - g})

    def step(b, g):
        a = alert(history, day, split(b, g))
        if a:
            history.append(a)
        return a
    assert step(0.77, 0.06), "the first decision must set a starting split"
    assert step(0.70, 0.10) is None, "a move inside the band is not worth a trade"
    assert step(0.50, 0.10), "a move past the band must alert"
    assert step(0.50, 0.0), "leaving an ETF completely must always alert"
    e = pd.Series([100.0, 120.0, 90.0, 130.0], pd.to_datetime(["2024-01-02", "2024-06-01",
                                                               "2025-01-02", "2025-12-31"]))
    st = stats(e, 100.0)
    assert st["worst_drop"] == -0.25 and st["years"] == {"2024": 0.2, "2025": round(130 / 120 - 1, 4)}, st
    print("daily job self-check passed: alerts fire exactly when due, stats are right")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("job", choices=["decide", "execute", "check"])
    ap.add_argument("--dry-run", action="store_true", help="compute and print, write nothing")
    a = ap.parse_args()
    if a.job == "check":
        return _self_check()
    print(f"{a.job}: {(decide if a.job == 'decide' else execute)(not a.dry_run)}")


if __name__ == "__main__":
    sys.exit(main())
