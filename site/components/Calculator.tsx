"use client";

import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useState } from "react";
import { colorOf, nameOf } from "@/lib/api";
import { day, inr, inrShort, pct, points, signedPct } from "@/lib/format";
import { useScenario } from "@/lib/scenario";
import { align } from "@/lib/series";
import { AmountField, BenchmarkSelect, DateField, StrategyList, TaxFields } from "./Controls";
import { Legend, LineChart, useHidden } from "./charts";
import { Counter, EASE, Reveal, Working } from "./motion";

export function Calculator({ sectionRef, amountRef, arrived }: { sectionRef: React.Ref<HTMLElement>; amountRef: React.Ref<HTMLInputElement>; arrived: number }) {
  const { choice, set } = useScenario();
  const [pulse, setPulse] = useState(false);
  useEffect(() => {
    if (!arrived) return;
    setPulse(true);
    const t = setTimeout(() => setPulse(false), 1400);
    return () => clearTimeout(t);
  }, [arrived]);

  return (
    <section className="calc wrap" id="calculator" ref={sectionRef}>
      <Reveal y={40} className="calc-grid">
        <aside className="panel">
          <motion.div animate={{ boxShadow: pulse ? "0 0 0 6px var(--accent-soft)" : "0 0 0 0px var(--accent-soft)" }} transition={{ duration: 0.6, ease: EASE }} className="pulse">
            <AmountField value={choice.amount} onChange={(amount) => set({ amount })} inputRef={amountRef} />
          </motion.div>
          <DateField value={choice.start} level={choice.level} onChange={(start) => set({ start })} />
          <StrategyList value={choice.level} onChange={(level) => set({ level })} />
          <BenchmarkSelect value={choice.benchmark} onChange={(benchmark) => set({ benchmark })} />
          <TaxFields regime={choice.regime} income={choice.other_income} onChange={set} />
        </aside>
        <Results />
      </Reveal>
    </section>
  );
}

function Status() {
  const { busy, error, answer } = useScenario();
  return (
    <div className="status">
      <Working on={busy} />
      <AnimatePresence mode="wait" initial={false}>
        <motion.span key={busy ? "busy" : error ? "err" : "ok"} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} transition={{ duration: 0.25 }}
          className={error && !busy ? "status-text err" : "status-text"} role={error && !busy ? "alert" : undefined}>
          {busy ? "Replaying every trade, charge and tax…" : error ? error : answer ? `Up to date · data to ${day(answer.stamps.data_as_of)}` : ""}
        </motion.span>
      </AnimatePresence>
    </div>
  );
}

function Results() {
  const { answer: a, busy, choice } = useScenario();
  const model = a?.results.find((r) => r.kind === "product");
  const bench = a?.results.find((r) => r.id === choice.benchmark);
  const amount = a ? Number(a.inputs.amount) : choice.amount;

  return (
    <div className="results">
      <Status />
      {!a ? (
        <div className="skeleton" style={{ height: 520 }} />
      ) : (
        <motion.div animate={{ opacity: busy ? 0.45 : 1 }} transition={{ duration: 0.4 }}>
          {model ? (
            <>
              <p className="result-lead">{inr(amount)} invested on {day(a.inputs.start)} in <b>{model.id.slice(8)}</b> would be</p>
              <Counter className="result-big" value={model.net.value} format={inr} />
              <p className="result-tail">on {day(a.inputs.end)}, after selling everything and paying every charge and tax.</p>
              <div className="metrics">
                <Metric label="Total return" value={model.net.value / amount - 1} format={signedPct} />
                <Metric label="A year (CAGR)" value={model.growth} format={(n) => pct(n)} />
                <Metric label="Worst fall" value={model.worst_fall} format={(n) => pct(n)} />
                <Metric label="Before charges and tax" value={model.gross_end.value} format={inr} />
                <Metric label="Charges paid" value={model.charges.value} format={inr} />
                <Metric label="Tax paid" value={model.tax.value} format={inr} />
              </div>
              {bench && <Versus model={model.net.value} modelGrowth={model.growth} bench={bench.net.value} benchGrowth={bench.growth} benchName={nameOf(bench.id)} />}
            </>
          ) : (
            <p className="empty">{a.messages.find((m) => m.id.startsWith("PRODUCT_"))?.text ?? "The strategy could not run on these dates."}</p>
          )}
        </motion.div>
      )}
      {a && <GrowthChart />}
      {a && a.messages.length > 0 && (
        <ul className="messages">{a.messages.map((m) => <li key={m.id}><b>{nameOf(m.id)}</b>: {m.text}</li>)}</ul>
      )}
      {a && <ul className="notes">{a.notes.filter((n) => !n.startsWith("Projections")).map((n) => <li key={n}>{n}</li>)}</ul>}
    </div>
  );
}

function Metric({ label, value, format }: { label: string; value: number; format: (n: number) => string }) {
  return (
    <div className="metric">
      <span className="label">{label}</span>
      <Counter value={value} format={format} />
    </div>
  );
}

function Versus({ model, modelGrowth, bench, benchGrowth, benchName }: { model: number; modelGrowth: number; bench: number; benchGrowth: number; benchName: string }) {
  const top = Math.max(model, bench);
  const diff = model - bench;
  return (
    <div className="versus">
      <div className="versus-head">
        <span className="label">Against {benchName}</span>
        <span className={diff >= 0 ? "pos" : "neg"}>
          <Counter value={Math.abs(diff)} format={inrShort} /> {diff >= 0 ? "more" : "less"} · {points(modelGrowth - benchGrowth)} a year
        </span>
      </div>
      {[{ label: "Intelligent Investment", v: model, c: "var(--accent)" }, { label: benchName, v: bench, c: "var(--ink-3)" }].map((row) => (
        <div className="vrow" key={row.label}>
          <span className="vlabel">{row.label}</span>
          <div className="vtrack">
            <motion.div className="vbar" style={{ background: row.c }} initial={{ width: 0 }}
              animate={{ width: `${(row.v / top) * 100}%` }} transition={{ duration: 1, ease: EASE }} />
          </div>
          <Counter className="vval" value={row.v} format={inrShort} />
        </div>
      ))}
    </div>
  );
}

function GrowthChart() {
  const { answer: a } = useScenario();
  const ids = a ? a.results.map((r) => r.id) : [];
  const key = ids.join();
  const grid = useMemo(() => (a ? align(a.series, ids) : null), [a, key]); // eslint-disable-line react-hooks/exhaustive-deps
  const [hidden, toggle] = useHidden();
  if (!a || !grid?.times.length) return null;
  return (
    <div className="growth">
      <div className="growth-head">
        <h3>How the money grew</h3>
        <p className="sub">Value along the way, after charges and the tax paid during the years. Click a name to show or hide its line.</p>
      </div>
      <Legend hidden={hidden} onToggle={(id) => toggle(id, ids)} items={a.results.map((r) => ({ id: r.id, label: nameOf(r.id), color: colorOf(r.id), sub: `${pct(r.growth)} a year` }))} />
      <LineChart times={grid.times} hidden={hidden} format={inrShort} height={400} baseline={Number(a.inputs.amount)} baselineLabel="Invested"
        lines={a.results.map((r) => ({ id: r.id, label: nameOf(r.id), color: colorOf(r.id), values: grid.values[r.id], emphasis: r.kind === "product" }))} />
    </div>
  );
}
