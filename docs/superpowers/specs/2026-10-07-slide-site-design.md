# The website as a slide deck: design (2026-10-07)

The user's brief: replace the whole frontend; keep the backend, the engine, the rules and the data; three sections (Overview, Performance, Evidence) of
full-screen slides that replace each other; one-time and monthly (SIP) calculations; the model's trades; Evidence about the final model only; real numbers
everywhere; desktop only; motion as the main finish.

## What changed in the backend (all through the existing engine)

- `research/sim.py`: `simulate(..., deposits=)` pays money in at the start of given days; a payment day buys up to the weights at once (threshold
  `min_trade`, not the band). Zero deposits give the old run bit for bit (test). Refused with the governor (its drawdown would count payments as gains).
- `engine/scenario.py`: `buy_monthly` (a lot per purchase, FIFO at the sale, dividends on units held before each ex-date, fees and tax as
  `buy_and_hold`); one payment equals `buy_and_hold` exactly (test). `buy_and_hold` now ends through the shared `_close` (same traces, same values).
- `calc/paths.py`: payment schedule, growth index without payments, drawdowns, calendar years, deepest fall, XIRR (one payment = plain growth, test).
- `calc/product.py` / `calc/compare.py`: `monthly=True` runs; a year is XIRR for monthly plans; worst fall from the growth index.
- `calc/api.py`: `mode` (lump or sip), `lean` (no traces, CSV or projections: the website's call), per option `invested`, `profit`, `years`, `fall`,
  series with `invested` and `drawdown` (deepest point kept through thinning), and the model's `activity` (mix through time by group, every trading day
  with what was bought and sold, holdings at the end, totals).
- `tests/test_research_stockmom_causal.py`: the Max picks on data cut after a day equal the full run's picks up to that day (look-ahead check).
- `tools/site_data.py`: writes `site/public/data/lump.json` (Rs 10 lakh once from 2017-04-03), `sip.json` (Rs 5,000 a month, same years) and
  `facts.json` (data counts, rule rows, cost assumptions, the Max level's selection runs read from `research/out`).

## The site

- One deck (`components/Deck.tsx`) kept mounted by the layout across `/`, `/performance`, `/evidence`. Next slide wipes up over the old one (clip-path);
  the old one recedes as a rounded card; between sections the wipe is sideways. Wheel (one slide per gesture), arrow keys, the next button, dots and the
  section tabs. Reduced motion: a short cross-fade. Below 1024 px wide or 540 px tall: the "larger screen" message.
- Overview: what Rs 10 lakh became (chart with each line's after-tax end marked), all six options ranked with a year and worst fall, the invitation.
- Performance: calculator (one-time / monthly SIP, strategy, up to five alternatives, tax profile), where the money went, the path (value / return /
  fall, morphing), the model's trades (mix through time, every trading day, biggest days, holdings), behaviour next to one alternative.
- Evidence: the Max model only, as the pipeline Data, Signals, Strategy, Decision, Trade, Costs and tax, Result; then safeguards and limits, including
  that the mix was chosen on the same 2017-2026 years.
- Type: Archivo only, normal width for words, expanded for money. Colour: one emerald for the model; series hues validated with the dataviz checks.

## Defaults and their honesty notes

- The research tax profile (new regime, Rs 12 lakh other income) stays the default; it sits at the FY2025-26 rebate limit, so small SIPs over the last
  years lose most gains to tax. The calculator says so when that profile is used, and the profile can be changed.
- The hero uses Rs 10 lakh from the Max level's first day, not a chosen start. The Nasdaq 100 ETF ended higher over these years; the site says so with
  its worst fall beside it.
