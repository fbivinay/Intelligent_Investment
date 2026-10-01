"""Training a position model: the loss, the purged validation split, and the fitting loop with early stopping.

The loss is minus the annualised Sharpe ratio of the daily return above the cash leg's, after a cost per unit of turnover (the share of the money that changes hands, one way).
It sees each day's weights next to the return they go on to earn (`dl.data.labels`), exactly as the simulator will fill them. Full batch, AdamW, no dropout, a seed per model.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass

import numpy as np
import torch

from research.dl.models import make_model, weights

SQRT252 = 252 ** 0.5


@dataclass(frozen=True)
class Config:
    arch: str
    seq_len: int
    cost: float                      # per unit of money traded one way, taken off the daily return in the loss
    hidden: int = 16
    lr: float = 3e-3
    weight_decay: float = 1e-3
    max_epochs: int = 150
    patience: int = 15


def net_excess(w: torch.Tensor, R: torch.Tensor, cost: float) -> torch.Tensor:
    """Daily return of the weights above the cash leg's, less cost x turnover (nothing is traded on the first day)."""
    turn = 0.5 * (w[1:] - w[:-1]).abs().sum(1)
    return (w * R).sum(1) - R[:, 4] - cost * torch.cat([torch.zeros(1, dtype=w.dtype, device=w.device), turn])


def sharpe_loss(w: torch.Tensor, R: torch.Tensor, cost: float) -> torch.Tensor:
    ex = net_excess(w, R, cost)
    return -ex.mean() / (ex.std() + 1e-8) * SQRT252


def split_days(first: int, cut: int, val_days: int, horizon: int = 2, embargo: int = 5) -> tuple[np.ndarray, np.ndarray]:
    """Training and validation days for a model trained before day `cut`. The last day with a known label is cut - 1 - horizon (its label ends on day t + horizon). Validation is the
    last `val_days` of them; training stops `horizon + embargo` days before it, so no training label reaches into validation."""
    last = cut - 1 - horizon
    v0 = last - val_days + 1
    train_end = v0 - 1 - horizon - embargo
    if train_end < first:
        raise ValueError("the window is too short for a validation set")
    return np.arange(first, train_end + 1), np.arange(v0, last + 1)


def predict(model, X: np.ndarray, device: str = "cpu") -> np.ndarray:
    model.eval()
    with torch.no_grad():
        return weights(model, torch.as_tensor(X, dtype=torch.float32, device=device)).cpu().numpy()


def fit(cfg: Config, Xtr, Rtr, seed: int, device: str = "cpu", Xval=None, Rval=None, epochs: int | None = None):
    """Train from a zero-started head (equal weights). With validation data (and no fixed `epochs`), stop when it has not improved for `patience` epochs and return the model as it
    was at the best epoch (epoch 0 is the untrained prior). With `epochs`, train exactly that many. Returns (model, epochs, history)."""
    torch.manual_seed(seed)
    model = make_model(cfg.arch, Xtr.shape[2], cfg.seq_len, cfg.hidden).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
    xt, rt = (torch.as_tensor(a, dtype=torch.float32, device=device) for a in (Xtr, Rtr))
    stopping = Xval is not None and epochs is None
    if stopping:
        xv, rv = (torch.as_tensor(a, dtype=torch.float32, device=device) for a in (Xval, Rval))
        with torch.no_grad():
            best_val = sharpe_loss(weights(model, xv), rv, cfg.cost).item()
        best_ep, best_state, stale = 0, copy.deepcopy(model.state_dict()), 0
    hist = {"train": [], "val": []}
    for ep in range(1, (cfg.max_epochs if epochs is None else epochs) + 1):
        model.train()
        opt.zero_grad()
        loss = sharpe_loss(weights(model, xt), rt, cfg.cost)
        loss.backward()
        opt.step()
        hist["train"].append(loss.item())
        if stopping:
            model.eval()
            with torch.no_grad():
                v = sharpe_loss(weights(model, xv), rv, cfg.cost).item()
            hist["val"].append(v)
            if v < best_val - 1e-9:
                best_val, best_ep, best_state, stale = v, ep, copy.deepcopy(model.state_dict()), 0
            else:
                stale += 1
                if stale >= cfg.patience:
                    break
    if stopping:
        model.load_state_dict(best_state)
        return model, best_ep, hist
    return model, len(hist["train"]), hist
