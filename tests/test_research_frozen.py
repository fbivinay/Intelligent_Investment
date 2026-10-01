import json
import subprocess
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from engine.rules import Rules
from research import baseline as B, frozen as FZ, panel as P, selector as S, sim, strategies as st
from research.kaggle.snapshot import sha256
from research.panel import ASSETS, Panel

RULES = Rules.load(Path(__file__).resolve().parents[1] / "rules")


def weekdays(start, n):
    d, out = start, []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def world(n=1700, start=date(2010, 4, 1), seed=11):
    days = weekdays(start, n)
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.01, (n, 4)), axis=0))
    nan = np.full(n, np.nan)
    return Panel(dates=np.array(days, dtype="datetime64[D]"), assets=list(ASSETS), open=close, high=close * 1.01, low=close * 0.99, close=close, value=np.full((n, 4), 1e9), vwap=close,
                 cash=1.0002 ** np.arange(n), nifty=close[:, 0], vix=nan, pe=nan, pb=nan)


def s0_trials():
    return [t for t in st.trials(s1_steps=2) if t.family == "S0"]


def test_the_frozen_period_starts_on_its_first_trading_day():
    p = world()
    i = FZ.start_index(p.dates, "2015-10-01")
    assert str(p.dates[i]) == "2015-10-01" and str(p.dates[i - 1]) == "2015-09-30"
    assert str(p.dates[FZ.start_index(p.dates, "2015-10-03")]) == "2015-10-05"                 # a Saturday: the Monday after


def test_a_level_run_holds_the_selector_s0_every_candidate_and_the_references_as_fresh_accounts_from_the_frozen_start():
    p = world()
    out = FZ.run_level(p, RULES, s0_trials(), st.ensembles(), "Aggressive", 0.3, margin=1.3, start="2015-10-01", sim_kw={"harvest": True})
    i0 = FZ.start_index(p.dates, "2015-10-01")
    rows = out["rows"]
    assert list(rows) == ["Selector", "Selector, 1 standard error", "S0", "E1", "E2", "E3", "E4", "E5", "Nifty BeES held", "Junior BeES held", "Bank BeES held", "Gold BeES held",
                          "Liquid fund held"]
    assert all(r["start"] == "2015-10-01" for r in rows.values())
    window = P.from_day(p, i0)
    s0 = [t for t in s0_trials() if t.cap == 0.3][0]
    direct = sim.simulate(window, s0.fn(p)[i0:], RULES, sim.SimConfig(cap=0.3, harvest=True))
    assert rows["S0"]["final"] == pytest.approx(B.measure(window, direct, B.fixed_total(window, RULES), 1_000_000.0)["final"])
    assert list(out["log"].columns) == S.LOG_COLUMNS and out["log"].margin.unique().tolist() == [1.3] and (out["log_1se"].margin == 1.0).all()
    assert out["weights"].shape == (len(p.dates), 5) and len(out["holder"]) == len(p.dates) and out["first_cut"] == S.cut_days(p.dates)[0]


def test_the_verdict_compares_the_selector_with_s0_after_selling_everything_and_checks_the_cap():
    rows = {"Selector": dict(cagr_liquidated=0.101, max_dd=0.21), "S0": dict(cagr_liquidated=0.095, max_dd=0.25)}
    v = FZ.verdict(rows, cap=0.3)
    assert v == dict(beats_s0=True, within_cap=True, edge=pytest.approx(0.006), same_as_s0=False)
    assert FZ.verdict({"Selector": dict(cagr_liquidated=0.09, max_dd=0.31), "S0": dict(cagr_liquidated=0.09, max_dd=0.31)}, cap=0.3) == dict(
        beats_s0=False, within_cap=False, edge=0.0, same_as_s0=True)


def test_the_code_state_must_be_the_tag_with_nothing_changed_in_code_rules_or_data_except_outputs():
    calls = []

    def runner(replies):
        def run(args, **kw):
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, replies.pop(0), "")
        return run
    ok = FZ.code_state("freeze", runner=runner(["abc123\n", "research/out/frozen/report.md\nresearch/out/s6_frozen/run.json\n", "?? research/out/frozen/x.csv\n"]))
    assert ok == "abc123"
    with pytest.raises(RuntimeError, match="changed since"):
        FZ.code_state("freeze", runner=runner(["abc123\n", "research/sim.py\n", ""]))
    with pytest.raises(RuntimeError, match="uncommitted"):
        FZ.code_state("freeze", runner=runner(["abc123\n", "", " M rules/tax/slabs.toml\n"]))

    def no_tag(args, **kw):
        return subprocess.CompletedProcess(args, 128, "", "fatal: ambiguous argument")
    with pytest.raises(RuntimeError, match="tag"):
        FZ.code_state("freeze", runner=no_tag)


def test_the_data_hashes_are_those_of_the_three_files_the_panel_reads(tmp_path):
    for name in FZ.PANEL_FILES:
        (tmp_path / "processed").mkdir(exist_ok=True)
        (tmp_path / "processed" / name).write_text(name)
    h = FZ.data_hashes(tmp_path)
    assert list(h) == list(FZ.PANEL_FILES) and h["etf_daily_adjusted.csv"] == sha256(tmp_path / "processed" / "etf_daily_adjusted.csv")


def test_the_artifact_is_the_weights_by_date_with_the_strategy_held_and_a_manifest_of_hashes(tmp_path):
    dates = np.array(["2013-03-28", "2013-04-01", "2013-04-02"], dtype="datetime64[D]")
    w = np.array([[0.5, 0, 0, 0, 0.5], [0.2, 0.2, 0.2, 0.2, 0.2], [0.21, 0.2, 0.19, 0.2, 0.2]])
    FZ.write_artifact(tmp_path, "Balanced", dates, w, ["S0|cap=0.2|band=0.01", "E1|x", "E1|x"], first=1)
    df = pd.read_csv(tmp_path / "signal_Balanced.csv")
    assert list(df.columns) == ["date", "NIFTYBEES", "JUNIORBEES", "BANKBEES", "GOLDBEES", "cash", "strategy"] and list(df.date) == ["2013-04-01", "2013-04-02"]
    assert df.strategy.tolist() == ["E1|x", "E1|x"] and df.NIFTYBEES.tolist() == [0.2, 0.21]
    m = json.loads((tmp_path / "manifest.json").read_text())
    assert m["files"]["signal_Balanced.csv"] == sha256(tmp_path / "signal_Balanced.csv")


def test_the_report_states_each_levels_verdict_the_rows_and_that_three_years_prove_little():
    p = world()
    lv = FZ.run_level(p, RULES, s0_trials(), st.ensembles(), "Balanced", 0.2, margin=1.3, start="2015-10-01", sim_kw={"harvest": True})
    text = FZ.report([lv], {"tag": "freeze", "commit": "abc123", "start": "2015-10-01", "end": str(p.dates[-1])})
    assert "## Balanced: drawdown cap 20%" in text and "Selector (deflated margin 1.30 standard errors)" in text and "S0 plain holding" in text
    assert "Nifty BeES held" in text and "Liquid fund held" in text and ("beats plain holding" in text or "does not beat plain holding" in text)
    assert "abc123" in text and "three years" in text
    log = lv["log"]
    before = log.cut[log.cut < "2015-10-01"].max()
    assert f"{before}: " in text and all(f"{c}: " in text for c in log.cut[log.cut >= "2015-10-01"]) and all(f"{c}: " not in text for c in log.cut[log.cut < before])


def test_the_pinned_margins_are_the_deflated_margins_measured_on_the_design_period():
    m = json.loads((Path(FZ.__file__).parent / "out" / "oos_margins.json").read_text())
    for risk, margin in FZ.MARGINS.items():
        assert margin == pytest.approx(m[risk]["ensembles"]["deflated_margin"], abs=5e-5)
    assert set(FZ.MARGINS) == set(B.RISKS)


def test_the_run_refuses_to_start_without_margins_or_on_code_that_is_not_the_tags(monkeypatch):
    monkeypatch.setattr(FZ, "code_state", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no tag")))
    loaded = []
    monkeypatch.setattr(P, "load_panel", lambda *a, **k: loaded.append(1))
    with pytest.raises(RuntimeError, match="tag"):
        FZ.main()
    monkeypatch.setattr(FZ, "MARGINS", {})
    with pytest.raises(RuntimeError, match="margins"):
        FZ.main()
    assert loaded == []
