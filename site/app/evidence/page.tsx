"use client";

import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";
import { EASE, glideTo, Reveal, Segmented } from "@/components/motion";

// Every figure on this page is copied from the research reports in the repository (README.md, research/out/frozen/report.md and notes_after_the_run.md,
// docs/verification/mutation-sweeps.md); none is worked out here.

const STEPS = [
  { id: "data", label: "Historical data" },
  { id: "strategies", label: "Strategies tried" },
  { id: "testing", label: "Testing" },
  { id: "walk", label: "Out-of-sample" },
  { id: "costs", label: "Costs and tax" },
  { id: "limits", label: "Limitations" },
];

const TRIED: { what: string; result: string; verdict: "Kept" | "Rejected" | "Part" | "Research" }[] = [
  { what: "Deep learning, five network types (Kaggle GPU)", result: "Lost to a simple equal mix of ETFs, in design years and in the frozen test", verdict: "Rejected" },
  { what: "Trend, momentum and volatility rules on four ETFs", result: "About 7–11% a year; a fall guard cut both risk and return", verdict: "Kept" },
  { what: "Six ETFs in equal parts (adds Midcap 100 and Nasdaq 100)", result: "About 15% a year, worst fall 28% (2013–2026)", verdict: "Kept" },
  { what: "Stock momentum: the 30 strongest of the 500 most traded shares", result: "About 23% a year, but a worst fall of 48% (2017–2026)", verdict: "Part" },
  { what: "Max: momentum half with a market switch, gold and Nasdaq 100 a quarter each", result: "21.4% a year, worst fall 18% (2017–2026)", verdict: "Kept" },
  { what: "Nifty futures for leverage, covered calls, insurance puts", result: "Added nothing after cost and tax", verdict: "Rejected" },
  { what: "About 100 intraday option automations (1,905 settings)", result: "Selling options with a stop on every leg wins; buying options on chart signals does not", verdict: "Research" },
];
const VERDICT = { Kept: "Kept", Rejected: "Rejected", Part: "Half of Max", Research: "Not in the calculator" };

type Row = { name: string; sold: string; fall: string; strong?: boolean };
const FROZEN: Record<"Conservative" | "Balanced" | "Aggressive", { cap: string; verdict: string; rows: Row[] }> = {
  Conservative: { cap: "10%", verdict: "No gain: the strategy held plainly every year (+0.00 points a year).", rows: [
    { name: "The strategy (selector)", sold: "4.0%", fall: "3.0%", strong: true }, { name: "Plain holding", sold: "4.0%", fall: "3.0%" },
    { name: "Equal weight", sold: "10.9%", fall: "8.9%" }, { name: "Deep model", sold: "10.0%", fall: "9.2%" },
    { name: "Nifty 50 ETF held", sold: "4.3%", fall: "15.2%" }, { name: "Gold ETF held", sold: "31.1%", fall: "24.4%" }, { name: "Liquid fund held", sold: "4.0%", fall: "0.0%" }] },
  Balanced: { cap: "20%", verdict: "Beat plain holding by 2.87 points a year, worst fall inside the cap.", rows: [
    { name: "The strategy (selector)", sold: "6.8%", fall: "13.1%", strong: true }, { name: "Plain holding", sold: "3.9%", fall: "7.0%" },
    { name: "Equal weight", sold: "10.0%", fall: "13.2%" }, { name: "Deep model", sold: "9.9%", fall: "12.8%" },
    { name: "Nifty 50 ETF held", sold: "4.3%", fall: "15.2%" }, { name: "Gold ETF held", sold: "31.1%", fall: "24.4%" }, { name: "Liquid fund held", sold: "4.0%", fall: "0.0%" }] },
  Aggressive: { cap: "30%", verdict: "Beat plain holding by 7.22 points a year, worst fall inside the cap.", rows: [
    { name: "The strategy (selector)", sold: "10.9%", fall: "13.2%", strong: true }, { name: "Plain holding", sold: "3.7%", fall: "11.1%" },
    { name: "Equal weight", sold: "10.9%", fall: "13.2%" }, { name: "Deep model", sold: "9.7%", fall: "12.8%" },
    { name: "Nifty 50 ETF held", sold: "4.3%", fall: "15.2%" }, { name: "Gold ETF held", sold: "31.1%", fall: "24.4%" }, { name: "Liquid fund held", sold: "4.0%", fall: "0.0%" }] },
};

const LIMITS = [
  "Past results, not a promise. Every figure is a replay of history, and history is one path the market happened to take.",
  "The Max strategy's mix, and the Midcap 100 and Nasdaq 100 ETFs in the six-ETF model, were chosen after seeing 2017–2026. Their results on the Overview are not out of sample.",
  "The frozen test covers three years. A result there, either way, is weak evidence on its own.",
  "Dividends are added as cash, not reinvested; cash earns nothing; exit loads on funds are not modelled.",
  "The strategy trades the day after it decides, at that day's average price plus slippage; the alternatives are bought on the start day and held.",
  "Tax depends on your income and regime. One profile (new regime, ₹12 lakh other income) sits on the section 87A rebate edge and is the worst case for fund gains.",
  "Option prices inside the day are modelled between the exchange's real open and close; the intraday research needs daily automated trading and ₹10–50 lakh, so it is not in the calculator.",
  "Not investment advice. No broker account is used and no order is ever sent.",
];

function Stepper({ active }: { active: string }) {
  return (
    <nav className="stepper" aria-label="Sections">
      {STEPS.map((s, i) => (
        <button key={s.id} className={active === s.id ? "step on" : "step"} onClick={() => glideTo(document.getElementById(s.id), 140)}>
          {active === s.id && <motion.span layoutId="step-pill" className="step-pill" transition={{ type: "spring", stiffness: 400, damping: 36 }} />}
          <span className="step-n">{String(i + 1).padStart(2, "0")}</span>
          <span>{s.label}</span>
        </button>
      ))}
    </nav>
  );
}

function Block({ id, n, title, lede, children }: { id: string; n: number; title: string; lede: string; children: React.ReactNode }) {
  return (
    <section id={id} className="block">
      <Reveal className="block-head">
        <span className="block-n">{String(n).padStart(2, "0")}</span>
        <h2 className="title">{title}</h2>
        <p className="sub">{lede}</p>
      </Reveal>
      <Reveal delay={0.08}>{children}</Reveal>
    </section>
  );
}

function Timeline() {
  const years = Array.from({ length: 14 }, (_, i) => 2013 + i);
  return (
    <div className="timeline">
      <div className="tl-years">{years.map((y) => <span key={y}>{y}</span>)}</div>
      {[2016, 2019, 2022, 2025].map((pick, i) => (
        <div className="tl-row" key={pick}>
          <span className="tl-label">Pick of April {pick}</span>
          <div className="tl-track">
            <motion.span className="tl-seen" style={{ width: `${((pick + 0.25 - 2013) / 14) * 100}%` }} initial={{ scaleX: 0 }} whileInView={{ scaleX: 1 }}
              viewport={{ once: true }} transition={{ duration: 1, ease: EASE, delay: i * 0.15 }} />
            <motion.span className="tl-used" style={{ left: `${((pick + 0.25 - 2013) / 14) * 100}%`, width: `${(1 / 14) * 100}%` }} initial={{ opacity: 0 }} whileInView={{ opacity: 1 }}
              viewport={{ once: true }} transition={{ duration: 0.6, delay: 0.8 + i * 0.15 }} />
          </div>
        </div>
      ))}
      <div className="tl-row">
        <span className="tl-label">Frozen test</span>
        <div className="tl-track">
          <motion.span className="tl-frozen" style={{ left: `${((2023.75 - 2013) / 14) * 100}%`, width: `${(3 / 14) * 100}%` }} initial={{ opacity: 0, scaleX: 0 }}
            whileInView={{ opacity: 1, scaleX: 1 }} viewport={{ once: true }} transition={{ duration: 0.9, ease: EASE, delay: 1.4 }} />
        </div>
      </div>
      <div className="tl-key">
        <span><i className="k-seen" />Years the choice could see</span>
        <span><i className="k-used" />Year it is used, unseen</span>
        <span><i className="k-frozen" />Run once, after the design was frozen</span>
      </div>
    </div>
  );
}

function Frozen() {
  const [level, setLevel] = useState<keyof typeof FROZEN>("Balanced");
  const f = FROZEN[level];
  return (
    <div className="frozen">
      <div className="frozen-bar">
        <Segmented id="frozen" size="sm" value={level} onChange={setLevel} options={(Object.keys(FROZEN) as (keyof typeof FROZEN)[]).map((k) => ({ id: k, label: k }))} />
        <span className="muted">₹10 lakh each, 3 Oct 2023 to 30 Sep 2026, after selling everything and paying tax. Fall cap {f.cap}.</span>
      </div>
      <table className="etable">
        <thead><tr><th>Account</th><th>A year, after tax</th><th>Worst fall</th></tr></thead>
        <AnimatePresence mode="wait" initial={false}>
          <motion.tbody key={level} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }}>
            {f.rows.map((r) => <tr key={r.name} className={r.strong ? "strong" : ""}><td>{r.name}</td><td className="num">{r.sold}</td><td className="num">{r.fall}</td></tr>)}
          </motion.tbody>
        </AnimatePresence>
      </table>
      <AnimatePresence mode="wait" initial={false}>
        <motion.p key={level} className="verdict" initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }}>{f.verdict}</motion.p>
      </AnimatePresence>
    </div>
  );
}

export default function Evidence() {
  const [active, setActive] = useState(STEPS[0].id);
  useEffect(() => {
    const io = new IntersectionObserver((es) => es.forEach((e) => e.isIntersecting && setActive(e.target.id)), { rootMargin: "-40% 0px -55% 0px" });
    STEPS.forEach((s) => { const el = document.getElementById(s.id); if (el) io.observe(el); });
    return () => io.disconnect();
  }, []);

  return (
    <div className="wrap evidence">
      <header className="page-head">
        <p className="eyebrow">Evidence</p>
        <h1 className="title-xl">Why you can check the analysis.</h1>
        <p className="sub">What the numbers are built on, what was tried and thrown away, how the tests kept the future out, and what the results cannot tell you.</p>
      </header>
      <Stepper active={active} />

      <Block id="data" n={1} title="Historical data" lede="Real market files, kept as downloaded, with a cleaned copy beside them.">
        <div className="figures">
          <div><span className="figure">2010–2026</span><span className="muted">daily prices and fund values</span></div>
          <div><span className="figure">2015–2026</span><span className="muted">minute bars for Nifty, Bank Nifty and India VIX</span></div>
          <div><span className="figure">192</span><span className="muted">dated tax and charge rules, each with its source</span></div>
        </div>
        <ul className="plain">
          <li>Every NSE daily file from 2016 to 2026: all shares, all futures and options, index closes.</li>
          <li>NSE website history from 2010 to 2016.</li>
          <li>Mutual fund and ETF values (NAVs) from AMFI.</li>
          <li>Gaps and checks are written down beside the data; the raw files and a cleaned copy are both in the repository.</li>
        </ul>
      </Block>

      <Block id="strategies" n={2} title="Strategies tried" lede="Most ideas did not survive. The ones that did are the levels in the calculator.">
        <table className="etable">
          <thead><tr><th>Tried</th><th>What happened, after tax</th><th>Verdict</th></tr></thead>
          <tbody>
            {TRIED.map((t) => (
              <tr key={t.what}><td>{t.what}</td><td>{t.result}</td><td><span className={`tag tag-${t.verdict.toLowerCase()}`}>{VERDICT[t.verdict]}</span></td></tr>
            ))}
          </tbody>
        </table>
      </Block>

      <Block id="testing" n={3} title="Testing without seeing the future" lede="A strategy only counts on years it was not chosen on.">
        <div className="points">
          <div><h3>Next-day fills</h3><p>Decisions are made at a day&rsquo;s close; trades fill the next day at that day&rsquo;s prices, plus slippage.</p></div>
          <div><h3>No future data</h3><p>Every signal is tested to use only data up to its own day.</p></div>
          <div><h3>Many trials, discounted</h3><p>A choice must beat plain holding by a margin that grows with the number of ideas tried (a deflated margin), not just by luck.</p></div>
          <div><h3>Two engines agree</h3><p>The fast simulator and the exact books differ by ₹1.59 to ₹3.03 in charges over 39 to 47 orders in the frozen test.</p></div>
          <div><h3>About 1,500 tests</h3><p>Covering charges, tax, lots, the data and the strategies.</p></div>
        </div>
      </Block>

      <Block id="walk" n={4} title="Walk-forward and the frozen test" lede="Each April the strategy is picked using only the years before it, then run unchanged for a year. Then the whole design was frozen and run once on three years nothing was designed on.">
        <Timeline />
        <Frozen />
        <p className="fine">
          The frozen test used the four-ETF model. The calculator&rsquo;s six-ETF model keeps the same yearly out-of-sample picks, but its two extra ETFs were
          added with hindsight. The deep model earned less than its own equal-weight starting point at every level and was rejected.
        </p>
      </Block>

      <Block id="costs" n={5} title="Transaction costs and tax" lede="Every rupee is charged and taxed by the rules of its own date, 2010 to 2026.">
        <div className="two">
          <div>
            <h3>Charges</h3>
            <ul className="plain">
              <li>Fyers brokerage</li><li>Securities transaction tax (STT)</li><li>Stamp duty</li><li>Exchange and SEBI fees</li><li>GST on charges</li>
              <li>Depository charges on each sale</li><li>Demat account opening and yearly fees</li>
            </ul>
          </div>
          <div>
            <h3>Income tax</h3>
            <ul className="plain">
              <li>Slabs, old and new regime</li><li>Surcharge, cess and the section 87A rebate</li><li>Short and long term capital gains, holding periods</li>
              <li>Exemptions and grandfathering</li><li>Business income for intraday trading</li>
            </ul>
          </div>
        </div>
        <p className="fine">
          Checked against hand calculations and the Fyers brokerage calculator. Each of the 192 rule rows was changed one field at a time (1,511 changes);
          every change is caught by a test.
        </p>
      </Block>

      <Block id="limits" n={6} title="Limitations" lede="What these results cannot tell you.">
        <ol className="limits">{LIMITS.map((l) => <li key={l}>{l}</li>)}</ol>
      </Block>
    </div>
  );
}
