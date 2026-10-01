import json

import numpy as np
import pytest

from research import causal, s6 as S6
from research.dl import configs as C
from research.kaggle.snapshot import sha256
from research.panel import ASSETS, Panel

CONFIGS = [{"name": "gru-L5-c5", "arch": "gru", "seq_len": 5, "cost": 0.0005}, {"name": "mlp-L5-c20", "arch": "mlp", "seq_len": 5, "cost": 0.002}]


def weekdays(n, start="2010-04-01"):
    d = np.arange(np.datetime64(start), np.datetime64(start) + 3 * n, dtype="datetime64[D]")
    return d[np.is_busday(d)][:n]


def out_dir(tmp_path, n=1700, first="2013-04-01", seed=0):
    """A folder like the one the S6 driver writes: weights per configuration (NaN before the first cut), the kernel's hashes, the dates and the input manifest."""
    out = tmp_path / "s6"
    out.mkdir(parents=True)
    dates = weekdays(n)
    np.save(out / "dates.npy", dates.astype("int64"))
    (out / "input_manifest.json").write_text(json.dumps({"files": {"d_dates.npy": sha256(out / "dates.npy")}}))
    rng = np.random.default_rng(seed)
    i0 = int(np.searchsorted(dates, np.datetime64(first)))
    files = {}
    for c in CONFIGS:
        w = rng.dirichlet(np.ones(5), n).astype("float32")
        w[:i0] = np.nan
        np.save(out / f"weights_{c['name']}.npy", w)
        files[f"weights_{c['name']}.npy"] = sha256(out / f"weights_{c['name']}.npy")
    (out / "outputs.json").write_text(json.dumps({"files": files}))
    return out, dates, i0


@pytest.fixture(autouse=True)
def two_configs(monkeypatch):
    monkeypatch.setattr(C, "committed", lambda: CONFIGS)


def panel_on(dates):
    n = len(dates)
    close = np.full((n, 4), 100.0)
    nan = np.full(n, np.nan)
    return Panel(dates=dates.astype("datetime64[D]"), assets=list(ASSETS), open=close, high=close, low=close, close=close, value=np.full((n, 4), 1e9), vwap=close, cash=np.ones(n),
                 nifty=close[:, 0], vix=nan, pe=nan, pb=nan)


def test_loading_checks_every_file_and_returns_the_weights_of_each_configuration_and_their_dates(tmp_path):
    out, dates, i0 = out_dir(tmp_path)
    weights, d = S6.load(out)
    assert list(weights) == ["gru-L5-c5", "mlp-L5-c20"] and np.array_equal(d, dates) and weights["gru-L5-c5"].dtype == np.float64
    assert np.isnan(weights["mlp-L5-c20"][:i0]).all() and np.isfinite(weights["mlp-L5-c20"][i0:]).all()


def test_a_changed_weights_file_or_a_dates_file_that_is_not_the_one_the_kernel_read_is_refused(tmp_path):
    out, dates, i0 = out_dir(tmp_path)
    np.save(out / "weights_gru-L5-c5.npy", np.zeros((3, 5), dtype="float32"))
    with pytest.raises(ValueError, match="changed"):
        S6.load(out)
    out2, _, _ = out_dir(tmp_path / "b")
    np.save(out2 / "dates.npy", (dates + 1).astype("int64"))
    with pytest.raises(ValueError, match="dates"):
        S6.load(out2)


def test_the_ensemble_is_the_mean_of_the_configurations_with_the_equal_weight_prior_before_the_first_model_and_rows_that_sum_to_one(tmp_path):
    out, dates, i0 = out_dir(tmp_path)
    t = S6.ensemble(out)
    weights, _ = S6.load(out)
    w = t.fn(panel_on(dates))
    want = np.mean(list(weights.values()), axis=0)
    assert t.family == "S6" and t.id == "S6|mean of 2 configurations|band=0.05" and t.band == 0.05 and t.cap is None and t.params == {"configs": 2, "seeds": 3}
    assert np.allclose(w[:i0], 0.2) and np.allclose(w[i0:], want[i0:] / want[i0:].sum(axis=1, keepdims=True)) and np.abs(w.sum(axis=1) - 1.0).max() < 1e-12


def test_each_configuration_is_a_trial_with_its_parameters(tmp_path):
    out, dates, i0 = out_dir(tmp_path)
    ts = S6.trials(out)
    assert [t.id for t in ts] == ["S6|gru-L5-c5|band=0.05", "S6|mlp-L5-c20|band=0.05"] and ts[1].params == {"arch": "mlp", "seq_len": 5, "cost": 0.002}
    weights, _ = S6.load(out)
    assert np.allclose(ts[0].fn(panel_on(dates))[i0:], weights["gru-L5-c5"][i0:] / weights["gru-L5-c5"][i0:].sum(axis=1, keepdims=True))


def test_a_model_may_be_picked_only_from_the_first_april_three_years_after_its_first_out_of_sample_day(tmp_path):
    out, dates, i0 = out_dir(tmp_path)
    assert str(dates[i0]) == "2013-04-01" and S6.ensemble(out).eligible_from == "2016-04-01"
    short, sdates, _ = out_dir(tmp_path / "short", n=1000)                                  # ends in 2014: never three years of record
    assert S6.ensemble(short).eligible_from == S6.NEVER


def test_the_weights_belong_to_one_calendar_and_a_panel_on_other_dates_is_refused_while_a_cut_panel_gets_the_prefix(tmp_path):
    out, dates, i0 = out_dir(tmp_path)
    t = S6.ensemble(out)
    with pytest.raises(ValueError, match="dates"):
        t.fn(panel_on(dates + 1))
    with pytest.raises(ValueError, match="dates"):
        t.fn(panel_on(weekdays(1800)))                                                       # longer than the weights
    p = panel_on(dates)
    causal.assert_causal(t.fn, p, n_cuts=4, seed=1)


def test_weights_missing_after_the_first_model_day_are_refused(tmp_path):
    out, dates, i0 = out_dir(tmp_path)
    w = np.load(out / "weights_gru-L5-c5.npy")
    w[i0 + 10] = np.nan
    np.save(out / "weights_gru-L5-c5.npy", w)
    files = json.loads((out / "outputs.json").read_text())["files"]
    files["weights_gru-L5-c5.npy"] = sha256(out / "weights_gru-L5-c5.npy")
    (out / "outputs.json").write_text(json.dumps({"files": files}))
    with pytest.raises(ValueError, match="missing"):
        S6.trials(out)[0].fn(panel_on(dates))


def frozen_dir(tmp_path, design_dates, extra=300, seed=5, first_new=None):
    """A frozen-run folder: dates extend the design dates, weights NaN before the frozen run's first cut."""
    out = tmp_path / "s6_frozen"
    out.mkdir(parents=True)
    dates = weekdays(len(design_dates) + extra)
    assert np.array_equal(dates[:len(design_dates)], design_dates)
    np.save(out / "dates.npy", dates.astype("int64"))
    (out / "input_manifest.json").write_text(json.dumps({"files": {"d_dates.npy": sha256(out / "dates.npy")}}))
    rng = np.random.default_rng(seed)
    start = len(design_dates) - 100 if first_new is None else first_new
    files = {}
    for c in CONFIGS:
        w = rng.dirichlet(np.ones(5), len(dates)).astype("float32")
        w[:start] = np.nan
        np.save(out / f"weights_{c['name']}.npy", w)
        files[f"weights_{c['name']}.npy"] = sha256(out / f"weights_{c['name']}.npy")
    (out / "outputs.json").write_text(json.dumps({"files": files}))
    return out, dates


def test_the_combined_model_keeps_the_design_weights_and_takes_only_the_new_days_from_the_frozen_run(tmp_path):
    design, ddates, i0 = out_dir(tmp_path)
    frozen, fdates = frozen_dir(tmp_path, ddates)
    t = S6.ensemble_combined(design, frozen)
    w = t.fn(panel_on(fdates))
    dw, _ = S6.load(design)
    fw, _ = S6.load(frozen)
    d_mean, f_mean = np.mean(list(dw.values()), axis=0), np.mean(list(fw.values()), axis=0)
    n = len(ddates)
    assert w.shape == (len(fdates), 5) and np.allclose(w[:i0], 0.2)
    assert np.allclose(w[i0:n], d_mean[i0:n] / d_mean[i0:n].sum(axis=1, keepdims=True))                # the record is not rewritten
    assert np.allclose(w[n:], f_mean[n:] / f_mean[n:].sum(axis=1, keepdims=True)) and t.eligible_from == "2016-04-01" and t.family == "S6"


def test_the_frozen_run_must_cover_every_new_day_and_extend_the_same_calendar(tmp_path):
    design, ddates, i0 = out_dir(tmp_path)
    late, _ = frozen_dir(tmp_path / "late", ddates, first_new=len(ddates) + 5)                    # the frozen run starts after the design run ends: a gap
    with pytest.raises(ValueError, match="missing"):
        S6.ensemble_combined(design, late)
    other = tmp_path / "other"
    other.mkdir()
    out2, d2, _ = out_dir(other, n=1900)
    shifted = d2 + 1
    np.save(out2 / "dates.npy", shifted.astype("int64"))
    (out2 / "input_manifest.json").write_text(json.dumps({"files": {"d_dates.npy": sha256(out2 / "dates.npy")}}))
    with pytest.raises(ValueError, match="calendar"):
        S6.ensemble_combined(design, out2)
