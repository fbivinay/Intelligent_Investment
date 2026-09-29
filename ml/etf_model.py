"""The ETF model: how much to hold in a spot Bitcoin ETF, a gold ETF and T-bills.

Decided after each US close from finished daily bars, traded at the next open:
  1. Two opinions on Bitcoin, averaged:
       - the Deep Momentum Network (etf_dl.py): a Transformer's calibrated
         position, 0..1, learned from 18 markets to maximise Sharpe ratio
       - eight trend signals: price above its 20/50/100/200-day average, and
         higher than 21/63/126/252 trading days ago; the share voting "hold"
  2. The result shrinks when Bitcoin's 20-day volatility runs above its own
     past-year median. It never grows above the opinion.
  3. Whatever Bitcoin leaves is offered to gold, decided the same way on gold.
  4. The rest sits in T-bills.
Without a network output (before 2019) the votes decide alone.

    python ml/etf_model.py      # self-check
"""

import numpy as np
import pandas as pd

SMA_DAYS = (20, 50, 100, 200)
MOMENTUM_DAYS = (21, 63, 126, 252)
N_VOTES = len(SMA_DAYS) + len(MOMENTUM_DAYS)


def votes(close: pd.Series) -> pd.Series:
    """How many of the 8 trend signals say 'hold', using closes up to each day."""
    v = [close > close.rolling(n).mean() for n in SMA_DAYS]
    v += [close > close.shift(n) for n in MOMENTUM_DAYS]
    return pd.concat(v, axis=1).sum(axis=1)


def vol_scale(close: pd.Series) -> pd.Series:
    """1.0 in normal conditions, below 1 when volatility runs above its past-year norm."""
    v = np.log(close).diff().rolling(20).std()
    return (v.rolling(252, min_periods=60).median() / v).clip(upper=1.0).fillna(0.0)


def signals(btc_close: pd.Series, gold_close: pd.Series, dl: pd.DataFrame | None = None) -> pd.DataFrame:
    """Everything the model decides, per day: network and votes, scaling, weights.
    `dl` holds the network's calibrated outputs (dl_btc, dl_gold); None = votes only."""
    s = pd.DataFrame({"btc_votes": votes(btc_close), "btc_vol": vol_scale(btc_close),
                      "gold_votes": votes(gold_close), "gold_vol": vol_scale(gold_close)})
    vb, vg = s["btc_votes"] / N_VOTES, s["gold_votes"] / N_VOTES
    if dl is None:
        s["dl_btc"], s["dl_gold"] = np.nan, np.nan
    else:
        s["dl_btc"], s["dl_gold"] = dl["dl_btc"].reindex(s.index), dl["dl_gold"].reindex(s.index)
    both = lambda net, v: ((net + v) / 2).fillna(v)          # average; votes alone where no network output
    s["w_btc"] = both(s["dl_btc"], vb) * s["btc_vol"]
    s["w_gold"] = (1 - s["w_btc"]) * both(s["dl_gold"], vg) * s["gold_vol"]
    s["w_cash"] = 1 - s["w_btc"] - s["w_gold"]
    return s


def weights(btc: pd.DataFrame, gold: pd.DataFrame, dl: pd.DataFrame | None = None) -> dict:
    s = signals(btc["close"], gold["close"], dl)
    return {"BTC": s["w_btc"], "GLD": s["w_gold"]}


def _self_check() -> None:
    rng = np.random.default_rng(0)
    days = pd.bdate_range("2020-01-01", periods=900)
    btc = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.04, 900))), days)
    gold = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, 900))), days)
    s = signals(btc, gold)

    # A decision on day t must not change when LATER prices change.
    cut = days[600]
    s2 = signals(btc.where(days < cut, btc * 3), gold.where(days < cut, gold * 0.5))
    assert np.allclose(s[days < cut], s2[days < cut], equal_nan=True), "the model reads the future"

    # The network half: averaged with the votes, and never lets weights leave [0, 1].
    net = pd.DataFrame({"dl_btc": rng.uniform(0, 1, 900), "dl_gold": rng.uniform(0, 1, 900)}, days)
    h = signals(btc, gold, net)
    assert np.allclose(h["w_btc"], (net["dl_btc"] + h["btc_votes"] / 8) / 2 * h["btc_vol"])
    s = h

    # No leverage and no shorting: weights stay in [0, 1] and never sum past 1.
    w = s[["w_btc", "w_gold", "w_cash"]]
    assert (w >= -1e-12).all().all() and (w.sum(axis=1) - 1).abs().max() < 1e-12

    # A steady rise ends fully voted in; a steady fall ends fully out.
    up = pd.Series(np.linspace(100, 300, 400), days[:400])
    down = pd.Series(np.linspace(300, 100, 400), days[:400])
    assert votes(up).iloc[-1] == N_VOTES and votes(down).iloc[-1] == 0
    print("ETF model self-check passed: no lookahead, no leverage")


if __name__ == "__main__":
    _self_check()
