"use client";

// Evidence: five questions, one picture each: what the model is, what data it reads, what goes into it, what it puts out, and how that becomes an
// investment. The model is the Max level's rule set (research/maxmodel.py, research/stockmom.py); figures come from site/public/data/facts.json and
// lump.json, which tools/site_data.py reads out of the repository and the calculator.
import { motion, useReducedMotion } from "motion/react";
import { useEffect, useState, type ReactNode } from "react";
import { useData } from "@/lib/data";
import type { SlideDef } from "@/lib/deck";
import { count, day, month } from "@/lib/format";
import { Appear, Arrow, EASE, ENTER, Rise, SWEEP } from "../ui";
import { Loading } from "./overview";
import { describe } from "./performance";

const STEPS = ["Model", "Data", "Features", "Signals", "Strategy"];

/** The five questions down the left edge; the marker moves to the one on screen. */
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
  return saved ? { a: saved.lump, f: saved.facts } : null;
}

function Shell({ title, className, children }: { title: string; className?: string; children?: ReactNode }) {
  return (
    <div className={`ev railed ${className ?? ""}`}>
      <div className="ev-head"><Rise className="statement" lines={[title]} /></div>
      <div className="ev-main">{children}</div>
    </div>
  );
}

const ICON = {
  data: <svg viewBox="0 0 24 24"><ellipse cx="12" cy="6" rx="7" ry="2.6" /><path d="M5 6v6c0 1.4 3.1 2.6 7 2.6s7-1.2 7-2.6V6M5 12v6c0 1.4 3.1 2.6 7 2.6s7-1.2 7-2.6v-6" /></svg>,
  features: <svg viewBox="0 0 24 24"><path d="M4 7h9M17 7h3M4 17h3M11 17h9" /><circle cx="15" cy="7" r="2" /><circle cx="9" cy="17" r="2" /></svg>,
  model: <svg viewBox="0 0 24 24"><path d="M5 19V10M10 19V5M15 19v-6M20 19v-3" /></svg>,
  signal: <svg viewBox="0 0 24 24"><path d="M6 21V4M6 5h11l-2.5 3.5L17 12H6" /></svg>,
  strategy: <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8" /><path d="M12 4v8l6.5 4" /></svg>,
  action: <svg viewBox="0 0 24 24"><path d="M4 12h12M12 7l5 5-5 5" /><path d="M20 5v14" /></svg>,
  trend: <svg viewBox="0 0 24 24"><path d="M3 17l6-6 4 4 8-8M15 7h6v6" /></svg>,
  risk: <svg viewBox="0 0 24 24"><path d="M2 12h3l3-7 4 14 3-9 2 2h5" /></svg>,
  liquidity: <svg viewBox="0 0 24 24"><path d="M5 20V12M10 20V6M15 20v-9M20 20V4" /></svg>,
  market: <svg viewBox="0 0 24 24"><path d="M3 15c3-1 5-6 8-6s5 4 10 1" /><path d="M3 18h18" strokeDasharray="2 3" /></svg>,
};

/* 1. What is our model? A chain read top to bottom; a dot runs down it. */
function Model() {
  const reduce = useReducedMotion();
  const steps = [
    { k: "Product", t: "Intelligent Investment Strategies", d: "Max and Growth" },
    { k: "Model", t: "Momentum time-series model", d: "Rules on daily prices: rank every share by its trend, check the market's trend" },
    { k: "Output", t: "Market signal", d: "Market on or off, and the 30 strongest shares" },
    { k: "Result", t: "Investment strategy", d: "Max: the 30 shares in half the account, gold and Nasdaq 100 a quarter each" },
  ];
  return (
    <Shell title="What is our model?" className="ev-model">
      <ol className="chain">
        {!reduce && <motion.span className="chain-dot" aria-hidden initial={{ top: "0%", opacity: 0 }} animate={{ top: ["0%", "100%"], opacity: [0, 1, 1, 0] }}
          transition={{ duration: 3.2, ease: "easeInOut", repeat: Infinity, repeatDelay: 0.6, delay: ENTER + 1.6 }} />}
        {steps.map((s, i) => (
          <motion.li key={s.k} initial={{ opacity: 0, x: -18 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.8, ease: EASE, delay: ENTER + 0.3 + i * 0.25 }}>
            <span className="chain-node" aria-hidden />
            <span className="chain-k">{s.k}</span>
            <b className="chain-t">{s.t}</b>
            <span className="chain-d">{s.d}</span>
          </motion.li>
        ))}
      </ol>
      <Appear delay={1.5}><p className="fine">Growth, the second strategy, needs no signal: six ETFs in equal parts, reset each April.</p></Appear>
    </Shell>
  );
}

const yr = (iso: string) => iso.slice(0, 4);
const price = (n: number) => n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/* 2. What data do we use? The facts on the left, real rows on the right. */
function Data() {
  const e = useEvidence();
  if (!e) return <Loading />;
  const { f } = e;
  const shares = f.stocks.symbols - f.stocks.funds;
  const facts = [
    { k: "Source", v: "NSE and AMFI", d: "the exchange's daily files, the fund's daily value" },
    { k: "Period", v: `${yr(f.stocks.from)} → ${yr(f.stocks.to)}`, d: `every trading day; ETFs from ${yr(f.etfs.from)}` },
    { k: "Format", v: "Daily time series", d: "high, low, close, volume, value traded" },
    { k: "Records", v: `${(f.stocks.rows / 1e6).toFixed(1)} million`, d: `daily rows of shares, and ${count(f.etfs.rows)} of ETFs` },
    { k: "Assets", v: `${count(shares)} shares, ${f.etfs.symbols.length} ETFs`, d: "and the liquid fund" },
  ];
  return (
    <Shell title="What data do we use?" className="ev-data">
      <dl className="data-strip">
        {facts.map((x, i) => (
          <motion.div key={x.k} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, ease: EASE, delay: ENTER + 0.3 + i * 0.12 }}>
            <dt>{x.k}</dt><dd><b>{x.v}</b><span>{x.d}</span></dd>
          </motion.div>
        ))}
      </dl>
      <Appear delay={0.9} className="data-form">
        <div className="form-head"><span className="badge-src">NSE</span><Arrow dir="right" /><span>In what form: one row per share per trading day. Three real rows:</span></div>
        <table className="rows">
          <thead><tr><th>Date</th><th>Share</th><th>High</th><th>Low</th><th>Close</th><th>Volume</th><th>Value traded</th></tr></thead>
          <tbody>
            {f.sample.map((r, i) => (
              <motion.tr key={r.symbol} initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.6, ease: EASE, delay: ENTER + 1.2 + i * 0.15 }}>
                <td>{day(r.date)}</td><td><b>{r.symbol}</b></td><td>{price(r.high)}</td><td>{price(r.low)}</td><td>{price(r.close)}</td><td>{count(r.qty)}</td>
                <td>₹{count(Math.round(r.value / 1e7))} crore</td>
              </motion.tr>
            ))}
            <tr className="more-rows"><td colSpan={7}>and {(f.stocks.rows / 1e6).toFixed(1)} million more like these, {month(f.stocks.from)} to {month(f.stocks.to)}</td></tr>
          </tbody>
        </table>
        <div className="form-foot"><Arrow dir="down" /><span className="badge-model">into the model</span></div>
      </Appear>
    </Shell>
  );
}

/* 3. What goes into the model? Six features in four groups. */
function Features() {
  const e = useEvidence();
  if (!e) return <Loading />;
  const groups = [
    { name: "Momentum", icon: ICON.trend, items: ["6-month return", "12-month return"] },
    { name: "Risk", icon: ICON.risk, items: ["1-year volatility"] },
    { name: "Liquidity", icon: ICON.liquidity, items: ["Median daily value traded", "A year of trading history"] },
    { name: "Market trend", icon: ICON.market, items: [`Nifty 50 ETF against its ${e.f.max.trend_days}-day average`] },
  ];
  const n = groups.reduce((x, g) => x + g.items.length, 0);
  return (
    <Shell title="What goes into the model?" className="ev-features">
      <div className="feat-head">
        <Appear delay={0.2} className="feat-count"><b>{n}</b><span>features, worked out each decision day from prices up to that day</span></Appear>
      </div>
      <div className="feat-groups">
        {groups.map((g, i) => (
          <motion.div key={g.name} className="feat-group" initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: EASE, delay: ENTER + 0.5 + i * 0.15 }}>
            <span className="feat-icon" aria-hidden>{g.icon}</span>
            <b>{g.name}</b>
            <ul>{g.items.map((x) => <li key={x}>{x}</li>)}</ul>
          </motion.div>
        ))}
      </div>
      <Appear delay={1.3} className="feat-into">
        <Arrow dir="down" />
        <p>Trend score of each share = (6-month return + 12-month return) ÷ 2 ÷ volatility</p>
      </Appear>
    </Shell>
  );
}

/* 4. What does the model predict? Two signals, two classes each; the class in force now is lit. */
function Signals() {
  const e = useEvidence();
  if (!e) return <Loading />;
  const { a, f } = e;
  const stocks = a.activity!.allocation.shares.STOCKS ?? [];
  const on = (stocks.at(-1) ?? 0) > 0.05;
  const off = [...a.activity!.days].reverse().find((d) => describe(d).title === "Switch to safety");
  const top = f.ranking.top.slice(0, 6).map((t) => t.symbol);
  return (
    <Shell title="What does the model predict?" className="ev-signals">
      <div className="classes">
        <Appear delay={0.3} className="class-row">
          <span className="class-k">Market signal</span>
          <div className={on ? "class lit" : "class"}><b>ON</b><span>Nifty 50 above its {f.max.trend_days}-day average: hold shares</span>{on && <i className="now">now</i>}</div>
          <div className={on ? "class" : "class lit off"}><b>OFF</b><span>below it: hold the liquid fund</span>
            {!on && <i className="now">now{off ? `, since ${day(off.date)}` : ""}</i>}</div>
        </Appear>
        <Appear delay={0.6} className="class-row">
          <span className="class-k">Share signal</span>
          <div className="class lit"><b>TOP 30</b><span>the highest trend scores: held</span><em>{top.join(", ")} …</em></div>
          <div className="class"><b>REST</b><span>every other share: not held</span></div>
        </Appear>
      </div>
      <Appear delay={1.0}>
        <p className="fine">Checked each month (market) and each quarter (shares), after the close. The top 30 shown are from {day(f.ranking.day)}, the last re-pick.</p>
      </Appear>
    </Shell>
  );
}

type Stage = { name: string; line: string; icon: ReactNode };

/** Stages joined by arrows; one is lit at a time, walking the flow by itself until the viewer points at a stage. */
function Flow({ stages }: { stages: Stage[] }) {
  const reduce = useReducedMotion();
  const [on, setOn] = useState(0);
  const [held, setHeld] = useState(false);
  useEffect(() => {
    if (held || reduce) return;
    const t = setInterval(() => setOn((k) => (k + 1) % stages.length), 1600);
    return () => clearInterval(t);
  }, [held, reduce, stages.length]);
  const pick = (i: number) => { setHeld(true); setOn(i); };
  return (
    <ol className="flow-row" style={{ gridTemplateColumns: `repeat(${stages.length}, minmax(0, 1fr))` }}>
      {stages.map((s, i) => (
        <motion.li key={s.name} className={i === on ? "flow-stage on" : "flow-stage"} initial={{ opacity: 0, y: 22 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: EASE, delay: ENTER + 0.3 + i * 0.1 }}>
          <button type="button" aria-pressed={i === on} onMouseEnter={() => pick(i)} onFocus={() => pick(i)} onClick={() => pick(i)}>
            {i === on && <motion.span layoutId="flow-lit" className="flow-lit" transition={{ duration: 0.5, ease: SWEEP }} />}
            <span className="flow-icon" aria-hidden>{s.icon}</span>
            <span className="flow-name">{s.name}</span>
            <span className="flow-line">{s.line}</span>
          </button>
          {i < stages.length - 1 && <span className="flow-arrow" aria-hidden><Arrow dir="right" /></span>}
        </motion.li>
      ))}
    </ol>
  );
}

/* 5. How does it become an investment? One flow, then the three actions. */
function Strategy() {
  const e = useEvidence();
  if (!e) return <Loading />;
  const mix = e.f.max;
  return (
    <Shell title="How does it become an investment?" className="ev-strategy">
      <Flow stages={[
        { name: "Data", line: "Daily prices", icon: ICON.data },
        { name: "Features", line: "Momentum, risk, liquidity, trend", icon: ICON.features },
        { name: "Model", line: "Trend score, market check", icon: ICON.model },
        { name: "Signal", line: "Market on or off, top 30", icon: ICON.signal },
        { name: "Strategy", line: `${Math.round(mix.momentum * 100)}% shares, ${Math.round(mix.fixed.GOLDBEES * 100)}% gold, ${Math.round(mix.fixed.MON100 * 100)}% Nasdaq 100`, icon: ICON.strategy },
        { name: "Action", line: "Buy, hold or sell", icon: ICON.action },
      ]} />
      <div className="actions">
        {[
          { a: "BUY", d: "a share joins the top 30", cls: "buy" },
          { a: "HOLD", d: "it stays in the top 30", cls: "hold" },
          { a: "SELL", d: "it leaves the top 30, or the market turns off (the money waits in the liquid fund)", cls: "sell" },
        ].map((x, i) => (
          <motion.div key={x.a} className={`act ${x.cls}`} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: EASE, delay: ENTER + 1.1 + i * 0.15 }}>
            <b>{x.a}</b><span>{x.d}</span>
          </motion.div>
        ))}
      </div>
      <Appear delay={1.7}><p className="fine">Orders go in the next trading day. The rules were set using 2017 to 2026 data; past results, not a promise.</p></Appear>
    </Shell>
  );
}

export const EVIDENCE: SlideDef[] = [
  { id: "model", title: "Our model", Slide: Model },
  { id: "data", title: "Our data", Slide: Data },
  { id: "features", title: "Our features", Slide: Features },
  { id: "signals", title: "Our signals", Slide: Signals },
  { id: "strategy", title: "From signal to investment", Slide: Strategy },
];
