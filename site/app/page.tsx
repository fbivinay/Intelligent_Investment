"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { calculate, DEFAULTS } from "@/lib/api";
import type { Answer, Inputs } from "@/lib/types";
import { download } from "@/lib/format";
import { Controls } from "@/components/Controls";
import { InfoProvider } from "@/components/Info";
import { ResultCard } from "@/components/ResultCard";
import { Chart } from "@/components/Chart";

export default function Calculator() {
  const [v, setV] = useState<Inputs>(DEFAULTS);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const seq = useRef(0);

  useEffect(() => {
    const id = ++seq.current;
    setBusy(true);
    const t = setTimeout(async () => {
      const a = await calculate(v);
      if (id !== seq.current) return;                       // a newer request is on its way
      setBusy(false);
      if ("error" in a) setError(a.error);
      else {
        setError(null);
        setAnswer(a);
      }
    }, 450);
    return () => clearTimeout(t);
  }, [v]);

  const set = (p: Partial<Inputs>) => setV((old) => ({ ...old, ...p }));
  const product = answer?.results.find((r) => r.kind === "product");
  const series = useMemo(() => (answer ? answer.results.map((r) => ({ id: r.id, name: r.name, ...answer.series[r.id] })).filter((s) => s.dates) : []), [answer]);
  const fanFrom = product && answer ? { date: answer.series[product.id].dates.at(-1)!, value: (product.headline === "sold" ? product.net : product.held_net).value } : undefined;

  return (
    <InfoProvider traces={answer?.traces ?? {}}>
      <section className="intro">
        <h1>If you had invested on a date, what would you have now, after every charge and tax?</h1>
        <p>The model picks once a year, from past data only, between plain holding at your risk level and simple mixes of Indian ETFs and a liquid fund; it is
          compared with buying and holding each alternative. Every rupee is charged and taxed by the rules of its own date.</p>
      </section>
      <Controls v={v} set={set} />
      <div className={busy ? "status busy" : "status"} aria-live="polite">{busy ? "Working it out…" : error ? "" : answer ? "Up to date" : ""}</div>
      {error && <p className="error" role="alert">{error}</p>}
      {answer && (
        <>
          {answer.messages.length > 0 && (
            <ul className="messages">{answer.messages.map((m) => <li key={m.id}><b>{m.id.replace("PRODUCT_", "Model ")}</b>: {m.text}</li>)}</ul>
          )}
          <Chart series={series} fan={product ? answer.projections[product.id] : undefined} fanFrom={fanFrom} />
          <section className="cards">
            {answer.results.map((r) => (
              <ResultCard key={r.id} r={r} amount={v.amount} start={answer.inputs.start as string} end={answer.inputs.end as string} projection={answer.projections[r.id]} />
            ))}
          </section>
          <section className="exports">
            {answer.csv.trades && <button onClick={() => download("model-trades.csv", answer.csv.trades)}>Model trades (CSV)</button>}
            {answer.csv.tax_lines && <button onClick={() => download("model-tax-lines.csv", answer.csv.tax_lines)}>Model tax lines (CSV)</button>}
          </section>
          <section className="stamps">
            <span>Data as of {answer.stamps.data_as_of}</span>
            <span>Rules verified on {answer.stamps.rules_verified_on}</span>
            <span>Signal: {answer.stamps.signal}</span>
            {answer.check.product_books_less_fast_simulator_rupees !== undefined &&
              <span>Model's exact books vs its fast simulator: Rs {answer.check.product_books_less_fast_simulator_rupees.toFixed(2)}</span>}
          </section>
          <ul className="notes">{answer.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </>
      )}
    </InfoProvider>
  );
}
