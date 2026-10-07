"use client";

// Evidence: our two models in four pictures: how each works, the data, what each reads, and the two side by side. Max is the rule set the site's
// calculator runs (research/maxmodel.py, research/stockmom.py); the LSTM is the deep-learning strategy (research/lstm.py, trained on a Kaggle GPU,
// research/lstm_result.py). Figures come from site/public/data/facts.json and lump.json (tools/site_data.py).
import { motion } from "motion/react";
import { useMemo, type ReactNode } from "react";
import { useData } from "@/lib/data";
import type { SlideDef } from "@/lib/deck";
import { count, day, money, month, pct } from "@/lib/format";
import { colorOf, nameOf } from "@/lib/names";
import { grid } from "@/lib/scale";
import type { Series } from "@/lib/types";
import { LineChart } from "../charts";
import { Appear, Arrow, Counter, EASE, ENTER, Key, Rise, SWEEP } from "../ui";
import { Loading } from "./overview";

const STEPS = ["Models", "Data", "Features", "Side by side"];
const LSTM_COLOR = "#44514A";

/** The four questions down the left edge; the marker moves to the one on screen. */
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
  return saved ? { a: saved.lump, f: saved.facts, max: saved.lump.results.find((r) => r.kind === "product")! } : null;
}

function Shell({ title, className, children }: { title: string; className?: string; children?: ReactNode }) {
  return (
    <div className={`ev railed ${className ?? ""}`}>
      <div className="ev-head"><Rise className="statement" lines={[title]} /></div>
      <div className="ev-main">{children}</div>
    </div>
  );
}

/** One model in three plain steps, revealed one after another. */
function ModelCard({ name, kind, steps, delay, lstm }: { name: string; kind: string; steps: { t: string; d: ReactNode }[]; delay: number; lstm?: boolean }) {
  return (
    <motion.div className={lstm ? "mcard lstm" : "mcard"} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, ease: EASE, delay: ENTER + delay }}>
      <div className="mcard-head"><Key color={lstm ? LSTM_COLOR : colorOf("PRODUCT_Max")} /><b>{name}</b><span className="mcard-kind">{kind}</span></div>
      <ol>
        {steps.map((s, i) => (
          <motion.li key={s.t} initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.7, ease: EASE, delay: ENTER + delay + 0.35 + i * 0.25 }}>
            <span className="mstep-n">{i + 1}</span><b>{s.t}</b><span>{s.d}</span>
          </motion.li>
        ))}
      </ol>
    </motion.div>
  );
}

/* 1. How do our models work? Max and the LSTM, in plain words. */
function Models() {
  const e = useEvidence();
  if (!e) return <Loading />;
  const l = e.f.lstm;
  return (
    <Shell title="How do our models work?" className="ev-models">
      <div className="model-pair">
        <ModelCard name="Max strategy" kind="Rules" delay={0.2} steps={[
          { t: "Picks 30 shares", d: "Every three months it ranks NSE shares by how steadily they rose over the last 6 and 12 months, and buys the top 30." },
          { t: "Watches the market", d: "Every month: if the Nifty 50 is below its 200-day average, it sells the shares and parks the money in a liquid fund." },
          { t: "Spreads the risk", d: "Half the money in the 30 shares, a quarter in gold, a quarter in the Nasdaq 100 (US tech)." },
        ]} />
        <ModelCard name="LSTM model" kind="Deep learning" lstm delay={0.5} steps={[
          { t: "Reads the recent past", d: <>Each day it looks at the last {l.seq_lens.join(" or ")} days of {l.inputs} numbers about {l.assets.length - 1} ETFs and the market.</> },
          { t: "Remembers patterns", d: "An LSTM is a neural network with a memory: it learned from earlier years which patterns came before good and bad times." },
          { t: "Sets tomorrow's mix", d: <>It splits the money across the {l.assets.length - 1} ETFs and the liquid fund. Retrained every April on a Kaggle GPU, only on the years before.</> },
        ]} />
      </div>
    </Shell>
  );
}

const yr = (iso: string) => iso.slice(0, 4);
const price = (n: number) => n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/* 2. What data do we use? The facts across the top, real rows below. */
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
    { k: "Assets", v: `${count(shares)} shares, ${f.etfs.symbols.length} ETFs`, d: "and the liquid fund: Max reads the shares, the LSTM the ETFs" },
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
        <div className="form-head"><span className="badge-src">NSE</span><Arrow dir="right" /><span>In what form: one row per share or ETF per trading day. Three real rows:</span></div>
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
        <div className="form-foot"><Arrow dir="down" /><span className="badge-model">into the models</span></div>
      </Appear>
    </Shell>
  );
}

/* 3. What does each model look at? Max: three numbers per share and one for the market. The LSTM: 76 numbers a day, over months. */
function Features() {
  const e = useEvidence();
  if (!e) return <Loading />;
  const l = e.f.lstm;
  const n = l.assets.length - 1;
  return (
    <Shell title="What does each model look at?" className="ev-features">
      <div className="feat-pair">
        <motion.div className="fcol" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, ease: EASE, delay: ENTER + 0.2 }}>
          <div className="fcol-head"><Key color={colorOf("PRODUCT_Max")} /><b>Max strategy</b></div>
          <p className="fcount"><b>3</b><span>numbers for each share, worked out on the day it decides</span></p>
          <ul className="fchips">
            <li><b>6-month return</b><span>how much the share rose in 6 months</span></li>
            <li><b>12-month return</b><span>how much it rose in 12 months</span></li>
            <li><b>1-year volatility</b><span>how much its price swung day to day</span></li>
          </ul>
          <p className="fformula">Trend score = (6-month + 12-month return) ÷ 2 ÷ volatility. The 30 highest are bought.</p>
          <p className="fnote">Plus <b>one number for the market</b>: the Nifty 50 against its 200-day average. Only the 500 most traded shares with a year of prices are ranked.</p>
        </motion.div>
        <motion.div className="fcol lstm" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, ease: EASE, delay: ENTER + 0.45 }}>
          <div className="fcol-head"><Key color={LSTM_COLOR} /><b>LSTM model</b></div>
          <p className="fcount"><b>{l.inputs}</b><span>numbers a day, read as a sequence over the last {l.seq_lens.join(" or ")} days</span></p>
          <ul className="fgroups">
            <li><b>{l.per_asset} for each of the {n} ETFs</b><span>return over 1, 5, 21, 63 and 252 days; volatility over 21 and 63 days; fall from the year&rsquo;s high; distance from the 50- and 200-day averages; a volatility spike</span></li>
            <li><b>{l.market} for the market</b><span>India VIX and its 5-day change; the Nifty&rsquo;s P/E and P/B against their history; gold against shares over 63 days; the liquid fund&rsquo;s yield</span></li>
            <li><b>{l.flags} flags</b><span>whether VIX, P/E or P/B is missing that day</span></li>
          </ul>
          <p className="fnote">Every number is worked out from prices up to that day, then scaled with statistics from the training years only.</p>
        </motion.div>
      </div>
    </Shell>
  );
}

/* 4. Max and the LSTM side by side: how each invests, and what Rs 10 lakh became in each. */
function SideBySide() {
  const e = useEvidence();
  const lstmSeries = e?.f.lstm.series;
  const g = useMemo(() => {
    if (!e || !lstmSeries) return null;
    const all: Record<string, Series> = { PRODUCT_Max: e.a.series[e.max.id], LSTM: { dates: lstmSeries.dates, values: lstmSeries.values, invested: [], drawdown: [] } };
    return grid(all, ["PRODUCT_Max", "LSTM"], (s) => s.values);
  }, [e, lstmSeries]);
  if (!e || !g) return <Loading />;
  const { max, f, a } = e;
  const l = f.lstm;
  const mix = Object.entries(l.average_mix).sort((x, y) => y[1] - x[1]).slice(0, 3);
  const cards = [
    { id: "PRODUCT_Max", name: "Max strategy", color: colorOf("PRODUCT_Max"), final: max.net.value, rate: max.growth, fall: max.worst_fall,
      how: "Half in the 30 strongest shares, a quarter gold, a quarter Nasdaq 100; shares sold when the market turns down." },
    { id: "LSTM", name: "LSTM model", color: LSTM_COLOR, final: l.final, rate: l.cagr, fall: l.worst_fall,
      how: <>A new mix of {l.assets.length - 1} ETFs and the liquid fund each day; on average {mix.map(([k, v]) => `${pct(v, 0)} ${nameOf(k)}`).join(", ")}.</> },
  ];
  return (
    <Shell title="Max and the LSTM, side by side" className="ev-side">
      <div className="side-body">
        <div className="side-cards">
          {cards.map((c, i) => (
            <motion.div key={c.id} className={c.id === "LSTM" ? "rcard lstm" : "rcard"} initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, ease: EASE, delay: ENTER + 0.25 + i * 0.2 }}>
              <span className="rcard-name"><Key color={c.color} />{c.name}</span>
              <Counter className="rcard-value" value={c.final} format={(n) => money(n)} delay={ENTER + 0.5} />
              <span className="rcard-line"><b>{pct(c.rate)}</b> a year</span>
              <span className="rcard-fall">Worst fall −{pct(c.fall, 0)}</span>
              <span className="rcard-how">{c.how}</span>
            </motion.div>
          ))}
        </div>
        <Appear delay={0.4} y={0} className="side-chart">
          <LineChart times={g.times} format={(v) => money(v)} axis={(v) => money(v, 0).replace(" lakh", "L").replace(" crore", "Cr")} area="wash"
            include={[1_000_000]} baseline={{ value: 1_000_000, label: "₹10 lakh put in" }}
            ends={{ PRODUCT_Max: { value: max.net.value, text: money(max.net.value) }, LSTM: { value: l.final, text: money(l.final) } }}
            series={[{ id: "PRODUCT_Max", label: "Max strategy", color: colorOf("PRODUCT_Max"), values: g.values.PRODUCT_Max, strong: true },
                     { id: "LSTM", label: "LSTM model", color: LSTM_COLOR, values: g.values.LSTM }]} />
        </Appear>
      </div>
      <Appear delay={1.2}>
        <p className="fine">
          ₹10 lakh from {day(a.inputs.start)} to {day(a.inputs.end)}, after every charge and tax. The LSTM&rsquo;s mix each year came from a network trained only on
          the years before it; Max&rsquo;s rules were chosen using 2017 to 2026.
          {l.tried.length > 1 && <> {l.tried.length} LSTM versions were trained; {l.tried.filter((t) => t.version !== l.version).map((t) =>
            `on ${t.etfs} ETFs one made ${pct(t.cagr)} a year with a ${pct(t.worst_fall, 0)} fall`).join("; ")}.</>} Past results, not a promise.
        </p>
      </Appear>
    </Shell>
  );
}

export const EVIDENCE: SlideDef[] = [
  { id: "models", title: "How our models work", Slide: Models },
  { id: "data", title: "Our data", Slide: Data },
  { id: "features", title: "What each model looks at", Slide: Features },
  { id: "side", title: "Max and the LSTM, side by side", Slide: SideBySide },
];
