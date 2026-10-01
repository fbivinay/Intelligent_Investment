import inspect
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

from research.kaggle import run as K, snapshot as SN


def arrays():
    return {"close": np.arange(12, dtype=float).reshape(6, 2), "dates": np.arange(6, dtype="int64"), "vix": np.array([np.nan, 1.0, 2.0, 3.0, 4.0, 5.0])}


def test_a_snapshot_writes_every_array_and_code_file_with_its_hash_and_verifies(tmp_path):
    code = tmp_path / "model.py"
    code.write_text("x = 1\n")
    m = SN.write_snapshot(tmp_path / "snap", arrays(), {"model.py": code}, {"design_end": "2023-09-29"})
    assert sorted(m["files"]) == ["c_model.py", "d_close.npy", "d_dates.npy", "d_vix.npy"] and m["meta"] == {"design_end": "2023-09-29"}
    assert m["files"]["c_model.py"] == SN.sha256(code)
    SN.verify(tmp_path / "snap")
    loaded = np.load(tmp_path / "snap" / "d_close.npy")
    assert np.array_equal(loaded, arrays()["close"]) and np.array_equal(np.load(tmp_path / "snap" / "d_vix.npy"), arrays()["vix"], equal_nan=True)


def test_a_snapshot_is_deterministic_to_the_byte(tmp_path):
    code = tmp_path / "model.py"
    code.write_text("x = 1\n")
    SN.write_snapshot(tmp_path / "a", arrays(), {"model.py": code}, {"k": 1})
    SN.write_snapshot(tmp_path / "b", arrays(), {"model.py": code}, {"k": 1})
    assert (tmp_path / "a" / "manifest.json").read_bytes() == (tmp_path / "b" / "manifest.json").read_bytes()
    for f in ("d_close.npy", "c_model.py"):
        assert SN.sha256(tmp_path / "a" / f) == SN.sha256(tmp_path / "b" / f)


def test_verify_catches_a_changed_a_missing_and_an_extra_file(tmp_path):
    code = tmp_path / "model.py"
    code.write_text("x = 1\n")
    snap = tmp_path / "snap"
    SN.write_snapshot(snap, arrays(), {"model.py": code}, {})
    (snap / "c_model.py").write_text("x = 2\n")
    with pytest.raises(ValueError, match="changed"):
        SN.verify(snap)
    SN.write_snapshot(snap, arrays(), {"model.py": code}, {})
    (snap / "d_vix.npy").unlink()
    with pytest.raises(ValueError, match="missing"):
        SN.verify(snap)
    SN.write_snapshot(snap, arrays(), {"model.py": code}, {})
    (snap / "d_extra.npy").write_bytes(b"x")
    with pytest.raises(ValueError, match="unexpected"):
        SN.verify(snap)


def test_a_snapshot_never_holds_data_past_the_design_end_it_states(tmp_path):
    a = arrays()
    a["dates"] = np.array(["2023-09-28", "2023-09-29", "2023-10-02"], dtype="datetime64[D]").astype("int64")
    with pytest.raises(ValueError, match="design end"):
        SN.write_snapshot(tmp_path / "snap", a, {}, {"design_end": "2023-09-30"}, dates_key="dates")


def test_dataset_and_kernel_names_must_carry_the_prefix_so_the_old_ones_cannot_be_touched():
    for ok in ("india-algo-panel", "india-algo-s6-run1"):
        assert K.check_slug(ok) == ok
    for bad in ("deeptrend-dmn", "btc-lstm-walkforward", "India-Algo-X", "india-algo-", "india-algo-a b", "other-india-algo-x"):
        with pytest.raises(ValueError, match="slug"):
            K.check_slug(bad)


def test_the_kernel_metadata_asks_for_a_private_gpu_kernel_without_internet_that_reads_our_dataset():
    m = K.kernel_metadata("fbivinay06", "india-algo-smoke", "India algo smoke", "kernel.py", ["fbivinay06/india-algo-panel"])
    assert m["id"] == "fbivinay06/india-algo-smoke" and m["is_private"] is True and m["enable_gpu"] is True and m["enable_internet"] is False
    assert m["machine_shape"] == "NvidiaTeslaT4" and m["dataset_sources"] == ["fbivinay06/india-algo-panel"] and m["code_file"] == "kernel.py" and m["kernel_type"] == "script"
    with pytest.raises(ValueError, match="slug"):
        K.kernel_metadata("fbivinay06", "deeptrend-dmn", "x", "kernel.py", [])
    with pytest.raises(ValueError, match="slug"):
        K.kernel_metadata("fbivinay06", "india-algo-x", "x", "kernel.py", ["fbivinay06/deeptrend-pooled"])


def test_the_dataset_metadata_names_the_dataset_with_the_prefix():
    m = K.dataset_metadata("fbivinay06", "india-algo-panel", "India algo panel")
    assert m["id"] == "fbivinay06/india-algo-panel" and m["title"] == "India algo panel" and m["licenses"]
    with pytest.raises(ValueError, match="slug"):
        K.dataset_metadata("fbivinay06", "btc-trading-code", "x")


class Fake:
    """Stands in for subprocess.run: answers each call from a script and records the argument lists."""
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def __call__(self, args, **kw):
        self.calls.append(list(args))
        code, out, err = self.replies.pop(0)
        return subprocess.CompletedProcess(args, code, out, err)


def test_the_cli_runs_the_kaggle_program_with_the_arguments_given_and_raises_with_its_message_on_failure():
    ok = Fake([(0, "fine\n", "")])
    assert K.cli(["kernels", "status", "a/b"], runner=ok) == "fine\n" and ok.calls == [["kaggle", "kernels", "status", "a/b"]]
    bad = Fake([(1, "", "403 Forbidden\n")])
    with pytest.raises(RuntimeError, match="403 Forbidden"):
        K.cli(["kernels", "push", "-p", "x"], runner=bad)


def test_the_status_is_read_from_the_cli_line():
    for text, want in (('fbivinay06/x has status "KernelWorkerStatus.COMPLETE"\n', "COMPLETE"), ('a/b has status "KernelWorkerStatus.RUNNING"', "RUNNING"),
                       ('a/b has status "KernelWorkerStatus.ERROR"', "ERROR"), ('a/b has status "KernelWorkerStatus.QUEUED"', "QUEUED")):
        assert K.status("a/b", runner=Fake([(0, text, "")])) == want
    with pytest.raises(RuntimeError, match="status"):
        K.status("a/b", runner=Fake([(0, "something else", "")]))


def test_waiting_polls_until_the_kernel_finishes_and_raises_on_an_error_or_a_timeout():
    stat = lambda s: (0, f'a/b has status "KernelWorkerStatus.{s}"', "")
    ticks = []
    assert K.wait("a/b", runner=Fake([stat("QUEUED"), stat("RUNNING"), stat("COMPLETE")]), sleep=ticks.append, timeout_s=100, interval_s=7) == "COMPLETE" and ticks == [7, 7]
    with pytest.raises(RuntimeError, match="ERROR"):
        K.wait("a/b", runner=Fake([stat("RUNNING"), stat("ERROR")]), sleep=lambda s: None, timeout_s=100, interval_s=7)
    with pytest.raises(TimeoutError):
        K.wait("a/b", runner=Fake([stat("RUNNING")] * 30), sleep=lambda s: None, timeout_s=20, interval_s=7)


def test_pulled_output_must_hold_every_expected_file_and_the_hashes_it_lists(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "weights.npy").write_bytes(b"abc")
    manifest = {"files": {"weights.npy": SN.sha256(out / "weights.npy")}}
    (out / "outputs.json").write_text(json.dumps(manifest))
    K.verify_output(out, ["weights.npy"])
    with pytest.raises(ValueError, match="missing"):
        K.verify_output(out, ["weights.npy", "second.npy"])
    (out / "weights.npy").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="changed"):
        K.verify_output(out, ["weights.npy"])
    (out / "outputs.json").unlink()
    with pytest.raises(ValueError, match="outputs.json"):
        K.verify_output(out, ["weights.npy"])


def test_the_modules_never_touch_the_kaggle_token():
    for mod in (K, SN):
        src = inspect.getsource(mod)
        assert "access_token" not in src and "kaggle.json" not in src and "os.environ" not in src and "getenv" not in src


def test_a_new_dataset_is_created_private_by_default_and_waited_for_until_it_is_ready(tmp_path):
    snap = tmp_path / "snap"
    snap.mkdir()
    fake = Fake([(1, "", "404 Not Found"), (0, "", ""), (0, "pending", ""), (0, "ready", "")])
    K.upload_dataset(snap, "fbivinay06", "india-algo-panel", "India algo panel", "first", runner=fake, sleep=lambda s: None)
    assert fake.calls[0] == ["kaggle", "datasets", "status", "fbivinay06/india-algo-panel"] and fake.calls[1] == ["kaggle", "datasets", "create", "-p", str(snap)]
    assert "--public" not in sum(fake.calls, []) and json.loads((snap / "dataset-metadata.json").read_text())["id"] == "fbivinay06/india-algo-panel"


def test_an_existing_dataset_gets_a_new_version_with_the_message_and_a_stuck_one_times_out(tmp_path):
    snap = tmp_path / "snap"
    snap.mkdir()
    fake = Fake([(0, "ready", ""), (0, "", ""), (0, "ready", "")])
    K.upload_dataset(snap, "fbivinay06", "india-algo-panel", "India algo panel", "second try", runner=fake, sleep=lambda s: None)
    assert fake.calls[1] == ["kaggle", "datasets", "version", "-p", str(snap), "-m", "second try"]
    stuck = Fake([(0, "ready", ""), (0, "", "")] + [(0, "pending", "")] * 200)
    with pytest.raises(TimeoutError):
        K.upload_dataset(snap, "fbivinay06", "india-algo-panel", "t", "m", runner=stuck, sleep=lambda s: None, timeout_s=30)
    with pytest.raises(ValueError, match="slug"):
        K.upload_dataset(snap, "fbivinay06", "deeptrend-pooled", "t", "m", runner=Fake([]), sleep=lambda s: None)


def test_running_a_kernel_pushes_waits_pulls_and_verifies_the_output(tmp_path):
    code = tmp_path / "kernel.py"
    code.write_text("print('hi')\n")
    out = tmp_path / "out"
    out.mkdir()
    (out / "w.npy").write_bytes(b"abc")
    (out / "outputs.json").write_text(json.dumps({"files": {"w.npy": SN.sha256(out / "w.npy")}}))
    fake = Fake([(0, "pushed", ""), (0, 'a/b has status "KernelWorkerStatus.RUNNING"', ""), (0, 'a/b has status "KernelWorkerStatus.COMPLETE"', ""), (0, "output", "")])
    K.run_kernel(tmp_path / "work", "fbivinay06", "india-algo-smoke", "India algo smoke", code, ["fbivinay06/india-algo-panel"], ["w.npy"], out, runner=fake, sleep=lambda s: None)
    assert [c[1:3] for c in fake.calls] == [["kernels", "push"], ["kernels", "status"], ["kernels", "status"], ["kernels", "output"]]
    meta = json.loads((tmp_path / "work" / "kernel-metadata.json").read_text())
    assert meta["enable_gpu"] is True and meta["enable_internet"] is False and meta["is_private"] is True and (tmp_path / "work" / "kernel.py").read_text() == "print('hi')\n"
    bad = Fake([(0, "pushed", ""), (0, 'a/b has status "KernelWorkerStatus.COMPLETE"', ""), (0, "output", "")])
    with pytest.raises(ValueError, match="missing"):
        K.run_kernel(tmp_path / "work2", "fbivinay06", "india-algo-smoke", "t", code, [], ["w.npy", "never_written.npy"], out, runner=bad, sleep=lambda s: None)


# ---- the snapshot of the research panel -----------------------------------------------------------------------------------------------------------------------

def tiny_panel(n=300, start="2022-01-03"):
    from research.panel import ASSETS, Panel
    dates = np.arange(np.datetime64(start), np.datetime64(start) + n, dtype="datetime64[D]")
    rng = np.random.default_rng(1)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, (n, 4)), axis=0))
    nan = np.full(n, np.nan)
    return Panel(dates=dates, assets=list(ASSETS), open=close, high=close * 1.01, low=close * 0.99, close=close, value=np.full((n, 4), 1e9), vwap=close, cash=1.0002 ** np.arange(n),
                 nifty=close[:, 0], vix=np.full(n, 15.0), pe=nan, pb=nan)


def test_the_panel_snapshot_holds_the_panel_arrays_the_features_the_dates_as_days_and_verifies(tmp_path):
    from research.kaggle import build as BU
    p = tiny_panel()
    m = BU.build_snapshot(p, tmp_path / "snap", design_end="2023-12-31")
    SN.verify(tmp_path / "snap")
    names = set(m["files"])
    assert {"d_dates.npy", "d_close.npy", "d_vwap.npy", "d_cash.npy", "d_vix.npy", "d_f_ret21.npy", "d_f_vol63.npy", "d_f_dd252.npy", "d_f_cash_yield63.npy", "c_snapshot.py"} <= names
    dates = np.load(tmp_path / "snap" / "d_dates.npy")
    assert dates.dtype == np.int64 and dates[0] == p.dates[0].astype("int64") and len(dates) == 300
    assert np.array_equal(np.load(tmp_path / "snap" / "d_close.npy"), p.close)
    assert m["meta"]["design_end"] == "2023-12-31" and m["meta"]["days"] == 300 and m["meta"]["first_day"] == "2022-01-03" and m["meta"]["assets"] == list(p.assets)


def test_the_panel_snapshot_refuses_a_panel_past_the_design_end_and_is_deterministic(tmp_path):
    from research.kaggle import build as BU
    p = tiny_panel(n=400, start="2023-06-01")                                          # runs into 2024
    with pytest.raises(ValueError, match="design end"):
        BU.build_snapshot(p, tmp_path / "late", design_end="2023-09-30")
    q = tiny_panel()
    a = BU.build_snapshot(q, tmp_path / "a", design_end="2023-12-31")
    b = BU.build_snapshot(q, tmp_path / "b", design_end="2023-12-31")
    assert a == b and (tmp_path / "a" / "manifest.json").read_bytes() == (tmp_path / "b" / "manifest.json").read_bytes()


# ---- the smoke kernel and the check on what it says -----------------------------------------------------------------------------------------------------------

def test_the_smoke_kernel_checks_the_dataset_hashes_and_writes_its_result_and_an_output_manifest(tmp_path):
    from research.kaggle import build as BU, kernel_smoke as KS
    BU.build_snapshot(tiny_panel(), tmp_path / "snap", design_end="2023-12-31")
    res = KS.main(tmp_path / "snap", tmp_path / "out")
    assert res["manifest_ok"] is True and res["bad_files"] == [] and res["n_files"] > 20 and res["cuda"] is False and "max_abs_diff" not in res
    K.verify_output(tmp_path / "out", ["smoke.json"])
    assert json.loads((tmp_path / "out" / "smoke.json").read_text())["cpu_checksum"] == res["cpu_checksum"]
    (tmp_path / "snap" / "d_close.npy").write_bytes(b"tampered")
    bad = KS.main(tmp_path / "snap", tmp_path / "out2")
    assert bad["manifest_ok"] is False and bad["bad_files"] == ["d_close.npy"]


def test_the_kernel_finds_its_dataset_wherever_kaggle_mounted_it(tmp_path):
    from research.kaggle import kernel_smoke as KS
    deep = tmp_path / "input" / "datasets" / "someone" / "india-algo-panel"
    deep.mkdir(parents=True)
    (deep / "manifest.json").write_text("{}")
    assert KS.find_input(tmp_path / "input") == deep


def test_the_smoke_check_demands_intact_data_a_gpu_and_agreement():
    from research.kaggle import smoke as SM
    good = {"manifest_ok": True, "cuda": True, "max_abs_diff": 1e-5, "bad_files": []}
    SM.check(good)
    for change, match in (({"manifest_ok": False, "bad_files": ["d_close.npy"]}, "changed"), ({"cuda": False}, "no GPU"), ({"max_abs_diff": 0.5}, "disagree")):
        with pytest.raises(RuntimeError, match=match):
            SM.check({**good, **change})


# ---- the S6 kernel --------------------------------------------------------------------------------------------------------------------------------------------

def s6_snapshot(tmp_path, configs):
    import json as _json
    from research.dl import configs as C  # noqa: F401
    from research.kaggle import build as BU
    root = Path(__file__).resolve().parents[1] / "research" / "dl"
    cfg_file = tmp_path / "configs.json"
    cfg_file.write_text(_json.dumps(configs))
    code = {f"dl_{n}.py": root / f"{n}.py" for n in ("data", "models", "train", "walk", "configs")}
    code["configs.json"] = cfg_file
    p = tiny_panel(n=700, start="2011-01-03")
    BU.build_snapshot(p, tmp_path / "snap", code=code, design_end="2030-01-01", extra_arrays={"cuts": np.array([420, 520])})
    return p, tmp_path / "snap"


def test_the_s6_kernel_trains_each_configuration_and_writes_weights_with_hashes_that_verify(tmp_path, monkeypatch):
    from research.dl import configs as C
    from research.kaggle import kernel_s6 as K6
    monkeypatch.setattr(C, "MIN_SAMPLES", 100)
    monkeypatch.setattr(C, "VAL_DAYS", 60)
    monkeypatch.setattr(C, "SEEDS", (0,))
    p, snap = s6_snapshot(tmp_path, [{"name": "mlp-L5-c5", "arch": "mlp", "seq_len": 5, "cost": 0.0005}, {"name": "mlp-L9-c20", "arch": "mlp", "seq_len": 9, "cost": 0.002}])
    run = K6.main(snap, tmp_path / "out", device="cpu")
    assert sorted(run["configs"]) == ["mlp-L5-c5", "mlp-L9-c20"] and run["device"] == "cpu" and run["cuts"] == 2
    K.verify_output(tmp_path / "out", ["weights_mlp-L5-c5.npy", "weights_mlp-L9-c20.npy", "run.json"])
    w = np.load(tmp_path / "out" / "weights_mlp-L5-c5.npy")
    assert w.shape == (700, 5) and w.dtype == np.float32 and np.isnan(w[:420]).all() and np.allclose(w[420:].sum(axis=1), 1.0, atol=1e-5)


def test_the_s6_kernel_refuses_a_dataset_that_does_not_match_its_manifest(tmp_path):
    from research.kaggle import kernel_s6 as K6
    p, snap = s6_snapshot(tmp_path, [{"name": "mlp-L5-c5", "arch": "mlp", "seq_len": 5, "cost": 0.0005}])
    (snap / "d_vwap.npy").write_bytes(b"tampered")
    with pytest.raises(RuntimeError, match="manifest"):
        K6.main(snap, tmp_path / "out", device="cpu")
    assert not (tmp_path / "out" / "outputs.json").exists()


def test_the_committed_configuration_list_is_twelve_unique_trials_of_three_architectures_two_windows_and_two_costs():
    from research.dl import configs as C
    cfgs = C.committed()
    assert len(cfgs) == 12 and len({c["name"] for c in cfgs}) == 12
    assert {c["arch"] for c in cfgs} == {"gru", "tcn", "mlp"} and {c["seq_len"] for c in cfgs} == {63, 126} and {c["cost"] for c in cfgs} == {0.0005, 0.002}
    assert cfgs[0] == {"name": "gru-L63-c5", "arch": "gru", "seq_len": 63, "cost": 0.0005} and C.SEEDS == (0, 1, 2)
