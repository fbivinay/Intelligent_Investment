"""A snapshot of everything a Kaggle kernel needs, with the SHA-256 of every file, so what ran there is exactly what was built here.

One flat folder (Kaggle skips sub-folders on upload): d_<name>.npy for each array, c_<name> for each code file, manifest.json listing every hash. Nothing in it is dated:
the same inputs give the same bytes. A snapshot refuses data past the design end it states, so the frozen test years cannot be uploaded by accident.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import numpy as np

IGNORED = ("manifest.json", "dataset-metadata.json")


def sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_snapshot(out, arrays: dict, code: dict, meta: dict, dates_key: str | None = None) -> dict:
    """Write the arrays and code files into `out` (replacing it) with a manifest of their hashes, and return the manifest."""
    out = Path(out)
    if dates_key is not None and "design_end" in meta:
        last = np.datetime64(int(np.max(arrays[dates_key])), "D")
        if last > np.datetime64(meta["design_end"]):
            raise ValueError(f"the data reaches {last}, past the design end {meta['design_end']}")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    files = {}
    for name, a in arrays.items():
        np.save(out / f"d_{name}.npy", np.asarray(a))
        files[f"d_{name}.npy"] = sha256(out / f"d_{name}.npy")
    for name, src in code.items():
        shutil.copyfile(src, out / f"c_{name}")
        files[f"c_{name}"] = sha256(out / f"c_{name}")
    manifest = {"files": dict(sorted(files.items())), "meta": meta}
    (out / "manifest.json").write_bytes((json.dumps(manifest, indent=1, sort_keys=True) + "\n").encode("utf-8"))
    return manifest


def verify(snap) -> None:
    """Every file the manifest lists is there with its hash, and nothing else is."""
    snap = Path(snap)
    listed = json.loads((snap / "manifest.json").read_text(encoding="utf-8"))["files"]
    present = {p.name for p in snap.iterdir() if p.name not in IGNORED}
    if set(listed) - present:
        raise ValueError(f"missing files: {sorted(set(listed) - present)}")
    if present - set(listed):
        raise ValueError(f"unexpected files: {sorted(present - set(listed))}")
    for name, h in listed.items():
        if sha256(snap / name) != h:
            raise ValueError(f"changed file: {name}")
