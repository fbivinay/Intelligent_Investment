"use client";

import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { BarChart, Legend, LineChart, useHidden } from "@/components/charts";
import { BenchmarkSelect } from "@/components/Controls";
import { Counter, EASE, Reveal, Segmented, Working } from "@/components/motion";
import { colorOf, LEVELS, nameOf } from "@/lib/api";
import { day, inr, inrShort, month, pct, signedPct } from "@/lib/format";
import { useScenario } from "@/lib/scenario";
import { align, deepestFall, drawdown, longestUnderwater, yearly, type Fall } from "@/lib/series";
import type { Level } from "@/lib/types";

type View = "growth" | "returns" | "drawdown";

const span = (days: number) => (days >= 365 ? `${(days / 365.25).toFixed(1)} years` : days >= 60 ? `${Math.round(days / 30.4)} months` : `${days} days`);

export default function Performance() {
  const { answer: a, choice, set, busy, error } = useScenario();
  const [view, setView] = useState<View>("growth");
  const [hidden, toggle] = useHidden();
  const model = a?.results.find((r) => r.kind === "product");
  const bench = a?.results.find((r) => r.id === choice.benchmark);
  const ids = [model?.id, bench?.id].filter((x): x is string => !!x);
  const key = `${a?.inputs.start}|${ids.join()}|${a?.results.map((r) => r.net.value).join()}`;

  const d = useMemo(() => {
    if (!a || !model) return null;
    const grid = align(a.series, ids);
    const years = new Map<number, { m?: number; b?: number; partial: boolean }>();
    for (const y of yearly(a.series[model.id])) years.set(y.year, { m: y.value, partial: y.partial });
    if (bench) for (const y of yearly(a.series[bench.id])) years.set(y.year, { ...(years.get(y.year) ?? { partial: y.partial }), b: y.value });
    const rows = [...years.entries()].sort(([x], [y]) => x - y).map(([year, r]) => ({ year, ...r }));
    const full = rows.filter((r) => !r.partial && r.m !== undefined);
    const pick = full.length ? full : rows;
    return {
      grid, rows,
      best: pick.reduce((p, r) => (r.m! > p.m! ? r : p)),
      worst: pick.reduce((p, r) => (r.m! < p.m! ? r : p)),
      fall: deepestFall(a.series[model.id]),
      benchFall: bench ? deepestFall(a.series[bench.id]) : null,
      under: longestUnderwater(a.series[model.id]),
      benchUnder: bench ? longestUnderwater(a.series[bench.id]) : 0,
    };
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="wrap perf">
      <header className="page-head">
        <p className="eyebrow">Performance</p>
        <h1 className="title-xl">What happened along the way.</h1>
        <p className="sub">
          {a && model ? <>{inr(Number(a.inputs.amount))} in <b>{model.id.slice(8)}</b> from {day(a.inputs.start)} to {day(a.inputs.end)}. </> : null}
          The amount and start date come from the calculator on the <Link href="/#calculator">Overview</Link>.
        </p>
        <div className="perf-controls">
          <Segmented id="perf-level" size="sm" value={choice.level} onChange={(level: Level) => set({ level })} options={LEVELS.map((l) => ({ id: l.id, label: l.name }))} />
          <div className="perf-bench"><BenchmarkSelect value={choice.benchmark} onChange={(benchmark) => set({ benchmark })} label="Against" /></div>
        </div>
        <div className="status"><Working on={busy} /><span className={error && !busy ? "status-text err" : "status-text"}>{busy ? "Replaying every trade, charge and tax…" : error ?? ""}</span></div>
      </header>

      {!a || !d || !model ? (
        <div className="skeleton" style={{ height: 520 }}>{a && !model && <p className="empty">{a.messages[0]?.text}</p>}</div>
      ) : (
        <motion.div animate={{ opacity: busy ? 0.45 : 1 }} transition={{ duration: 0.4 }}>
          <section className="card-plain">
            <div className="chart-bar">
              <Segmented id="perf-view" value={view} onChange={setView} options={[{ id: "growth", label: "Growth" }, { id: "returns", label: "Returns" }, { id: "drawdown", label: "Drawdown" }]} />
              <Legend hidden={hidden} onToggle={(id) => toggle(id, ids)} items={ids.map((id) => ({ id, label: nameOf(id), color: colorOf(id) }))} />
            </div>
            <AnimatePresence mode="wait" initial={false}>
              {view === "returns" ? (
                <motion.div key="bars" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.35, ease: EASE }}>
                  <BarChart years={d.rows.map((r) => r.year)} partial={d.rows.map((r) => r.partial)} format={(n) => pct(n, 0)}
                    groups={ids.filter((id) => !hidden.has(id)).map((id) => ({ id, label: nameOf(id), color: colorOf(id), values: d.rows.map((r) => (id === model.id ? r.m : r.b) ?? null) }))} />
                </motion.div>
              ) : (
                <motion.div key="lines" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.35, ease: EASE }}>
                  <LineChart times={d.grid.times} hidden={hidden} kind={view === "drawdown" ? "drawdown" : "value"} format={view === "drawdown" ? (n) => pct(n, 0) : inrShort}
                    baseline={view === "growth" ? Number(a.inputs.amount) : undefined} baselineLabel="Invested"
                    lines={ids.map((id) => ({ id, label: nameOf(id), color: colorOf(id), emphasis: id === model.id,
                      values: view === "drawdown" ? drawdown(d.grid.values[id]) : d.grid.values[id] }))} />
                </motion.div>
              )}
            </AnimatePresence>
            <p className="fine">
              {view === "growth" && "Account value along the way, after charges and the tax paid during the years."}
              {view === "returns" && "Change in account value in each calendar year. * marks a part year (the first or the last)."}
              {view === "drawdown" && "How far the account stood below its own highest value so far."}
            </p>
          </section>

          <section className="stats">
            <Stat label="Worst fall" value={<Counter value={model.worst_fall} format={(n) => pct(n)} />} vs={bench && pct(bench.worst_fall)} />
            <Stat label="Longest time below a peak" value={span(d.under)} vs={bench && span(d.benchUnder)} />
            <Stat label="Best calendar year" value={<>{d.best.year} · <Counter value={d.best.m!} format={(n) => signedPct(n)} /></>} />
            <Stat label="Worst calendar year" value={<>{d.worst.year} · <Counter value={d.worst.m!} format={(n) => signedPct(n)} /></>} />
            <Stat label="A year, after tax" value={<Counter value={model.growth} format={(n) => pct(n)} />} vs={bench && pct(bench.growth)} />
          </section>

          {d.fall && <FallStory fall={d.fall} name="Intelligent Investment" benchFall={d.benchFall} benchName={bench ? nameOf(bench.id) : ""} />}

          <section className="years">
            <Reveal className="section-head">
              <h2 className="title">Year by year</h2>
              <p className="sub">Change in account value in each calendar year, against {bench ? nameOf(bench.id) : "the benchmark"}.</p>
            </Reveal>
            <table className="ytable">
              <thead><tr><th>Year</th><th>Intelligent Investment</th><th>{bench ? nameOf(bench.id) : "Benchmark"}</th><th>Difference</th></tr></thead>
              <tbody>
                {d.rows.map((r, i) => (
                  <motion.tr key={r.year} initial={{ opacity: 0, y: 8 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.5, ease: EASE, delay: i * 0.03 }}>
                    <td>{r.year}{r.partial ? <span className="muted"> · part</span> : null}</td>
                    <td><YBar v={r.m} color="var(--accent)" /></td>
                    <td><YBar v={r.b} color="var(--ink-3)" /></td>
                    <td className={r.m !== undefined && r.b !== undefined ? (r.m >= r.b ? "pos num" : "neg num") : "num"}>
                      {r.m !== undefined && r.b !== undefined ? `${r.m >= r.b ? "+" : "−"}${Math.abs((r.m - r.b) * 100).toFixed(1)} pts` : "–"}
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </section>
        </motion.div>
      )}
    </div>
  );
}

function Stat({ label, value, vs }: { label: string; value: React.ReactNode; vs?: string | false }) {
  return (
    <Reveal className="stat">
      <span className="label">{label}</span>
      <span className="stat-value num">{value}</span>
      {vs && <span className="stat-vs">Benchmark: {vs}</span>}
    </Reveal>
  );
}

function YBar({ v, color }: { v?: number; color: string }) {
  if (v === undefined) return <span className="muted">–</span>;
  const w = Math.min(50, Math.abs(v) * 100);
  return (
    <span className="ybar">
      <span className="ybar-track">
        <motion.span className="ybar-fill" style={{ background: color, [v >= 0 ? "left" : "right"]: "50%" }} initial={{ width: 0 }} whileInView={{ width: `${w}%` }} viewport={{ once: true }} transition={{ duration: 0.8, ease: EASE }} />
      </span>
      <span className={v >= 0 ? "num" : "num neg"}>{signedPct(v)}</span>
    </span>
  );
}

function FallStory({ fall, name, benchFall, benchName }: { fall: Fall; name: string; benchFall: Fall | null; benchName: string }) {
  const steps = [
    { k: "Peak", d: fall.peak, t: "highest value before the fall" },
    { k: "Bottom", d: fall.trough, t: `${pct(-fall.depth)} below the peak` },
    { k: fall.recovered ? "Back to the peak" : "Not yet back", d: fall.recovered, t: fall.recovered ? `${span(fall.days)} after the peak` : `${span(fall.days)} so far` },
  ];
  return (
    <section className="fall">
      <Reveal className="section-head">
        <h2 className="title">The deepest fall, and the way back</h2>
        <p className="sub">
          {name}&rsquo;s worst stretch, read from the account&rsquo;s values about once a week, so its depth can be less than the exact worst fall above, which is measured on every day.
          {benchFall && ` ${benchName}'s worst: ${pct(-benchFall.depth)} from ${month(benchFall.peak)}, ${benchFall.recovered ? `back in ${span(benchFall.days)}` : "not yet back"}.`}
        </p>
      </Reveal>
      <div className="fall-line">
        <motion.div className="fall-track" initial={{ scaleX: 0 }} whileInView={{ scaleX: 1 }} viewport={{ once: true }} transition={{ duration: 1.4, ease: EASE }} />
        {steps.map((s, i) => (
          <Reveal key={s.k} delay={0.25 + i * 0.25} className="fall-step">
            <span className={i === 1 ? "dot neg" : "dot"} />
            <span className="label">{s.k}</span>
            <span className="fall-date">{s.d ? day(s.d) : "–"}</span>
            <span className="muted">{s.t}</span>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
