"""Train the LSTM strategy on a Kaggle GPU and bring its out-of-sample weights back.

    python -m research.kaggle.lstm          # v1: the six ETFs and the liquid fund; writes research/out/lstm/
    python -m research.kaggle.lstm v2       # v2: the Nifty 50, Gold and Nasdaq 100 ETFs and the liquid fund; writes research/out/lstm_v2/

Builds the hashed snapshot (the ETFs' prices and causal features to 2026-09-30, the April cuts from 2017, the code of research.lstm), adds it as a
version of a private dataset, pushes the kernel, waits, pulls the weights and verifies every file against the hashes the kernel wrote.

v1 was written down before any result. v2 came after v1's result (10.8% a year, worst fall 36%, below the Max level): the same network, training and
test, on the ETFs the Max level holds and the market itself. Choosing gold and the Nasdaq 100 is hindsight, the same as the Max level's.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np

from research import features as F, lstm as L, panel as P, selector as S
from research.kaggle import build, kernel_lstm, run, snapshot as SN

OWNER = "fbivinay06"
END = "2026-09-30"
FIRST_CUT = "2017-04-01"                                   # the Max level's first day is 2017-04-03: both are tested on the same years
VERSIONS = {"v1": P.GROWTH, "v2": ["NIFTYBEES", "GOLDBEES", "MON100"]}
SLUGS = {"v1": ("india-algo-lstm", "india-algo-lstm-train"), "v2": ("india-algo-lstm-v2", "india-algo-lstm-v2-train")}


def out_dir(version: str) -> Path:
    return build.ROOT / "research" / "out" / ("lstm" if version == "v1" else f"lstm_{version}")


def arrays(version: str) -> dict:
    """What the kernel reads: the dates, the ETFs' fill prices, the liquid fund, the April cuts and the causal features, cut to the version's ETFs.
    The features are built on the six-ETF panel (research/features.py names its columns) and then cut, so every version sees the same numbers."""
    p = P.load_panel(end=END, assets=P.GROWTH)
    cols = [p.assets.index(a) for a in VERSIONS[version]]
    feats = {k: (v[:, cols] if v.ndim == 2 else v) for k, v in F.build(p).items()}
    return {"dates": p.dates.astype("datetime64[D]").astype("int64"), "vwap": p.vwap[:, cols], "cash": p.cash,
            "cuts": np.array(S.cut_days(p.dates, FIRST_CUT), dtype="int64"), **{f"f_{k}": v for k, v in feats.items()}}


def main(version: str = "v1") -> dict:
    out, snap = out_dir(version), build.ROOT / "artifacts" / "kaggle" / f"snapshot_lstm_{version}"
    dataset, kernel = SLUGS[version]
    SN.write_snapshot(snap, arrays(version), {"snapshot.py": Path(SN.__file__), "lstm.py": Path(L.__file__)},
                      {"design_end": END, "assets": VERSIONS[version], "version": version}, dates_key="dates")
    run.upload_dataset(snap, OWNER, dataset, f"India algo LSTM {version}", f"ETF prices, features, April cuts and the code of the LSTM strategy ({version})")
    names = [f"weights_{c['name']}.npy" for c in L.CONFIGS] + ["weights_chosen.npy", "run.json"]
    run.run_kernel(build.ROOT / "artifacts" / "kaggle" / f"lstm_{version}_kernel", OWNER, kernel, f"India algo LSTM {version} train", Path(kernel_lstm.__file__),
                   [f"{OWNER}/{dataset}"], names, out)                     # a kernel cannot share its dataset's slug (409)
    shutil.copyfile(snap / "manifest.json", out / "input_manifest.json")
    shutil.copyfile(snap / "d_dates.npy", out / "dates.npy")
    return json.loads((out / "run.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    print(json.dumps(main(*sys.argv[1:2]), indent=1)[:4000])
