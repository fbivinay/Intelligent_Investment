"""CPU baseline: every committed trial at each risk level, one reference account per run, from the start of the design period to its end.

    python -m research.baseline

Writes research/out/trials.csv (the ledger: one row per run) and research/out/baseline.md (the first table). Nothing here reads past the design end: `load_panel` is
called with it and the runner refuses a panel that goes further. No clock and no randomness, so the same code and data give the same bytes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from engine.rules import Rules
from research import costs as C, panel as P, sim, strategies as st

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "out"
FIRST_PICK = np.datetime64("2013-04-01")           # the walk-forward selector's first pick; the figures "from 2013" start here
RISKS = dict(zip(("Conservative", "Balanced", "Aggressive"), st.RISK_CAPS))
FAMILIES = ("S0", "S1", "S2", "S3", "S4", "S5", "S6")
REFERENCE = {"Nifty BeES": [1, 0, 0, 0, 0], "Junior BeES": [0, 1, 0, 0, 0], "Bank BeES": [0, 0, 1, 0, 0], "Gold BeES": [0, 0, 0, 1, 0], "Liquid fund": [0, 0, 0, 0, 1]}
COLUMNS = ["id", "family", "params", "risk", "cap", "band", "start", "end", "years", "orders", "final", "cagr", "cagr_liquidated", "max_dd", "cagr_2013", "max_dd_2013",
           "sharpe", "turnover", "charges", "slippage", "tax", "liquidation_tax"]


def cagr(final: float, start: float, years: float) -> float:
    """Yearly growth rate; NaN when there is nothing to measure."""
    return float((final / start) ** (1 / years) - 1) if years > 0 and start > 0 and final > 0 else float("nan")


def measure(panel: P.Panel, r: sim.Result, fixed_total: float, capital: float) -> dict:
    """The ledger figures of one run. Growth is after tax: the tax of the year still in progress at the end is taken off, and `cagr_liquidated` also sells everything
    at the last close and pays its charges and tax. Drawdown is before tax, as the cap is. `tax` is the tax on every sale of the run, paid or pending."""
    d = r.dates
    years = float((d[-1] - d[0]).astype(int)) / 365.25
    final = float(r.equity[-1] - r.pending_tax)
    pre = r.equity + np.cumsum(r.tax_paid)
    i0 = int(np.searchsorted(d, FIRST_PICK))
    window = i0 < len(d) - 1
    excess = r.equity[1:] / r.equity[:-1] - panel.cash[1:] / panel.cash[:-1]
    sd = float(excess.std(ddof=1)) if len(excess) > 1 else 0.0
    return dict(
        start=str(d[0]), end=str(d[-1]), years=years, orders=r.orders, final=final, cagr=cagr(final, capital, years),
        cagr_liquidated=cagr(r.liquidation_equity, capital, years), max_dd=float(r.drawdown.max()),
        cagr_2013=cagr(final, float(r.equity[i0]), float((d[-1] - d[i0]).astype(int)) / 365.25) if window else float("nan"),
        max_dd_2013=float((1 - pre[i0:] / np.maximum.accumulate(pre[i0:])).max()) if window else float("nan"),
        sharpe=float(excess.mean() / sd * np.sqrt(252)) if sd > 0 else float("nan"),
        turnover=float(r.traded.sum() / 2 / r.equity.mean() / years), charges=float(r.charges.sum() + fixed_total), slippage=float(r.slippage.sum()),
        tax=float(sum(r.tax_by_fy.values()) + r.pending_tax), liquidation_tax=float(r.liquidation_tax))


def fixed_total(panel: P.Panel, rules: Rules) -> float:
    """The fixed fees (account opening, yearly demat fee) a run over the panel's days pays."""
    return float(C.fixed_costs(rules, [pd.Timestamp(x).date() for x in panel.dates]).sum())


def ledger(panel: P.Panel, rules: Rules, trials: list, progress=None) -> pd.DataFrame:
    """Run every trial at every risk level (S0 only at its own) and the reference holdings, and return one row per run."""
    if panel.dates[-1] > np.datetime64(P.DESIGN_END):
        raise ValueError(f"the panel ends {panel.dates[-1]}, after the design end {P.DESIGN_END}: the frozen test years are never loaded by the baseline")
    fixed = fixed_total(panel, rules)
    rows, total = [], sum(len([c for c in RISKS.values() if t.cap in (None, c)]) for t in trials) + len(REFERENCE)

    def run(cfg, w, **row):
        rows.append({**row, **measure(panel, sim.simulate(panel, w, rules, cfg), fixed, cfg.capital)})
        if progress:
            progress(len(rows), total)

    for t in trials:
        w = t.fn(panel)
        for risk, cap in RISKS.items():
            if t.cap in (None, cap):
                run(sim.SimConfig(cap=cap, band=t.band), w, id=t.id, family=t.family, params=json.dumps(t.params, sort_keys=True, separators=(",", ":")), risk=risk, cap=cap,
                    band=t.band)
    for name, mix in REFERENCE.items():
        run(sim.SimConfig(governor=False), st.s1_static(mix, "never")(panel), id=f"REF|hold={name}", family="REF", params=json.dumps({"hold": name}), risk="none",
            cap=float("nan"), band=0.01)
    return pd.DataFrame(rows, columns=COLUMNS)


def write_ledger(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False, float_format="%.10g", lineterminator="\n")


def _pct(x) -> str:
    return "n/a" if x != x else f"{x * 100:.1f}%"


def _row(label: str, r, s0=None) -> str:
    vs = "" if s0 is None else ("n/a" if r.cagr != r.cagr else f"{(r.cagr - s0.cagr) * 100:+.1f}")
    return (f"| {label} | {_pct(r.cagr)} | {_pct(r.cagr_liquidated)} | {_pct(r.max_dd)} | {_pct(r.cagr_2013)} | {_pct(r.max_dd_2013)} | {r.turnover:.2f} | "
            f"Rs {r.tax:,.0f} | {vs} |")


def report(df: pd.DataFrame) -> str:
    head = "| Strategy | After-tax growth a year | After selling all | Worst drawdown | From 2013-04: growth | From 2013-04: drawdown | Turnover a year | Tax | vs S0 (points) |"
    rule = "|---|---|---|---|---|---|---|---|---|"
    n_trials = int((df.family != "REF").sum())
    out = ["# Baseline: plain holding against the first strategy families", "",
           f"Design period {df.start.iloc[0]} to {df.end.iloc[0]}; one reference account per run (Rs 10 lakh, new tax regime, other income Rs 12 lakh); charges, slippage and "
           "tax by each transaction's own date; the drawdown governor on at the risk level's cap. Every number is a row of `research/out/trials.csv`.", "",
           f"**All of this is in-sample.** The ledger holds {n_trials} runs; the best of many beating plain holding is what chance alone produces. The walk-forward selector "
           "and the deflated Sharpe ratio decide, not this table. Worst drawdown is before tax, like the cap. Dividends the ETFs paid are not added back.", ""]
    ref = df[df.family == "REF"]
    if len(ref):
        out += ["## Other investments (bought on day one and held, no governor)", "", head.replace(" | vs S0 (points) |", " | |"), rule]
        out += [_row(r.id.split("=", 1)[1], r) for r in ref.itertuples()]
        out += [""]
    for risk, cap in RISKS.items():
        d = df[df.risk == risk]
        if d.empty:
            continue
        s0 = d[d.family == "S0"].iloc[0] if (d.family == "S0").any() else None
        out += [f"## {risk}: drawdown cap {cap * 100:.0f}%", "", head, rule]
        if s0 is not None:
            out += [_row(f"{s0.id} (plain holding)", s0, s0)]
        for fam in FAMILIES[1:]:
            f = d[d.family == fam]
            ok = f[f.max_dd <= cap]
            if len(ok):
                b = ok.loc[ok.cagr.idxmax()]
                out += [_row(f"{b.id} (best of {len(ok)} within the cap, of {len(f)})", b, s0)]
            elif len(f):
                out += [f"| {fam}: none within the cap (of {len(f)}) | | | | | | | | |"]
        if s0 is not None:
            others = d[d.family != "S0"]
            beat = others[others.cagr > s0.cagr]
            out += ["", f"{len(beat)} of {len(others)} other trials beat S0 after tax, {int((beat.max_dd <= cap).sum())} of them within the cap.", ""]
    return "\n".join(out) + "\n"


def main(out: Path = OUT, s1_steps: int = 10) -> pd.DataFrame:
    rules = Rules.load(ROOT / "rules")
    panel = P.load_panel(end=P.DESIGN_END)
    from research import s6
    df = ledger(panel, rules, st.trials(s1_steps) + s6.trials(), progress=lambda n, total: print(f"\r{n}/{total}", end="", file=sys.stderr) if n % 100 == 0 or n == total else None)
    out.mkdir(parents=True, exist_ok=True)
    write_ledger(df, out / "trials.csv")
    (out / "baseline.md").write_text(report(df), encoding="utf-8")
    print(file=sys.stderr)
    return df


if __name__ == "__main__":
    main()
