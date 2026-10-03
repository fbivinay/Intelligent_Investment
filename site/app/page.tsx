"use client";

import { motion, useReducedMotion } from "motion/react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { Calculator } from "@/components/Calculator";
import { Legend, LineChart, useHidden } from "@/components/charts";
import { Counter, EASE, glideTo, Reveal } from "@/components/motion";
import { colorOf, nameOf, savedAnswer } from "@/lib/api";
import { day, inrShort, pct } from "@/lib/format";
import { align } from "@/lib/series";
import type { Answer } from "@/lib/types";

const HERO = ["See what your money", "could have become."];

function Hero() {
  const reduce = useReducedMotion();
  return (
    <section className="hero wrap">
      <motion.p className="eyebrow" initial={reduce ? false : { opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 1, delay: 0.1 }}>
        Indian markets · 2010 to 2026 · after every charge and tax
      </motion.p>
      <h1 className="display">
        {HERO.map((line, i) => (
          <span key={line} className="mask">
            <motion.span initial={reduce ? false : { y: "105%" }} animate={{ y: "0%" }} transition={{ duration: 1.1, ease: EASE, delay: 0.15 + i * 0.12 }}>{line}</motion.span>
          </span>
        ))}
      </h1>
      <motion.p className="lede" initial={reduce ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.9, ease: EASE, delay: 0.55 }}>
        Intelligent Investment replays a tested strategy on real Indian market history and sets it beside the ordinary alternatives, after brokerage,
        government charges and income tax, each by the rules of its own date.
      </motion.p>
      <motion.div className="scroll-cue" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1.3, duration: 1 }} aria-hidden>
        <motion.span animate={reduce ? undefined : { y: [0, 8, 0] }} transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }} />
      </motion.div>
    </section>
  );
}

function ModelHistory({ a }: { a: Answer | null }) {
  const ids = a ? a.results.map((r) => r.id) : [];
  const [hidden, toggle] = useHidden();
  const grid = useMemo(() => (a ? align(a.series, ids) : null), [a]); // eslint-disable-line react-hooks/exhaustive-deps
  const model = a?.results.find((r) => r.kind === "product");
  const amount = a ? Number(a.inputs.amount) : 0;

  return (
    <section className="history wrap">
      <Reveal className="section-head">
        <p className="eyebrow">What the system has done</p>
        <h2 className="title">{a ? <>₹10 lakh, invested on {day(a.inputs.start)}.</> : "Loading the record…"}</h2>
        <p className="sub">
          The Max strategy against four alternatives bought the same day and held. Lines show the account along the way; the figures are after selling
          everything on {a ? day(a.inputs.end) : "the last day"} and paying every charge and tax.
        </p>
      </Reveal>
      {a && grid && model ? (
        <Reveal delay={0.1}>
          <Legend hidden={hidden} onToggle={(id) => toggle(id, ids)} items={a.results.map((r) => ({
            id: r.id, label: r.kind === "product" ? "Intelligent Investment · Max" : nameOf(r.id), color: colorOf(r.id),
            sub: <><Counter value={r.growth} format={(n) => `${pct(n)} a year`} fromZero /> · fell {pct(r.worst_fall, 0)} at worst</>,
          }))} />
          <LineChart times={grid.times} hidden={hidden} format={inrShort} height={460} baseline={amount} baselineLabel="Invested"
            lines={a.results.map((r) => ({ id: r.id, label: r.kind === "product" ? "Intelligent Investment" : nameOf(r.id), color: colorOf(r.id), values: grid.values[r.id], emphasis: r.kind === "product" }))} />
          <div className="facts">
            <div><span className="label">Max, after tax</span><Counter className="fact" value={model.net.value} format={inrShort} fromZero /></div>
            <div><span className="label">A year, after tax</span><Counter className="fact" value={model.growth} format={(n) => pct(n)} fromZero /></div>
            <div><span className="label">Worst fall along the way</span><Counter className="fact" value={model.worst_fall} format={(n) => pct(n)} fromZero /></div>
            <p className="fine">
              {a.results.filter((r) => r.growth > model.growth).map((r) => `${nameOf(r.id)} earned more in these years (${pct(r.growth)} a year) and fell ${pct(r.worst_fall, 0)} at worst. `)}
              Max&rsquo;s mix was chosen after seeing these years; the fully out-of-sample tests are on the <Link href="/evidence">Evidence</Link> page.
              Tax: new regime, ₹12 lakh other income.
            </p>
          </div>
        </Reveal>
      ) : (
        <div className="chart skeleton" style={{ height: 460 }} />
      )}
    </section>
  );
}

function TryIt({ onGo }: { onGo: () => void }) {
  return (
    <section className="tryit wrap">
      <Reveal>
        <h2 className="title center">See what it could have meant for your money.</h2>
        <div className="center">
          <motion.button className="cta" onClick={onGo} whileHover="hover" whileTap={{ scale: 0.97 }}>
            Try it out
            <motion.svg width="16" height="16" viewBox="0 0 16 16" variants={{ hover: { y: 3 } }} transition={{ type: "spring", stiffness: 400, damping: 20 }} aria-hidden>
              <path d="M8 3v10M3.5 8.5 8 13l4.5-4.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
            </motion.svg>
          </motion.button>
        </div>
      </Reveal>
    </section>
  );
}

export default function Overview() {
  const [history, setHistory] = useState<Answer | null>(null);
  const calc = useRef<HTMLElement>(null);
  const amount = useRef<HTMLInputElement>(null);
  const [arrived, setArrived] = useState(0);
  useEffect(() => { savedAnswer().then(setHistory, () => {}); }, []);

  return (
    <>
      <Hero />
      <ModelHistory a={history} />
      <TryIt onGo={() => glideTo(calc.current).then(() => { setArrived((n) => n + 1); amount.current?.focus({ preventScroll: true }); })} />
      <Calculator sectionRef={calc} amountRef={amount} arrived={arrived} />
    </>
  );
}
