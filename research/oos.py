"""The first honest out-of-sample number: python -m research.oos

For each risk level: run every strategy once (governor on), let the walk-forward selector pick each April from data before it, stitch the picks into ONE account started on the
first April, and put it next to plain holding (S0) and the reference investments started the same day with the same capital. Two margins are run: the spec's one standard
error and a deflated one, sqrt(2 ln N) standard errors for N effective trials, what the best of N strategies without skill would clear by luck. The diagnostics (probability of
backtest overfitting, deflated Sharpe ratio) go next to the table. Deterministic: same code and data give the same bytes.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from engine.rules import Rules
from research import baseline as B, diagnostics as D, panel as P, selector as S, strategies as st

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "out"
VARIANTS = ("spec", "deflated")


def margin_for(variant: str, n_eff: float) -> float:
    if variant == "spec":
        return 1.0
    if variant == "deflated":
        return float(np.sqrt(2 * np.log(n_eff))) if n_eff > 1 else 0.0
    raise ValueError(f"the variant is spec or deflated, not {variant!r}")


def excess(equity: np.ndarray, cash: np.ndarray) -> np.ndarray:
    """Daily return of a wealth path above the cash leg's."""
    return equity[1:] / equity[:-1] - cash[1:] / cash[:-1]


def run_level(panel: P.Panel, rules: Rules, trials: list, risk: str, cap: float, capital: float = 1_000_000.0, progress=None) -> dict:
    runs, weights_of = S.candidates(panel, rules, trials, cap, progress)
    paths = np.vstack([excess(r.equity, panel.cash) for r in runs]).T
    sharpes = paths.mean(axis=0) / paths.std(axis=0, ddof=1)
    n_eff, var_sr = D.effective_trials(paths), float(np.var(sharpes, ddof=1)) if len(runs) > 1 else 0.0
    best = int(np.argmax(sharpes))
    out = dict(risk=risk, cap=cap, n_trials=len(runs), n_eff=n_eff, var_sr=var_sr, pbo=D.pbo(paths, blocks=16)["pbo"],
               best_insample=dict(id=runs[best].id, sr=float(sharpes[best]), dsr=D.deflated_sharpe(paths[:, best], n_eff, var_sr)["dsr"]), variants={})
    s0 = [i for i, r in enumerate(runs) if r.family == "S0"][0]
    stitched = {}
    for v in VARIANTS:
        sel = S.walk_forward(runs, weights_of, panel.dates, cap, margin_for(v, n_eff), capital)
        if sel.first_cut is None:
            raise ValueError("the panel has no April cut from 2013 on, so nothing can be selected")
        acct = S.stitched_account(panel, sel, rules, cap, capital)
        window = P.from_day(panel, sel.first_cut)
        stitched[v] = (sel, acct, window)
    window = stitched[VARIANTS[0]][2]
    fixed = B.fixed_total(window, rules)
    refs = S.references(panel, stitched[VARIANTS[0]][0], weights_of(s0), rules, cap, capital)
    sr_v = [D.sharpe(excess(a.equity, window.cash)) for _, a, _ in stitched.values()]
    for v, (sel, acct, _) in stitched.items():
        d = D.deflated_sharpe(excess(acct.equity, window.cash), len(VARIANTS), float(np.var(sr_v, ddof=1)))
        out["variants"][v] = dict(margin=margin_for(v, n_eff), log=sel.log, row=B.measure(window, acct, fixed, capital), dsr=d,
                                  edge=S.paired_se(acct.equity, refs["S0"].equity, int(window.dates[0].astype("datetime64[D]").astype(int))))
    out["refs"] = {name: B.measure(window, r, fixed, capital) for name, r in refs.items()}
    return out


def _line(label: str, r: dict) -> str:
    return (f"| {label} | {B._pct(r['cagr'])} | {B._pct(r['cagr_liquidated'])} | {B._pct(r['max_dd'])} | {r['sharpe']:.2f} | {r['turnover']:.2f} | Rs {r['tax']:,.0f} |")


def _label(v: str, d: dict) -> str:
    return "Selector, 1 standard error" if v == "spec" else f"Selector, deflated margin ({d['margin']:.1f} standard errors)"


def report(levels: list[dict]) -> str:
    out = ["# Out of sample: the walk-forward selector against plain holding", "",
           "Each April the selector picks among every strategy using only data before that day; the picks are stitched into one account started on the first April with Rs 10 lakh, "
           "the drawdown governor on at the risk level's cap, charges, slippage and tax by each transaction's own date. Plain holding (S0) and the reference investments start the "
           "same day with the same money. Everything in this table is out of sample for the selection; the design (candidate list, margins, caps) was fixed with the design period "
           "in view, and the last three years stay untouched until the freeze.", ""]
    for lv in levels:
        first = lv["refs"]["S0"]
        out += [f"## {lv['risk']}: drawdown cap {lv['cap'] * 100:.0f}%", "", f"| Account, fresh from {first['start']} to {first['end']} | After-tax growth a year | After selling all | Worst drawdown | Sharpe | Turnover a year | Tax |",
                "|---|---|---|---|---|---|---|"]
        out += [_line(_label(v, d), d["row"]) for v, d in lv["variants"].items()]
        out += [_line(name, lv["refs"][key]) for name, key in (("S0 plain holding", "S0"), ("Nifty BeES held", "Nifty BeES"), ("Gold BeES held", "Gold BeES"), ("Liquid fund held", "Liquid fund"))]
        out += [""]
        for v, d in lv["variants"].items():
            n, picked = len(d["log"]), d["log"][d["log"].decision == "picked"]
            fams = ", ".join(f"{f}: {k}" for f, k in picked.family.value_counts().sort_index().items()) or "none"
            out += [f"- {_label(v, d)}: edge over S0 out of sample {d['edge'][0] * 100:+.1f} points a year (bootstrap standard error {d['edge'][1] * 100:.1f}); "
                    f"picked a strategy at {len(picked)} of {n} cuts ({fams})."]
        out += ["", f"{lv['n_trials']} trials, about {lv['n_eff']:.0f} independent. Probability of backtest overfitting of the candidate set (in-sample, whole design period): "
                f"{lv['pbo']:.0%}. Best in-sample candidate {lv['best_insample']['id']}: deflated Sharpe probability {lv['best_insample']['dsr']:.0%} (shown to size the selection effect, "
                f"not a result). Selector out of sample, deflated for the two margins tried: "
                + ", ".join(f"{d['dsr']['dsr']:.0%} ({v})" for v, d in lv["variants"].items()) + ".", ""]
    return "\n".join(out) + "\n"


def main(out: Path = OUT, s1_steps: int = 10) -> list[dict]:
    rules = Rules.load(ROOT / "rules")
    panel = P.load_panel(end=P.DESIGN_END)
    trials = st.trials(s1_steps)
    out.mkdir(parents=True, exist_ok=True)
    levels = []
    for risk, cap in B.RISKS.items():
        lv = run_level(panel, rules, trials, risk, cap, progress=lambda n, total, risk=risk: print(f"\r{risk} {n}/{total}", end="", file=sys.stderr) if n % 200 == 0 or n == total else None)
        for v, d in lv["variants"].items():
            d["log"].to_csv(out / f"selection_{risk}_{v}.csv", index=False, float_format="%.10g", lineterminator="\n")
        levels.append(lv)
    (out / "oos.md").write_text(report(levels), encoding="utf-8")
    print(file=sys.stderr)
    return levels


if __name__ == "__main__":
    main()
