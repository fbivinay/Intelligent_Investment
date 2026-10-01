"use client";

import { useState } from "react";
import type { TraceNode } from "@/lib/types";

const OPS: Record<string, string> = { const: "input", rule: "from a rule", add: "sum", sub: "difference", mul: "product", div: "ratio", max: "larger of", min: "smaller of",
  round: "rounded", floor: "rounded down", more: "the rest, summed" };

function value(v: string): string {
  const n = Number(v);
  if (!Number.isFinite(n)) return v;
  return Math.abs(n) >= 1000 ? n.toLocaleString("en-IN", { maximumFractionDigits: 6 }) : v;
}

function Source({ s }: { s: string }) {
  const url = s.match(/https?:\/\/\S+/)?.[0];
  return url ? <a href={url} target="_blank" rel="noreferrer">{s}</a> : <span>{s}</span>;
}

function Node({ n, depth }: { n: TraceNode; depth: number }) {
  const [open, setOpen] = useState(depth < 1);
  const kids = n.inputs ?? [];
  return (
    <li className="tnode">
      <div className="trow">
        {kids.length ? <button className="tog" onClick={() => setOpen(!open)} aria-expanded={open}>{open ? "−" : "+"}</button> : <span className="tog" />}
        <span className="tlabel">{n.label}</span>
        <span className="tval">{value(n.value)}</span>
        <span className="top">{kids.length ? n.formula : OPS[n.op] ?? n.op}</span>
      </div>
      {n.note && <div className="tnote">{n.note}</div>}
      {n.rules?.map((r, i) => (
        <div key={i} className={`trule ${r.confidence}`}>
          <b>{r.id}</b> {r.from}{r.to ? ` to ${r.to}` : " on"} · {r.confidence} · checked {r.verified_on} · <Source s={r.source} />
        </div>
      ))}
      {open && kids.length > 0 && <ul>{kids.map((k, i) => <Node key={i} n={k} depth={depth + 1} />)}</ul>}
    </li>
  );
}

export function TraceTree({ node }: { node: TraceNode }) {
  return (
    <div className="trace">
      {node.flags && node.flags.length > 0 && (
        <details className="flags">
          <summary>{node.flags.length} rule{node.flags.length > 1 ? "s" : ""} behind this number {node.flags.length > 1 ? "are" : "is"} not from an official text (show)</summary>
          <ul>{node.flags.map((f, i) => <li key={i}><b>{f.id}</b> ({f.confidence}){f.note ? `: ${f.note}` : ""}</li>)}</ul>
        </details>
      )}
      <ul className="troot"><Node n={node} depth={0} /></ul>
      <p className="hint">Every value is worked out from the lines under it, exactly; expand a line with +. Long lists show their first lines and the rest summed.</p>
    </div>
  );
}
