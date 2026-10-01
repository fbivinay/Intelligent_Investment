"""Kaggle kernel for the deep model S6: train every committed configuration, retraining each April, and write the out-of-sample weights.

Self-contained apart from the code files the dataset carries (c_dl_*.py become the package research.dl): standard library, numpy, torch. It checks the dataset against its manifest
first and refuses to run on a changed one. GPU training is not bit-repeatable, so the weights it writes (with their SHA-256 in outputs.json) are the record.
"""
import hashlib
import json
import sys
import time
from pathlib import Path


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def find_input(root="/kaggle/input"):
    return next(Path(root).rglob("manifest.json")).parent


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def main(src, out, device="cuda", only=None):
    src, out = Path(src), Path(out)
    listed = json.loads((src / "manifest.json").read_text(encoding="utf-8"))["files"]
    bad = [n for n, h in listed.items() if not (src / n).exists() or sha256(src / n) != h]
    if bad:
        raise RuntimeError(f"the dataset does not match its manifest: {bad}")
    out.mkdir(parents=True, exist_ok=True)
    pkg = out / "_pkg"
    (pkg / "research" / "dl").mkdir(parents=True, exist_ok=True)
    (pkg / "research" / "__init__.py").write_text("")
    for f in src.glob("c_dl_*.py"):
        (pkg / "research" / "dl" / f.name[len("c_dl_"):]).write_bytes(f.read_bytes())
    sys.path.insert(0, str(pkg))
    import numpy as np
    import torch
    from research.dl import configs as C, train as T, walk as W
    if device == "cuda":
        torch.backends.cudnn.deterministic, torch.backends.cudnn.benchmark = True, False
    load = lambda name: np.load(src / f"d_{name}.npy")
    feats = {n[len("d_f_"):-len(".npy")]: np.load(src / n) for n in listed if n.startswith("d_f_")}
    vwap, cash, cuts = load("vwap"), load("cash"), [int(c) for c in load("cuts")]
    configs = json.loads((src / "c_configs.json").read_text(encoding="utf-8"))
    run = {"device": device, "torch": torch.__version__, "cuda": str(torch.cuda.get_device_name(0)) if device == "cuda" else "cpu", "cuts": len(cuts), "configs": {},
           "input_manifest": sha256(src / "manifest.json")}
    files = {}
    for cfg in configs:
        if only and cfg["name"] not in only:
            continue
        t0 = time.time()
        w = W.walk_weights(feats, vwap, cash, cuts, T.Config(arch=cfg["arch"], seq_len=cfg["seq_len"], cost=cfg["cost"]), C.SEEDS, device, C.VAL_DAYS, C.MIN_SAMPLES,
                           progress=lambda k, n, name=cfg["name"]: log(name, f"cut {k}/{n}"))
        np.save(out / f"weights_{cfg['name']}.npy", w.astype("float32"))
        files[f"weights_{cfg['name']}.npy"] = sha256(out / f"weights_{cfg['name']}.npy")
        run["configs"][cfg["name"]] = {**cfg, "seconds": round(time.time() - t0, 1), "equal_weight_days_after_first_cut": int(np.isclose(w[cuts[0]:], 0.2).all(axis=1).sum())}
        log(cfg["name"], "done in", run["configs"][cfg["name"]]["seconds"], "s")
    (out / "run.json").write_text(json.dumps(run, indent=1, sort_keys=True), encoding="utf-8")
    files["run.json"] = sha256(out / "run.json")
    (out / "outputs.json").write_text(json.dumps({"files": files}, indent=1, sort_keys=True), encoding="utf-8")
    return run


if __name__ == "__main__":
    main(find_input(), "/kaggle/working")
