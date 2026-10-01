# Strategy engine 3B: walk-forward selector, diagnostics, Kaggle GPU pipeline, deep model S6, tax wrapper W1, freeze

> Executed inline (author and executor are the same session); every task is test first, every module mutation-tested, every ruling written to the ledger
> `.superpowers/sdd/2026-10-01-strategy-engine-3b-selector-and-model/progress.md`. Plan 3A (panel, simulator, strategies S0 to S5, baseline) is done.

**Goal:** the first honest out-of-sample answer to "does anything beat plain holding after every tax and cost at the same risk?" (selector over S0 to S5), then the
deep model on a Kaggle GPU as one more candidate, the tax-aware wrapper, and the frozen test.

**Spec:** `docs/superpowers/specs/2026-10-01-strategy-engine-design.md` (sections 4 to 8). Plan 3A: `2026-10-01-strategy-engine-3a-baseline.md`.

**Tech:** Python 3.13, numpy, pandas, numba, scipy, pytest; PyTorch (CPU here, T4 GPU on Kaggle); Kaggle CLI 2.2.4 (user `fbivinay06`).

## Global constraints

- Everything in plan 3A's constraints still holds: decision after the close of t, fill at the next day's VWAP, research capital Rs 10 lakh, new regime with Rs 12 lakh
  other income, design period 2010-04-01 to 2023-09-29, frozen test 2023-10-01 to 2026-09-30 never loaded before the freeze, caps 10 / 20 / 30%, governor on every run.
- The selector at an April uses data before that day only. A strategy's run is a prefix property: the simulator is causal, so one full run gives its training-window result at
  every April (after-tax wealth at the cut = equity on the last day before it minus the tax of the financial year that just ended, which `Result.tax_by_fy` holds).
- Out-of-sample means the stitched weights: for each financial year the weights of the strategy picked at its April, simulated as ONE account starting 2013-04-01.
- Every candidate, every selector variant and every design-time experiment is written to the ledger; its count feeds the deflated Sharpe ratio.
- Kaggle: private kernels only, no internet, new slugs prefixed `india-algo-`; never touch the old `deeptrend-*`, `btc-*` kernels or datasets; the token in `~/.kaggle/access_token`
  is never printed or written anywhere. GPU training is not bit-repeatable, so the saved weights (with SHA-256) are the record.
- Push of the branch is the user's decision (the safety layer denied it earlier); nothing here pushes.

## Files

```
research/selector.py     Run, cut days, prefix statistics, pick rule (one-standard-error margin by stationary block bootstrap), walk-forward, stitching, stitched account
research/diagnostics.py  deflated Sharpe ratio, effective number of trials, probability of backtest overfitting (CSCV)
research/select.py       python -m research.select: all risk levels, selection logs, out-of-sample table
research/kaggle/         snapshot.py (dataset + manifest), kernel template, run.py (push, poll, pull, verify)
research/dl/             dataset.py, models.py, loss.py, train.py, walk.py (S6)
research/out/            selection_<risk>.csv, oos.md, kaggle/<run>/weights_*.npy + manifest.json
tests/test_research_*.py
```

## Tasks

1. **Runs and prefix statistics.** `Run(id, family, cap, equity, drawdown, tax_by_fy)` built from `sim.Result` (arrays only, so 2,000 runs fit in memory);
   `cut_days(dates, first)` = the first trading day of April on or after `first` for each year the panel covers; `prefix_stats(runs, c)` = after-tax wealth at the cut,
   after-tax growth a year, maximum drawdown so far, all vectorised over runs. Tests: hand-made equity paths give the stated growth and drawdown; the tax of the year that just ended
   comes off the wealth; the first trading day of April is chosen when 1 April is a weekend or holiday; a panel that starts after April has no cut that year.
2. **Pick rule.** `paired_se(a, b, seed)` = standard error of the annualised mean difference of daily log changes by stationary block bootstrap (mean block 21 days, 1,000 draws,
   seed from the cut date); `pick(stats, cap, s0, margin)` = best after-tax growth among runs whose drawdown so far is within the cap, kept only if its paired difference from S0
   exceeds `margin` standard errors, else S0; returns a log row (cut, eligible count, best, its growth and drawdown, S0's, difference, SE, decision, reason). Tests: the filter, the
   argmax, a clear winner is picked and a noisy small edge is not, S0 is kept when nothing is eligible, ties go to the first run, the bootstrap SE of iid normal differences is within 15% of
   sigma / sqrt(n) annualised, same inputs same SE, **changing any data after the cut changes nothing**.
3. **Walk-forward and stitching.** `walk_forward(runs, weights_of, dates, cap, margin)` returns the log and the stitched T x 5 weights (before the first cut S0's); `stitched_account` simulates them
   from the first cut as one fresh account with the governor, next to fresh accounts of S0, Nifty BeES, Gold BeES and the liquid fund from the same day. Tests: stitched weights equal the picked
   strategy's weights inside each financial year and S0's before the first cut; valid weights; end to end on a small synthetic panel with four candidates; the run on data cut at an April
   equals the full run up to that April.
4. **Diagnostics.** `deflated_sharpe(returns, n_trials, var_sr)`, `effective_trials(returns_matrix)`, `pbo(returns_matrix, blocks=16)`. Tests: N = 1 gives the plain probabilistic Sharpe by hand;
   the deflated value falls as N grows and rises with the Sharpe; PBO is near one half for independent noise strategies and zero when one strategy dominates in every block; effective trials
   is 1 for identical series and N for independent ones.
5. **Selection run.** `python -m research.select` runs S0 to S5 at each level (about 1 minute a level), the selector with margin 1 standard error (spec) and with the deflated margin
   (sqrt(2 ln N_eff) standard errors), writes `research/out/selection_<risk>_<margin>.csv` and `oos.md` (stitched account against S0 and the references: after-tax growth, after selling all,
   drawdown, Sharpe, turnover, tax, picks by family, PBO and DSR). Done when it is byte-identical on a second run. **This is the first honest out-of-sample number.** The shipping margin is
   chosen from theory (the deflated one) before the frozen test and said so; choosing between the two with the design-period result is disclosed hindsight.
6. **Kaggle pipeline.** `snapshot.py` writes `panel.npz`, `features.npz`, `manifest.json` (SHA-256 of every file and of the code), uploads as a private dataset; `run.py` pushes a kernel
   (GPU T4, internet off), polls its status, pulls the output, verifies the manifest hashes. Smoke job: a deterministic torch computation and the S3 weights computed on the GPU against the
   local numpy result. Tests (offline): manifest hashing, metadata JSON content, refusal to use a slug without the `india-algo-` prefix, the token never appears in any log line the module writes.
   Done when the smoke job on the real GPU matches the local result.
7. **S6 data and model code.** Causal feature tensor (train-only normalisation, missing P/E and VIX before they exist become zero with a flag), sequences, returns timed like the simulator (VWAP t+1 to t+2),
   five models (MLP, GRU, LSTM, TCN, small Transformer) ending in a softmax over the four ETFs and cash, loss = negative Sharpe of the daily return above the fund's plus a turnover penalty,
   training with purged and embargoed validation and early stopping, 3 seeds averaged, retrained each April on the expanding window. Tests (CPU, tiny): output weights valid; the loss equals a hand-computed
   Sharpe; the feature tensor at day t is unchanged when the data after t is cut (the causality harness); purge and embargo leave a gap of at least the horizon between train and validation; training
   lowers the loss on a synthetic task with a planted signal; same seed same weights on the CPU; a model trained on labels shifted one day into the future is caught by the validation gap test.
8. **S6 on the Kaggle GPU.** The committed configuration list (written before any result): architectures GRU, TCN and MLP; sequence 63 and 126 days; turnover penalty 0.0005 and 0.002; 3 seeds averaged:
   12 trials. Kernel trains every April 2013 to 2023, writes stitched out-of-sample weights per configuration; pulled, hashed, simulated locally with the governor, added to the ledger; the selector
   is rerun with S6 as candidates whose record is their own out-of-sample record (eligible after 3 years of it). Done when the table says, per risk level, whether S6 earned a pick and what it added.
9. **Tax wrapper W1.** In the simulator: `hold_days` (do not sell a lot within 30 or 60 days of turning long term unless the target for that asset is zero) and `harvest` (each financial year, in the last
   month, realise long-term equity gains up to the exemption by selling the lots with the largest gains and buying back the next day). Tests: against `engine` on a hand-worked scenario; fewer
   short-term sales on a synthetic path that crosses the one-year mark; harvest raises the cost basis by what it realised and the tax of the later sale falls by the rate times it; wealth never jumps.
   The four execution variants are evaluated on the stitched out-of-sample path (not multiplied into every trial).
10. **Replay, freeze, frozen test, artifacts.** Replay the stitched weights through `engine/` (exact) and state the gap to the fast simulator; git tag, code hash and data hash; one run of the frozen years
    (the selector re-picks each April 2024, 2025, 2026 from past data only); signal artifact per risk level (weights by date, selection log, ledger, diagnostics), its hash; a plain-words result.
    Any later change to the candidate list or the selector voids the frozen run and is stated. (S7, the futures overlay for Aggressive, is optional and only after this.)

## Review focus (inputs the tests above do not exercise, most likely to bite)

- A cut where S0's own drawdown already exceeds the cap (S0 is still the default; the log says so).
- A candidate whose wealth at the cut is zero or negative (growth NaN: never eligible, never picked).
- Two candidates with identical growth (the first in the ledger order wins, stated).
- An April cut when the panel's last day is before the cut (no pick, no crash).
- Stitching across a split, a unit change or the 2018-01-31 grandfathering date: wealth must not jump.
- A deep model whose weights are NaN for a day (the day falls back to S0, and the count is reported).
- A kernel that finishes with fewer output files than configurations (the pull must fail loudly).
