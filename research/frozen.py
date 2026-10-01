"""The frozen test (spec section 6): run once, after the design is frozen under a git tag, on the three years nothing was designed on.

    python -m research.frozen

What runs is fixed in docs/superpowers/specs/2026-10-01-frozen-test-preregistration.md: for each risk level the walk-forward selector over plain holding (S0), the five
ensembles and the deep model, with the deflated margin measured on the design period (MARGINS), every account with W1 harvesting, re-picking each April from past data only.
The product's account, plain holding's, each candidate's and the reference investments' all start fresh on the first trading day of the frozen period with Rs 10 lakh.
The run refuses to start unless the code, rules and data are exactly those of the tag, and it writes its own record (commit, data hashes, run date).
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from engine.rules import Rules
from research import baseline as B, panel as P, replay as RP, selector as S, sim, strategies as st
from research.kaggle.snapshot import sha256

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "out" / "frozen"
TAG = "frozen-design-v1"
FROZEN_START, FROZEN_END = "2023-10-01", "2026-09-30"
EXECUTION = {"harvest": True}
# The deflated margins, sqrt(2 ln N_eff) standard errors for the effective number of candidates measured on the design period (research/out/oos_margins.json, design
# "ensembles"); fixed here before the tag, as the pre-registration says.
MARGINS: dict[str, float] = {"Conservative": 1.3852, "Balanced": 1.3319, "Aggressive": 1.3082}
PANEL_FILES = ("etf_daily_adjusted.csv", "amfi_nav_adjusted.csv", "nse_index_daily.csv")
NAMES = {"S0": "S0 plain holding", "E1": "E1 equal weight", "E2": "E2 trend filters", "E3": "E3 momentum rotation", "E4": "E4 volatility targeting",
         "E5": "E5 drawdown-aware exposure", "S6": "S6 deep model"}


def start_index(dates: np.ndarray, start: str) -> int:
    return int(np.searchsorted(dates, np.datetime64(start)))


def verdict(rows: dict, cap: float) -> dict:
    """Primary comparison: the selector against plain holding after selling everything at the end, and the selector's worst drawdown against the cap."""
    a, b = rows["Selector"], rows["S0"]
    edge = float(a["cagr_liquidated"] - b["cagr_liquidated"])
    return dict(beats_s0=edge > 0, within_cap=bool(a["max_dd"] <= cap), edge=edge, same_as_s0=bool(edge == 0 and a["max_dd"] == b["max_dd"]))


def run_level(panel: P.Panel, rules: Rules, s0_trials: list, candidates: list, risk: str, cap: float, margin: float, start: str = FROZEN_START,
              capital: float = 1_000_000.0, sim_kw: dict | None = None) -> dict:
    s0 = [t for t in s0_trials if t.cap == cap]
    runs, weights_of = S.candidates(panel, rules, s0 + candidates, cap, sim_kw=sim_kw)
    sel = S.walk_forward(runs, weights_of, panel.dates, cap, margin, capital)
    sel_1se = S.walk_forward(runs, weights_of, panel.dates, cap, 1.0, capital)
    i0 = start_index(panel.dates, start)
    window = P.from_day(panel, i0)
    fixed = B.fixed_total(window, rules)
    acct = S.stitched_account(panel, sel, rules, cap, capital, sim_kw, start=i0)
    rows = {"Selector": B.measure(window, acct, fixed, capital),
            "Selector, 1 standard error": B.measure(window, S.stitched_account(panel, sel_1se, rules, cap, capital, sim_kw, start=i0), fixed, capital)}
    for k, run in enumerate(runs):
        r = sim.simulate(window, weights_of(k)[i0:], rules, sim.SimConfig(cap=cap, capital=capital, band=(s0 + candidates)[k].band, **(sim_kw or {})))
        rows[run.family] = B.measure(window, r, fixed, capital)
    refs = S.references(panel, sel, weights_of(0), rules, cap, capital, sim_kw, start=i0)
    rows.update({f"{k} held": B.measure(window, r, fixed, capital) for k, r in refs.items() if k != "S0"})
    return dict(risk=risk, cap=cap, margin=margin, rows=rows, verdict=verdict(rows, cap), log=sel.log, log_1se=sel_1se.log, weights=sel.weights,
                holder=[runs[i].id for i in sel.holder], first_cut=sel.first_cut, replay=RP.check(acct, rules, [pd.Timestamp(d).date() for d in window.dates]))


def code_state(tag: str = TAG, runner=subprocess.run) -> str:
    """The tag's commit, after checking that no code, rule or data file differs from it (outputs under research/out may)."""
    def git(*args):
        r = runner(["git", *args], capture_output=True, text=True, cwd=ROOT)
        if r.returncode != 0:
            raise RuntimeError(f"no tag {tag}: freeze the design first ({r.stderr.strip()})")
        return r.stdout
    commit = git("rev-parse", f"{tag}^{{commit}}").strip()
    keep = lambda lines: [ln for ln in lines if ln.strip() and "research/out/" not in ln]
    changed = keep(git("diff", "--name-only", tag, "--", "research", "engine", "rules", "data").splitlines())
    if changed:
        raise RuntimeError(f"code, rules or data changed since {tag}: {changed}")
    dirty = keep(git("status", "--porcelain", "--", "research", "engine", "rules", "data").splitlines())
    if dirty:
        raise RuntimeError(f"uncommitted changes in code, rules or data: {dirty}")
    return commit


def data_hashes(root: Path = P.DATA) -> dict:
    return {name: sha256(Path(root) / "processed" / name) for name in PANEL_FILES}


def write_artifact(out: Path, risk: str, dates: np.ndarray, weights: np.ndarray, holder: list[str], first: int) -> None:
    """The signal artifact of a risk level: the target weights decided after each day's close from the first April cut on, and the strategy they came from."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(weights[first:], columns=["NIFTYBEES", "JUNIORBEES", "BANKBEES", "GOLDBEES", "cash"])
    df.insert(0, "date", [str(d) for d in dates[first:]])
    df["strategy"] = holder[first:]
    df.to_csv(out / f"signal_{risk}.csv", index=False, float_format="%.10g", lineterminator="\n")
    m = json.loads((out / "manifest.json").read_text(encoding="utf-8")) if (out / "manifest.json").exists() else {"files": {}}
    m["files"][f"signal_{risk}.csv"] = sha256(out / f"signal_{risk}.csv")
    (out / "manifest.json").write_bytes((json.dumps(m, indent=1, sort_keys=True) + "\n").encode("utf-8"))


def _line(label: str, r: dict) -> str:
    return f"| {label} | {B._pct(r['cagr'])} | {B._pct(r['cagr_liquidated'])} | {B._pct(r['max_dd'])} | {r['sharpe']:.2f} | {r['turnover']:.2f} | Rs {r['tax']:,.0f} |"


def report(levels: list[dict], record: dict) -> str:
    out = ["# Frozen test: the three years nothing was designed on", "",
           f"Run once on code {record['commit']} (tag {record['tag']}), {record['start']} to {record['end']}. Every account starts fresh on the first trading day with Rs 10 lakh; "
           "the strategies and plain holding run with the drawdown governor at the risk level's cap and with W1 harvesting; the reference investments are bought and held plainly. "
           "Charges, slippage and tax by each transaction's own date; growth is after tax, and 'after selling all' also sells everything on the last day and pays that tax.", "",
           "Three years is one market path: a result here, either way, is weak evidence on its own. It is the honest check the design was frozen for, not proof.", ""]
    for lv in levels:
        v = lv["verdict"]
        out += [f"## {lv['risk']}: drawdown cap {lv['cap'] * 100:.0f}%", "",
                "| Account | After-tax growth a year | After selling all | Worst drawdown | Sharpe | Turnover a year | Tax |", "|---|---|---|---|---|---|---|"]
        for k, r in lv["rows"].items():
            label = (f"Selector (deflated margin {lv['margin']:.2f} standard errors)" if k == "Selector" else NAMES.get(k, k))
            out.append(_line(label, r))
        log = lv["log"]
        in_force = log[(log.cut >= record["start"]) | (log.cut == log.cut[log.cut < record["start"]].max())]       # the pick held on the first day, then each April's
        picks = "; ".join(f"{c}: {p}" for c, p in zip(in_force.cut, in_force.picked))
        out += ["", ("The product **beats plain holding**" if v["beats_s0"] else ("The product **is plain holding** in these years" if v["same_as_s0"] else
                     "The product **does not beat plain holding**")) + f" after selling all ({v['edge'] * 100:+.2f} points a year), and its worst drawdown is "
                + ("within" if v["within_cap"] else "**above**") + " the cap.", f"Held in these years (pick of each April): {picks}.",
                f"Replay of the product's {lv['replay']['orders']} orders through the exact engine: charges differ by Rs {lv['replay']['total_gap']:,.2f} in total "
                f"({lv['replay']['wealth_gap_share'] * 100:.4f}% of the final wealth; largest single order Rs {lv['replay']['max_order_gap']:.2f}).", ""]
    return "\n".join(out) + "\n"


def main(out: Path = OUT, tag: str = TAG) -> list[dict]:
    if not MARGINS:
        raise RuntimeError("the margins are not set: pre-register them first")
    commit = code_state(tag)
    rules = Rules.load(ROOT / "rules")
    panel = P.load_panel(end=FROZEN_END)
    from research import s6
    candidates = st.ensembles() + [s6.ensemble_combined()]
    s0 = [t for t in st.trials(2) if t.family == "S0"]
    out.mkdir(parents=True, exist_ok=True)
    levels = []
    for risk, cap in B.RISKS.items():
        print(risk, file=sys.stderr)
        lv = run_level(panel, rules, s0, candidates, risk, cap, MARGINS[risk], FROZEN_START, sim_kw=EXECUTION)
        lv["log"].to_csv(out / f"selection_{risk}.csv", index=False, float_format="%.10g", lineterminator="\n")
        lv["log_1se"].to_csv(out / f"selection_{risk}_1se.csv", index=False, float_format="%.10g", lineterminator="\n")
        write_artifact(out, risk, panel.dates, lv["weights"], lv["holder"], lv["first_cut"])
        levels.append(lv)
    record = {"tag": tag, "commit": commit, "start": str(panel.dates[start_index(panel.dates, FROZEN_START)]), "end": str(panel.dates[-1]), "run_on": date.today().isoformat(),
              "data": data_hashes(), "margins": MARGINS, "execution": EXECUTION,
              "s6": {d: sha256(Path(s6.OUT).parent / d / "outputs.json") for d in ("s6", "s6_frozen")}}
    (out / "report.md").write_text(report(levels, record), encoding="utf-8")
    summary = {lv["risk"]: {"verdict": lv["verdict"], "rows": lv["rows"], "replay": lv["replay"]} for lv in levels}
    (out / "record.json").write_bytes((json.dumps({**record, "results": summary}, indent=1, sort_keys=True, default=float) + "\n").encode("utf-8"))
    return levels


if __name__ == "__main__":
    main()
