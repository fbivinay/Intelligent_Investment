"""Retrain each April on the expanding window and write the weights for the financial year that follows: the out-of-sample weight path of one configuration.

For the cut on day c: features are normalised with statistics from rows before c; the model trains on the days whose label (to day t + 2) is known before c, with the last
`val_days` of them held out (purged and embargoed, see train.split_days) to choose the number of epochs; it is then refitted on all of them for that many epochs, for each
seed, and the seeds' weights are averaged. If validation never beats the untrained prior the weights stay equal, and so they do when there are too few days to learn from.
"""
from __future__ import annotations

import numpy as np

from research.dl import data as D, train as T


def walk_weights(feats: dict, vwap: np.ndarray, cash: np.ndarray, cuts: list[int], cfg: T.Config, seeds=(0, 1, 2), device: str = "cpu", val_days: int = 126,
                 min_samples: int = 300, progress=None) -> np.ndarray:
    """T x 5 weights (four ETFs and cash), NaN before the first cut. Day t's weights use only the data up to day t and a model trained on data before its cut."""
    X, names = D.feature_matrix(feats)
    t0 = D.first_valid(X, names)
    first = t0 + cfg.seq_len - 1
    R = D.labels(vwap, cash)
    out = np.full((len(cash), 5), np.nan)
    for k, c in enumerate(cuts):
        end = cuts[k + 1] if k + 1 < len(cuts) else len(cash)
        out[c:end] = 0.2
        days = np.arange(first, c - 2)                                              # the days whose label (to t + 2) is known before the cut
        try:
            train, val = T.split_days(first, c, val_days)
        except ValueError:
            continue
        if len(days) < min_samples:
            continue
        mu, sd = D.fit_norm(X, t0, c)
        Z = D.normalise(X, mu, sd)
        seq = lambda idx: D.sequences(Z, idx, cfg.seq_len)
        Xp, ws = seq(np.arange(c, end)), []
        for seed in seeds:
            _, epochs, _ = T.fit(cfg, seq(train), R[train], seed, device, seq(val), R[val])
            if epochs == 0:
                ws.append(np.full((end - c, 5), 0.2))
                continue
            model, _, _ = T.fit(cfg, seq(days), R[days], seed, device, epochs=epochs)
            ws.append(T.predict(model, Xp, device))
        out[c:end] = np.mean(ws, axis=0)
        if progress:
            progress(k + 1, len(cuts))
    return out
