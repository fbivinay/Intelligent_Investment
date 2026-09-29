"""DeepTrend on Kaggle GPU: Deep Momentum Networks, pooled pre-training + fine-tuning.

For every January 2019..2026 and every architecture:
  base  pooled training on 18 markets (windows every 21 days), minus-Sharpe loss
  ft    base, then fine-tuned on Bitcoin + gold windows only (every 5 days), lower lr
Positions are written raw and calibrated: each test-day output as a percentile of
the same network's outputs over the 3 years BEFORE the test year (past data only).
Output: positions.csv (date, asset, kind, variant, raw, pct).
"""
import glob
import os
import time

import numpy as np
import pandas as pd
import torch
from torch import nn

DEV = torch.device("cuda" if torch.cuda.is_available() else "cpu")
root = glob.glob("/kaggle/input/**/pooled.parquet", recursive=True)[0]
D = os.path.dirname(root)
FEATS = ["ret1", "ret21", "ret63", "ret126", "ret252", "macd8", "macd16", "macd32"]
long = pd.read_parquet(root)
long["date"] = pd.to_datetime(long["date"])
FRAMES = {m: g.set_index("date").sort_index()[FEATS + ["target"]] for m, g in long.groupby("market")}
DAYS = {"BTC": pd.to_datetime(pd.read_csv(f"{D}/btc_days.csv")["date"]),
        "GLD": pd.to_datetime(pd.read_csv(f"{D}/gld_days.csv")["date"])}
SEQ, SEEDS, YEARS = 63, (0, 1, 2), range(2019, 2027)
print("device", DEV, "markets", len(FRAMES), flush=True)


def windows(markets, end, stride):
    """63-day windows ending before `end`, every `stride` days; sorted by end date."""
    xs, ys, ends = [], [], []
    for m in markets:
        f = FRAMES[m]
        f = f[f.index < end].dropna()
        a, idx = f.to_numpy(np.float32), f.index
        for i in range(len(a) - SEQ, -1, -stride):
            xs.append(a[i:i + SEQ, :-1]); ys.append(a[i:i + SEQ, -1]); ends.append(idx[i + SEQ - 1])
    order = np.argsort(np.array(ends, dtype="datetime64[ns]"))
    return torch.tensor(np.array(xs)[order]), torch.tensor(np.array(ys)[order])


class Seq(nn.Module):
    def __init__(self, kind, n_in=8, h=32):
        super().__init__()
        self.kind = kind
        if kind in ("lstm", "gru"):
            self.body = (nn.LSTM if kind == "lstm" else nn.GRU)(n_in, h, batch_first=True)
        elif kind == "tcn":
            self.convs = nn.ModuleList([nn.Conv1d(n_in if i == 0 else h, h, 3, dilation=d)
                                        for i, d in enumerate((1, 2, 4, 8))])
        elif kind == "transformer":
            self.proj = nn.Linear(n_in, h)
            self.pos = nn.Parameter(torch.zeros(1, SEQ, h))
            self.body = nn.TransformerEncoder(nn.TransformerEncoderLayer(h, 2, 64, dropout=0.1, batch_first=True), 1)
        else:
            self.body = nn.Sequential(nn.Linear(n_in, h), nn.ELU(), nn.Linear(h, h), nn.ELU())
        self.drop = nn.Dropout(0.2)
        self.head = nn.Linear(h, 1)

    def forward(self, x):
        if self.kind in ("lstm", "gru"):
            z, _ = self.body(x)
        elif self.kind == "tcn":
            z = x.transpose(1, 2)
            for conv in self.convs:
                z = torch.relu(conv(nn.functional.pad(z, (conv.dilation[0] * 2, 0))))
            z = z.transpose(1, 2)
        elif self.kind == "transformer":
            t = x.shape[1]
            mask = torch.triu(torch.full((t, t), float("-inf"), device=x.device), 1)
            z = self.body(self.proj(x) + self.pos[:, :t], mask=mask)
        else:
            z = self.body(x)
        return torch.sigmoid(self.head(self.drop(z))).squeeze(-1)


def neg_sharpe(pos, y):
    pnl = (pos * y).flatten()
    return -(pnl.mean() / (pnl.std() + 1e-6)) * np.sqrt(252)


def train(kind, x, y, seed, init=None, lr=1e-3, epochs=60, patience=6, val=0.1):
    torch.manual_seed(seed); np.random.seed(seed)
    m = Seq(kind).to(DEV)
    if init is not None:
        m.load_state_dict(init)
    opt = torch.optim.Adam(m.parameters(), lr=lr)
    cut = int(len(x) * (1 - val))                      # validation = the most recent windows
    xt, yt = x[:cut].to(DEV), y[:cut].to(DEV)
    xv, yv = x[cut:].to(DEV), y[cut:].to(DEV)
    best, state, bad = -np.inf, None, 0
    for _ in range(epochs):
        m.train()
        perm = torch.randperm(len(xt), device=DEV)
        for i in range(0, len(xt), 128):
            b = perm[i:i + 128]
            opt.zero_grad()
            neg_sharpe(m(xt[b]), yt[b]).backward()
            nn.utils.clip_grad_norm_(m.parameters(), 1.0)
            opt.step()
        m.eval()
        with torch.no_grad():
            v = -neg_sharpe(m(xv), yv).item()
        if v > best:
            best, state, bad = v, {k: t.detach().clone() for k, t in m.state_dict().items()}, 0
        else:
            bad += 1
            if bad >= patience:
                break
    m.load_state_dict(state)
    return m.eval()


def predict(models, market, days):
    f = FRAMES[market]
    a = f[FEATS].fillna(0).to_numpy(np.float32)
    pos = {d: i for i, d in enumerate(f.index)}
    rows = [(d, pos[d]) for d in days if d in pos and pos[d] >= SEQ - 1]
    if not rows:
        return pd.Series(dtype=float)
    x = torch.tensor(np.array([a[i - SEQ + 1:i + 1] for _, i in rows])).to(DEV)
    with torch.no_grad():
        p = np.mean([m(x)[:, -1].cpu().numpy() for m in models], axis=0)
    return pd.Series(p, index=[d for d, _ in rows])


out = []
for kind in ("lstm", "gru", "tcn", "transformer", "mlp"):
    for y in YEARS:
        t0 = time.time()
        start = pd.Timestamp(f"{y}-01-01")
        end = start - pd.Timedelta(days=2)
        x, yy = windows(list(FRAMES), end, 21)
        base = [train(kind, x, yy, s) for s in SEEDS]
        xf, yf = windows(["BTC", "GLD"], end, 5)
        ft = [train(kind, xf, yf, s, init=b.state_dict(), lr=3e-4, epochs=30, patience=5, val=0.15)
              for s, b in zip(SEEDS, base)]
        for variant, models in (("base", base), ("ft", ft)):
            for asset in ("BTC", "GLD"):
                days = DAYS[asset]
                test = days[(days >= start) & (days < pd.Timestamp(f"{y + 1}-01-01"))]
                past = FRAMES[asset].index
                past = past[(past >= start - pd.DateOffset(years=3)) & (past < end)]
                p_test, p_past = predict(models, asset, test), predict(models, asset, past).to_numpy()
                # Too little past (Bitcoin's features start late 2018): no calibration possible, keep raw.
                pct = (np.searchsorted(np.sort(p_past), p_test.to_numpy()) / len(p_past)
                       if len(p_past) >= 60 else p_test.to_numpy())
                out.append(pd.DataFrame({"date": p_test.index, "asset": asset, "kind": kind,
                                         "variant": variant, "raw": p_test.to_numpy(), "pct": pct}))
        print(f"{kind} {y}: {len(x)} pooled + {len(xf)} fine-tune windows, {time.time() - t0:.0f}s", flush=True)
    pd.concat(out).to_csv("positions.csv", index=False)       # save progress after each architecture
print("done", flush=True)
