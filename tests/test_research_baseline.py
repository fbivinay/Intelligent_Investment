import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from engine.rules import Rules
from research import baseline as B, costs as C, panel as P, sim, strategies as st
from research.panel import ASSETS, Panel

RULES = Rules.load(Path(__file__).resolve().parents[1] / "rules")


def weekdays(start, n):
    d, out = start, []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def small_panel(n=900, start=date(2012, 4, 2), cash_growth=0.00025, seed=5, vol=0.01):
    days = weekdays(start, n)
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0004, vol, (n, 4)), axis=0))
    nan = np.full(n, np.nan)
    return Panel(dates=np.array(days, dtype="datetime64[D]"), assets=list(ASSETS), open=close, high=close * 1.01, low=close * 0.99, close=close, value=np.full((n, 4), 1e9),
                 vwap=close, cash=(1 + cash_growth) ** np.arange(n), nifty=close[:, 0], vix=nan, pe=nan, pb=nan)


def some_trials():
    return [t for t in st.trials(s1_steps=2) if (t.family == "S0") or (t.family == "S2" and t.params["length"] == 50 and t.band == 0.01) or (t.family == "S4" and t.params["target"] == 0.12 and t.band == 0.05 and t.params["lookback"] == 20)]


def test_cagr_is_the_yearly_growth_rate_and_nan_when_there_is_nothing_to_measure():
    assert B.cagr(1_210_000, 1_000_000, 2.0) == pytest.approx(0.1)
    assert np.isnan(B.cagr(1_000_000, 1_000_000, 0.0)) and np.isnan(B.cagr(0.0, 1_000_000, 3.0)) and np.isnan(B.cagr(1e6, 0.0, 3.0))


def test_a_run_that_only_holds_the_fund_earns_about_the_funds_growth_with_no_drawdown_and_a_small_turnover():
    p = small_panel(n=900, cash_growth=0.00025)
    w = np.tile([0, 0, 0, 0, 1.0], (900, 1))
    cfg = sim.SimConfig(governor=False, slippage=True)
    r = sim.simulate(p, w, RULES, cfg)
    m = B.measure(p, r, 0.0, cfg.capital)
    years = (p.dates[-1] - p.dates[0]).astype(int) / 365.25
    assert (m["start"], m["end"]) == (str(p.dates[0]), str(p.dates[-1])) and m["years"] == pytest.approx(years)
    assert m["cagr"] == pytest.approx(1.00025 ** (899 / years) - 1, abs=6e-4)
    assert m["max_dd"] < 0.002 and m["tax"] == pytest.approx(r.pending_tax + sum(r.tax_by_fy.values()))
    assert m["turnover"] == pytest.approx(r.traded.sum() / 2 / r.equity.mean() / years)
    assert 0.3 / years < m["turnover"] < 0.6 / years                         # one purchase of the whole account: half of the rupees traded, one way, over a growing account
    assert m["final"] == pytest.approx(r.equity[-1] - r.pending_tax)
    assert m["cagr_liquidated"] <= m["cagr"] and m["orders"] == r.orders


def test_the_figures_from_the_first_pick_date_cover_only_the_days_from_then_and_are_nan_when_the_panel_ends_before_it():
    p = small_panel(n=900, start=date(2012, 4, 2))
    w = st.s2_trend(50, "equal")(p)
    cfg = sim.SimConfig(governor=True, cap=0.2)
    r = sim.simulate(p, w, RULES, cfg)
    m = B.measure(p, r, 0.0, cfg.capital)
    i0 = int(np.searchsorted(p.dates, np.datetime64("2013-04-01")))
    pre = r.equity + np.cumsum(r.tax_paid)
    assert m["max_dd_2013"] == pytest.approx((1 - pre[i0:] / np.maximum.accumulate(pre[i0:])).max())
    yrs = (p.dates[-1] - p.dates[i0]).astype(int) / 365.25
    assert m["cagr_2013"] == pytest.approx(((r.equity[-1] - r.pending_tax) / r.equity[i0]) ** (1 / yrs) - 1)
    early = small_panel(n=200, start=date(2011, 4, 4))
    r2 = sim.simulate(early, st.s2_trend(50, "equal")(early), RULES, cfg)
    m2 = B.measure(early, r2, 0.0, cfg.capital)
    assert np.isnan(m2["cagr_2013"]) and np.isnan(m2["max_dd_2013"])


def test_the_drawdown_in_the_ledger_is_before_tax_like_the_cap():
    p = small_panel(n=900, cash_growth=0.0002)
    cfg = sim.SimConfig(governor=False)
    r = sim.simulate(p, st.s1_static([1, 0, 0, 0, 0], "never")(p), RULES, cfg)
    assert B.measure(p, r, 0.0, cfg.capital)["max_dd"] == pytest.approx(r.drawdown.max())


def test_the_ledger_has_one_row_per_trial_and_risk_level_s0_only_at_its_own_level_and_five_reference_rows():
    p = small_panel(n=700)
    df = B.ledger(p, RULES, some_trials())
    assert list(df.columns) == B.COLUMNS
    s0 = df[df.family == "S0"]
    assert sorted(zip(s0.risk, s0.cap)) == sorted(B.RISKS.items()) and len(s0) == 3
    for risk, cap in B.RISKS.items():
        g = df[df.risk == risk]
        assert len(g) == 4 and (g.cap == cap).all()                            # S0 of this level, two S2 (equal, inverse volatility) and one S4
        assert sorted(g.family) == ["S0", "S2", "S2", "S4"]
    ref = df[df.family == "REF"]
    assert len(ref) == 5 and (ref.risk == "none").all() and ref.cap.isna().all()
    assert len(df) == 3 * 4 + 5 and not df.duplicated(["id", "risk"]).any()


def test_the_ledger_is_deterministic_to_the_byte(tmp_path):
    p = small_panel(n=700)
    trials = some_trials()
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    B.write_ledger(B.ledger(p, RULES, trials), a)
    B.write_ledger(B.ledger(p, RULES, trials), b)
    assert hashlib.sha256(a.read_bytes()).hexdigest() == hashlib.sha256(b.read_bytes()).hexdigest()
    back = pd.read_csv(a)
    assert list(back.columns) == B.COLUMNS and json.loads(back.params[0]) == some_trials()[0].params
    assert np.allclose(back.final, B.ledger(p, RULES, some_trials()).final, rtol=1e-9, atol=0)             # ten significant digits are kept


def test_every_row_of_the_ledger_is_a_trial_or_a_labelled_reference_and_the_params_are_json():
    p = small_panel(n=700)
    df = B.ledger(p, RULES, some_trials())
    assert set(df.family) <= {"S0", "S1", "S2", "S3", "S4", "S5", "REF"}
    assert all(isinstance(json.loads(x), dict) for x in df.params)
    assert df[df.family != "REF"].band.isin([0.01, 0.05]).all()


def test_a_panel_that_reaches_into_the_frozen_years_is_refused():
    p = small_panel(n=900, start=date(2023, 5, 1))                              # runs well past 2023-09-30
    assert p.dates[-1] > np.datetime64(P.DESIGN_END)
    with pytest.raises(ValueError, match="frozen"):
        B.ledger(p, RULES, some_trials())


def test_main_loads_the_panel_up_to_the_design_end_and_writes_the_ledger_and_the_table(tmp_path, monkeypatch):
    seen = {}

    def fake_load(*args, **kwargs):
        seen["args"], seen["kwargs"] = args, kwargs
        return small_panel(n=700)
    chosen = some_trials()
    monkeypatch.setattr(P, "load_panel", fake_load)
    monkeypatch.setattr(st, "trials", lambda s1_steps=10: chosen)
    from research import s6
    monkeypatch.setattr(s6, "trials", lambda: [])
    df = B.main(out=tmp_path)
    assert seen["kwargs"].get("end", P.DESIGN_END) == P.DESIGN_END
    assert (tmp_path / "trials.csv").exists() and (tmp_path / "baseline.md").exists()
    assert len(pd.read_csv(tmp_path / "trials.csv")) == len(df)
    assert "Conservative" in (tmp_path / "baseline.md").read_text(encoding="utf-8")


def test_charges_are_the_trading_charges_plus_the_fixed_fees_and_slippage_is_what_the_run_lost_to_it():
    p = small_panel(n=900)
    cfg = sim.SimConfig(governor=True, cap=0.2, slippage=True)
    r = sim.simulate(p, st.s2_trend(50, "equal")(p), RULES, cfg)
    m = B.measure(p, r, 123.0, cfg.capital)
    assert m["charges"] == pytest.approx(r.charges.sum() + 123.0) and r.charges.sum() > 0
    assert m["slippage"] == pytest.approx(r.slippage.sum()) and r.slippage.sum() > 0


def test_the_sharpe_ratio_is_the_yearly_mean_over_the_deviation_of_the_daily_return_above_the_funds():
    p = small_panel(n=900)
    cfg = sim.SimConfig(governor=True, cap=0.2)
    r = sim.simulate(p, st.s2_trend(50, "equal")(p), RULES, cfg)
    excess = r.equity[1:] / r.equity[:-1] - p.cash[1:] / p.cash[:-1]
    assert B.measure(p, r, 0.0, cfg.capital)["sharpe"] == pytest.approx(excess.mean() / excess.std(ddof=1) * np.sqrt(252))


def test_the_tax_on_the_year_still_in_progress_comes_off_the_final_wealth_and_is_part_of_the_tax_line():
    days = weekdays(date(2016, 6, 1), 150)                                     # ends in December: the year's tax is not due yet
    close = np.concatenate([np.linspace(100, 150, 100), np.full(50, 150.0)])
    nan = np.full(150, np.nan)
    p = Panel(dates=np.array(days, dtype="datetime64[D]"), assets=list(ASSETS), open=np.tile(close[:, None], (1, 4)), high=np.tile(close[:, None], (1, 4)),
              low=np.tile(close[:, None], (1, 4)), close=np.tile(close[:, None], (1, 4)), value=np.full((150, 4), 1e9), vwap=np.tile(close[:, None], (1, 4)),
              cash=np.ones(150), nifty=close, vix=nan, pe=nan, pb=nan)
    w = np.tile([1.0, 0, 0, 0, 0], (150, 1))
    w[100:] = [0, 0, 0, 0, 1.0]
    cfg = sim.SimConfig(governor=False, slippage=False)
    r = sim.simulate(p, w, RULES, cfg)
    m = B.measure(p, r, 0.0, cfg.capital)
    assert r.pending_tax > 30_000 and r.tax_paid.sum() == 0
    assert m["final"] == pytest.approx(r.equity[-1] - r.pending_tax) and m["tax"] == pytest.approx(r.pending_tax)
    assert m["liquidation_tax"] == pytest.approx(r.liquidation_tax) and m["cagr"] == pytest.approx(B.cagr(m["final"], cfg.capital, m["years"]))
    assert m["cagr_liquidated"] == pytest.approx(B.cagr(r.liquidation_equity, cfg.capital, m["years"]))


def test_the_reference_holdings_are_run_without_the_governor():
    p = small_panel(n=900, vol=0.015)
    df = B.ledger(p, RULES, [])
    row = df[df.id == "REF|hold=Nifty BeES"].iloc[0]
    free = sim.simulate(p, st.s1_static([1, 0, 0, 0, 0], "never")(p), RULES, sim.SimConfig(governor=False))
    governed = sim.simulate(p, st.s1_static([1, 0, 0, 0, 0], "never")(p), RULES, sim.SimConfig(governor=True, cap=0.1))
    assert governed.drawdown.max() < free.drawdown.max() - 0.01                   # the scenario is one where the governor would have changed the result
    assert row.max_dd == pytest.approx(free.drawdown.max()) and row.final == pytest.approx(free.equity[-1] - free.pending_tax)
    days = [pd.Timestamp(x).date() for x in p.dates]
    assert row.charges == pytest.approx(free.charges.sum() + C.fixed_costs(RULES, days).sum()) and C.fixed_costs(RULES, days).sum() > 0


def test_a_ledger_row_is_the_direct_simulation_of_that_trial_at_that_risk_level_with_that_band():
    p = small_panel(n=900, vol=0.014)
    trials = some_trials()
    df = B.ledger(p, RULES, trials)
    for t in trials:
        for risk, cap in B.RISKS.items():
            if t.cap not in (None, cap):
                continue
            r = sim.simulate(p, t.fn(p), RULES, sim.SimConfig(cap=cap, band=t.band))
            row = df[(df.id == t.id) & (df.risk == risk)].iloc[0]
            assert row.final == pytest.approx(r.equity[-1] - r.pending_tax) and row.max_dd == pytest.approx(r.drawdown.max()) and row.orders == r.orders
    s4 = [t for t in trials if t.family == "S4"][0]
    other = sim.simulate(p, s4.fn(p), RULES, sim.SimConfig(cap=0.2, band=0.01))
    assert df[(df.id == s4.id) & (df.risk == "Balanced")].iloc[0].orders != other.orders          # the 5% band of this trial trades differently from the default 1%


def test_the_design_end_day_itself_is_allowed_and_a_panel_one_day_longer_is_not(monkeypatch):
    p = small_panel(n=300)
    monkeypatch.setattr(P, "DESIGN_END", str(p.dates[-1]))
    assert len(B.ledger(p, RULES, [])) == 5
    monkeypatch.setattr(P, "DESIGN_END", str(p.dates[-2]))
    with pytest.raises(ValueError, match="frozen"):
        B.ledger(p, RULES, [])


def test_a_panel_that_ends_on_the_first_pick_day_has_no_figures_from_then_and_the_figures_after_a_crash_before_it_leave_the_crash_out():
    full = small_panel(n=900)
    i0 = int(np.searchsorted(full.dates, B.FIRST_PICK))
    short = small_panel(n=i0 + 1)
    assert short.dates[-1] == full.dates[i0]
    cfg = sim.SimConfig(governor=False)
    m = B.measure(short, sim.simulate(short, st.s1_static([1, 0, 0, 0, 0], "never")(short), RULES, cfg), 0.0, cfg.capital)
    assert np.isnan(m["cagr_2013"]) and np.isnan(m["max_dd_2013"])
    n = 900
    close = np.concatenate([np.linspace(100, 60, 150), np.linspace(60, 90, n - 150)])                    # a 40% crash in 2012, a calm climb after
    p = Panel(dates=full.dates, assets=list(ASSETS), open=np.tile(close[:, None], (1, 4)), high=np.tile(close[:, None], (1, 4)), low=np.tile(close[:, None], (1, 4)),
              close=np.tile(close[:, None], (1, 4)), value=np.full((n, 4), 1e9), vwap=np.tile(close[:, None], (1, 4)), cash=full.cash, nifty=close, vix=full.vix, pe=full.pe, pb=full.pb)
    m = B.measure(p, sim.simulate(p, st.s1_static([1, 0, 0, 0, 0], "never")(p), RULES, cfg), 0.0, cfg.capital)
    assert m["max_dd"] > 0.35 and m["max_dd_2013"] < 0.05


def test_selling_everything_at_the_end_costs_the_tax_on_gains_not_yet_realised():
    days = weekdays(date(2016, 6, 1), 150)
    close = np.linspace(100, 150, 150)
    nan = np.full(150, np.nan)
    c4 = np.tile(close[:, None], (1, 4))
    p = Panel(dates=np.array(days, dtype="datetime64[D]"), assets=list(ASSETS), open=c4, high=c4, low=c4, close=c4, value=np.full((150, 4), 1e9), vwap=c4, cash=np.ones(150),
              nifty=close, vix=nan, pe=nan, pb=nan)
    cfg = sim.SimConfig(governor=False, slippage=False)
    r = sim.simulate(p, st.s1_static([1, 0, 0, 0, 0], "never")(p), RULES, cfg)
    m = B.measure(p, r, 0.0, cfg.capital)
    assert r.liquidation_tax > 30_000 and r.pending_tax == 0
    assert m["cagr_liquidated"] < m["cagr"] and m["cagr_liquidated"] == pytest.approx(B.cagr(r.liquidation_equity, cfg.capital, m["years"]))


def test_the_params_are_written_as_compact_json_with_sorted_keys():
    p = small_panel(n=300)
    s3 = [t for t in st.trials(s1_steps=2) if t.family == "S3" and t.params == {"lookback": 63, "k": 1, "every": "month"}]
    df = B.ledger(p, RULES, s3)
    assert df.params.iloc[0] == '{"every":"month","k":1,"lookback":63}'


def ledger_row(**kw):
    base = dict(id="x", family="S2", params="{}", risk="Balanced", cap=0.2, band=0.01, start="2010-04-01", end="2023-09-29", years=13.5, orders=100, final=2.0e6,
                cagr=0.05, cagr_liquidated=0.045, max_dd=0.1, cagr_2013=0.05, max_dd_2013=0.1, sharpe=0.5, turnover=0.4, charges=1000.0, slippage=500.0, tax=20000.0,
                liquidation_tax=1000.0)
    base.update(kw)
    return base


def test_the_report_shows_s0_and_the_best_trial_of_each_family_that_stayed_within_the_cap():
    rows = [ledger_row(id="S0|cap=0.2", family="S0", cagr=0.060, max_dd=0.15),
            ledger_row(id="S2|a", cagr=0.080, max_dd=0.25),                      # best of the family but above the cap: not eligible
            ledger_row(id="S2|b", cagr=0.070, max_dd=0.18),
            ledger_row(id="S2|c", cagr=0.065, max_dd=0.10),
            ledger_row(id="S4|a", family="S4", cagr=0.090, max_dd=0.30),         # a family with nothing within the cap
            ledger_row(id="REF|hold=Nifty BeES", family="REF", risk="none", cap=np.nan, cagr=0.10, max_dd=0.38)]
    text = B.report(pd.DataFrame(rows, columns=B.COLUMNS))
    assert text.count("S0|cap=0.2") == 1 and "S2|b" in text and "S2|a" not in text and "S2|c" not in text
    assert "S4|a" not in text and "none within the cap" in text
    assert "Nifty BeES" in text and "10.0%" in text and "+1.0" in text           # the best S2 beats S0 by 1.0 point of after-tax growth
    assert "in-sample" in text


def test_the_report_counts_how_many_trials_beat_s0_and_stayed_within_the_cap():
    rows = [ledger_row(id="S0|cap=0.2", family="S0", cagr=0.060, max_dd=0.15)] + [ledger_row(id=f"S2|{i}", cagr=0.0475 + 0.005 * i, max_dd=0.04 + 0.05 * i) for i in range(6)] + [ledger_row(id="S2|tie", cagr=0.06, max_dd=0.1),
                                                                                                           ledger_row(id="REF|hold=Liquid fund", family="REF", risk="none", cap=np.nan)]
    text = B.report(pd.DataFrame(rows, columns=B.COLUMNS))
    # growth beats 6% for i = 3, 4, 5 (6.25, 6.75, 7.25%); the cap of 20% holds for i = 0..3 (4 to 19%): only i = 3 does both
    assert "3 of 7 other trials beat S0 after tax, 1 of them within the cap" in text and "holds 8 runs" in text                  # the tie does not beat it


def test_a_trial_exactly_at_the_cap_is_within_it_and_one_a_hair_above_is_not():
    rows = [ledger_row(id="S0|cap=0.2", family="S0", cagr=0.05, max_dd=0.15),
            ledger_row(id="S3|edge", family="S3", cagr=0.07, max_dd=0.2), ledger_row(id="S4|over", family="S4", cagr=0.07, max_dd=0.2 + 1e-9)]
    text = B.report(pd.DataFrame(rows, columns=B.COLUMNS))
    assert "S3|edge" in text and "S4|over" not in text and "S4: none within the cap (of 1)" in text


def test_the_report_leaves_out_a_risk_level_that_was_not_run_and_the_reference_section_when_there_is_none():
    text = B.report(pd.DataFrame([ledger_row(id="S0|cap=0.2", family="S0")], columns=B.COLUMNS))
    assert "## Balanced" in text and "## Conservative" not in text and "## Aggressive" not in text and "Other investments" not in text


def test_the_fixed_fees_of_a_panel_are_those_of_its_days_and_a_longer_panel_pays_more():
    p = small_panel(n=900)
    days = [pd.Timestamp(d).date() for d in p.dates]
    assert B.fixed_total(p, RULES) == pytest.approx(C.fixed_costs(RULES, days).sum()) and B.fixed_total(p, RULES) > 0
    assert B.fixed_total(small_panel(n=300), RULES) < B.fixed_total(p, RULES)
