"""Smoke test run on Kaggle: is there a GPU, is the dataset intact, and does a torch computation on the GPU agree with the CPU? Writes smoke.json and outputs.json.

Self-contained (standard library, numpy, torch): a kernel cannot import this package. The same file runs locally in the tests with the GPU part skipped.
"""
import hashlib
import json
from pathlib import Path


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def find_input(root="/kaggle/input"):
    """The folder holding manifest.json, wherever Kaggle mounted the dataset."""
    return next(Path(root).rglob("manifest.json")).parent


def main(src, out):
    import torch
    src, out = Path(src), Path(out)
    listed = json.loads((src / "manifest.json").read_text(encoding="utf-8"))["files"]
    bad = [name for name, h in listed.items() if not (src / name).exists() or sha256(src / name) != h]
    res = {"torch": torch.__version__, "cuda": bool(torch.cuda.is_available()), "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
           "manifest_ok": not bad, "bad_files": bad, "n_files": len(listed)}
    torch.manual_seed(0)
    a, b = torch.randn(512, 512), torch.randn(512, 512)
    cpu = a @ b
    res["cpu_checksum"] = float(cpu.double().sum())
    if torch.cuda.is_available():
        res["max_abs_diff"] = float((cpu - (a.cuda() @ b.cuda()).cpu()).abs().max())
    out.mkdir(parents=True, exist_ok=True)
    (out / "smoke.json").write_text(json.dumps(res, indent=1, sort_keys=True), encoding="utf-8")
    (out / "outputs.json").write_text(json.dumps({"files": {"smoke.json": sha256(out / "smoke.json")}}, indent=1), encoding="utf-8")
    return res


if __name__ == "__main__":
    main(find_input(), "/kaggle/working")
