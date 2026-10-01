import hashlib
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from engine.rules import Rules
from research import baseline as B, diagnostics as D, oos, panel as P, selector as S, strategies as st
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


def test_a_level_run_gives_every_figure_the_report_needs():
    p = world()
    out = oos.run_level(p, RULES, few_trials(), "Balanced", 0.2)
    assert out["risk"] == "Balanced" and out["cap"] == 0.2 and out["n_trials"] == 4 and 1.0 <= out["n_eff"] <= 4.0 and 0.0 <= out["pbo"] <= 1.0
    assert out["best_insample"]["id"] in [t.id for t in few_trials()] and 0.0 <= out["best_insample"]["dsr"] <= 1.0
    assert list(out["variants"]) == ["spec", "deflated"] and out["variants"]["deflated"]["margin"] >= 0.0 and out["variants"]["spec"]["margin"] == 1.0
    for v in out["variants"].values():
        assert list(v["log"].columns) == S.LOG_COLUMNS and len(v["log"]) == 2 and v["row"]["start"] == "2013-04-01"
        assert set(("cagr", "cagr_liquidated", "max_dd", "sharpe", "turnover", "tax")) <= set(v["row"]) and len(v["edge"]) == 2 and 0.0 <= v["dsr"]["dsr"] <= 1.0
    assert list(out["refs"]) == ["S0", "Nifty BeES", "Gold BeES", "Liquid fund"] and out["refs"]["Nifty BeES"]["start"] == "2013-04-01"


def test_a_level_run_needs_a_panel_that_reaches_the_first_april():
    p = world(n=400)
    with pytest.raises(ValueError, match="cut"):
        oos.run_level(p, RULES, few_trials(), "Balanced", 0.2)


def row(**kw):
    base = dict(start="2013-04-01", end="2023-09-29", years=10.5, cagr=0.08, cagr_liquidated=0.075, max_dd=0.12, sharpe=0.9, turnover=0.4, tax=50_000.0)
    base.update(kw)
    return base


def level(risk="Balanced", cap=0.2):
    log = pd.DataFrame({"cut": ["2013-04-01", "2014-04-01", "2015-04-01"], "decision": ["picked", "S0", "picked"], "family": ["S1", "S0", "S3"], "picked": ["a", "s0", "c"]})
    return dict(risk=risk, cap=cap, n_trials=2064, n_eff=310.5, var_sr=1e-6, pbo=0.31, best_insample=dict(id="S1|best", sr=0.05, dsr=0.97),
                variants={"spec": dict(margin=1.0, log=log, row=row(cagr=0.10), dsr=dict(dsr=0.88, sr=0.04, sr0=0.01), edge=(0.012, 0.007)),
                          "deflated": dict(margin=3.4, log=log.assign(decision=["S0", "S0", "S0"], family=["S0", "S0", "S0"]), row=row(cagr=0.08), dsr=dict(dsr=0.5, sr=0.03, sr0=0.01),
                                           edge=(0.0, 0.0))},
                refs={"S0": row(cagr=0.08), "Nifty BeES": row(cagr=0.135, max_dd=0.36), "Gold BeES": row(cagr=0.055, max_dd=0.25), "Liquid fund": row(cagr=0.068, max_dd=0.002)})


def test_the_report_has_a_table_per_level_with_the_stitched_rows_the_references_the_picks_and_the_diagnostics():
    text = oos.report([level("Conservative", 0.1), level("Balanced", 0.2)])
    assert "## Conservative: drawdown cap 10%" in text and "## Balanced: drawdown cap 20%" in text and "Aggressive" not in text
    assert "Selector, 1 standard error" in text and "Selector, deflated margin (3.4 standard errors)" in text
    for name in ("S0 plain holding", "Nifty BeES held", "Gold BeES held", "Liquid fund held"):
        assert name in text
    assert "10.0%" in text and "13.5%" in text and "+1.2" in text and "0.7" in text                         # growth of the selector and of Nifty; edge over S0 +1.2 points, error 0.7
    assert "2 of 3 cuts" in text and "S1: 1" in text and "S3: 1" in text and "0 of 3 cuts" in text
    assert "2064" in text and "310" in text and "31%" in text and "97%" in text and "88%" in text and "S1|best" in text
    assert "in-sample" in text and "out of sample" in text


def test_main_writes_a_selection_log_per_level_and_variant_and_the_table_and_is_byte_identical_on_a_second_run(tmp_path, monkeypatch):
    p = world()
    chosen = few_trials()
    monkeypatch.setattr(P, "load_panel", lambda *a, **k: p)
    monkeypatch.setattr(st, "trials", lambda s1_steps=10: chosen)
    a, b = tmp_path / "a", tmp_path / "b"
    oos.main(out=a)
    oos.main(out=b)
    names = sorted(x.name for x in a.iterdir())
    assert names == sorted(["oos.md"] + [f"selection_{r}_{v}.csv" for r in ("Conservative", "Balanced", "Aggressive") for v in ("spec", "deflated")])
    for n in names:
        assert hashlib.sha256((a / n).read_bytes()).hexdigest() == hashlib.sha256((b / n).read_bytes()).hexdigest()
    log = pd.read_csv(a / "selection_Balanced_spec.csv")
    assert list(log.columns) == S.LOG_COLUMNS and len(log) == 2
