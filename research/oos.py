"""The out-of-sample numbers: python -m research.oos

For each risk level: run every candidate once (governor on), let the walk-forward selector pick each April from data before it, stitch the picks into ONE account started on
the first April, and put it next to each candidate held alone and next to the reference investments, started the same day with the same capital. Two designs of the
candidate list are run (design 1: every one of the 2,065 parameter sets; design 2, made after design 1's result was seen: plain holding plus one ensemble per family) and two
margins for each: the spec's one standard error and a deflated one, sqrt(2 ln N) standard errors for N effective trials, what the best of N strategies without skill would clear
by luck. The diagnostics (probability of backtest overfitting, deflated Sharpe ratio) go next to the table. Deterministic: same code and data give the same bytes.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from engine.rules import Rules
from research import baseline as B, diagnostics as D, panel as P, s6 as S6, selector as S, sim, strategies as st

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "out"
VARIANTS = ("spec", "deflated")
DESIGNS = ("ensembles", "all trials")
NAMES = {"S0": "S0 plain holding (Nifty ETF and cash)", "E1": "E1 equal weight, four ETFs and cash", "E2": "E2 trend filters (mean of 6)", "E3": "E3 momentum rotation (mean of 18)",
         "E4": "E4 volatility targeting (mean of 10)", "E5": "E5 drawdown-aware exposure (mean of 6)", "S6": "S6 deep model (mean of 12 configurations, 3 seeds each)"}


def margin_for(variant: str, n_eff: float) -> float:
    if variant == "spec":
        return 1.0
    if variant == "deflated":
        return float(np.sqrt(2 * np.log(n_eff))) if n_eff > 1 else 0.0
    raise ValueError(f"the variant is spec or deflated, not {variant!r}")


def excess(equity: np.ndarray, cash: np.ndarray) -> np.ndarray:
    """Daily return of a wealth path above the cash leg's."""
    return equity[1:] / equity[:-1] - cash[1:] / cash[:-1]


def _design(panel: P.Panel, rules: Rules, trials: list, cap: float, capital: float, progress=None) -> dict:
    """Run the candidates, then the diagnostics on their excess returns and the stitched account of each margin."""
    runs, weights_of = S.candidates(panel, rules, trials, cap, progress)
    paths = np.vstack([excess(r.equity, panel.cash) for r in runs]).T
    sharpes = paths.mean(axis=0) / paths.std(axis=0, ddof=1)
    n_eff, var_sr = D.effective_trials(paths), float(np.var(sharpes, ddof=1)) if len(runs) > 1 else 0.0
    best = int(np.argmax(sharpes))
    out = dict(n_trials=len(runs), n_eff=n_eff, pbo=D.pbo(paths, blocks=16)["pbo"], runs=runs, weights_of=weights_of, variants={},
               best_insample=dict(id=runs[best].id, sr=float(sharpes[best]), dsr=D.deflated_sharpe(paths[:, best], n_eff, var_sr)["dsr"]))
    for v in VARIANTS:
        sel = S.walk_forward(runs, weights_of, panel.dates, cap, margin_for(v, n_eff), capital)
        if sel.first_cut is None:
            raise ValueError("the panel has no April cut from 2013 on, so nothing can be selected")
        out["variants"][v] = dict(margin=margin_for(v, n_eff), sel=sel)
    return out


def run_level(panel: P.Panel, rules: Rules, trials: list, ensembles: list, risk: str, cap: float, capital: float = 1_000_000.0, progress=None) -> dict:
    s0 = [t for t in trials if t.family == "S0"]
    designs = {"ensembles": _design(panel, rules, s0 + ensembles, cap, capital), "all trials": _design(panel, rules, trials, cap, capital, progress)}
    first = designs["ensembles"]["variants"]["spec"]["sel"].first_cut
    window = P.from_day(panel, first)
    fixed = B.fixed_total(window, rules)
    refs = S.references(panel, designs["ensembles"]["variants"]["spec"]["sel"], [t for t in s0 if t.cap == cap][0].fn(panel), rules, cap, capital)
    srs = []
    for d in designs.values():
        for v in d["variants"].values():
            v["acct"] = S.stitched_account(panel, v["sel"], rules, cap, capital)
            srs.append(D.sharpe(excess(v["acct"].equity, window.cash)))
    alone = {}
    for t in s0 + ensembles:
        if t.cap in (None, cap):
            alone[t.family] = B.measure(window, sim.simulate(window, t.fn(panel)[first:], rules, sim.SimConfig(cap=cap, band=t.band, capital=capital)), fixed, capital)
    seed = int(window.dates[0].astype("datetime64[D]").astype(int))
    for d in designs.values():
        for v in d["variants"].values():
            v["row"] = B.measure(window, v["acct"], fixed, capital)
            v["dsr"] = D.deflated_sharpe(excess(v["acct"].equity, window.cash), len(srs), float(np.var(srs, ddof=1)))
            v["edge"] = S.paired_se(v["acct"].equity, refs["S0"].equity, seed)
            v["log"] = v["sel"].log
    for d in designs.values():
        d.pop("runs"), d.pop("weights_of")
        for v in d["variants"].values():
            v.pop("sel"), v.pop("acct")
    return dict(risk=risk, cap=cap, designs=designs, alone=alone, refs={k: B.measure(window, r, fixed, capital) for k, r in refs.items() if k != "S0"}, n_variants=len(srs))


def _line(label: str, r: dict) -> str:
    return f"| {label} | {B._pct(r['cagr'])} | {B._pct(r['cagr_liquidated'])} | {B._pct(r['max_dd'])} | {r['sharpe']:.2f} | {r['turnover']:.2f} | Rs {r['tax']:,.0f} |"


def _label(design: str, n: int, v: str, d: dict) -> str:
    what = "the ensembles" if design == "ensembles" else f"all {n} trials"
    return f"Selector over {what}, " + ("1 standard error" if v == "spec" else f"deflated margin ({d['margin']:.1f} standard errors)")


def report(levels: list[dict]) -> str:
    out = ["# Out of sample: the walk-forward selector, each candidate alone, and the other investments", "",
           "Each April the selector picks among its candidates using only data before that day; the picks are stitched into one account started on the first April with Rs 10 lakh. "
           "Every account has the drawdown governor on at the risk level's cap (the reference investments, held without one, are the exception) and pays charges, slippage and tax "
           "by each transaction's own date. All start the same day with the same money. The selection is out of sample; the design (candidate lists, margins, caps) was fixed with "
           "the design period in view. Design 2 (plain holding plus one ensemble per family) was chosen after design 1's result was seen, so its numbers here are in-sample for that "
           "choice: only the last three years, untouched until the freeze, can confirm it.", ""]
    for lv in levels:
        first = lv["alone"]["S0"]
        out += [f"## {lv['risk']}: drawdown cap {lv['cap'] * 100:.0f}%", "",
                f"| Account, fresh from {first['start']} to {first['end']} | After-tax growth a year | After selling all | Worst drawdown | Sharpe | Turnover a year | Tax |", "|---|---|---|---|---|---|---|"]
        for design, d in lv["designs"].items():
            out += [_line(_label(design, d["n_trials"], v, x), x["row"]) for v, x in d["variants"].items()]
        out += [_line(NAMES[k] + " (alone)", r) for k, r in lv["alone"].items()]
        out += [_line(f"{k} held", r) for k, r in lv["refs"].items()]
        out += [""]
        for design, d in lv["designs"].items():
            for v, x in d["variants"].items():
                n, picked = len(x["log"]), x["log"][x["log"].decision == "picked"]
                fams = ", ".join(f"{f}: {k}" for f, k in picked.family.value_counts().sort_index().items()) or "none"
                out += [f"- {_label(design, d['n_trials'], v, x)}: edge over S0 {x['edge'][0] * 100:+.1f} points a year (bootstrap standard error {x['edge'][1] * 100:.1f}); "
                        f"picked a strategy at {len(picked)} of {n} cuts ({fams})."]
        out += [""]
        for design, d in lv["designs"].items():
            out += [f"{design}: {d['n_trials']} candidates, about {d['n_eff']:.0f} independent. Probability of backtest overfitting (in-sample, whole design period): {d['pbo']:.0%}. "
                    f"Best in-sample candidate {d['best_insample']['id']}: deflated Sharpe probability {d['best_insample']['dsr']:.0%} (sizes the selection effect, not a result)."]
        out += ["", "Selector paths, deflated for the four variants tried: " + ", ".join(f"{x['dsr']['dsr']:.0%} ({design}, {v})" for design, d in lv["designs"].items()
                                                                                         for v, x in d["variants"].items()) + ".", ""]
    return "\n".join(out) + "\n"


def main(out: Path = OUT, s1_steps: int = 10) -> list[dict]:
    rules = Rules.load(ROOT / "rules")
    panel = P.load_panel(end=P.DESIGN_END)
    trials, ensembles = st.trials(s1_steps) + S6.trials(), st.ensembles() + [S6.ensemble()]
    out.mkdir(parents=True, exist_ok=True)
    levels = []
    for risk, cap in B.RISKS.items():
        lv = run_level(panel, rules, trials, ensembles, risk, cap, progress=lambda n, total, risk=risk: print(f"\r{risk} {n}/{total}", end="", file=sys.stderr) if n % 200 == 0 or n == total else None)
        for design, d in lv["designs"].items():
            for v, x in d["variants"].items():
                x["log"].to_csv(out / f"selection_{risk}_{design.replace(' ', '-')}_{v}.csv", index=False, float_format="%.10g", lineterminator="\n")
        levels.append(lv)
    (out / "oos.md").write_text(report(levels), encoding="utf-8")
    print(file=sys.stderr)
    return levels


if __name__ == "__main__":
    main()
