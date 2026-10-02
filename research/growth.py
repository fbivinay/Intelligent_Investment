"""The wider universe, six ETFs:

    python -m research.growth level <name>      each of Conservative, Balanced, Aggressive, "Capped 40%", "No guard" (they can run side by side)
    python -m research.growth                   the report (research/out/growth/report.md) and the margins
    python -m research.growth signal            the product's signal (research/out/signal_growth)

The same walk-forward machinery as research/oos.py (every candidate run once, the selector picking each April from data before it, the picks stitched into one
account from the first April), on six ETFs instead of four: the Midcap 100 ETF (MOM100) and the Nasdaq 100 ETF (MON100) added. Two more study levels: a 40%
drawdown cap, and no guard at all (no cap, governor off). Next to them, fixed mixes held with no guard and rebalanced each April. The panel runs to the end of
the data (2026-09-30): no year is left unseen, so nothing here is a frozen test. The selection is out of sample; the choice of the two ETFs is not: they were added
after their history was known to be good, and that is said next to every number. S6, the deep model, was trained on the four-ETF panel and is not a candidate here.

The product's Growth level is the equal mix of the six ETFs, no cash, back to equal each April, no guard: the one rule here with nothing fitted (1/N).
"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

from engine.rules import Rules
from research import artifact as A, baseline as B, oos, panel as P, sim, strategies as st

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "out" / "growth"
SIGNAL = A.SIGNAL_SIX
END = "2026-09-30"
S1_STEPS = 5                     # mixes of six ETFs and cash in steps of 20%: 462 mixes, each held yearly or never rebalanced
STUDY = {**B.RISKS, "Capped 40%": 0.40, "No guard": 1.0}
NO_GUARD = {**oos.EXECUTION, "governor": False}
NAMES = {**oos.NAMES, "E1": "E1 equal weight, six ETFs and cash"}
MIXES = {"Equal six ETFs, no cash (the product's Growth level)": A.GROWTH_MIX, "Equal six ETFs and cash (E1)": [1 / 7] * 7,
         "Junior 25 / Midcap 25 / Nasdaq 25 / Gold 25": [0, .25, 0, .25, .25, .25, 0], "Midcap 40 / Nasdaq 40 / Gold 20 (picked with hindsight)": [0, 0, 0, .2, .4, .4, 0],
         "Nasdaq 50 / Midcap 25 / Gold 25 (picked with hindsight)": [0, 0, 0, .25, .25, .5, 0]}
HEAD = ("# The wider universe: six ETFs, walk-forward\n\nThe Midcap 100 ETF and the Nasdaq 100 ETF join the four ETFs (their NAV, scaled to the exchange price, stands in "
        "before 2016). Read every number with this in mind: **these two were added after their 2013-2026 history was known to be strong**. The yearly picks use only "
        "data before each April, but the menu they pick from was chosen with hindsight, and no unseen years are left to test it. The Nasdaq ETF is taxed as a "
        "non-equity ETF (as gold ETFs are) and has traded above its NAV since 2022 (13% at the end): a buyer pays that premium.\n\n"
        "What it shows: with a drawdown guard the walk-forward selector stays near 7-11% a year after tax whatever the cap, because the guard sells after falls and "
        "the selector keeps plain holding unless a candidate's edge is large. Without a guard, the plain equal mix of the six ETFs made about 15% a year after selling "
        "all, with a worst fall near 28%; 18-19% needed a mix picked knowing which ETFs did best.\n")


def _trials(n: int, caps=STUDY.values()) -> tuple[list, list]:
    """The four-ETF lists on six ETFs, with plain holding (S0) at every study cap."""
    trials = st.trials(S1_STEPS, n)
    trials += [st.Trial(f"S0|cap={cap:g}|band=0.01", "S0", {"cap": cap}, st.s0_plain(cap), 0.01, cap) for cap in caps if cap not in st.RISK_CAPS]
    return trials, st.ensembles(n, S1_STEPS)


def _kw(risk: str) -> dict:
    return NO_GUARD if risk == "No guard" else oos.EXECUTION


def level(risk: str, out: Path = OUT) -> dict:
    """One level's study, kept as a pickle so the levels can run side by side."""
    rules = Rules.load(ROOT / "rules")
    panel = P.load_panel(end=END, assets=P.GROWTH)
    trials, ensembles = _trials(len(panel.assets), [STUDY[risk]])
    out.mkdir(parents=True, exist_ok=True)
    oos.NAMES.update(NAMES)
    lv = oos.run_level(panel, rules, trials, ensembles, risk, STUDY[risk], progress=lambda k, total: print(f"\r{risk} {k}/{total}", end="", file=sys.stderr)
                       if k % 100 == 0 or k == total else None, sim_kw=_kw(risk))
    for design, d in lv["designs"].items():
        for v, x in d["variants"].items():
            x["log"].to_csv(out / f"selection_{risk.replace(' ', '-').replace('%', '')}_{design.replace(' ', '-')}_{v}.csv", index=False, float_format="%.10g",
                            lineterminator="\n")
    (out / f"level_{risk}.pkl").write_bytes(pickle.dumps(lv))
    return lv


def mixes() -> list[str]:
    """Rows of the fixed-mix table: each mix bought on 2013-04-01, back to its weights each April, no guard."""
    rules = Rules.load(ROOT / "rules")
    panel = P.load_panel(end=END, assets=P.GROWTH)
    win = P.from_day(panel, int(__import__("numpy").searchsorted(panel.dates, __import__("numpy").datetime64("2013-04-01"))))
    fixed = B.fixed_total(win, rules)
    return [oos._line(name, B.measure(win, sim.simulate(win, st.s1_static(w, "year")(win), rules, sim.SimConfig(cap=1.0, **NO_GUARD)), fixed, 1e6))
            for name, w in MIXES.items()]


def main(out: Path = OUT) -> list[dict]:
    """The report and margins from the levels' pickles (python -m research.growth level <name>, for each level, first)."""
    # pickles this module wrote itself in research/out/growth, never files from elsewhere
    levels = [pickle.loads((out / f"level_{risk}.pkl").read_bytes()) for risk in STUDY]
    oos.NAMES.update(NAMES)
    body = oos.report(levels).split("\n", 2)[2].replace("## No guard: drawdown cap 100%", "## No guard: no cap, governor off")
    table = ["## Fixed mixes, no guard", "", "Bought on 2013-04-01 with Rs 10 lakh, back to the mix's weights each April, harvesting as above, no governor; to 2026-09-30.", "",
             "| Mix | After-tax growth a year | After selling all | Worst drawdown | Sharpe | Turnover a year | Tax |", "|---|---|---|---|---|---|---|", *mixes(), ""]
    (out / "report.md").write_text(HEAD + "\n" + "\n".join(table) + "\n" + body, encoding="utf-8")
    margins = {lv["risk"]: {d: {"n_trials": x["n_trials"], "n_eff": x["n_eff"], "deflated_margin": x["variants"]["deflated"]["margin"]} for d, x in lv["designs"].items()}
               for lv in levels}
    (out / "margins.json").write_bytes((json.dumps(margins, indent=1, sort_keys=True) + "\n").encode("utf-8"))
    return levels


def signal(out: Path = SIGNAL, margins: Path = OUT / "margins.json") -> dict:
    """The product's signal on six ETFs. Conservative, Balanced and Aggressive: the rule the four-ETF product was frozen with (decided before the study's numbers
    were seen), the selector over plain holding and the ensembles at that design's deflated margin, the stitched weights from the first April scaled by the
    governor of a reference account (Rs 10 lakh, the level's cap, W1 harvesting), as research/artifact.py does for the four ETFs. Growth: the equal mix of the six
    ETFs, no cash, back to equal each April, no governor."""
    from research import selector as S
    from research.kaggle.snapshot import sha256
    import pandas as pd
    rules = Rules.load(ROOT / "rules")
    panel = P.load_panel(end=END, assets=P.GROWTH)
    trials, ensembles = _trials(len(panel.assets))
    cands = [t for t in trials if t.family == "S0"] + ensembles
    m = json.loads(Path(margins).read_text(encoding="utf-8"))
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    files = {}
    i0 = S.cut_days(panel.dates)[0]
    for lvl in A.LEVELS_SIX:
        if lvl == "Growth":
            target = st.s1_static(A.GROWTH_MIX, "year")(P.from_day(panel, i0))
            ref = sim.simulate(P.from_day(panel, i0), target, rules, sim.SimConfig(cap=1.0, **NO_GUARD))
            strategy = ["S1|equal six ETFs, no cash,rebalance=year|no guard"] * len(target)
        else:
            cap = B.RISKS[lvl]
            runs, weights_of = S.candidates(panel, rules, cands, cap, sim_kw=oos.EXECUTION)
            sel = S.walk_forward(runs, weights_of, panel.dates, cap, m[lvl]["ensembles"]["deflated_margin"])
            if sel.first_cut != i0:
                raise ValueError("the selection starts on another day than the first April")
            target = sel.weights[i0:]
            ref = sim.simulate(P.from_day(panel, i0), target, rules, sim.SimConfig(cap=cap, **oos.EXECUTION))
            strategy = [runs[i].id for i in sel.holder[i0:]]
            sel.log.to_csv(out / f"selection_{lvl}.csv", index=False, float_format="%.10g", lineterminator="\n")
        df = pd.DataFrame(A.effective(target, ref.multiplier), columns=list(panel.assets) + ["cash"])
        df.insert(0, "date", [str(d) for d in panel.dates[i0:]])
        df["multiplier"] = ref.multiplier
        df["strategy"] = strategy
        df.to_csv(out / f"{lvl}.csv", index=False, float_format="%.10g", lineterminator="\n")
        files[f"{lvl}.csv"] = sha256(out / f"{lvl}.csv")
        print(lvl, "reference account:", round(float(ref.liquidation_equity)), file=sys.stderr)
    manifest = {"files": files, "execution": oos.EXECUTION, "assets": list(panel.assets) + ["cash"],
                "rule": "Conservative, Balanced, Aggressive: ensembles design, deflated margin, governor; Growth: equal six ETFs, yearly, no governor"}
    (out / "manifest.json").write_bytes((json.dumps(manifest, indent=1, sort_keys=True) + "\n").encode("utf-8"))
    return manifest


if __name__ == "__main__":
    if sys.argv[1:2] == ["level"]:
        level(sys.argv[2])
    elif sys.argv[1:] == ["signal"]:
        signal()
    else:
        main()
