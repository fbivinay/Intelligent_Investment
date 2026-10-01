"""Run the committed deep-model configurations on a Kaggle GPU and bring the out-of-sample weights back.

    python -m research.kaggle.s6            # all 12 configurations, design period; writes research/out/s6/

Builds the hashed snapshot (panel, features, April cuts, the code of research.dl and the configuration list), adds it as a new version of the private dataset, pushes the kernel,
waits, pulls the weights and verifies every file against the hashes the kernel wrote.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from research import panel as P, selector as S
from research.dl import configs as C
from research.kaggle import build, kernel_s6, run

OWNER, DATASET, KERNEL = "fbivinay06", "india-algo-panel", "india-algo-s6"
OUT = build.ROOT / "research" / "out" / "s6"
DL = Path(__file__).resolve().parents[1] / "dl"
CODE = ("data", "models", "train", "walk", "configs")


def main() -> dict:
    panel = P.load_panel(end=P.DESIGN_END)
    cfgs = C.committed()
    cfg_file = build.SNAP.parent / "configs.json"
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    cfg_file.write_bytes((json.dumps(cfgs, indent=1, sort_keys=True) + "\n").encode("utf-8"))
    code = {f"dl_{n}.py": DL / f"{n}.py" for n in CODE}
    code["configs.json"] = cfg_file
    build.build_snapshot(panel, build.SNAP, code=code, extra_arrays={"cuts": np.array(S.cut_days(panel.dates), dtype="int64")})
    run.upload_dataset(build.SNAP, OWNER, DATASET, "India algo panel (design period)", "panel, features, cuts and the code of the deep model")
    run.run_kernel(build.ROOT / "artifacts" / "kaggle" / "s6_kernel", OWNER, KERNEL, "India algo S6", Path(kernel_s6.__file__), [f"{OWNER}/{DATASET}"],
                   [f"weights_{c['name']}.npy" for c in cfgs] + ["run.json"], OUT)
    return json.loads((OUT / "run.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
