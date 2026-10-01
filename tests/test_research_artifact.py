import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from engine.rules import Rules
from research import artifact as A, panel as P, sim
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


def world(n=900, start=date(2012, 4, 2), crash_at=None):
    days = weekdays(start, n)
    rng = np.random.default_rng(3)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.004, (n, 4)), axis=0))
    if crash_at is not None:
        close[crash_at:] *= np.r_[np.linspace(1.0, 0.6, 30), np.full(n - crash_at - 30, 0.6)][:, None]
    nan = np.full(n, np.nan)
    return Panel(dates=np.array(days, dtype="datetime64[D]"), assets=list(ASSETS), open=close, high=close, low=close, close=close, value=np.full((n, 4), 1e9), vwap=close,
                 cash=1.0002 ** np.arange(n), nifty=close[:, 0], vix=nan, pe=nan, pb=nan)


def frozen_dir(tmp_path, p, i0, w=(0.6, 0.1, 0.1, 0.1, 0.1)):
    """Signal files like the frozen run's: from day i0 on, target weights and the strategy held, with a manifest of hashes."""
    d = tmp_path / "frozen"
    d.mkdir(parents=True)
    files = {}
    for level in A.LEVELS:
        df = pd.DataFrame([list(w)] * (len(p.dates) - i0), columns=["NIFTYBEES", "JUNIORBEES", "BANKBEES", "GOLDBEES", "cash"])
        df.insert(0, "date", [str(x) for x in p.dates[i0:]])
        df["strategy"] = "E1|equal-weight,rebalance=year|band=0.01"
        df.to_csv(d / f"signal_{level}.csv", index=False, lineterminator="\n")
        files[f"signal_{level}.csv"] = sha256(d / f"signal_{level}.csv")
    (d / "manifest.json").write_text(json.dumps({"files": files}))
    return d


def test_the_effective_weights_scale_the_risky_part_by_the_governor_and_put_the_rest_in_the_fund():
    target = np.array([[0.4, 0.2, 0.1, 0.1, 0.2], [0.4, 0.2, 0.1, 0.1, 0.2]])
    eff = A.effective(target, np.array([1.0, 0.5]))
    assert np.allclose(eff[0], target[0]) and np.allclose(eff[1], [0.2, 0.1, 0.05, 0.05, 0.6]) and np.allclose(eff.sum(axis=1), 1.0)
    with pytest.raises(ValueError, match="multiplier"):
        A.effective(target, np.array([1.0, 1.5]))


def test_building_the_artifact_runs_the_reference_account_and_writes_the_governed_weights_with_hashes(tmp_path):
    p = world(crash_at=500)
    i0 = 100
    src = frozen_dir(tmp_path, p, i0)
    out = tmp_path / "signal"
    m = A.build(p, RULES, src, out)
    assert sorted(m["files"]) == sorted(f"{lv}.csv" for lv in A.LEVELS) and m["source"] == json.loads((src / "manifest.json").read_text())["files"]
    df = pd.read_csv(out / "Conservative.csv")
    assert list(df.columns) == ["date", "NIFTYBEES", "JUNIORBEES", "BANKBEES", "GOLDBEES", "cash", "multiplier", "strategy"] and df.date.iloc[0] == str(p.dates[i0])
    w = df[["NIFTYBEES", "JUNIORBEES", "BANKBEES", "GOLDBEES", "cash"]].to_numpy()
    assert np.allclose(w.sum(axis=1), 1.0, atol=1e-9) and df.multiplier.min() < 1.0                     # the 40% fall cut the risk of a 10% cap account
    ref = sim.simulate(P.from_day(p, i0), np.tile([0.6, 0.1, 0.1, 0.1, 0.1], (len(p.dates) - i0, 1)), RULES, sim.SimConfig(cap=0.1, harvest=True))
    assert np.allclose(df.multiplier, ref.multiplier) and np.allclose(w[:, 0], 0.6 * ref.multiplier)
    assert m["files"]["Conservative.csv"] == sha256(out / "Conservative.csv")


def test_the_artifact_is_byte_identical_on_a_second_build(tmp_path):
    p = world()
    src = frozen_dir(tmp_path, p, 50)
    A.build(p, RULES, src, tmp_path / "a")
    A.build(p, RULES, src, tmp_path / "b")
    for lv in A.LEVELS:
        assert (tmp_path / "a" / f"{lv}.csv").read_bytes() == (tmp_path / "b" / f"{lv}.csv").read_bytes()


def test_a_signal_that_does_not_match_its_hash_or_the_panels_dates_is_refused(tmp_path):
    p = world()
    src = frozen_dir(tmp_path, p, 50)
    (src / "signal_Balanced.csv").write_text((src / "signal_Balanced.csv").read_text().replace("0.6,", "0.7,", 1))
    with pytest.raises(ValueError, match="hash"):
        A.build(p, RULES, src, tmp_path / "x")
    src2 = frozen_dir(tmp_path / "two", p, 50)
    short = Panel(**{**{k: getattr(p, k) for k in ("assets", "special_days")}, **{k: getattr(p, k)[:-5] for k in ("dates", "open", "high", "low", "close", "value", "vwap", "cash",
                                                                                                                   "nifty", "vix", "pe", "pb")}})
    with pytest.raises(ValueError, match="dates"):
        A.build(short, RULES, src2, tmp_path / "y")


def test_reading_the_artifact_back_gives_the_dates_the_weights_and_the_strategy_after_checking_the_hash(tmp_path):
    p = world()
    src = frozen_dir(tmp_path, p, 50)
    out = tmp_path / "signal"
    A.build(p, RULES, src, out)
    dates, w, strategy = A.load("Aggressive", out)
    assert dates[0] == p.dates[50] and w.shape == (len(p.dates) - 50, 5) and strategy[0].startswith("E1|")
    (out / "Aggressive.csv").write_text((out / "Aggressive.csv").read_text() + "\n")
    with pytest.raises(ValueError, match="hash"):
        A.load("Aggressive", out)
