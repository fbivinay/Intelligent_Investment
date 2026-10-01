# DeepTrend

A deep-learning model that decides, every US trading day, how much of your money
to hold in a US spot Bitcoin ETF (IBIT), a gold ETF (GLD) and T-bills. It is built for an
Indian resident investing under the Liberalised Remittance Scheme, and measured in
**rupees, after every Indian tax**, against what an Indian would otherwise buy.

**Site:** https://btc-paper-trader-fbivinays-projects.vercel.app

## The result that matters to an Indian investor

₹1,00,000 put in on 11 Jan 2024 (IBIT's launch), worth this much in hand at the end of
Sep 2026, after tax at the 30% slab. The rupee's fall (₹83 to ₹96 a dollar) is taxed as a
gain, so it is counted too.

| Option | In hand | Per year | Worst fall |
|---|---|---|---|
| Gold ETF in India (GOLDBEES) | ₹2,17,872 | +33.2% | −23% |
| Bitcoin ETF held (IBIT via LRS) | ₹1,86,483 | +25.8% | −40% |
| Bitcoin on an Indian exchange | ₹1,86,585 | +25.9% | −43% |
| **DeepTrend model** | **₹1,65,801** | **+20.5%** | **−16%** |
| Bank FD (SBI, 1 year) | ₹1,12,990 | +4.6% | 0% |
| Nifty 50 ETF (NIFTYBEES) | ₹1,10,575 | +3.8% | −15% |

The model roughly quadruples Nifty and FD returns, and takes less than half the falls of
holding Bitcoin. The site lets you pick your own slab; lower slabs raise the model most,
because its gains are short-term.

## The deep learning model

A **Deep Momentum Network** (Lim, Zohren & Roberts, University of Oxford, 2019).

- **Why this model:** our first model, an LSTM, guessed Bitcoin's 4-hour direction right
  44.3% of the time (37.6% by chance) and still lost money: a 0.04% edge against 0.25% fees.
  So this network is not trained to guess. Its loss is minus the Sharpe ratio of the
  positions it takes, so it learns directly to earn more per unit of risk.
- **Why pooled:** Bitcoin has too little history for a neural network. The network learns
  from 18 markets at once (95,615 market-days since 2000: stocks, bonds, gold, silver, oil,
  Nifty, crypto), on scale-free features, then applies what it learned to Bitcoin and gold.
- **How it works:**
  1. Input: 63 trading days × 8 features (volatility-scaled returns over 1/21/63/126/252
     days, three MACD trend signals).
  2. A Transformer encoder (1 layer, 2 heads, causal mask) outputs a position from 0 to 1.
  3. The output is calibrated: each value is ranked against the network's own outputs over
     the previous 3 years.
  4. The live model averages this with the share of 8 classic trend votes. It then shrinks
     the position in wild markets, gives what's left to gold, and keeps the rest in T-bills.
- **How it was chosen:** 40 variants were trained on a Kaggle GPU: 5 architectures (LSTM,
  GRU, TCN, Transformer, MLP), each pooled or fine-tuned, raw or calibrated, alone or with
  the votes. Every one was retrained each January on data before that year, chosen on
  2019–2023 only, then tested on IBIT's real prices from 2024.

| Model | 2019–23 per year / worst fall | Real ETF 2024+ per year / worst fall |
|---|---|---|
| **Transformer, calibrated + 8 votes (live)** | +26.6% / −28% | +18.1% / −16% |
| 8 trend votes alone | +33.1% / −34% | +25.9% / −15% |
| Transformer, calibrated, alone | +22.9% / −21% | +10.3% / −16% |
| Buy & hold | +56.5% / −76% | +19.9% / −44% |

Honest note: on real prices the simple trend votes alone earned more. The hybrid keeps the
network in charge of half the decision and stays level with the rules on the years used to
choose.

## How it runs (free, no database)

```
GitHub Actions, Mon-Fri
  22:30 UTC decide  -> real prices (Yahoo) -> checks -> Transformer + votes -> decision
                    -> append to web/data/decisions.csv, rebuild web/data/site.json
                    -> commit -> Vercel rebuilds the site
  14:45 UTC execute -> broker orders, only if keys exist and SEND_ORDERS=on
```

- **Tamper-evident record:** `web/data/decisions.csv` is append-only, and git timestamps
  every row, so the live record cannot be edited after the fact without it showing.
- **Phone alerts (ntfy.sh):** sent when the split should change, so the model can be
  followed by hand in any broker app.
- **Safety rules in code:** buys come from cash only (no leverage), it never sells more than
  it holds, orders are capped, and duplicate orders are impossible. Stale or absurd data
  stops the run.
- **Yearly retraining:** each January the job trains that year's Transformer and commits
  its weights to `models/`.

## Repository

| Path | What |
|---|---|
| `ml/etf_dl.py` | the Deep Momentum Network: features, Transformer, training, calibration |
| `ml/dmn_kaggle.py` | the GPU run that compared all 40 variants |
| `ml/dl_results.csv`, `ml/dmn_walkforward.csv` | its results and walk-forward outputs |
| `ml/etf_model.py` | the live model: network + votes, volatility sizing, gold fill |
| `ml/etf_tax_sim.py` | Indian tax simulator: FIFO lots, 24-month rule, loss set-off |
| `ml/india_compare.py` | FD, Nifty, Indian gold, Indian Bitcoin, in rupees after tax |
| `ml/etf_daily.py` | the daily decide / execute job |
| `ml/broker.py` | Alpaca client and the cash-only rebalance |
| `ml/etf_research.py` | rule-based strategies compared the same way |
| `web/` | the Next.js site; `web/data/` is written by the daily job |

Every module has an assert-based self-check; CI runs them on every push.

Paper trading on real prices. Not investment advice. Confirm tax treatment with a
Chartered Accountant.
