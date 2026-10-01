"""Smoke job: build the dataset snapshot, upload it as a private dataset, run the smoke kernel on a Kaggle GPU, pull and check what it says.

    python -m research.kaggle.smoke
"""
from __future__ import annotations

import json
from pathlib import Path

from research import panel as P
from research.kaggle import build, run

OWNER = "fbivinay06"
DATASET = "india-algo-panel"
KERNEL = "india-algo-smoke"
WORK = build.ROOT / "artifacts" / "kaggle"


def check(res: dict) -> None:
    """What a good smoke run says: the data arrived intact, a GPU was there and agreed with the CPU."""
    if not res["manifest_ok"]:
        raise RuntimeError(f"the dataset changed on its way to Kaggle: {res['bad_files']}")
    if not res["cuda"]:
        raise RuntimeError("the kernel had no GPU")
    if res["max_abs_diff"] > 1e-3:
        raise RuntimeError(f"the GPU and the CPU disagree by {res['max_abs_diff']}")


def main() -> dict:
    snap = build.SNAP
    build.build_snapshot(P.load_panel(end=P.DESIGN_END), snap)
    run.upload_dataset(snap, OWNER, DATASET, "India algo panel (design period)", "panel and features, design period")
    out = WORK / "smoke_out"
    run.run_kernel(WORK / "smoke_kernel", OWNER, KERNEL, "India algo smoke", Path(__file__).with_name("kernel_smoke.py"), [f"{OWNER}/{DATASET}"], ["smoke.json"], out)
    res = json.loads((out / "smoke.json").read_text(encoding="utf-8"))
    check(res)
    print(json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    main()
