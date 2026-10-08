"use client";

// Evidence: our two models in four pictures: how each works, the data, what each reads, and the two side by side. Max is the rule set the site's
// calculator runs (research/maxmodel.py, research/stockmom.py); the LSTM is the deep-learning strategy (research/lstm.py, trained on a Kaggle GPU,
// research/lstm_result.py). Figures come from site/public/data/facts.json and lump.json (tools/site_data.py).
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useData } from "@/lib/data";
import type { SlideDef } from "@/lib/deck";
import { count, day, money, month, pct } from "@/lib/format";
import { colorOf, LSTM, nameOf } from "@/lib/names";
import { grid } from "@/lib/scale";
import type { Facts, Series } from "@/lib/types";
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
  const [open, setOpen] = useState<number | null>(null);
  if (!e) return <Loading />;
  const { f } = e;
  const shares = f.stocks.symbols - f.stocks.funds;
  const classes = f.classes ?? [];                                     // facts.json written before the classes were added: no row
  const facts = [
    { k: "Source", v: "NSE and AMFI", d: "the exchange's daily files, the fund's daily value" },
    { k: "Period", v: `${yr(f.stocks.from)} → ${yr(f.stocks.to)}`, d: `every trading day; ETFs from ${yr(f.etfs.from)}` },
    { k: "Format", v: "Daily time series", d: "open, high, low, close, volume, value traded" },
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
      {classes.length > 0 && (
        <Appear delay={0.75}>
          <div className="class-row" role="group" aria-labelledby="class-count">
            <p id="class-count" className="class-count"><b>{classes.length} classes</b> of data, {classes.reduce((n, c) => n + c.datasets.length, 0)} datasets:</p>
            {classes.map((c, i) => <button key={c.name} type="button" className="class-chip" onClick={() => setOpen(i)}>{c.name}</button>)}
          </div>
        </Appear>
      )}
      <Appear delay={0.9} className="data-form">
        <div className="form-head"><span className="badge-src">NSE</span><Arrow dir="right" /><span>In what form: one row per share or ETF per trading day. Three real rows:</span></div>
        <table className="rows">
          <thead><tr><th>Date</th><th>Share</th><th>Open</th><th>High</th><th>Low</th><th>Close</th><th>Volume</th><th>Value traded</th></tr></thead>
          <tbody>
            {f.sample.map((r, i) => (
              <motion.tr key={r.symbol} initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.6, ease: EASE, delay: ENTER + 1.2 + i * 0.15 }}>
                <td>{day(r.date)}</td><td><b>{r.symbol}</b></td><td>{price(r.open)}</td><td>{price(r.high)}</td><td>{price(r.low)}</td><td>{price(r.close)}</td><td>{count(r.qty)}</td>
                <td>₹{count(Math.round(r.value / 1e7))} crore</td>
              </motion.tr>
            ))}
            <tr className="more-rows"><td colSpan={8}>and {(f.stocks.rows / 1e6).toFixed(1)} million more like these, {month(f.stocks.from)} to {month(f.stocks.to)}</td></tr>
          </tbody>
        </table>
        <div className="form-foot"><Arrow dir="down" /><span className="badge-model">into the models</span></div>
      </Appear>
      <AnimatePresence>{open !== null && <ClassesModal key="classes" classes={classes} focus={open} onClose={() => setOpen(null)} />}</AnimatePresence>
    </Shell>
  );
}

type Group = "etf" | "market" | "flags";

/** What each of the LSTM's inputs measures, by its name in research/features.py. */
const FEATURE: Record<string, { name: string; what: string }> = {
  ret1: { name: "1-day return", what: "the change since the day before" },
  ret5: { name: "5-day return", what: "the change over the last week" },
  ret21: { name: "21-day return", what: "the change over about a month" },
  ret63: { name: "63-day return", what: "the change over about three months" },
  ret252: { name: "252-day return", what: "the change over about a year" },
  vol21: { name: "21-day volatility", what: "how much the price swung day to day over the last month" },
  vol63: { name: "63-day volatility", what: "the same over the last three months" },
  dd252: { name: "Fall from the year's high", what: "how far the price is below its highest close of the last year" },
  dist50: { name: "Distance from the 50-day average", what: "the price against its average of the last 50 days" },
  dist200: { name: "Distance from the 200-day average", what: "the price against its average of the last 200 days" },
  vspike: { name: "Volume spike", what: "today's value traded against its average of the last 63 days" },
  vix: { name: "India VIX", what: "how much the market expects prices to swing: its fear gauge" },
  vixchg5: { name: "VIX 5-day change", what: "how fast that fear rose or fell over the last week" },
  pe_pct: { name: "Nifty P/E against its history", what: "how expensive the Nifty is on earnings, as a share of its past days that were cheaper" },
  pb_pct: { name: "Nifty P/B against its history", what: "the same on book value" },
  gold_vs_equity63: { name: "Gold against shares", what: "the Gold ETF's three-month return minus the Nifty 50 ETF's" },
  cash_yield63: { name: "Liquid fund yield", what: "what cash earned over the last three months, as a yearly rate" },
};
const FLAG: Record<string, string> = { vix: "India VIX missing", vixchg5: "VIX change missing", pe_pct: "P/E missing", pb_pct: "P/B missing" };

/** A pop-up over the page: Escape, the close button or a click outside closes it, and the focus goes back to what opened it. */
function Modal({ id, title, onClose, children }: { id: string; title: string; onClose: () => void; children: ReactNode }) {
  const close = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const back = document.activeElement as HTMLElement | null;
    close.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => { window.removeEventListener("keydown", onKey); back?.focus(); };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return createPortal(
    <motion.div className="modal-back" data-modal onClick={onClose} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }}>
      <motion.div className="modal" role="dialog" aria-modal="true" aria-labelledby={id} onClick={(e) => e.stopPropagation()}
        initial={{ y: 26, scale: 0.98 }} animate={{ y: 0, scale: 1 }} exit={{ y: 18, opacity: 0 }} transition={{ duration: 0.35, ease: EASE }}>
        <div className="modal-head">
          <h2 id={id}>{title}</h2>
          <button ref={close} type="button" className="modal-close" onClick={onClose} aria-label="Close">&times;</button>
        </div>
        <div className="modal-body" data-scroll>{children}</div>
      </motion.div>
    </motion.div>,
    document.body,
  );
}

const years = (from: string, to: string) => (!from ? "" : yr(from) === yr(to) ? yr(from) : `${yr(from)}–${yr(to)}`);

/** Every dataset of the project, class by class; it opens at the class that was clicked. */
function ClassesModal({ classes, focus, onClose }: { classes: NonNullable<Facts["classes"]>; focus: number; onClose: () => void }) {
  const sections = useRef<(HTMLElement | null)[]>([]);
  useEffect(() => {
    if (focus > 0) sections.current[focus]?.scrollIntoView({ block: "start" });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <Modal id="class-title" title={`The ${classes.length} classes of data`} onClose={onClose}>
      <p className="modal-sub">Every dataset the project uses, {classes.reduce((n, c) => n + c.datasets.length, 0)} in all, each counted from its own files.
        The same list is in the classes folder of the repository.</p>
      {classes.map((c, i) => (
        <section key={c.name} ref={(el) => { sections.current[i] = el; }} className="modal-sec">
          <h3><b>{i + 1}</b>{c.name}<span>{years(c.from, c.to)}</span></h3>
          <p className="cls-what">{c.what}.</p>
          <dl className="cls-meta"><div><dt>Source</dt><dd>{c.source}</dd></div><div><dt>Used by</dt><dd>{c.used_by}</dd></div></dl>
          <table className="ftable ctable">
            <thead><tr><th>Dataset</th><th className="num">Size</th><th className="num">Years</th></tr></thead>
            <tbody>
              {c.datasets.map((d) => (
                <tr key={d.name}>
                  <td>{d.name}</td>
                  <td className="num">{d.rows != null ? `${count(d.rows)} rows` : `${count(d.files)} ${d.files === 1 ? "file" : "files"}`}</td>
                  <td className="num">{years(d.from, d.to)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}
    </Modal>
  );
}

/** Every number the LSTM reads each day, in three groups; it opens at the group that was clicked. */
function FeaturesModal({ l, etfs, focus, onClose }: { l: Facts["lstm"]; etfs: string[]; focus: Group; onClose: () => void }) {
  const sections = useRef<Partial<Record<Group, HTMLElement | null>>>({});
  useEffect(() => {
    if (focus !== "etf") sections.current[focus]?.scrollIntoView({ block: "start" });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const what = (c: string) => FEATURE[c] ?? { name: c, what: "" };
  const codes = l.codes ?? { per_asset: [], market: [], flags: [] };      // facts.json written before the codes were added: nothing to list
  return (
    <Modal id="feat-title" title={`The ${l.inputs} numbers the LSTM reads each day`} onClose={onClose}>
        <p className="modal-sub">It reads them for each of the last {l.seq_lens.join(" or ")} days, oldest first, and from that sequence sets tomorrow&rsquo;s mix.</p>
        <section ref={(el) => { sections.current.etf = el; }} className="modal-sec">
          <h3><b>{l.per_asset * etfs.length}</b> about the ETFs <span>{l.per_asset} numbers, worked out for each of the {etfs.length}</span></h3>
          <table className="ftable">
            <thead><tr><th>Number</th><th>What it measures</th>{etfs.map((a) => <th key={a} className="etf-col"><Key dot color={colorOf(a)} />{nameOf(a).replace(" ETF", "")}</th>)}</tr></thead>
            <tbody>
              {codes.per_asset.map((c) => (
                <tr key={c}><td><b>{what(c).name}</b></td><td>{what(c).what}</td>{etfs.map((a) => <td key={a} className="tick" aria-label={nameOf(a)}>&#10003;</td>)}</tr>
              ))}
            </tbody>
          </table>
        </section>
        <section ref={(el) => { sections.current.market = el; }} className="modal-sec">
          <h3><b>{l.market}</b> about the market <span>one number each, the same for every ETF</span></h3>
          <ul className="flist">{codes.market.map((c) => <li key={c}><b>{what(c).name}</b><span>{what(c).what}</span></li>)}</ul>
        </section>
        <section ref={(el) => { sections.current.flags = el; }} className="modal-sec">
          <h3><b>{l.flags}</b> missing-data flags <span>1 on a day the number is not available (India VIX starts later, for example), otherwise 0</span></h3>
          <ul className="flist flags">{codes.flags.map((c) => <li key={c}><b>{FLAG[c] ?? `${c} missing`}</b></li>)}</ul>
        </section>
        <p className="modal-total">{l.per_asset * etfs.length} + {l.market} + {l.flags} = <b>{l.inputs}</b> numbers a day, each scaled with statistics from the training years only.</p>
    </Modal>
  );
}

/* 3. What does each model look at? Max: three numbers per share and one for the market. The LSTM: 76 numbers a day, over months. */
function Features() {
  const e = useEvidence();
  const [open, setOpen] = useState<Group | null>(null);
  if (!e) return <Loading />;
  const l = e.f.lstm;
  const etfs = l.assets.filter((a) => a !== "LIQUID_FUND");
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
          <ol className="lflow" aria-label="How the LSTM reads its numbers">
            {[
              { t: `Last ${l.seq_lens.join(" or ")} days`, d: "of history, in order" },
              { t: `${l.inputs} numbers`, d: "for each of those days" },
              { t: "LSTM", d: "a network with memory" },
              { t: "Tomorrow's mix", d: `${etfs.map((a) => nameOf(a).replace(" ETF", "")).join(", ")}, liquid fund` },
            ].map((x, i, all) => (
              <motion.li key={x.t} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.6, ease: EASE, delay: ENTER + 0.7 + i * 0.18 }}>
                <b>{x.t}</b><span>{x.d}</span>
                {i < all.length - 1 && <span className="lflow-arrow" aria-hidden><Arrow dir="right" /></span>}
              </motion.li>
            ))}
          </ol>
          <div className="fgroup-row">
            {[
              { k: "etf" as const, n: l.per_asset * etfs.length, t: "about the ETFs", d: `${l.per_asset} for each of the ${etfs.length}` },
              { k: "market" as const, n: l.market, t: "about the market", d: "fear gauge, valuation, gold, cash" },
              { k: "flags" as const, n: l.flags, t: "missing-data flags", d: "a day without VIX, P/E or P/B" },
            ].map((g) => (
              <button key={g.k} type="button" className="fgroup-btn" disabled={!l.codes} onClick={() => setOpen(g.k)}>
                <b>{g.n}</b><span className="fg-t">{g.t}</span><span className="fg-d">{g.d}</span>
              </button>
            ))}
          </div>
          {l.codes && <button type="button" className="see-all" onClick={() => setOpen("etf")}>See all {l.inputs} numbers <Arrow dir="right" /></button>}
          <p className="fnote">Each is worked out from prices up to that day, then scaled with statistics from the training years only.</p>
        </motion.div>
        <AnimatePresence>{open && <FeaturesModal key="features" l={l} etfs={etfs} focus={open} onClose={() => setOpen(null)} />}</AnimatePresence>
      </div>
    </Shell>
  );
}

/* 4. Max and the LSTM side by side: how each invests, and what Rs 10 lakh became in each. */
function SideBySide() {
  const e = useEvidence();
  const calc = e?.a.results.find((r) => r.id === LSTM);                    // the calculator's own run of the LSTM level, the one the other pages show
  const lstmSeries = e ? (e.a.series[LSTM] ?? e.f.lstm.series) : undefined;
  const g = useMemo(() => {
    if (!e || !lstmSeries) return null;
    const all: Record<string, Series> = { PRODUCT_Max: e.a.series[e.max.id], LSTM: { dates: lstmSeries.dates, values: lstmSeries.values, invested: [], drawdown: [] } };
    return grid(all, ["PRODUCT_Max", "LSTM"], (s) => s.values);
  }, [e, lstmSeries]);
  if (!e || !g) return <Loading />;
  const { max, f, a } = e;
  const l = f.lstm;
  const final = calc?.net.value ?? l.final;
  const mix = Object.entries(l.average_mix).sort((x, y) => y[1] - x[1]).slice(0, 3);
  const cards = [
    { id: "PRODUCT_Max", name: "Max strategy", color: colorOf("PRODUCT_Max"), final: max.net.value, rate: max.growth, fall: max.worst_fall,
      how: "Half in the 30 strongest shares, a quarter gold, a quarter Nasdaq 100; shares sold when the market turns down." },
    { id: "LSTM", name: "LSTM model", color: LSTM_COLOR, final, rate: calc?.growth ?? l.cagr, fall: calc?.worst_fall ?? l.worst_fall,
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
            ends={{ PRODUCT_Max: { value: max.net.value, text: money(max.net.value) }, LSTM: { value: final, text: money(final) } }}
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
