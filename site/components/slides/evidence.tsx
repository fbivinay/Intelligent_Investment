"use client";

// Evidence: the model on the site (the Max level) in seven screens: what it is, its data, its signals, how a signal becomes trades, how it was
// tested, costs and tax, limits. Rules are described from the code (research/maxmodel.py, research/stockmom.py, research/costs.py, calc/product.py);
// figures come from site/public/data/facts.json and lump.json, which tools/site_data.py reads out of the repository and the calculator.
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useState, type ReactNode } from "react";
import { useData } from "@/lib/data";
import type { SlideDef } from "@/lib/deck";
import { count, day, inr, money, month, pct, signed } from "@/lib/format";
import { groupColor, groupName, nameOf } from "@/lib/names";
import { Appear, Arrow, EASE, ENTER, Rise, SWEEP } from "../ui";
import { Loading } from "./overview";
import { describe } from "./performance";

const STEPS = ["Model", "Data", "Signals", "Strategy", "Testing", "Costs and tax", "Limits"];

/** The seven screens down the left edge; the marker moves to the one on screen. */
export function EvidenceRail({ slide }: { slide: number }) {
  return (
    <motion.nav className="rail" aria-label="Evidence, step by step" initial={{ opacity: 0, x: -24 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -24 }}
      transition={{ duration: 0.7, ease: EASE }}>
      <ol>
        {STEPS.map((s, i) => {
          const state = i === slide ? "now" : i < slide ? "done" : "next";
          return (
            <li key={s} className={`rail-step is-${state}`} aria-current={state === "now" ? "step" : undefined}>
              {state === "now" && <motion.span layoutId="rail-mark" className="rail-mark" transition={{ duration: 0.8, ease: SWEEP }} />}
              <span className="rail-n">{String(i + 1).padStart(2, "0")}</span>
              <span className="rail-name">{s}</span>
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

function Shell({ title, lead, className, children }: { title: string[]; lead?: ReactNode; className?: string; children?: ReactNode }) {
  return (
    <div className={`ev railed ${className ?? ""}`}>
      <div className="ev-head">
        <Rise className="statement" lines={title} />
        {lead && <Appear delay={0.3}><p className="lead">{lead}</p></Appear>}
      </div>
      <div className="ev-main">{children}</div>
    </div>
  );
}

type Stage = { name: string; line: string; detail: ReactNode; icon: ReactNode };

/** Stages joined by arrows. One is lit at a time: the flow walks itself until the viewer points at a stage, and the lit stage's detail shows below. */
function Flow({ stages }: { stages: Stage[] }) {
  const reduce = useReducedMotion();
  const [on, setOn] = useState(0);
  const [held, setHeld] = useState(false);
  useEffect(() => {
    if (held || reduce) return;
    const t = setInterval(() => setOn((k) => (k + 1) % stages.length), 3200);
    return () => clearInterval(t);
  }, [held, reduce, stages.length]);
  const pick = (i: number) => { setHeld(true); setOn(i); };
  return (
    <div className="flow">
      <ol className="flow-row" style={{ gridTemplateColumns: `repeat(${stages.length}, minmax(0, 1fr))` }}>
        {stages.map((s, i) => (
          <motion.li key={s.name} className={i === on ? "flow-stage on" : "flow-stage"} initial={{ opacity: 0, y: 22 }} animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: EASE, delay: ENTER + 0.4 + i * 0.1 }}>
            <button type="button" aria-pressed={i === on} onMouseEnter={() => pick(i)} onFocus={() => pick(i)} onClick={() => pick(i)}>
              {i === on && <motion.span layoutId="flow-lit" className="flow-lit" transition={{ duration: 0.55, ease: SWEEP }} />}
              <span className="flow-icon" aria-hidden>{s.icon}</span>
              <span className="flow-name">{s.name}</span>
              <span className="flow-line">{s.line}</span>
            </button>
            {i < stages.length - 1 && <span className="flow-arrow" aria-hidden><Arrow dir="right" /></span>}
          </motion.li>
        ))}
      </ol>
      <AnimatePresence mode="wait" initial={false}>
        <motion.div key={on} className="flow-detail" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.28 }}>
          <span className="flow-detail-n">{String(on + 1).padStart(2, "0")}</span>
          <div><b>{stages[on].name}</b>{stages[on].detail}</div>
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

const ICON = {
  data: <svg viewBox="0 0 24 24"><ellipse cx="12" cy="6" rx="7" ry="2.6" /><path d="M5 6v6c0 1.4 3.1 2.6 7 2.6s7-1.2 7-2.6V6M5 12v6c0 1.4 3.1 2.6 7 2.6s7-1.2 7-2.6v-6" /></svg>,
  features: <svg viewBox="0 0 24 24"><path d="M4 7h9M17 7h3M4 17h3M11 17h9" /><circle cx="15" cy="7" r="2" /><circle cx="9" cy="17" r="2" /></svg>,
  model: <svg viewBox="0 0 24 24"><path d="M5 19V10M10 19V5M15 19v-6M20 19v-3" /></svg>,
  signal: <svg viewBox="0 0 24 24"><path d="M6 21V4M6 5h11l-2.5 3.5L17 12H6" /></svg>,
  strategy: <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8" /><path d="M12 4v8l6.5 4" /></svg>,
  portfolio: <svg viewBox="0 0 24 24"><rect x="4" y="8" width="16" height="11.5" rx="2" /><path d="M9 8V6.5a3 3 0 0 1 6 0V8M4 13h16" /></svg>,
};

function Model() {
  return (
    <Shell title={["What is the model?"]} className="ev-model"
      lead="A set of rules, not a trained network. It ranks what trades on NSE by recent trend, holds the strongest 30 in half the account, keeps a quarter each in a gold ETF and a Nasdaq 100 ETF, and parks the half in a liquid fund while the market is below its 200-day average.">
      <Flow stages={[
        { name: "Market data", line: "Daily NSE prices, 2016 to 2026", icon: ICON.data,
          detail: <p>Everything traded in NSE&rsquo;s equity segment each day: close, high, low, quantity and value. Plus the Gold and Nasdaq 100 ETFs, and the liquid fund&rsquo;s daily value from AMFI.</p> },
        { name: "Features", line: "Return, volatility, liquidity, trend", icon: ICON.features,
          detail: <p>Worked out on each decision day from prices up to that day only: 6- and 12-month return, yearly volatility, median daily traded value, days of history, and the Nifty 50 ETF against its 200-day average.</p> },
        { name: "Model", line: "Score, rank, check the market", icon: ICON.model,
          detail: <p>Trend score = (6-month return + 12-month return) &divide; 2 &divide; yearly volatility, for the 500 most traded shares (ETFs left out). A fixed formula from a published momentum-index method: nothing is fitted.</p> },
        { name: "Signal", line: "30 picks, market on or off", icon: ICON.signal,
          detail: <p>Two outputs: the 30 highest scores, and a market state with two values, hold shares or hold the liquid fund. No price forecasts, no probabilities.</p> },
        { name: "Strategy", line: "Half, a quarter, a quarter", icon: ICON.strategy,
          detail: <p>Half the account in the 30 picks, equal parts; a quarter in the Gold ETF; a quarter in the Nasdaq 100 ETF. Picks renewed each quarter, the market checked each month.</p> },
        { name: "Portfolio", line: "Orders the next trading day", icon: ICON.portfolio,
          detail: <p>Orders fill the next trading day at its average price plus slippage, in whole shares. Every charge and tax is paid by the rules of its date.</p> },
      ]} />
      <Appear delay={1.1}>
        <p className="fine">
          Deep learning was tested too: five kinds of network, trained on GPU. On years they had not seen, they lost to a plain equal mix of ETFs, so it was dropped.
        </p>
      </Appear>
    </Shell>
  );
}

const FIELD: Record<string, string> = { close: "close", prev_close: "previous close", high: "high", low: "low", qty: "quantity", value: "value traded", isin: "ISIN" };

function Data() {
  const e = useEvidence();
  if (!e) return <Loading />;
  const { f, a } = e;
  const t0 = Date.parse(f.stocks.from), t1 = Date.parse(f.stocks.to), at = (iso: string) => `${((Date.parse(iso) - t0) / (t1 - t0)) * 100}%`;
  return (
    <Shell title={["What it reads"]} lead="Only what was published on or before each day: the exchange's daily files, the fund's daily value, and dated rules for every charge and tax.">
      <div className="data-figures">
        <Appear delay={0.35} className="dfig"><b>{count(f.stocks.symbols)}</b><span>instruments in NSE&rsquo;s equity segment: {count(f.stocks.symbols - f.stocks.funds)} shares, which it ranks, and {count(f.stocks.funds)} ETFs, which it does not</span></Appear>
        <Appear delay={0.45} className="dfig"><b>{(f.stocks.rows / 1e6).toFixed(1)}M</b><span>daily records, one per instrument per trading day</span></Appear>
        <Appear delay={0.55} className="dfig"><b>{f.stocks.fields.length}</b><span>fields each: {f.stocks.fields.map((c) => FIELD[c] ?? c).join(", ")}</span></Appear>
        <Appear delay={0.65} className="dfig"><b>{f.rules.rows}</b><span>dated rules for charges and tax since {f.rules.from.slice(0, 4)}, checked {day(f.rules.verified_on)}</span></Appear>
      </div>
      <div className="sources">
        {[
          { who: "NSE", what: "Daily equity files", line: "every instrument, every trading day" },
          { who: "NSE", what: "ETF prices", line: "Gold ETF, Nasdaq 100 ETF, Nifty 50 ETF" },
          { who: "AMFI", what: "Fund values", line: "the liquid fund, where the share half waits" },
        ].map((s, i) => (
          <motion.div key={s.what} className="src" initial={{ opacity: 0, x: -14 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.7, ease: EASE, delay: ENTER + 0.7 + i * 0.12 }}>
            <span className="src-who">{s.who}</span><b>{s.what}</b><span>{s.line}</span>
          </motion.div>
        ))}
        <motion.span className="flow-arrow" aria-hidden initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.5, delay: ENTER + 1.1 }}><Arrow dir="right" /></motion.span>
        <motion.div className="src out" initial={{ opacity: 0, x: -14 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.7, ease: EASE, delay: ENTER + 1.2 }}>
          <span className="src-who">Model</span><b>One table per day</b><span>prices up to that day, nothing later</span>
        </motion.div>
      </div>
      <Appear delay={1.3} className="coverage">
        <div className="cov-track">
          <motion.span className="cov-fill" initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} transition={{ duration: 1.4, ease: SWEEP, delay: ENTER + 1.3 }} />
          {[
            { at: f.stocks.from, top: "Data starts", sub: month(f.stocks.from) },
            { at: a.inputs.start, top: "First decision", sub: `${day(a.inputs.start)}, after a year of prices` },
            { at: f.stocks.to, top: "Data ends", sub: day(f.stocks.to) },
          ].map((m) => (
            <span key={m.top} className="cov-mark" style={{ left: at(m.at) }}><i /><b>{m.top}</b><small>{m.sub}</small></span>
          ))}
        </div>
        <p className="fine">Instruments that later stopped trading stay in, so the past is not judged only by the survivors.</p>
      </Appear>
    </Shell>
  );
}

function Signals() {
  const e = useEvidence();
  if (!e) return <Loading />;
  const { f, a } = e;
  const r = f.ranking;
  const top = r.top.slice(0, 8);
  const hi = Math.max(...top.map((t) => t.score));
  const stocks = a.activity!.allocation.shares.STOCKS ?? [];
  const inShares = (stocks.at(-1) ?? 0) > 0.05;
  return (
    <Shell title={["Data in, signal out"]} className="ev-signals">
      <div className="sig-flow">
        <Appear delay={0.3} className="sig-col">
          <span className="sig-k">Features</span>
          <ul className="feat">
            <li>6-month return</li><li>12-month return</li><li>Yearly volatility</li><li>Median traded value<small>keeps the 500 most traded shares</small></li>
            <li>Days of history<small>a year at least, traded last week</small></li><li>Nifty 50 ETF vs its {f.max.trend_days}-day average</li>
          </ul>
        </Appear>
        <span className="flow-arrow" aria-hidden><Arrow dir="right" /></span>
        <Appear delay={0.45} className="sig-col">
          <span className="sig-k">Model</span>
          <p className="formula"><span>score</span><span className="eq">=</span>
            <span className="frac"><span><span className="nb">6-month return</span> + <span className="nb">12-month return</span></span><span className="over">2 × yearly volatility</span></span></p>
          <p>Rank the 500; keep the 30 highest.</p>
          <p>Market below its average: the share half goes to the liquid fund instead.</p>
        </Appear>
        <span className="flow-arrow" aria-hidden><Arrow dir="right" /></span>
        <Appear delay={0.6} className="sig-col sig-out">
          <span className="sig-k">Signal on {day(r.day)}</span>
          <ol className="rank">
            {top.map((t, i) => (
              <li key={t.symbol}>
                <span className="rank-n">{i + 1}</span><span className="rank-sym">{t.symbol}</span>
                <span className="rank-bar"><motion.i initial={{ scaleX: 0 }} animate={{ scaleX: t.score / hi }} transition={{ duration: 0.9, ease: EASE, delay: ENTER + 0.8 + i * 0.05 }} /></span>
                <span className="rank-s">{t.score.toFixed(1)}</span>
              </li>
            ))}
          </ol>
          <p className="rank-more">…down to 30. Each held at a sixtieth of the account.</p>
          <p className="state"><span className={inShares ? "state-dot on" : "state-dot"} /><span>Market state on {day(a.inputs.end)}: <b>{inShares ? "hold shares" : "hold the liquid fund"}</b></span></p>
        </Appear>
      </div>
      <Appear delay={1.1}>
        <p className="fine">
          Shares only. ETFs trade in the same segment but are left out: a liquid ETF&rsquo;s tiny volatility would give it the top score, and a fund is
          taxed differently from a share. The Nifty 50 ETF is read only for the market switch.
        </p>
      </Appear>
    </Shell>
  );
}

function Strategy() {
  const e = useEvidence();
  if (!e) return <Loading />;
  const { f, a } = e;
  const days = a.activity!.days;
  const repick = [...days].reverse().find((d) => describe(d).title === "Re-pick");
  const turn = [...days].reverse().find((d) => ["Switch to safety", "Back into shares"].includes(describe(d).title));
  const end = a.activity!.holdings;
  const total = end.reduce((x, h) => x + h.value, 0);
  const now = Object.entries(end.reduce<Record<string, number>>((o, h) => ((o[h.group] = (o[h.group] ?? 0) + h.value), o), {})).sort((x, y) => y[1] - x[1]);
  const parts = [{ id: "STOCKS", share: f.max.momentum, name: "30 picks" }, ...Object.entries(f.max.fixed).map(([id, share]) => ({ id, share, name: nameOf(id) }))];
  return (
    <Shell title={["From signal to trades"]}>
      <div className="s2t">
        {[
          { k: "Signal", t: "30 picks and a market state", d: "Read after the close on decision days only: the first trading day of each quarter (re-pick) and of each month (market check)." },
          { k: "Rule", t: "Back to half, a quarter, a quarter", d: "Each pick gets a sixtieth of the account. Market below its average: that half sits in the liquid fund. Between decisions, weights drift with prices." },
          { k: "Action", t: "Orders the next trading day", d: "Sell what left the list, buy what joined, top up the ETFs, in whole shares. A gap under 1% of the account is left alone." },
        ].map((s, i) => (
          <motion.div key={s.k} className="s2t-step" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, ease: EASE, delay: ENTER + 0.3 + i * 0.22 }}>
            <span className="s2t-k">{s.k}</span><b>{s.t}</b><p>{s.d}</p>
            {i < 2 && <span className="flow-arrow" aria-hidden><Arrow dir="right" /></span>}
          </motion.div>
        ))}
      </div>
      <div className="mixbar slim" aria-label="The target mix">
        {parts.map((p, i) => (
          <motion.div key={p.id} className="mix-part" initial={{ flexGrow: 0, opacity: 0 }} animate={{ flexGrow: p.share, opacity: 1 }}
            transition={{ duration: 1.2, ease: SWEEP, delay: ENTER + 0.9 + i * 0.12 }}>
            <span className="mix-fill" style={{ background: groupColor(p.id) }}><b>{pct(p.share, 0)}</b></span>
            <span className="mix-name">{p.name}</span>
          </motion.div>
        ))}
      </div>
      <Appear delay={1.3} className="examples">
        {repick && <p><span className="ex-when">{day(repick.date)}</span><span><b>Re-pick.</b> {describe(repick).text}.</span></p>}
        {turn && <p><span className="ex-when">{day(turn.date)}</span><span><b>{describe(turn).title}.</b> {describe(turn).text}.</span></p>}
        <p><span className="ex-when">{day(a.inputs.end)}</span><span><b>Held, after drifting.</b> {now.map(([g, v]) => `${groupName(g)} ${pct(v / total, 0)}`).join(", ")}.</span></p>
      </Appear>
    </Shell>
  );
}

function Testing() {
  const e = useEvidence();
  if (!e) return <Loading />;
  const { f, a, model } = e;
  const t = a.activity!.totals;
  const yrs = model.years;
  const lo = Math.min(0, ...yrs.map((y) => y.value)), w = Math.max(0, ...yrs.map((y) => y.value)) - lo || 1;
  const x = (v: number) => `${((v - lo) / w) * 100}%`;
  return (
    <Shell title={["How it was tested"]} className="ev-testing"
      lead={<>A replay of every trading day from {day(a.inputs.start)} to {day(a.inputs.end)}: {count(t.orders)} orders, each charged and taxed. Result: {pct(model.growth)} a year after tax, worst fall {pct(model.worst_fall, 0)}.</>}>
      <div className="test-grid">
        <Appear delay={0.4} className="test-col">
          <h3>Kept honest by</h3>
          <ul className="checks">
            <li><b>No look-ahead.</b> A decision sees prices up to that close only. A test cuts the data at several days and checks no earlier pick changes.</li>
            <li><b>Realistic fills.</b> Next trading day, at its average price, plus {pct(f.costs.stock_half_spread, 2)} half-spread and a market-impact term, capped at {pct(f.costs.max_slippage, 0)}.</li>
            <li><b>No survivor bias.</b> Instruments that later stopped trading are in.</li>
            <li><b>Two books agree.</b> A fast simulator and exact rupee books end {inr(Math.abs(a.check.product_books_less_fast_simulator_rupees ?? 0))} apart.</li>
          </ul>
        </Appear>
        <Appear delay={0.55} className="test-col">
          <h3>Chosen on these same years</h3>
          <p className="warn">The switch, the two ETFs and the half / quarter / quarter mix were picked after seeing 2017 to 2026; the 30-of-500 rule was
            compared with other sizes on the same years. No hold-out or walk-forward test.</p>
          <table className="mini-table"><tbody>
            <tr><th colSpan={3}>Momentum alone, other sizes, after tax</th></tr>
            {f.universe_runs.map((r) => (
              <tr key={`${r.picks}-${r.universe}`} className={r.picks === 30 && r.universe === 500 ? "on" : ""}><td>{r.picks} of {r.universe}</td><td>{pct(r.a_year)} a year</td><td>fell {pct(r.worst_fall, 0)}</td></tr>
            ))}
          </tbody></table>
        </Appear>
        <Appear delay={0.7} className="test-col">
          <h3>Year by year</h3>
          <ul className="yrs">
            {yrs.map((y, i) => (
              <li key={y.year}>
                <span>{y.year}{y.partial ? "*" : ""}</span>
                <span className="yr-bar">
                  <span className="yr-zero" style={{ left: x(0) }} />
                  <motion.i className={y.value < 0 ? "neg" : ""} style={{ left: x(Math.min(y.value, 0)), width: `${(Math.abs(y.value) / w) * 100}%`, originX: y.value < 0 ? 1 : 0 }}
                    initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} transition={{ duration: 0.8, ease: EASE, delay: ENTER + 0.9 + i * 0.05 }} />
                </span>
                <b>{signed(y.value)}</b>
              </li>
            ))}
          </ul>
          <p className="fine">* part of a year. Before income tax.</p>
        </Appear>
      </div>
    </Shell>
  );
}

function CostsTax() {
  const e = useEvidence();
  if (!e) return <Loading />;
  const { f, model, a } = e;
  const top = [...model.charges_by_kind].sort((x, y) => y.value - x.value).slice(0, 4);
  return (
    <Shell title={["Every rupee, by the rules", "of its own date"]} lead={`${f.rules.rows} dated rules since ${f.rules.from.slice(0, 4)}, each checked against its source. A trade in 2018 pays 2018's charges and 2018's tax.`}>
      <div className="two-lists">
        <Appear delay={0.4} className="list-block">
          <h3>Charges on each order</h3>
          <ul>
            <li>Fyers brokerage</li><li>Securities transaction tax</li><li>Exchange and SEBI fees</li><li>Stamp duty, and GST on the charges</li>
            <li>Depository charge on each sale</li>
          </ul>
        </Appear>
        <Appear delay={0.5} className="list-block">
          <h3>Income tax, year by year</h3>
          <ul>
            <li>Short- and long-term gains on each lot, first in, first out</li><li>The rates of the sale&rsquo;s date</li>
            <li>Exemption, surcharge, cess and rebate</li><li>Your regime and other income</li>
          </ul>
        </Appear>
        <Appear delay={0.6} className="list-block numbers">
          <h3>On ₹10 lakh since {month(a.inputs.start)}</h3>
          <p className="big-pair"><b>{money(model.charges.value)}</b><span>charges</span></p>
          <p className="big-pair"><b>{money(model.tax.value)}</b><span>tax, {model.tax_by_fy.length} financial years</span></p>
          <ul className="small-list">{top.map((c) => <li key={c.label}><span>{c.label}</span><b>{inr(c.value)}</b></li>)}</ul>
        </Appear>
      </div>
    </Shell>
  );
}

function Limits() {
  const e = useEvidence();
  if (!e) return <Loading />;
  const { a } = e;
  const nas = a.results.find((r) => r.id === "MON100");
  const years = Math.round(((Date.parse(a.inputs.end) - Date.parse(a.inputs.start)) / 3.156e10) * 10) / 10;
  return (
    <Shell title={["What it cannot tell you"]} className="ev-limits">
      <Appear delay={0.35} className="col-limit">
        <ul>
          <li><b>Chosen with hindsight.</b> The switch, the two ETFs and the mix were picked after seeing 2017 to 2026, the years shown, and the 30-of-500 rule was compared with other sizes on them. No untouched test period.</li>
          <li><b>One path.</b> {years} years, with strong runs for gold and US shares{nas ? `: the Nasdaq 100 ETF alone made ${pct(nas.growth)} a year` : ""}.</li>
          <li><b>Data stand-ins.</b> An instrument that stops trading keeps its last price until the next re-pick sells it; a daily move over 50% is read as a missed corporate action.</li>
          <li><b>Small accounts</b> cannot hold 30 picks in equal parts; whole shares make them follow loosely.</li>
          <li><b>Your tax.</b> Results change with income and regime; {money(a.inputs.other_income, 0)} of other income sits at the new regime&rsquo;s rebate limit.</li>
          <li><b>Not a promise.</b> Past results, not investment advice. No account is used and no order is ever sent.</li>
        </ul>
      </Appear>
    </Shell>
  );
}

export const EVIDENCE: SlideDef[] = [
  { id: "model", title: "What the model is", Slide: Model },
  { id: "data", title: "Data", Slide: Data },
  { id: "signals", title: "Signals", Slide: Signals },
  { id: "strategy", title: "From signal to trades", Slide: Strategy },
  { id: "testing", title: "Testing", Slide: Testing },
  { id: "costs", title: "Costs and tax", Slide: CostsTax },
  { id: "limits", title: "Limits", Slide: Limits },
];
