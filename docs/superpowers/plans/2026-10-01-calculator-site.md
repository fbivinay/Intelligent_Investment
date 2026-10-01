# Calculator, comparison, projection, web app, Fyers demo: Implementation Plan

> Executed inline, test first; money paths (replay, buy-and-hold changes) mutation-tested. Spec: `docs/superpowers/specs/2026-10-01-calculator-site-design.md`.

**Goal:** the user picks amount, dates, risk level and tax profile; the site shows the product and eight alternatives after every charge and tax, each number with an ⓘ trace,
a labelled projection, and a Fyers preview; deployable on Vercel.

**Tech:** Python 3.13 (engine, research, new `calc/`), Next.js 16 + React 19 + TypeScript in `site/`, Vercel Python function.

## Global constraints

- The engine stays exact Decimal; every displayed money number comes from a trace node.
- Data and rules are read from the repository's committed files; nothing is fetched at run time.
- The old `web/`, `ml/`, `models/` and their workflow are not touched. No public deploy without the user's yes.

## Tasks

1. **Signal artifact.** `research/artifact.py`: `effective(target, mult)` and `build()` writing `research/out/signal/<level>.csv` and `manifest.json` from the frozen
   signals and a reference account run. Tests: rows sum to 1, risky weights scaled by the multiplier, the frozen signal's hash is checked, deterministic bytes.
2. **Buy-and-hold for funds.** `engine/scenario.buy_and_hold(..., unit_step=1, demat=True)`: fractional units for funds, no depository, opening or yearly demat fee
   without demat. Tests: the existing golden cases unchanged; units to three decimals; the trace balances.
3. **Options.** `calc/options.py`: the registry of the eight alternatives and three product levels; price and NAV bars, dividends, plan choice by start date. Tests:
   each option's first day; regular before the direct plan's first day; a start before an option existed is refused with its first day in the message.
4. **Exact replay.** `calc/replay.py`: `book(order_log, panel, days, amount, profile, rules, sell_at_end)` returns the traced waterfall, charges by kind, tax by
   financial year, the trade and tax lines. Tests: every node balances; the charges equal the engine's per order; the tax of a year equals `investment_tax` on that
   year's slices; within Rs 50 of the fast simulator; still-holding and sell-at-end differ by the liquidation's charges and tax.
5. **Product.** `calc/product.py`: `run(level, amount, start, end, profile, slippage, sell_at_end)`; series for the chart. Tests: start before 2013-04-01 refused; the
   weights are the artifact's; a slice in the middle of the history starts with cash and buys the next day.
6. **Projection.** `calc/project.py`: `bootstrap(returns, years, paths, seed)`, `tax_curve(...)`, `project(option result)`. Tests: P10 <= P50 <= P90; zero-volatility
   history gives its own growth; after-tax never above pre-tax for gains; same seed same numbers.
7. **API.** `calc/api.py`: `calculate(params) -> dict`, validation messages, traces by id (depth-limited), CSV, stamps. Tests: JSON round trip; every money figure has
   a trace id that exists; the edge cases (end before start, amount too small, product before 2013-04, a fund not yet started).
8. **Serving.** `calc/server.py` (local), `site/api/calc.py` (Vercel), `tools/bundle_site.py`. Tests: the handler answers a request with the same JSON as `calculate`.
9. **Web app.** `site/`: controls, cards with ⓘ, trace modal, chart with ESTIMATE fan, CSV, stamps, disclaimer. Checks: `next build` passes; a browser check that
   every number has an ⓘ and the trace opens.
10. **Fyers demo.** `calc/fyers.py` and the page: orders of a past date as Fyers API v3 payloads with the engine's fee estimate. Tests: payload fields, sides,
    quantities, the fund leg marked as not an exchange order.
11. **Deploy** on Vercel after the user's yes.
