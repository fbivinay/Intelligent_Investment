import numpy as np
import pytest
import torch

from research.dl import models as M, train as T

F, L = 6, 12


@pytest.mark.parametrize("arch", M.ARCHS)
def test_every_architecture_maps_a_batch_of_sequences_to_five_logits_and_starts_at_equal_weights(arch):
    model = M.make_model(arch, F, L, hidden=8)
    x = torch.randn(7, L, F)
    out = model(x)
    assert out.shape == (7, 5) and torch.equal(out, torch.zeros(7, 5))
    assert torch.allclose(M.weights(model, x), torch.full((7, 5), 0.2))


@pytest.mark.parametrize("arch", M.ARCHS)
def test_training_moves_the_layers_below_the_zero_started_head_once_the_head_has_moved(arch):
    torch.manual_seed(0)
    model = M.make_model(arch, F, L, hidden=8)
    first = next(p for n, p in model.named_parameters() if not n.startswith("head")).detach().clone()
    x = torch.randn(64, L, F)
    target = (x[:, -1, 0] > 0).float()
    opt = torch.optim.Adam(model.parameters(), lr=0.05)
    for _ in range(25):
        opt.zero_grad()
        loss = ((M.weights(model, x)[:, 0] - target) ** 2).mean()
        loss.backward()
        opt.step()
    now = next(p for n, p in model.named_parameters() if not n.startswith("head"))
    assert not torch.allclose(first, now.detach()) and loss.item() < 0.2


def test_an_unknown_architecture_is_refused():
    with pytest.raises(ValueError, match="architecture"):
        M.make_model("rnn2", F, L)


def test_the_sharpe_loss_is_minus_the_annualised_sharpe_ratio_of_the_return_above_the_funds_by_hand():
    w = torch.full((4, 5), 0.2)
    R = torch.tensor([[0.01, 0.00, 0.00, 0.00, 0.001], [-0.01, 0.00, 0.00, 0.00, 0.001], [0.02, 0.00, 0.00, 0.00, 0.001], [0.0, 0.00, 0.00, 0.00, 0.001]])
    ex = (w * R).sum(1) - R[:, 4]
    assert T.sharpe_loss(w, R, cost=0.0).item() == pytest.approx(-(ex.mean() / ex.std()).item() * np.sqrt(252), rel=1e-5)


def test_a_cost_per_unit_of_turnover_comes_off_every_day_the_weights_change_and_the_first_day_trades_nothing():
    w = torch.tensor([[0.2, 0.2, 0.2, 0.2, 0.2], [1.0, 0, 0, 0, 0], [1.0, 0, 0, 0, 0]])
    R = torch.tensor([[0.01, 0, 0, 0, 0.001], [0.02, 0, 0, 0, 0.001], [-0.01, 0, 0, 0, 0.001]])
    net = T.net_excess(w, R, cost=0.001)
    gross = (w * R).sum(1) - R[:, 4]
    assert torch.allclose(net, gross - torch.tensor([0.0, 0.001 * 0.8, 0.0]))                  # day 2 trades 0.8 of the money one way: 0.5 x (0.8 + 4 x 0.2)
    assert torch.equal(T.net_excess(w, R, cost=0.0), gross)


def test_the_loss_is_nan_free_when_the_return_above_the_fund_never_varies():
    w = torch.full((5, 5), 0.2)
    R = torch.tensor([[0.001] * 5] * 5)
    assert torch.isfinite(T.sharpe_loss(w, R, cost=0.001))


def test_the_validation_gap_leaves_the_label_horizon_and_an_embargo_between_the_training_days_and_the_validation_days():
    train, val = T.split_days(first=10, cut=400, val_days=100, horizon=2, embargo=5)
    assert val[-1] == 400 - 3 and len(val) == 100 and val[0] == 400 - 3 - 99                          # the last day whose label (to day t + 2) is known before the cut
    assert train[0] == 10 and train[-1] + 2 + 5 < val[0] and len(set(train) & set(val)) == 0
    assert train[-1] == val[0] - 1 - 2 - 5


def test_a_window_too_short_for_a_validation_set_is_refused():
    with pytest.raises(ValueError, match="short"):
        T.split_days(first=10, cut=60, val_days=100, horizon=2, embargo=5)


def planted(n=600, seed=0):
    """Features whose first column is +1 or -1 at random; asset 0 earns 0.3% when it is +1 and loses 0.3% when it is -1; the others and the fund are quiet."""
    rng = np.random.default_rng(seed)
    s = rng.choice([-1.0, 1.0], n)
    X = np.zeros((n, 5, 3))
    X[:, :, 0] = s[:, None]
    X[:, :, 1:] = rng.normal(0, 1, (n, 5, 2))
    R = np.zeros((n, 5))
    R[:, 0] = 0.003 * s + rng.normal(0, 0.002, n)
    R[:, 1:4] = rng.normal(0, 0.002, (n, 3))
    R[:, 4] = 0.0002
    return X.astype("float32"), R.astype("float32"), s


def cfg(**kw):
    base = dict(arch="mlp", seq_len=5, cost=0.0005, hidden=8, lr=0.02, weight_decay=0.0, max_epochs=120, patience=15)
    base.update(kw)
    return T.Config(**base)


def test_training_on_a_planted_signal_lowers_the_loss_and_puts_the_money_on_the_asset_the_signal_points_to():
    X, R, s = planted()
    model, best, hist = T.fit(cfg(), X[:450], R[:450], seed=0, Xval=X[450:], Rval=R[450:])
    assert hist["train"][-1] < hist["train"][0] and best > 0
    w = T.predict(model, X[450:])
    assert w.shape == (150, 5) and np.allclose(w.sum(1), 1.0, atol=1e-5)
    assert w[s[450:] > 0, 0].mean() > 0.5 and w[s[450:] < 0, 0].mean() < 0.1


def test_a_model_trained_for_zero_epochs_is_the_equal_weight_prior():
    X, R, s = planted()
    model, best, hist = T.fit(cfg(), X[:450], R[:450], seed=0, epochs=0)
    assert best == 0 and np.allclose(T.predict(model, X[450:]), 0.2)


def test_early_stopping_returns_the_prior_when_validation_disagrees_with_training_and_a_fixed_epoch_count_is_obeyed():
    X, R, s = planted()
    flipped = R[450:].copy()
    flipped[:, 0] = -flipped[:, 0]                                                           # in validation the signal points the other way
    model, best, hist = T.fit(cfg(), X[:450], R[:450], seed=0, Xval=X[450:], Rval=flipped)
    assert best == 0 and np.allclose(T.predict(model, X[450:]), 0.2) and len(hist["val"]) == cfg().patience         # stops after `patience` epochs without improvement
    _, ep, hist = T.fit(cfg(), X[:450], R[:450], seed=0, epochs=7)
    assert ep == 7 and len(hist["train"]) == 7


def test_the_same_seed_gives_the_same_weights_and_another_seed_a_different_model():
    X, R, s = planted()
    a, _, _ = T.fit(cfg(), X[:450], R[:450], seed=3, epochs=20)
    b, _, _ = T.fit(cfg(), X[:450], R[:450], seed=3, epochs=20)
    c, _, _ = T.fit(cfg(), X[:450], R[:450], seed=4, epochs=20)
    assert np.array_equal(T.predict(a, X[450:]), T.predict(b, X[450:])) and not np.array_equal(T.predict(a, X[450:]), T.predict(c, X[450:]))


def test_a_label_that_peeks_one_day_ahead_is_what_the_validation_gap_exists_to_catch():
    # Labels two days ahead of the features overlap a validation day's features when a training day is within `horizon` of it: the gap must be at least the horizon.
    train, val = T.split_days(first=0, cut=500, val_days=100, horizon=2, embargo=0)
    assert all(t + 2 < val[0] for t in train)
    train_bad = [t for t in range(0, val[0] + 3) if t + 2 >= val[0]]
    assert train_bad and all(t not in set(train) for t in train_bad)


@pytest.mark.parametrize("arch", M.ARCHS)
def test_the_output_depends_on_the_most_recent_day_and_on_earlier_days_too(arch):
    torch.manual_seed(1)
    model = M.make_model(arch, F, L, hidden=8)
    for p in model.head.parameters():
        torch.nn.init.normal_(p, std=1.0)                                                      # a head that is not zero, so the inputs show
    x = torch.randn(4, L, F)
    base = model(x).detach()
    last, first = x.clone(), x.clone()
    last[:, -1] += 1.0
    first[:, 0] += 1.0
    assert not torch.allclose(model(last).detach(), base, atol=1e-6) and not torch.allclose(model(first).detach(), base, atol=1e-6)


def test_the_mlp_reads_todays_row_for_its_first_group_of_inputs():
    torch.manual_seed(2)
    model = M.make_model("mlp", F, L, hidden=8)
    with torch.no_grad():
        model.net[0].weight[:, F:] = 0.0                                                         # only today's features reach the hidden layer
        for p in model.head.parameters():
            torch.nn.init.normal_(p, std=1.0)
    x = torch.randn(4, L, F)
    base = model(x)
    mid, last = x.clone(), x.clone()
    mid[:, 5] += 1.0
    last[:, -1] += 1.0
    assert torch.allclose(model(mid), base) and not torch.allclose(model(last), base, atol=1e-6)


def test_the_transformer_reads_the_last_token_of_the_window():
    torch.manual_seed(3)
    model = M.make_model("transformer", F, L, hidden=8)
    with torch.no_grad():
        for p in model.head.parameters():
            torch.nn.init.normal_(p, std=1.0)
        model.pos.normal_(std=1.0)
    x = torch.randn(4, L, F)
    want = model.head(model.enc(model.inp(x) + model.pos)[:, -1])
    assert torch.allclose(model(x), want, atol=1e-6)
