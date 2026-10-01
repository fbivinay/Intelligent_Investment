"""Run the committed deep-model configurations on a Kaggle GPU and bring the out-of-sample weights back.

    python -m research.kaggle.s6            # design period: all 12 configurations at every April cut; writes research/out/s6/
    python -m research.kaggle.s6 frozen     # after the freeze tag only: retrain at the April cuts from 2023 on data to 2026-09-30; writes research/out/s6_frozen/

Builds the hashed snapshot (panel, features, April cuts, the code of research.dl and the configuration list), adds it as a new version of a private dataset, pushes the kernel,
waits, pulls the weights and verifies every file against the hashes the kernel wrote.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np

from research import panel as P, selector as S
from research.dl import configs as C
from research.kaggle import build, kernel_s6, run

OWNER = "fbivinay06"
OUT = build.ROOT / "research" / "out" / "s6"
OUT_FROZEN = build.ROOT / "research" / "out" / "s6_frozen"
DL = Path(__file__).resolve().parents[1] / "dl"
CODE = ("data", "models", "train", "walk", "configs")
FROZEN_FIRST_CUT = "2023-04-01"            # the last design-period cut: its model is retrained so the days after 2023-09-30 get weights


def record_inputs(snap: Path, out: Path) -> None:
    """Keep, next to the weights, the manifest of the dataset the kernel read and the dates the weights belong to."""
    shutil.copyfile(Path(snap) / "manifest.json", Path(out) / "input_manifest.json")
    shutil.copyfile(Path(snap) / "d_dates.npy", Path(out) / "dates.npy")


def frozen_cuts(dates: np.ndarray) -> list[int]:
    """The April cuts the frozen run trains at: the last design-period one and every one after it."""
    return S.cut_days(dates, FROZEN_FIRST_CUT)


def _go(panel: P.Panel, cuts: list[int], snap: Path, dataset: str, kernel: str, out: Path, design_end: str, title: str) -> dict:
    cfgs = C.committed()
    cfg_file = snap.parent / f"{snap.name}_configs.json"
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    cfg_file.write_bytes((json.dumps(cfgs, indent=1, sort_keys=True) + "\n").encode("utf-8"))
    code = {f"dl_{n}.py": DL / f"{n}.py" for n in CODE}
    code["configs.json"] = cfg_file
    build.build_snapshot(panel, snap, code=code, design_end=design_end, extra_arrays={"cuts": np.array(cuts, dtype="int64")})
    run.upload_dataset(snap, OWNER, dataset, title, "panel, features, cuts and the code of the deep model")
    run.run_kernel(build.ROOT / "artifacts" / "kaggle" / f"{kernel}_kernel", OWNER, kernel, title, Path(kernel_s6.__file__), [f"{OWNER}/{dataset}"],
                   [f"weights_{c['name']}.npy" for c in cfgs] + ["run.json"], out)
    record_inputs(snap, out)
    return json.loads((out / "run.json").read_text(encoding="utf-8"))


def main() -> dict:
    panel = P.load_panel(end=P.DESIGN_END)
    return _go(panel, S.cut_days(panel.dates), build.SNAP, "india-algo-panel", "india-algo-s6", OUT, P.DESIGN_END, "India algo S6")


def main_frozen() -> dict:
    from research import frozen
    frozen.code_state()                                                        # the frozen years are loaded only on the frozen code
    panel = P.load_panel(end=frozen.FROZEN_END)
    return _go(panel, frozen_cuts(panel.dates), build.ROOT / "artifacts" / "kaggle" / "snapshot_frozen", "india-algo-panel-full", "india-algo-s6-frozen", OUT_FROZEN,
               frozen.FROZEN_END, "India algo S6 frozen")


if __name__ == "__main__":
    print(json.dumps(main_frozen() if sys.argv[1:] == ["frozen"] else main(), indent=1))
