"""Deep Momentum Network: the deep-learning half of the live model.

Why this model (and not the LSTM we started with)
  Our first LSTM predicted 4-hour direction better than chance (44.3% vs 37.6%)
  and still lost money: accuracy is not profit. A Deep Momentum Network
  (Lim, Zohren & Roberts, Oxford, 2019) is trained on what we care about -- the
  Sharpe ratio of the positions it takes.

Why pooled across markets
  Bitcoin has ~2,000 daily bars before 2024: far too few for a neural network.
  Trends behave alike across markets, so the network learns from 18 of them
  (stocks, bonds, gold, silver, oil, Nifty, crypto; ~95,000 market-days) on
  scale-free features, then applies what it learned to Bitcoin and gold.

How it works
  input      63 trading days x 8 features: vol-scaled returns over 1/21/63/126/252
             days and three MACD trend signals (8/24, 16/48, 32/96)
  network    Transformer encoder (1 layer, 2 heads, width 32, causal mask)
  output     a position in [0, 1] per day -- long or cash, never short
  loss       minus the annualised Sharpe ratio of position x next-day return
  calibrated each output becomes its percentile among the same network's outputs
             on that asset over the 3 years before the year it trades, so a
             cautious network still spans the full 0..1 range -- past data only
  live model (calibrated network + share of the 8 trend votes) / 2, then
             volatility sizing and the gold fill (etf_model.signals)

Chosen among 5 architectures x {pooled, fine-tuned} x {raw, calibrated} x
{alone, + votes} on 2019-2023 only; see dmn_kaggle.py (the GPU run) and
dl_results.csv. Retrained every January on data before that year.

    python ml/etf_dl.py --eval positions.csv    # judge a Kaggle run with the tax simulator
"""

from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn

from etf_data import load, yahoo

POOL = ("SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "IEF", "GLD", "SLV", "USO", "DBC", "VNQ",
        "^NSEI", "^N225", "^GDAXI", "^FTSE", "ETH-USD", "BTC")
FEATS = ["ret1", "ret21", "ret63", "ret126", "ret252", "macd8", "macd16", "macd32"]
KIND, SEQ, SEEDS = "transformer", 63, (0, 1, 2)
MODELS = Path(__file__).resolve().parent.parent / "models"
WALK_FORWARD = Path(__file__).with_name("dmn_walkforward.csv")   # the Kaggle run's 2019+ outputs


def features(close: pd.Series) -> pd.DataFrame:
    """8 scale-free trend features from closes up to each day (Lim et al. 2019)."""
    r = close.pct_change()
    vol = r.ewm(span=60, min_periods=20).std()
    f = pd.DataFrame(index=close.index)
    for k in (1, 21, 63, 126, 252):
        f[f"ret{k}"] = close.pct_change(k) / (vol * np.sqrt(k))
    for s, l in ((8, 24), (16, 48), (32, 96)):
        macd = close.ewm(span=s).mean() - close.ewm(span=l).mean()
        q = macd / close.rolling(63).std()
        f[f"macd{s}"] = q / q.rolling(252).std()
    f["target"] = r.shift(-1) / vol                 # next-day return, volatility-scaled
    return f.clip(-10, 10)


def pooled(btc_close: pd.Series) -> dict:
    """{market: feature frame}; Bitcoin uses the same spliced series the model trades."""
    out = {}
    for tk in POOL:
        c = btc_close if tk == "BTC" else yahoo(tk, start=946684800)["close"]   # from 2000
        out[tk] = features(c).dropna(subset=["ret252", "macd32"])
    return out


def windows(frames: dict, end: pd.Timestamp, stride: int = 21):
    """63-day windows ending before `end`, every `stride` days, sorted by end date."""
    xs, ys, ends = [], [], []
    for f in frames.values():
        f = f[f.index < end].dropna()
        a, idx = f.to_numpy(np.float32), f.index
        for i in range(len(a) - SEQ, -1, -stride):
            xs.append(a[i:i + SEQ, :-1]); ys.append(a[i:i + SEQ, -1]); ends.append(idx[i + SEQ - 1])
    order = np.argsort(np.array(ends, dtype="datetime64[ns]"))
    return torch.tensor(np.array(xs)[order]), torch.tensor(np.array(ys)[order])


class Seq(nn.Module):
    def __init__(self, kind: str = KIND, n_in: int = 8, h: int = 32):
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
            self.body = nn.TransformerEncoder(nn.TransformerEncoderLayer(
                h, 2, 64, dropout=0.1, batch_first=True), 1)
        else:
            self.body = nn.Sequential(nn.Linear(n_in, h), nn.ELU(), nn.Linear(h, h), nn.ELU())
        self.drop = nn.Dropout(0.2)
        self.head = nn.Linear(h, 1)

    def forward(self, x):
        if self.kind in ("lstm", "gru"):
            z, _ = self.body(x)
        elif self.kind == "tcn":
            z = x.transpose(1, 2)
            for conv in self.convs:                    # causal: pad the past only
                z = torch.relu(conv(nn.functional.pad(z, (conv.dilation[0] * 2, 0))))
            z = z.transpose(1, 2)
        elif self.kind == "transformer":
            t = x.shape[1]
            mask = torch.triu(torch.full((t, t), float("-inf"), device=x.device), 1)   # no peeking ahead
            z = self.body(self.proj(x) + self.pos[:, :t], mask=mask)
        else:
            z = self.body(x)
        return torch.sigmoid(self.head(self.drop(z))).squeeze(-1)


def neg_sharpe(pos, y):
    pnl = (pos * y).flatten()
    return -(pnl.mean() / (pnl.std() + 1e-6)) * np.sqrt(252)


def train(x, y, seed: int, kind: str = KIND) -> nn.Module:
    """Adam on minus Sharpe; the most recent 10% of windows pick the epoch."""
    torch.manual_seed(seed); np.random.seed(seed)
    m = Seq(kind)
    opt = torch.optim.Adam(m.parameters(), lr=1e-3)
    cut = int(len(x) * 0.9)
    xt, yt, xv, yv = x[:cut], y[:cut], x[cut:], y[cut:]
    best, state, bad = -np.inf, None, 0
    for _ in range(60):
        m.train()
        perm = torch.randperm(len(xt))
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
            best, state, bad = v, {k: t.clone() for k, t in m.state_dict().items()}, 0
        elif (bad := bad + 1) >= 6:
            break
    m.load_state_dict(state)
    return m.eval()


def predict(models: list, f: pd.DataFrame, days) -> pd.Series:
    """Average position of the ensemble for each day, from the 63 days ending that day."""
    a = f[FEATS].fillna(0).to_numpy(np.float32)
    pos = {d: i for i, d in enumerate(f.index)}
    rows = [(d, pos[d]) for d in days if d in pos and pos[d] >= SEQ - 1]
    if not rows:
        return pd.Series(dtype=float)
    x = torch.tensor(np.array([a[i - SEQ + 1:i + 1] for _, i in rows]))
    with torch.no_grad():
        p = np.mean([m(x)[:, -1].numpy() for m in models], axis=0)
    return pd.Series(p, index=[d for d, _ in rows])


def year_models(frames: dict, year: int) -> list:
    """The networks that trade `year`, trained on data before it. Trained once (each
    January, by the daily job), then loaded from models/."""
    path = MODELS / f"dmn-{KIND}-{year}.pt"
    if path.exists():
        out = []
        for st in torch.load(path, weights_only=True):     # tensors only, no pickled code
            m = Seq()
            m.load_state_dict(st)
            out.append(m.eval())
        return out
    x, y = windows(frames, pd.Timestamp(f"{year}-01-01") - pd.Timedelta(days=2))
    out = [train(x, y, s) for s in SEEDS]
    MODELS.mkdir(exist_ok=True)
    torch.save([m.state_dict() for m in out], path)
    return out


def calibrated(models: list, frames: dict, asset: str, days, year: int) -> pd.Series:
    """Each day's output as a percentile of the same networks' outputs on this asset
    over the 3 years before `year` -- a cautious network still spans 0..1."""
    start = pd.Timestamp(f"{year}-01-01")
    idx = frames[asset].index
    past = idx[(idx >= start - pd.DateOffset(years=3)) & (idx < start - pd.Timedelta(days=2))]
    ref = np.sort(predict(models, frames[asset], past).to_numpy())
    p = predict(models, frames[asset], days)
    return pd.Series(np.searchsorted(ref, p.to_numpy()) / len(ref), index=p.index)


def dl_signal(btc_close: pd.Series, gold_close: pd.Series) -> pd.DataFrame:
    """Calibrated network output (dl_btc, dl_gold) for every day from 2019.

    Up to the Kaggle run's last day: the recorded walk-forward outputs. After it:
    live inference with the current year's networks (trained on first use)."""
    hist = pd.read_csv(WALK_FORWARD, index_col="date", parse_dates=True)
    todo = btc_close.index[btc_close.index > hist.index.max()]
    if len(todo) == 0:
        return hist
    frames = pooled(btc_close)
    frames["GLD"] = features(gold_close).dropna(subset=["ret252", "macd32"])
    new = []
    for year in sorted(set(todo.year)):
        days = todo[todo.year == year]
        ms = year_models(frames, year)
        new.append(pd.DataFrame({"dl_btc": calibrated(ms, frames, "BTC", days, year),
                                 "dl_gold": calibrated(ms, frames, "GLD", days, year)}))
    return pd.concat([hist] + new)


def evaluate(path: str) -> pd.DataFrame:
    """Judge a Kaggle positions file (every architecture, pooled or fine-tuned, raw or
    calibrated, alone or with the 8 votes) like every other strategy: on 2019-23."""
    from etf_model import signals, vol_scale
    from etf_research import judge
    btc, gold, rate, _ = load()
    px = {"BTC": btc, "GLD": gold}
    s = signals(btc["close"], gold["close"])
    vb, vg = vol_scale(btc["close"]), vol_scale(gold["close"])
    pos = pd.read_csv(path, parse_dates=["date"])
    rows = {"8-vote trend rules": {"BTC": s["w_btc"], "GLD": s["w_gold"]},
            "Buy & hold": {"BTC": pd.Series(1.0, btc.index)}}
    for (kind, variant), g in pos.groupby(["kind", "variant"]):
        for col in ("raw", "pct"):
            b = g[g.asset == "BTC"].set_index("date")[col].reindex(btc.index).fillna(0)
            o = g[g.asset == "GLD"].set_index("date")[col].reindex(gold.index).fillna(0)
            tag = ("Transformer" if kind == "transformer" else kind.upper())
            tag += f"{', fine-tuned' if variant == 'ft' else ''}{', calibrated' if col == 'pct' else ''}"
            pb, pg = b * vb, o * vg
            rows[tag] = {"BTC": pb, "GLD": (1 - pb) * pg}
            hb, hg = (pb + s["btc_votes"] / 8 * vb) / 2, (pg + s["gold_votes"] / 8 * vg) / 2
            rows[tag + " + 8 votes"] = {"BTC": hb, "GLD": (1 - hb) * hg}
    res = pd.DataFrame({n: judge(px, w, rate) for n, w in rows.items()}).T
    return res.sort_values("dev_score", ascending=False)


def _self_check() -> None:
    """The network's output at day t must not change when LATER prices change."""
    rng = np.random.default_rng(0)
    days = pd.bdate_range("2015-01-01", periods=700)
    c = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.02, 700))), days)
    f1 = features(c).dropna(subset=["ret252", "macd32"])
    f2 = features(c.where(days < days[600], c * 3)).dropna(subset=["ret252", "macd32"])
    m = [Seq().eval()]
    test = f1.index[(f1.index >= days[400]) & (f1.index < days[600])]
    assert np.allclose(predict(m, f1, test), predict(m, f2, test), atol=1e-6), "the network reads the future"
    x = torch.tensor(f1[FEATS].fillna(0).to_numpy(np.float32)[None, :SEQ])
    out = m[0](x)
    assert out.shape == (1, SEQ) and ((out >= 0) & (out <= 1)).all(), "positions must be long or cash"
    print("deep learning self-check passed: causal, no lookahead, long-or-cash")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2 and sys.argv[1] == "--eval":
        r = evaluate(sys.argv[2])
        r.drop(columns="real_years").to_csv(Path(__file__).with_name("dl_results.csv"))
        print(r[["dev_cagr", "dev_dd", "dev_score", "real_cagr", "real_dd", "real_gross"]].head(20).to_string(
            float_format=lambda v: f"{v:+.3f}"))
    else:
        _self_check()
