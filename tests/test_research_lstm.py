"""The LSTM strategy's machinery: the timing of what weights earn, the purged split, the equal-weight start, and no weights before the first cut."""
import numpy as np
import torch

from research import lstm as L


def test_weights_decided_after_day_t_earn_the_fill_on_t_plus_1_to_the_fill_on_t_plus_2():
    vwap = np.array([[10.0], [11.0], [12.1], [13.31]])
    cash = np.array([100.0, 100.0, 101.0, 101.0])
    R = L.labels(vwap, cash)
    assert np.allclose(R[0], [12.1 / 11 - 1, 101 / 100 - 1]) and np.isnan(R[-2:]).all()


def test_no_training_label_reaches_into_validation_and_none_reaches_the_cut():
    train, val = L.split_days(first=0, cut=1000, val_days=126)
    assert val[-1] + 2 < 1000                                      # each label runs to t + 2
    assert train[-1] + 2 + 5 < val[0]                              # purged and embargoed


def test_the_untrained_network_holds_every_asset_equally():
    m = L.Allocator(n_features=4, hidden=8, n_out=7)
    w = m(torch.randn(3, 10, 4)).detach().numpy()
    assert np.allclose(w, 1 / 7)


def test_the_walk_writes_nothing_before_its_first_cut_and_weights_that_add_to_one_after():
    rng = np.random.default_rng(0)
    T, n = 900, 2
    feats = {k: rng.normal(size=(T, n)) for k in L.PER_ASSET}
    feats.update({k: rng.normal(size=T) for k in L.MARKET})
    vwap = np.cumprod(1 + rng.normal(0.0005, 0.01, size=(T, n)), axis=0)
    cash = np.cumprod(np.full(T, 1.0002))
    cuts = [700, 800]
    r = L.walk(feats, vwap, cash, cuts, configs=[{"name": "t", "seq_len": 20, "hidden": 4}], seeds=(0,), f=L.Fit(max_epochs=3, patience=2))
    w = r["chosen"]
    assert np.isnan(w[:700]).all() and np.allclose(w[700:].sum(axis=1), 1) and [c["chosen"] for c in r["choice"]] == ["t", "t"]
