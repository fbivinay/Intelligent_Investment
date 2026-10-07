"""The LSTM strategy: a long short-term memory network reads the last months of six ETFs and the market, and sets tomorrow's mix of the six and the
liquid fund. A strategy of its own, separate from the Max level; written down before any of its results were seen.

The design (after Zhang, Zohren and Roberts, "Deep Learning for Portfolio Optimization", 2020: an LSTM that outputs portfolio weights and is trained to
maximise the Sharpe ratio directly):
- What it holds: the Nifty 50, Nifty Next 50, Bank Nifty, Gold, Midcap 100 and Nasdaq 100 ETFs, and the liquid fund. Long only, no borrowing: a softmax
  gives seven weights that add to one. The last layer starts at zero, so the untrained network holds the seven in equal parts.
- What it reads: on each day, the last `seq_len` days of 76 numbers: for each ETF its return over 1, 5, 21, 63 and 252 days, its volatility over 21 and 63
  days, its fall from the year's high, its distance from the 50- and 200-day averages and a volatility spike (66); for the market India VIX and its
  5-day change, the Nifty's P/E and P/B percentiles, gold against equities over 63 days, the liquid fund's yield (6); and a flag for each of the four
  market numbers that can be missing (4). research/features.py works them out from prices up to that day; each is standardised with statistics from
  before the training cut.
- What it learns: weights decided after day t's close earn the return from the fill on day t+1 to the fill on day t+2 (the simulator's timing). The
  loss is minus the annualised Sharpe ratio of that return above the liquid fund's, after a cost of 0.3% of every rupee traded (charges, spread and
  some of the tax a sale brings).
- How it is tested: retrained on the first trading day of each April from 2017, on every day before it (an expanding window from 2012), and used for
  the year that follows: every day's weights come from a network that never saw that day. The last 126 training days are held out (purged and
  embargoed) to choose the number of epochs and, at each cut, the settings: sequence length 63 or 126 days, 32 or 64 hidden units, the pair with the
  best mean validation Sharpe over five seeds. That pair is refitted on all the days and the five seeds' weights are averaged.

numpy and torch only: the Kaggle kernel (research/kaggle/kernel_lstm.py) runs this file as it is.
"""
from __future__ import annotations

import copy
import warnings
from dataclasses import dataclass

import numpy as np
import torch
from torch import nn

PER_ASSET = ("ret1", "ret5", "ret21", "ret63", "ret252", "vol21", "vol63", "dd252", "dist50", "dist200", "vspike")
MARKET = ("vix", "vixchg5", "pe_pct", "pb_pct", "gold_vs_equity63", "cash_yield63")
MAY_BE_MISSING = ("vix", "vixchg5", "pe_pct", "pb_pct")
CONFIGS = [{"name": f"L{L}-h{h}", "seq_len": L, "hidden": h} for L in (63, 126) for h in (32, 64)]
SEEDS = (0, 1, 2, 3, 4)
COST = 0.003
VAL_DAYS = 126
MIN_SAMPLES = 300
SQRT252 = 252 ** 0.5


@dataclass(frozen=True)
class Fit:
    lr: float = 3e-3
    weight_decay: float = 1e-3
    max_epochs: int = 200
    patience: int = 20


def feature_matrix(feats: dict) -> tuple[np.ndarray, list[str]]:
    """T x F: each per-asset feature for every ETF in turn, then the market ones, then a 0/1 flag for each market feature that can be missing."""
    n = feats[PER_ASSET[0]].shape[1]
    cols, names = [], []
    for k in PER_ASSET:
        for j in range(n):
            cols.append(feats[k][:, j])
            names.append(f"{k}:{j}")
    for k in MARKET:
        cols.append(feats[k])
        names.append(k)
    for k in MAY_BE_MISSING:
        cols.append(np.isnan(feats[k]).astype(float))
        names.append(f"{k}:missing")
    return np.column_stack(cols), names


def first_valid(X: np.ndarray, names: list[str]) -> int:
    """The first day every feature that is always present (not VIX, P/E, P/B or a flag) is known."""
    core = [i for i, n in enumerate(names) if not n.startswith(("vix", "pe_pct", "pb_pct")) and not n.endswith(":missing")]
    return int(np.flatnonzero(np.isfinite(X[:, core]).all(axis=1))[0])


def fit_norm(X: np.ndarray, start: int, upto: int) -> tuple[np.ndarray, np.ndarray]:
    with warnings.catch_warnings(), np.errstate(all="ignore"):
        warnings.simplefilter("ignore", RuntimeWarning)
        mu, sd = np.nanmean(X[start:upto], axis=0), np.nanstd(X[start:upto], axis=0, ddof=1)
    return np.where(np.isfinite(mu), mu, 0.0), np.where(np.isfinite(sd) & (sd > 0), sd, 1.0)


def normalise(X: np.ndarray, mu: np.ndarray, sd: np.ndarray, clip: float = 5.0) -> np.ndarray:
    Z = np.clip((X - mu) / sd, -clip, clip)
    return np.where(np.isnan(Z), 0.0, Z)


def sequences(Z: np.ndarray, days: np.ndarray, length: int) -> np.ndarray:
    """(N, length, F): for each day, the `length` rows that end on it."""
    days = np.asarray(days)
    if (days - length + 1 < 0).any():
        raise ValueError(f"a sequence of {length} days would start before the first row")
    return Z[days[:, None] + np.arange(-length + 1, 1)]


def labels(vwap: np.ndarray, cash: np.ndarray) -> np.ndarray:
    """T x (N + 1): row t is the return from the fill price on day t+1 to the one on day t+2, what weights decided after day t's close earn."""
    px = np.column_stack([vwap, cash])
    R = np.full(px.shape, np.nan)
    R[:-2] = px[2:] / px[1:-1] - 1
    return R


class Allocator(nn.Module):
    """LSTM over the window; its last hidden state, through one linear layer started at zero, gives the logits of the N + 1 weights."""
    def __init__(self, n_features: int, hidden: int, n_out: int):
        super().__init__()
        self.lstm = nn.LSTM(n_features, hidden, batch_first=True)
        self.head = nn.Linear(hidden, n_out)
        nn.init.zeros_(self.head.weight)
        nn.init.zeros_(self.head.bias)

    def forward(self, x):
        return torch.softmax(self.head(self.lstm(x)[0][:, -1]), dim=-1)


def sharpe_loss(w: torch.Tensor, R: torch.Tensor, cost: float) -> torch.Tensor:
    """Minus the annualised Sharpe ratio of the daily return above the liquid fund's (the last column), after cost x turnover."""
    turn = 0.5 * (w[1:] - w[:-1]).abs().sum(1)
    ex = (w * R).sum(1) - R[:, -1] - cost * torch.cat([torch.zeros(1, dtype=w.dtype, device=w.device), turn])
    return -ex.mean() / (ex.std() + 1e-8) * SQRT252


def split_days(first: int, cut: int, val_days: int = VAL_DAYS, horizon: int = 2, embargo: int = 5) -> tuple[np.ndarray, np.ndarray]:
    """Training and validation days for a network trained before day `cut`: validation is the last `val_days` days whose label is known before the cut;
    training stops `horizon + embargo` days before it, so no training label reaches into validation."""
    last = cut - 1 - horizon
    v0 = last - val_days + 1
    train_end = v0 - 1 - horizon - embargo
    if train_end < first:
        raise ValueError("the window is too short for a validation set")
    return np.arange(first, train_end + 1), np.arange(v0, last + 1)


def fit(Xtr, Rtr, hidden: int, seed: int, device: str, cost: float = COST, f: Fit = Fit(), Xval=None, Rval=None, epochs: int | None = None):
    """Train from the equal-weight start. With validation data (and no fixed `epochs`): stop after `patience` epochs without improvement and return the
    network as at its best epoch (0: the untrained prior), with that validation loss. With `epochs`: train exactly that many. Returns (model, epochs, val)."""
    torch.manual_seed(seed)
    model = Allocator(Xtr.shape[2], hidden, Rtr.shape[1]).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=f.lr, weight_decay=f.weight_decay)
    xt, rt = (torch.as_tensor(a, dtype=torch.float32, device=device) for a in (Xtr, Rtr))
    stopping = Xval is not None and epochs is None
    if stopping:
        xv, rv = (torch.as_tensor(a, dtype=torch.float32, device=device) for a in (Xval, Rval))
        with torch.no_grad():
            best = sharpe_loss(model(xv), rv, cost).item()
        best_ep, best_state, stale = 0, copy.deepcopy(model.state_dict()), 0
    for ep in range(1, (f.max_epochs if epochs is None else epochs) + 1):
        model.train()
        opt.zero_grad()
        sharpe_loss(model(xt), rt, cost).backward()
        opt.step()
        if stopping:
            model.eval()
            with torch.no_grad():
                v = sharpe_loss(model(xv), rv, cost).item()
            if v < best - 1e-9:
                best, best_ep, best_state, stale = v, ep, copy.deepcopy(model.state_dict()), 0
            else:
                stale += 1
                if stale >= f.patience:
                    break
    if stopping:
        model.load_state_dict(best_state)
        return model, best_ep, best
    return model, epochs, float("nan")


def predict(model, X: np.ndarray, device: str) -> np.ndarray:
    model.eval()
    with torch.no_grad():
        return model(torch.as_tensor(X, dtype=torch.float32, device=device)).cpu().numpy()


def walk(feats: dict, vwap: np.ndarray, cash: np.ndarray, cuts: list[int], configs=CONFIGS, seeds=SEEDS, device: str = "cpu", f: Fit = Fit(),
         progress=None) -> dict:
    """Out-of-sample weights: {"configs": {name: T x (N+1)}, "chosen": T x (N+1), "choice": [{cut, name, val_sharpe per config}]}. NaN before the first
    cut. Each cut's networks see only days before it; the chosen settings are the ones with the best mean validation Sharpe."""
    X, names = feature_matrix(feats)
    R = labels(vwap, cash)
    n_out, T = R.shape[1], len(cash)
    t0 = first_valid(X, names)
    cuts = [c for c in cuts if c < T]
    out = {c["name"]: np.full((T, n_out), np.nan) for c in configs}
    chosen, choice = np.full((T, n_out), np.nan), []
    for k, c in enumerate(cuts):
        end = cuts[k + 1] if k + 1 < len(cuts) else T
        mu, sd = fit_norm(X, t0, c)
        Z = normalise(X, mu, sd)
        scores = {}
        for cfg in configs:
            first = t0 + cfg["seq_len"] - 1
            days = np.arange(first, c - 2)                                    # the days whose label (to t + 2) is known before the cut
            out[cfg["name"]][c:end] = 1.0 / n_out
            try:
                train, val = split_days(first, c)
            except ValueError:
                continue
            if len(days) < MIN_SAMPLES:
                continue
            seq = lambda idx, L=cfg["seq_len"]: sequences(Z, idx, L)      # noqa: E731
            Xp, ws, vals = seq(np.arange(c, end)), [], []
            for seed in seeds:
                _, ep, v = fit(seq(train), R[train], cfg["hidden"], seed, device, f=f, Xval=seq(val), Rval=R[val])
                vals.append(v)
                if ep == 0:
                    ws.append(np.full((end - c, n_out), 1.0 / n_out))
                    continue
                model, _, _ = fit(seq(days), R[days], cfg["hidden"], seed, device, f=f, epochs=ep)
                ws.append(predict(model, Xp, device))
            out[cfg["name"]][c:end] = np.mean(ws, axis=0)
            scores[cfg["name"]] = float(-np.mean(vals))
        best = max(scores, key=scores.get) if scores else configs[0]["name"]
        chosen[c:end] = out[best][c:end]
        choice.append({"cut": int(c), "chosen": best, "val_sharpe": scores})
        if progress:
            progress(k + 1, len(cuts), best)
    return {"configs": out, "chosen": chosen, "choice": choice}
