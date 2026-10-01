import hashlib
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from engine.rules import Rules
from research import baseline as B, oos, panel as P, selector as S, strategies as st
from research.panel import ASSETS, Panel

RULES = Rules.load(Path(__file__).resolve().parents[1] / "rules")


def weekdays(start, n):
    d, out = start, []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def world(n=1150, seed=11):
    days = weekdays(date(2010, 4, 1), n)
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.01, (n, 4)), axis=0))
    nan = np.full(n, np.nan)
    return Panel(dates=np.array(days, dtype="datetime64[D]"), assets=list(ASSETS), open=close, high=close * 1.01, low=close * 0.99, close=close, value=np.full((n, 4), 1e9), vwap=close,
                 cash=1.0002 ** np.arange(n), nifty=close[:, 0], vix=nan, pe=nan, pb=nan)


def few_trials():
    return [t for t in st.trials(s1_steps=2) if t.family == "S0" or (t.family == "S2" and t.params["length"] == 50 and t.band == 0.01)
            or (t.family == "S4" and t.params["target"] == 0.12 and t.band == 0.05 and t.params["lookback"] == 20)]


def test_the_spec_margin_is_one_standard_error_and_the_deflated_one_is_what_the_best_of_n_noise_strategies_would_show():
    assert oos.margin_for("spec", 500.0) == 1.0
    assert oos.margin_for("deflated", 100.0) == pytest.approx(np.sqrt(2 * np.log(100)))
    assert oos.margin_for("deflated", 1.0) == 0.0 and oos.margin_for("deflated", 0.2) == 0.0
    with pytest.raises(ValueError, match="variant"):
        oos.margin_for("whatever", 10.0)


def test_excess_is_the_daily_return_above_the_funds():
    eq = np.array([100.0, 101.0, 103.02])
    cash = np.array([1.0, 1.001, 1.002001])
    assert np.allclose(oos.excess(eq, cash), [0.01 - 0.001, 103.02 / 101 - 1 - 0.001])


def test_a_level_run_gives_every_figure_the_report_needs_for_both_designs():
    p = world()
    out = oos.run_level(p, RULES, few_trials(), st.ensembles(), "Balanced", 0.2)
    assert out["risk"] == "Balanced" and out["cap"] == 0.2 and list(out["designs"]) == ["ensembles", "all trials"] and out["n_variants"] == 4
    ens, allt = out["designs"]["ensembles"], out["designs"]["all trials"]
    assert ens["n_trials"] == 6 and allt["n_trials"] == 4 and 1.0 <= ens["n_eff"] <= 6.0 and 0.0 <= ens["pbo"] <= 1.0 and 0.0 <= allt["best_insample"]["dsr"] <= 1.0
    assert allt["best_insample"]["id"] in [t.id for t in few_trials()]
    for d in (ens, allt):
        assert list(d["variants"]) == ["spec", "deflated"] and d["variants"]["spec"]["margin"] == 1.0 and d["variants"]["deflated"]["margin"] >= 0.0
        for v in d["variants"].values():
            assert list(v["log"].columns) == S.LOG_COLUMNS and len(v["log"]) == 2 and v["row"]["start"] == "2013-04-01"
            assert set(("cagr", "cagr_liquidated", "max_dd", "sharpe", "turnover", "tax")) <= set(v["row"]) and len(v["edge"]) == 2 and 0.0 <= v["dsr"]["dsr"] <= 1.0
            assert "sel" not in v and "acct" not in v and "runs" not in d                    # the heavy objects are not kept
    assert list(out["alone"]) == ["S0", "E1", "E2", "E3", "E4", "E5"] and list(out["refs"]) == ["Nifty BeES", "Gold BeES", "Liquid fund"]
    assert all(r["start"] == "2013-04-01" for r in out["alone"].values()) and out["refs"]["Nifty BeES"]["start"] == "2013-04-01"


def test_a_candidate_alone_is_the_fresh_account_of_its_weights_with_the_governor_and_its_own_band():
    p = world()
    ensembles = st.ensembles()
    out = oos.run_level(p, RULES, few_trials(), ensembles, "Balanced", 0.2)
    c0 = S.cut_days(p.dates)[0]
    window = P.from_day(p, c0)
    e2 = [e for e in ensembles if e.family == "E2"][0]
    from research import sim
    r = sim.simulate(window, e2.fn(p)[c0:], RULES, sim.SimConfig(cap=0.2, band=0.05))
    assert out["alone"]["E2"]["final"] == pytest.approx(B.measure(window, r, B.fixed_total(window, RULES), 1_000_000.0)["final"])


def test_a_level_run_needs_a_panel_that_reaches_the_first_april():
    p = world(n=400)
    with pytest.raises(ValueError, match="cut"):
        oos.run_level(p, RULES, few_trials(), st.ensembles(), "Balanced", 0.2)


def row(**kw):
    base = dict(start="2013-04-01", end="2023-09-29", years=10.5, cagr=0.08, cagr_liquidated=0.075, max_dd=0.12, sharpe=0.9, turnover=0.4, tax=50_000.0)
    base.update(kw)
    return base


def design(n_trials, picks, margin=3.4):
    log = pd.DataFrame({"cut": ["2013-04-01", "2014-04-01", "2015-04-01"], "decision": ["picked" if p else "S0" for p in picks], "family": [p or "S0" for p in picks]})
    variant = lambda cagr, m, dsr, edge: dict(margin=m, log=log, row=row(cagr=cagr), dsr=dict(dsr=dsr, sr=0.04, sr0=0.01), edge=edge)
    return dict(n_trials=n_trials, n_eff=310.5, pbo=0.31, best_insample=dict(id="S1|best", sr=0.05, dsr=0.97),
                variants={"spec": variant(0.10, 1.0, 0.88, (0.012, 0.007)), "deflated": variant(0.08, margin, 0.5, (0.0, 0.0))})


def level(risk="Balanced", cap=0.2):
    return dict(risk=risk, cap=cap, n_variants=4,
                designs={"ensembles": design(6, ["E1", None, "E4"]), "all trials": design(2065, ["S1", "S1", None])},
                alone={"S0": row(cagr=0.08), "E1": row(cagr=0.091), "E2": row(cagr=0.074), "E3": row(cagr=0.065), "E4": row(cagr=0.087), "E5": row(cagr=0.085)},
                refs={"Nifty BeES": row(cagr=0.135, max_dd=0.36), "Gold BeES": row(cagr=0.055, max_dd=0.25), "Liquid fund": row(cagr=0.068, max_dd=0.002)})


def test_the_report_has_a_table_per_level_with_the_stitched_rows_the_candidates_alone_the_references_the_picks_and_the_diagnostics():
    text = oos.report([level("Conservative", 0.1), level("Balanced", 0.2)])
    assert "## Conservative: drawdown cap 10%" in text and "## Balanced: drawdown cap 20%" in text and "Aggressive" not in text
    for label in ("Selector over the ensembles, 1 standard error", "Selector over the ensembles, deflated margin (3.4 standard errors)", "Selector over all 2065 trials, 1 standard error",
                  "Selector over all 2065 trials, deflated margin (3.4 standard errors)"):
        assert label in text
    for name in ("S0 plain holding (Nifty ETF and cash) (alone)", "E1 equal weight, four ETFs and cash (alone)", "E5 drawdown-aware exposure (mean of 6) (alone)", "Nifty BeES held", "Gold BeES held",
                 "Liquid fund held"):
        assert name in text
    assert "10.0%" in text and "13.5%" in text and "9.1%" in text and "+1.2" in text and "0.7" in text
    assert "picked a strategy at 2 of 3 cuts (E1: 1, E4: 1)" in text and "picked a strategy at 2 of 3 cuts (S1: 2)" in text
    assert "ensembles: 6 candidates, about 310 independent" in text and "all trials: 2065 candidates" in text and "31%" in text and "97%" in text and "88%" in text and "S1|best" in text
    assert "four variants" in text and "in-sample" in text and "out of sample" in text


def test_main_writes_a_selection_log_per_design_level_and_variant_and_the_table_and_is_byte_identical_on_a_second_run(tmp_path, monkeypatch):
    p = world()
    chosen, ens = few_trials(), st.ensembles()
    monkeypatch.setattr(P, "load_panel", lambda *a, **k: p)
    monkeypatch.setattr(st, "trials", lambda s1_steps=10: chosen)
    monkeypatch.setattr(st, "ensembles", lambda: ens)
    a, b = tmp_path / "a", tmp_path / "b"
    oos.main(out=a)
    oos.main(out=b)
    names = sorted(x.name for x in a.iterdir())
    assert names == sorted(["oos.md"] + [f"selection_{r}_{d}_{v}.csv" for r in ("Conservative", "Balanced", "Aggressive") for d in ("ensembles", "all-trials") for v in ("spec", "deflated")])
    for n in names:
        assert hashlib.sha256((a / n).read_bytes()).hexdigest() == hashlib.sha256((b / n).read_bytes()).hexdigest()
    log = pd.read_csv(a / "selection_Balanced_ensembles_spec.csv")
    assert list(log.columns) == S.LOG_COLUMNS and len(log) == 2
