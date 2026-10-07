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
- Overview: what Rs 10 lakh became "N years ago" (chart with each line's after-tax end marked), all eleven options ranked by final value, a year or
  worst fall, the invitation.
- Performance: calculator (one-time from a month and a year, or monthly SIP; strategy; any of the ten alternatives; tax profile), where the money went,
  the path (value / return / fall, morphing), the model's trades (mix through time, every trading day, biggest days, holdings), invest today.
- Evidence: the Max model only, in seven steps: the model, data, signals, strategy, testing, costs and tax, limits (including that the mix was chosen on
  the same 2017-2026 years).
- Type: Archivo only, normal width for words, expanded for money. Colour: one emerald for the model; series hues validated with the dataviz checks.

## Defaults and their honesty notes

- The research tax profile (new regime, Rs 12 lakh other income) stays the default; it sits at the FY2025-26 rebate limit, so small SIPs over the last
  years lose most gains to tax. The calculator says so when that profile is used, and the profile can be changed.
- The hero uses Rs 10 lakh from the Max level's first day, not a chosen start. The Nasdaq 100 ETF ended higher over these years; the site says so with
  its worst fall beside it.

## Refinement pass (2026-10-08)

- Speed: `research/sim.py`'s `_run` loops only over the assets held or bought, and the long-term table is worked out once per asset class (runs are
  bit-identical to the saved ones); `calc/options.py` reads each price and NAV file once; `calc/api.py` answers a `warm` ping (the site sends it on load)
  and remembers recent lean answers. Bundled without numba, as on Vercel, locally: the first answer 2.4 s cold, then 0.7 to 2.6 s.
- Dates: each level starts at its first possible decision (Max on 3 Apr 2017: share data from January 2016 plus a year of prices; the ETF levels in
  April 2013). The one-time start is a month and a year inside that range.
- Comparisons: all ten alternatives `calc/options.py` supports (adds the Nifty 50 and Next 50 index funds and the arbitrage fund). The Overview ranks
  all eleven; the calculator starts with four and cuts a saved answer when options are removed (each option is worked out on its own).
- Invest today (`calc/future.py`, `site/public/data/future.json`): each option's past yearly return after charges and tax (Rs 10 lakh once, 2017-04-03
  to 2026-09-30) compounded over 1 to 20 years, once or monthly; the slide calls it an estimate, not a forecast. It replaces "behaviour next to one
  alternative".
- Evidence shows the latest real ranking (`facts.json` `ranking`, asserted equal to the model's own 30 picks).
- Fixed (user's go): the momentum ranking took every equity-segment instrument, ETFs included; by January 2026 half of the 30 picks were liquid, silver
  or gold ETFs, charged and taxed as shares. `research/stocks_build.py` now keeps each row's ISIN and `research/stockmom.py` ranks shares only (fund units,
  ISIN INF..., left out; the Nifty ETF still drives the market switch). Rebuilt `research/out/signal_max` and `stockmom.csv`: Max 20.3% a year after tax
  (21.4% before the fix), worst fall 18%; momentum alone 22.0% (22.8%), worst fall 48%. `research/out/mixes.txt`, which chose the 50 / 25 / 25 mix, is the
  record from before the fix and no longer goes to the site.
- Short screens (under 820 px and 680 px tall): tighter spacing and fewer secondary lines, so nothing runs under the bottom bar.
