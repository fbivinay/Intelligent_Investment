"""Kaggle kernel for the LSTM strategy: retrain each April, choose the settings on validation days, and write the out-of-sample weights.

Self-contained apart from the code file the dataset carries (c_lstm.py becomes research.lstm): standard library, numpy, torch. It checks the dataset against
its manifest first and refuses to run on a changed one. GPU training is not bit-repeatable, so the weights it writes (with their SHA-256 in outputs.json) are
the record.
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


def main(src, out, device="cuda"):
    src, out = Path(src), Path(out)
    listed = json.loads((src / "manifest.json").read_text(encoding="utf-8"))["files"]
    bad = [n for n, h in listed.items() if not (src / n).exists() or sha256(src / n) != h]
    if bad:
        raise RuntimeError(f"the dataset does not match its manifest: {bad}")
    out.mkdir(parents=True, exist_ok=True)
    pkg = out / "_pkg"
    (pkg / "research").mkdir(parents=True, exist_ok=True)
    (pkg / "research" / "__init__.py").write_text("")
    (pkg / "research" / "lstm.py").write_bytes((src / "c_lstm.py").read_bytes())
    sys.path.insert(0, str(pkg))
    import numpy as np
    import torch
    from research import lstm as L
    if device == "cuda":
        torch.backends.cudnn.deterministic, torch.backends.cudnn.benchmark = True, False
    feats = {n[len("d_f_"):-len(".npy")]: np.load(src / n) for n in listed if n.startswith("d_f_")}
    vwap, cash, cuts = np.load(src / "d_vwap.npy"), np.load(src / "d_cash.npy"), [int(c) for c in np.load(src / "d_cuts.npy")]
    t0 = time.time()
    r = L.walk(feats, vwap, cash, cuts, device=device, progress=lambda k, n, best: log(f"cut {k}/{n}: chose {best}"))
    files = {}
    for name, w in r["configs"].items():
        np.save(out / f"weights_{name}.npy", w.astype("float32"))
        files[f"weights_{name}.npy"] = sha256(out / f"weights_{name}.npy")
    np.save(out / "weights_chosen.npy", r["chosen"].astype("float32"))
    files["weights_chosen.npy"] = sha256(out / "weights_chosen.npy")
    run = {"device": device, "torch": torch.__version__, "gpu": str(torch.cuda.get_device_name(0)) if device == "cuda" else "cpu", "cuts": len(cuts),
           "seconds": round(time.time() - t0, 1), "configs": L.CONFIGS, "seeds": list(L.SEEDS), "cost": L.COST, "choice": r["choice"],
           "input_manifest": sha256(src / "manifest.json")}
    (out / "run.json").write_text(json.dumps(run, indent=1, sort_keys=True), encoding="utf-8")
    files["run.json"] = sha256(out / "run.json")
    (out / "outputs.json").write_text(json.dumps({"files": files}, indent=1, sort_keys=True), encoding="utf-8")
    log("done in", run["seconds"], "s")
    return run


if __name__ == "__main__":
    main(find_input(), "/kaggle/working")
