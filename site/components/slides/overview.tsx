"use client";

// Overview: what ₹10 lakh became, how each option got there, and the way into the calculator. Every figure is the saved calculator answer
// (site/public/data/lump.json, made by tools/site_data.py).
import { motion, useReducedMotion } from "motion/react";
import { useMemo, useState } from "react";
import { useData } from "@/lib/data";
import { useDeck, type SlideDef } from "@/lib/deck";
import { day, money, pct, span } from "@/lib/format";
import { colorOf, isMax, nameOf } from "@/lib/names";
import { grid } from "@/lib/scale";
import type { Answer, Result } from "@/lib/types";
import { LineChart, RankedBars } from "../charts";
import { Appear, Counter, ENTER, Key, Primary, Rise, Segmented } from "../ui";

export function Loading({ text = "Loading the record" }: { text?: string }) {
  return (
    <div className="loading" role="status">
      <span className="loading-bar" />
      <span>{text}</span>
    </div>
  );
}

const HERO_ALTS = ["NIFTYBEES", "GOLDBEES", "MON100"];

function parts(a: Answer) {
  const model = a.results.find((r) => isMax(r.id))!;
  const alts = a.results.filter((r) => !isMax(r.id));                    // the LSTM and the funds
  return { model, alts };
}

function Hero() {
  const { saved } = useData();
  if (!saved) return <Loading />;
  return <HeroBody a={saved.lump} />;
}

function HeroBody({ a }: { a: Answer }) {
  const { model, alts } = parts(a);
  const shown = HERO_ALTS.map((id) => alts.find((r) => r.id === id)).filter((r): r is Result => !!r);
  const ids = [model.id, ...shown.map((r) => r.id)];
  const g = useMemo(() => grid(a.series, ids, (s) => s.values), [a]); // eslint-disable-line react-hooks/exhaustive-deps
  const ends = Object.fromEntries([model, ...shown].map((r) => [r.id, { value: r.net.value, text: money(r.net.value) }]));
  return (
    <div className="hero">
      <div className="hero-copy">
        <Rise className="statement" lines={[`${money(model.invested, 0)} invested ${span(a.inputs.start, a.inputs.end)} ago`, "could have become"]} />
        <div className="hero-figure">
          <Counter value={model.net.value} format={(n) => money(n)} delay={ENTER + 0.35} duration={2.2} />
        </div>
        <Appear delay={0.5}>
          <p className="lead">today, after every charge and every tax. Its worst fall along the way was {pct(model.worst_fall, 0)}.</p>
        </Appear>
        <Appear delay={0.75} className="versus">
          {shown.map((r) => (
            <div key={r.id} className="vs-row">
              <span className="vs-word">vs</span>
              <Key color={colorOf(r.id)} />
              <span className="vs-value">{money(r.net.value)}</span>
              <span className="vs-name">in a {nameOf(r.id)}</span>
              <span className="vs-fall">fell {pct(r.worst_fall, 0)}</span>
            </div>
          ))}
        </Appear>
      </div>
      <Appear delay={0.15} className="hero-chart" y={0}>
        <LineChart times={g.times} format={(v) => money(v)} axis={(v) => money(v, 0).replace(" lakh", "L").replace(" crore", "Cr")}
          include={[model.invested]} baseline={{ value: model.invested, label: `${money(model.invested, 0)} put in` }} ends={ends} area="wash"
          series={ids.map((id) => ({ id, label: isMax(id) ? "Intelligent Investment" : nameOf(id), color: colorOf(id), values: g.values[id], strong: isMax(id) }))} />
        <p className="chart-note">
          Lines: what each was worth along the way. Dots: what was left after selling everything on {day(a.inputs.end)} and paying all tax
          (new regime, {money(a.inputs.other_income, 0)} other income). The model&rsquo;s record starts on {day(a.inputs.start)}, its first possible
          pick: the NSE share data begins in January 2016 and every pick needs a year of prices.
        </p>
      </Appear>
    </div>
  );
}

function Different() {
  const { saved } = useData();
  if (!saved) return <Loading />;
  return <DifferentBody a={saved.lump} />;
}

type Metric = "value" | "year" | "fall";
const METRICS: { id: Metric; label: string }[] = [{ id: "value", label: "Final value" }, { id: "year", label: "Per year" }, { id: "fall", label: "Worst fall" }];

function DifferentBody({ a }: { a: Answer }) {
  const { model, alts } = parts(a);
  const [metric, setMetric] = useState<Metric>("value");
  const [switched, setSwitched] = useState(false);
  const of = (r: Result) => (metric === "value" ? r.net.value : metric === "year" ? r.growth : r.worst_fall);
  const fmt = metric === "value" ? (n: number) => money(n) : metric === "year" ? (n: number) => `${pct(n)} a year` : (n: number) => `fell ${pct(n, 0)}`;
  const rows = [model, ...alts].sort((x, y) => (metric === "fall" ? of(x) - of(y) : of(y) - of(x)));        // best first: highest value or return, smallest fall
  const higher = alts.filter((r) => r.net.value > model.net.value);
  const lower = alts.filter((r) => r.net.value < model.net.value).sort((x, y) => y.net.value - x.net.value);
  const nifty = alts.find((r) => r.id === "NIFTYBEES");
  return (
    <div className="different">
      <div className="different-head">
        <div>
          <Rise className="statement" lines={[`Same ${money(model.invested, 0)}. Same day. Different decisions.`]} />
          <Appear delay={0.3}>
            <p className="terms-line">
              {money(model.invested, 0)} on {day(a.inputs.start)} in each of {rows.length} options, valued on {day(a.inputs.end)} ({span(a.inputs.start, a.inputs.end)}),
              after every charge and tax.
            </p>
          </Appear>
        </div>
        <Appear delay={0.35}>
          <Segmented id="rank-by" label="Rank by" value={metric} onChange={(m) => { setMetric(m); setSwitched(true); }} options={METRICS} />
        </Appear>
      </div>
      <RankedBars label="What each option became" version={metric} rows={rows.map((r) => ({
        id: r.id, name: isMax(r.id) ? "Intelligent Investment" : nameOf(r.id), color: colorOf(r.id), value: Math.max(of(r), 0), strong: isMax(r.id),
        text: <Counter key={metric} value={of(r)} format={fmt} delay={switched ? 0.05 : ENTER + 0.5} duration={switched ? 0.8 : 1.4} />,
        aside: (
          <>
            {metric !== "value" && <span><b>{money(r.net.value)}</b></span>}
            {metric !== "year" && <span><b>{pct(r.growth)}</b> a year</span>}
            {metric !== "fall" && <span>fell <b>{pct(r.worst_fall, 0)}</b></span>}
          </>
        ),
      }))} />
      <Appear delay={1.1} className="takeaway">
        <p>
          {higher.length > 0 && <>{higher.map((r) => nameOf(r.id)).join(" and ")} ended higher, {money(higher[0].net.value - model.net.value)} more, after falling {pct(higher[0].worst_fall, 0)} at {higher.length > 1 ? "their" : "its"} worst. </>}
          The model&rsquo;s worst fall was {pct(model.worst_fall, 0)}
          {nifty && nifty.net.value < model.net.value ? <>, and it ended {money(model.net.value - nifty.net.value)} above the Nifty 50 ETF.</> : lower.length ? <>, and it ended above {lower.map((r) => nameOf(r.id)).join(", ")}.</> : "."}
        </p>
      </Appear>
    </div>
  );
}

function Invite() {
  const { saved } = useData();
  const { go } = useDeck();
  const reduce = useReducedMotion();
  const a = saved?.lump;
  const model = a?.results.find((r) => r.kind === "product");
  const g = useMemo(() => (a && model ? grid(a.series, [model.id], (s) => s.values, 160) : null), [a, model]);
  const path = useMemo(() => {
    if (!g || !model) return "";
    const v = g.values[model.id], lo = Math.min(...v), hi = Math.max(...v);
    return v.map((y, i) => `${i ? "L" : "M"}${(i / (v.length - 1)) * 1000},${300 - ((y - lo) / (hi - lo)) * 280}`).join("");
  }, [g, model]);
  return (
    <div className="invite">
      <div className="invite-copy">
        <Rise className="statement big" lines={["See what it could have", "meant for your money."]} />
        <Appear delay={0.45}><p className="lead">Pick an amount, once or every month, a start and your tax. The same engine replays every order and every rupee of tax.</p></Appear>
        <Appear delay={0.7}><Primary onClick={() => go("performance", 0)}>Try it out</Primary></Appear>
      </div>
      {path && (
        <svg className="invite-line" viewBox="0 0 1000 300" preserveAspectRatio="none" aria-hidden>
          <motion.path d={path} fill="none" stroke="var(--model)" strokeWidth="2.5" vectorEffect="non-scaling-stroke" initial={reduce ? false : { pathLength: 0 }}
            animate={{ pathLength: 1 }} transition={{ duration: 3.2, ease: [0.45, 0, 0.2, 1], delay: ENTER + 0.3 }} />
        </svg>
      )}
    </div>
  );
}

export const OVERVIEW: SlideDef[] = [
  { id: "today", title: "What the money became", Slide: Hero },
  { id: "different", title: "Same money, different decisions", Slide: Different },
  { id: "invite", title: "Try it with your money", Slide: Invite },
];
