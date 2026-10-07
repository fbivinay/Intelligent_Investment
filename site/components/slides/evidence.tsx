"use client";

// Evidence: the model on the site (the Max level) as a pipeline, one step per slide, then how it was chosen and what it cannot tell you.
// Rules are described from the code (research/maxmodel.py, research/stockmom.py, research/costs.py, calc/product.py); figures come from
// site/public/data/facts.json and lump.json, which tools/site_data.py reads out of the repository and the calculator.
import { motion } from "motion/react";
import type { ReactNode } from "react";
import { useData } from "@/lib/data";
import type { SlideDef } from "@/lib/deck";
import { count, day, inr, money, month, pct } from "@/lib/format";
import { groupColor, groupName, nameOf } from "@/lib/names";
import { Scatter, StackArea } from "../charts";
import { Appear, EASE, ENTER, Key, Rise, SWEEP } from "../ui";
import { Loading } from "./overview";
import { describe } from "./performance";

const STEPS = [
  { name: "Data", line: "Daily prices of every NSE share, the two ETFs and the liquid fund" },
  { name: "Signals", line: "Each share's trend score and the market's 200-day average" },
  { name: "Strategy", line: "Half in momentum shares, a quarter gold, a quarter Nasdaq 100" },
  { name: "Decision", line: "A re-pick each quarter and a market check each month, after the close" },
  { name: "Trade", line: "The next day, at that day's average price plus slippage" },
  { name: "Costs and tax", line: "Every charge and every tax, by the rules of its own date" },
  { name: "Result", line: "What is left after selling everything" },
];

/** The pipeline down the left edge while the slides walk through it; the marker moves to the step on screen. */
export function EvidenceRail({ slide }: { slide: number }) {
  const on = slide >= 1 && slide <= STEPS.length;
  if (!on) return null;
  return (
    <motion.nav className="rail" aria-label="The model, step by step" initial={{ opacity: 0, x: -24 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -24 }}
      transition={{ duration: 0.7, ease: EASE }}>
      <ol>
        {STEPS.map((s, i) => {
          const state = i === slide - 1 ? "now" : i < slide - 1 ? "done" : "next";
          return (
            <li key={s.name} className={`rail-step is-${state}`} aria-current={state === "now" ? "step" : undefined}>
              {state === "now" && <motion.span layoutId="rail-mark" className="rail-mark" transition={{ duration: 0.8, ease: SWEEP }} />}
              <span className="rail-n">{String(i + 1).padStart(2, "0")}</span>
              <span className="rail-name">{s.name}</span>
            </li>
          );
        })}
      </ol>
    </motion.nav>
  );
}

function useEvidence() {
  const { saved } = useData();
  return saved ? { a: saved.lump, f: saved.facts, model: saved.lump.results.find((r) => r.kind === "product")! } : null;
}

function Shell({ step, title, lead, children, aside }: { step?: number; title: string[]; lead?: ReactNode; children?: ReactNode; aside?: ReactNode }) {
  return (
    <div className={step ? "ev railed" : "ev"}>
      <div className="ev-head">
        {step && <Appear delay={0} className="ev-step"><span>Step {step} of {STEPS.length}</span></Appear>}
        <Rise className="statement" lines={title} />
        {lead && <Appear delay={0.3}><p className="lead">{lead}</p></Appear>}
      </div>
      <div className="ev-body">
        <div className="ev-main">{children}</div>
        {aside && <Appear delay={0.5} className="ev-aside">{aside}</Appear>}
      </div>
    </div>
  );
}

function What() {
  return (
    <div className="ev what">
      <div className="ev-head">
        <Rise className="statement" lines={["What is this model?"]} />
        <Appear delay={0.3}>
          <p className="lead wide">
            A fixed set of rules running one account: half in the Indian shares with the strongest recent trend, a quarter in a gold ETF and a quarter
            in a Nasdaq 100 ETF. When the Indian market turns down, the share half waits in a liquid fund. No machine learning and no price forecasts:
            it ranks, checks one market signal and rebalances on fixed days.
          </p>
        </Appear>
      </div>
      <ol className="pipeline" aria-label="How the model works">
        {STEPS.map((s, i) => (
          <motion.li key={s.name} initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, ease: EASE, delay: ENTER + 0.45 + i * 0.09 }}>
            <span className="pl-n">{String(i + 1).padStart(2, "0")}</span>
            <span className="pl-name">{s.name}</span>
            <span className="pl-line">{s.line}</span>
            {i < STEPS.length - 1 && (
              <motion.span className="pl-arrow" aria-hidden initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} transition={{ duration: 0.5, ease: EASE, delay: ENTER + 0.8 + i * 0.09 }} />
            )}
          </motion.li>
        ))}
      </ol>
    </div>
  );
}

function Data() {
  const e = useEvidence();
  if (!e) return <Loading />;
  const { f, a } = e;
  const t0 = Date.parse(f.stocks.from), t1 = Date.parse(f.stocks.to), at = (iso: string) => `${((Date.parse(iso) - t0) / (t1 - t0)) * 100}%`;
  return (
    <Shell step={1} title={["What it reads"]} lead="Only what was published on or before each day: the exchange's own daily files, the fund's daily value and the dated rules.">
      <div className="figures">
        <Appear delay={0.4} className="figure"><b>{count(f.stocks.symbols)}</b><span>NSE shares, every one that traded from {month(f.stocks.from)} to {month(f.stocks.to)}: {(f.stocks.rows / 1e6).toFixed(1)} million daily prices</span></Appear>
        <Appear delay={0.5} className="figure"><b>4</b><span>funds: the Nifty 50 ETF for the market signal, the Gold and Nasdaq 100 ETFs from the exchange, the liquid fund&rsquo;s daily value from AMFI</span></Appear>
        <Appear delay={0.6} className="figure"><b>{f.rules.rows}</b><span>dated rules for every charge and tax from {f.rules.from.slice(0, 4)}, each with its source, checked on {day(f.rules.verified_on)}</span></Appear>
      </div>
      <Appear delay={0.75} className="coverage">
        <div className="cov-track">
          <motion.span className="cov-fill" initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} transition={{ duration: 1.4, ease: SWEEP, delay: ENTER + 0.8 }} />
          {[
            { at: f.stocks.from, top: "Share data starts", sub: month(f.stocks.from) },
            { at: a.inputs.start, top: "First pick", sub: `${day(a.inputs.start)}, after a year of history` },
            { at: f.stocks.to, top: "Data ends", sub: day(f.stocks.to) },
          ].map((m) => (
            <span key={m.top} className="cov-mark" style={{ left: at(m.at) }}><i /><b>{m.top}</b><small>{m.sub}</small></span>
          ))}
        </div>
        <p className="fine">Shares that later stopped trading stay in the data, so the past is not judged only by the companies that survived.</p>
      </Appear>
    </Shell>
  );
}

function Signals() {
  const e = useEvidence();
  if (!e) return <Loading />;
  const sh = e.a.activity!.allocation.shares;
  const inShares = sh.STOCKS.filter((v) => v > 0.05).length / sh.STOCKS.length;
  return (
    <Shell step={2} title={["Two signals, both from", "past prices only"]}>
      <div className="signals">
        <Appear delay={0.4} className="signal">
          <h3>Which shares</h3>
          <p className="formula">
            <span>Trend score</span><span className="eq">=</span>
            <span className="frac"><span>6-month return + 12-month return</span><span className="over">2 × the past year&rsquo;s volatility</span></span>
          </p>
          <p>Worked out for the 500 most traded shares (by their median daily trading over six months) that have a year of history and traded in the last week.
            The 30 highest scores are held.</p>
        </Appear>
        <Appear delay={0.55} className="signal">
          <h3>Whether to hold shares at all</h3>
          <p className="formula"><span>Nifty 50 ETF</span><span className="eq">vs</span><span>its average of the last {e.f.max.trend_days} days</span></p>
          <p>Above it: hold the 30 shares. Below it: the share half moves to the liquid fund until the market is back above.</p>
        </Appear>
      </div>
      <Appear delay={0.7} className="switch-strip">
        <div className="chart-title"><span>Where the share half was, 2017 to 2026</span>
          <span className="mini-legend"><span><Key color={groupColor("STOCKS")} />In shares, {pct(inShares, 0)} of the time</span><span><Key color={groupColor("LIQUID_FUND")} />In the liquid fund</span></span></div>
        <StackArea dates={e.a.activity!.allocation.dates} shares={{ STOCKS: sh.STOCKS.map((v) => (v > 0.05 ? 1 : 0)), LIQUID_FUND: sh.STOCKS.map((v) => (v > 0.05 ? 0 : 1)) }}
          order={["STOCKS", "LIQUID_FUND"]} color={groupColor} name={(g) => (g === "STOCKS" ? "In shares" : "In the liquid fund")} />
      </Appear>
    </Shell>
  );
}

function Strategy() {
  const e = useEvidence();
  if (!e) return <Loading />;
  const { f, a } = e;
  const parts = [
    { id: "STOCKS", share: f.max.momentum, name: "Momentum shares", line: "The 30 highest trend scores, equal parts: each a sixtieth of the account. In the liquid fund while the market is below its average." },
    ...Object.entries(f.max.fixed).map(([id, share]) => ({ id, share, name: nameOf(id), line: id === "GOLDBEES" ? "Gold, held all the time." : "100 large US companies in rupees, held all the time." })),
  ];
  const end = a.activity!.holdings;
  const total = end.reduce((x, h) => x + h.value, 0);
  const now = Object.entries(end.reduce<Record<string, number>>((o, h) => ((o[h.group] = (o[h.group] ?? 0) + h.value), o), {})).sort((x, y) => y[1] - x[1]);
  return (
    <Shell step={3} title={["One account,", "three parts"]} lead="On every decision day the account goes back to these shares of its value. In between, each part grows or shrinks with its prices. No borrowing, no short selling.">
      <div className="mixbar" aria-label="The target mix">
        {parts.map((p, i) => (
          <motion.div key={p.id} className="mix-part" initial={{ flexGrow: 0, opacity: 0 }} animate={{ flexGrow: p.share, opacity: 1 }}
            transition={{ duration: 1.2, ease: SWEEP, delay: ENTER + 0.4 + i * 0.12 }}>
            <span className="mix-fill" style={{ background: groupColor(p.id) }}><b>{pct(p.share, 0)}</b></span>
            <span className="mix-name">{p.name}</span>
            <span className="mix-line">{p.line}</span>
          </motion.div>
        ))}
      </div>
      <Appear delay={0.9} className="drifted">
        <span className="drift-label">On {day(a.inputs.end)}, after drifting since the last decision:</span>
        {now.map(([g, v]) => <span key={g} className="drift-item"><Key color={groupColor(g)} />{groupName(g)} <b>{pct(v / total, 0)}</b></span>)}
      </Appear>
    </Shell>
  );
}

function Decision() {
  const e = useEvidence();
  if (!e) return <Loading />;
  const days = e.a.activity!.days;
  const recent = [...days].reverse().find((d) => ["Switch to safety", "Back into shares", "Re-pick"].includes(describe(d).title));
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return (
    <Shell step={4} title={["When it decides"]} lead="Decisions are made after the market closes, on fixed days. Nothing is decided in between.">
      <div className="calendar" aria-label="A year of decision days">
        {months.map((m, i) => {
          const q = i % 3 === 0;
          return (
            <motion.div key={m} className={q ? "cal-m q" : "cal-m"} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, ease: EASE, delay: ENTER + 0.4 + i * 0.05 }}>
              <span className="cal-dot" />
              <span className="cal-name">{m}</span>
              <span className="cal-what">{q ? "Re-pick and market check" : "Market check"}</span>
            </motion.div>
          );
        })}
      </div>
      <div className="rules">
        <Appear delay={0.9}><p><b>First trading day of each quarter.</b> Rank the shares again and hold the new 30; the whole account goes back to half, a quarter and a quarter.</p></Appear>
        <Appear delay={1.0}><p><b>First trading day of each month.</b> If the Nifty 50 ETF is below its 200-day average, the share half moves to the liquid fund. When it is back above, the 30 are picked again at once.</p></Appear>
        {recent && (
          <Appear delay={1.1} className="example">
            <span className="ex-when">Most recent, {day(recent.date)}</span>
            <span className="ex-what"><b>{describe(recent).title}.</b> {describe(recent).text}.</span>
          </Appear>
        )}
      </div>
    </Shell>
  );
}

function Trade() {
  const e = useEvidence();
  if (!e) return <Loading />;
  const { f, a } = e;
  const t = a.activity!.totals;
  const c = f.costs;
  const first = a.activity!.days[0];
  const firstIn = first ? Object.values(first.bought).reduce((x, y) => x + y, 0) : 0;
  return (
    <Shell step={5} title={["How it trades"]} lead="The rules decide at one day's close; the orders go in the next trading day, so no decision uses a price it could not have seen.">
      <div className="timeline2">
        {[
          { when: "Day 1, after the close", what: "Decide the new mix from prices up to that close." },
          { when: "Day 2, during the day", what: "Buy and sell at that day's average traded price (VWAP), worse by an assumed slippage." },
          { when: "Every order", what: "Whole shares only. Orders smaller than ₹5,000 (or 0.5% of a small account) are skipped, and gaps under 1% of the account are left alone." },
        ].map((s, i) => (
          <motion.div key={s.when} className="tl2" initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.7, ease: EASE, delay: ENTER + 0.4 + i * 0.15 }}>
            <span className="tl2-when">{s.when}</span><span className="tl2-what">{s.what}</span>
          </motion.div>
        ))}
      </div>
      <Appear delay={0.9} className="slip">
        <h3>Slippage assumed on every order</h3>
        <dl>
          <div><dt>Half the spread, shares</dt><dd>{pct(c.stock_half_spread, 2)}</dd></div>
          {Object.entries(c.etf_half_spread).map(([id, v]) => <div key={id}><dt>Half the spread, {nameOf(id)}</dt><dd>{pct(v, 2)}</dd></div>)}
          <div><dt>Market impact</dt><dd>{pct(c.impact, 1)} × √(order ÷ a normal day&rsquo;s trading)</dd></div>
          <div><dt>Most it can be</dt><dd>{pct(c.max_slippage, 0)}</dd></div>
        </dl>
        <p className="fine">On the ₹10 lakh account since {month(a.inputs.start)}: {count(t.orders)} orders on {count(t.trade_days)} days.</p>
      </Appear>
      {first && (
        <Appear delay={1.05} className="first-trade">
          <span className="ex-when">The first decision</span>
          <span>Made after the close on {day(a.inputs.start)}; its {first.buys} orders, {money(firstIn)} in all, went in on {day(first.date)}, the next trading day.</span>
        </Appear>
      )}
    </Shell>
  );
}

function CostsTax() {
  const e = useEvidence();
  if (!e) return <Loading />;
  const { f, model, a } = e;
  const top = [...model.charges_by_kind].sort((x, y) => y.value - x.value).slice(0, 5);
  return (
    <Shell step={6} title={["Every rupee, by the rules", "of its own date"]} lead={`${f.rules.rows} dated rules, from ${f.rules.from.slice(0, 4)} to today, each checked against its source. A trade in 2018 pays 2018's charges and 2018's tax.`}>
      <div className="two-lists">
        <Appear delay={0.4} className="list-block">
          <h3>Charges on each order</h3>
          <ul>
            <li>Fyers brokerage</li><li>Securities transaction tax</li><li>Exchange and SEBI fees</li><li>Stamp duty</li><li>GST on the charges</li>
            <li>Depository charge on each sale</li><li>Demat opening and yearly fees</li>
          </ul>
        </Appear>
        <Appear delay={0.5} className="list-block">
          <h3>Income tax, year by year</h3>
          <ul>
            <li>Short- and long-term gains on each lot, first in, first out</li><li>The rates and holding periods of the sale&rsquo;s date</li>
            <li>The yearly exemption, surcharge, cess and rebate</li><li>Your regime and your other income</li><li>Paid out of the account when the next financial year starts</li>
          </ul>
        </Appear>
        <Appear delay={0.6} className="list-block numbers">
          <h3>On the ₹10 lakh account</h3>
          <p className="big-pair"><b>{money(model.charges.value)}</b><span>charges</span></p>
          <p className="big-pair"><b>{money(model.tax.value)}</b><span>tax, {model.tax_by_fy.length} financial years</span></p>
          <ul className="small-list">{top.map((c) => <li key={c.label}><span>{c.label}</span><b>{inr(c.value)}</b></li>)}</ul>
          <p className="fine">New regime, {money(a.inputs.other_income, 0)} other income.</p>
        </Appear>
      </div>
    </Shell>
  );
}

const CHOSEN = "momT50+gold25+nasdaq25";
const SHOWN = ["nifty", "gold", "nasdaq", "mom", "momT", CHOSEN];
const MIX_LABEL: Record<string, string> = {
  nifty: "Nifty 50 ETF", gold: "Gold ETF", nasdaq: "Nasdaq 100 ETF", mom: "Momentum shares alone", momT: "Momentum with the switch",
  "momT50+gold25+nasdaq25": "The model, 50 / 25 / 25", "momT60+gold20+nasdaq20": "60 / 20 / 20", "momT70+gold30": "70 momentum, 30 gold",
  "momT50+growth50": "50 momentum, 50 six ETFs",
};

function Result() {
  const e = useEvidence();
  if (!e) return <Loading />;
  const { f, model } = e;
  const runs = [...f.universe_runs];
  const others = f.mixes.filter((m) => !SHOWN.includes(m.what));
  return (
    <Shell step={7} title={["The result, and", "how it was chosen"]}
      lead={<>On ₹10 lakh: {pct(model.growth)} a year after every charge and tax, with a worst fall of {pct(model.worst_fall, 0)}. Here is every choice that shaped it, and what the others gave on the same years.</>}
      aside={
        <div className="choices">
          <h3>The choices, in order</h3>
          <ol>
            <li><b>The trend score</b> follows a published momentum-index method, fixed before the first run.</li>
            <li><b>30 shares of the 500 most traded</b>, set beside other sizes on the same years (momentum shares alone, after tax):
              <table className="mini-table"><tbody>{runs.map((r) => (
                <tr key={`${r.picks}-${r.universe}`} className={r.picks === 30 && r.universe === 500 ? "on" : ""}><td>{r.picks} of {r.universe}</td><td>{pct(r.a_year)} a year</td><td>{pct(r.worst_fall, 0)} fall</td></tr>
              ))}</tbody></table>
            </li>
            <li><b>The market switch</b> was added to cut the shares&rsquo; worst fall.</li>
            <li><b>The 50 / 25 / 25 mix</b> was picked from a handful, on the chart.</li>
          </ol>
        </div>
      }>
      <Appear delay={0.4} y={0} className="scatter-wrap">
        <div className="chart-title"><span>A year after tax against the worst fall, 2017 to 2026</span></div>
        <Scatter x={(v) => pct(v, 0)} y={(v) => pct(v, 0)} points={f.mixes.filter((m) => SHOWN.includes(m.what)).map((m) => ({
          id: m.what, label: MIX_LABEL[m.what] ?? m.what, x: m.worst_fall, y: m.a_year, chosen: m.what === CHOSEN,
          group: ["nifty", "gold", "nasdaq"].includes(m.what) ? "asset" as const : "mix" as const,
        }))} />
        <p className="fine">
          Research runs as separate accounts, after each year&rsquo;s tax; held in one account the model gives the {pct(model.growth)} above.
          {others.length > 0 && <> Other mixes tried on the same years: {others.map((m) => `${MIX_LABEL[m.what] ?? m.what} (${pct(m.a_year)}, ${pct(m.worst_fall, 0)} fall)`).join("; ")}.</>}
        </p>
      </Appear>
    </Shell>
  );
}

function Limits() {
  const e = useEvidence();
  if (!e) return <Loading />;
  const { a, f } = e;
  const gap = a.check.product_books_less_fast_simulator_rupees;
  const nas = a.results.find((r) => r.id === "MON100");
  return (
    <div className="ev limits">
      <div className="ev-head"><Rise className="statement" lines={["What protects the result,", "and what it cannot tell you"]} /></div>
      <div className="limits-body">
        <Appear delay={0.35} className="col-good">
          <h3>Safeguards</h3>
          <ul>
            <li>Decisions see prices only up to that day&rsquo;s close and trade the next day. A test cuts the data at several days and checks that no earlier pick changes.</li>
            <li>All {count(f.stocks.symbols)} shares that traded since {f.stocks.from.slice(0, 4)} are in the data, not only today&rsquo;s survivors.</li>
            <li>An exact engine charges and taxes each order by the rules of its date, checked against hand calculations and the Fyers brokerage calculator, with about 1,500 automated tests.</li>
            {gap !== undefined && <li>Two separate books of the same account agree: the fast simulator and the exact books end {inr(Math.abs(gap))} apart after {count(a.activity?.totals.orders ?? 0)} orders.</li>}
          </ul>
        </Appear>
        <Appear delay={0.5} className="col-limit">
          <h3>Limits</h3>
          <ul>
            <li><b>Chosen with hindsight.</b> The 500-share universe, the market switch, the gold and Nasdaq ETFs and the 50 / 25 / 25 mix were picked after seeing 2017 to 2026, the same years shown here. There is no untouched test period for this mix.</li>
            <li><b>One path.</b> {Math.round((Date.parse(a.inputs.end) - Date.parse(a.inputs.start)) / 3.156e10 * 10) / 10} years, with strong years for gold and US shares{nas ? ` (the Nasdaq 100 ETF alone made ${pct(nas.growth)} a year)` : ""}.</li>
            <li><b>Data stand-ins.</b> A share that stops trading keeps its last price until the next re-pick sells it, and a real delisting can pay less. A daily move over 50% is treated as a missed corporate action.</li>
            <li><b>Small accounts.</b> Whole shares make a small account follow the 30 shares loosely.</li>
            <li><b>Your tax.</b> Results change with income and regime; {money(a.inputs.other_income, 0)} of other income sits at the new regime&rsquo;s rebate limit, where the first gains are taxed heavily.</li>
            <li><b>Not a promise.</b> Past results, not investment advice. No account is used and no order is ever sent.</li>
          </ul>
        </Appear>
      </div>
    </div>
  );
}

export const EVIDENCE: SlideDef[] = [
  { id: "what", title: "What this model is", Slide: What },
  { id: "data", title: "Data", Slide: Data },
  { id: "signals", title: "Signals", Slide: Signals },
  { id: "strategy", title: "Strategy", Slide: Strategy },
  { id: "decision", title: "Decision", Slide: Decision },
  { id: "trade", title: "Trade", Slide: Trade },
  { id: "costs", title: "Costs and tax", Slide: CostsTax },
  { id: "result", title: "Result and how it was chosen", Slide: Result },
  { id: "limits", title: "Safeguards and limits", Slide: Limits },
];

