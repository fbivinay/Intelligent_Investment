# Calculator, comparison, projection, web app and Fyers demo (sub-projects 4 to 6): Design

Date: 2026-10-01. Refines sections 11 to 13 of `2026-09-29-india-algo-system-design.md`. The user's go-ahead: "go ahead with calculator, finish all the jobs".

## 1. What it answers

For an amount, a start date, an end date, a risk level and a tax profile: what the product would have left after every charge and tax, what each alternative would
have left on the same terms, every number with its trace, and a labelled estimate of the range from the end date on.

## 2. The signal artifact the calculator replays

The frozen run wrote the product's target weights per risk level (`research/out/frozen/signal_<level>.csv`, 2013-04-01 to 2026-09-30). The spec of sub-project 3
says the artifact holds the weights of one reference account including its drawdown governor, so that weights depend on the date only. `research/artifact.py` runs
that reference account (Rs 10 lakh from 2013-04-01, governor at the cap, W1 harvesting) and writes the effective weights (target times the governor's multiplier,
the rest in the fund) to `research/out/signal/<level>.csv` with hashes. A user's account follows these weights with no governor of its own; their own drawdown can
exceed the cap, and the site says so.

## 3. Product replay (exact)

1. The fast simulator decides the orders for the user's amount, dates and tax profile on the effective weights (fills at the next day's VWAP with the slippage
   assumption, whole ETF units, the trading band, W1 harvesting, tax paid on the first trading day of each financial year).
2. `calc/replay.py` books every one of those orders again through the exact engine: Decimal, `engine.charges.order_charges` plus the depository charge, FIFO lots
   (`engine.lots.Inventory`), each financial year's tax by `engine.tax.investment_tax` with the user's profile, the opening fee and the yearly demat fee, and, when
   the end convention is "sell", the sale of everything at the last close. Every number is a trace node.
3. The result: money invested, gross end value, charges by kind, tax by financial year, net; "if still holding" beside it; the trade list and the tax lines as CSV.
   The fast simulator's and the exact books' final values are compared and the gap is reported.

The product starts on or after 2013-04-01 (its first April pick); an earlier start gives a message, not a number.

## 4. Alternatives (at least 8)

Bought on the start day and held, through the engine's traced buy-and-hold with the same amount, dates and profile: Nifty BeES, Junior BeES, Bank BeES, Gold BeES
(exchange close, whole units, demat charges), HDFC Nifty 50 index fund, ICICI Nifty Next 50 index fund, SBI Arbitrage fund, Nippon India Liquid fund (NAV, units
to three decimals, no demat; the direct plan from its first day in 2013, the regular plan for earlier starts, labelled). A fund or ETF that did not exist on the start
day gives a message.

## 5. Projection (estimate)

Per option: stationary block bootstrap (mean block 21 days) of its own daily returns up to the end date, 2,000 paths over the chosen horizon. The value at the horizon
is taxed on the rules of the last financial year in the tables, as one sale of the option's holdings (the product: split by its last weights into equity, gold and
fund), through `engine.tax.investment_tax` at a grid of gains and interpolated. Output: P10, P50, P90 before and after tax, chance of ending below the amount. Always
labelled ESTIMATE: rules assumed unchanged, history may flatter the future, one path of the past is resampled, not a forecast.

## 6. API and web app

- `calc/api.py`: one function, `calculate(params) -> dict` (JSON safe): validation and edge-case messages, the product at the chosen risk level, the alternatives, the
  projections, depth-limited traces by id, the CSV text, and stamps (data as of, rules verified on).
- `site/`: Next.js app (the old `web/` is not touched). Controls: amount, start, end, risk level, alternatives shown, tax regime, other income, slippage on or off,
  end convention, projection horizon. Results: a card per option with net, gross, charges, tax, if still holding, growth a year, worst fall; an ⓘ on every number
  opens its trace tree; a value chart with the projection fan dashed and badged ESTIMATE; CSV export; stamps; "not investment advice".
- `site/api/calc.py`: a Vercel Python function wrapping `calc.api.calculate`; `tools/bundle_site.py` copies the code, rule tables, data files and artifact it needs
  into the function before a deploy. Local: `python -m calc.server` serves the same function; `next dev` forwards `/api` to it.
- Deploying on Vercel is a publication and waits for the user's yes.

## 7. Fyers demo

A page "How it would run on Fyers": for a past date, the target weights, the account's holdings, the orders the replay placed the next day, each order as the JSON a
Fyers API v3 place-order call would take (field names checked against the Fyers documentation at build time), and the estimated Fyers fees from the engine. The
liquid fund leg is not an exchange order and is shown as such. Preview only: no credentials, no network call to Fyers, past dates only (a public page of live signals
may be investment advice under SEBI rules).

## 8. Choices made for you (say which to change)

1. The user's account follows the reference account's effective weights (governor included) and has no governor of its own (sub-project 3 spec).
2. Alternatives use the engine's buy-and-hold: ETFs at the close of the start day, funds at the NAV of the start day; the product decides at that close and fills
   the next day. Labelled.
3. Funds are held directly (no demat): no depository, opening or yearly demat fee; ETFs carry them.
4. FD is not in v1: no dated FD rate table is in the data yet. It needs its own sourced rule table.
5. Projection tax uses the last year's rules for a single sale at the horizon; the product's tax is split by its last weights.
