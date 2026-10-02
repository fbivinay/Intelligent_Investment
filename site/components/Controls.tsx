"use client";

import type { Inputs } from "@/lib/types";
import { OPTIONS } from "@/lib/api";

const LEVELS: { id: Inputs["level"]; cap: string }[] = [
  { id: "Conservative", cap: "falls up to about 10%" },
  { id: "Balanced", cap: "about 20%" },
  { id: "Aggressive", cap: "about 30%" },
  { id: "Growth", cap: "no fall guard: fell up to about 30%" },
];

export function Controls({ v, set }: { v: Inputs; set: (p: Partial<Inputs>) => void }) {
  return (
    <section className="controls" aria-label="Inputs">
      <label>Amount (₹)
        <input type="number" min={10000} step={10000} value={v.amount} onChange={(e) => set({ amount: Number(e.target.value) })} name="amount" />
      </label>
      <label>Start
        <input type="date" min="2010-04-01" max="2026-09-29" value={v.start} onChange={(e) => set({ start: e.target.value })} name="start" />
      </label>
      <label>End
        <input type="date" min="2010-04-02" max="2026-09-30" value={v.end} onChange={(e) => set({ end: e.target.value })} name="end" />
      </label>
      <fieldset className="levels">
        <legend>Model risk level</legend>
        {LEVELS.map((l) => (
          <button key={l.id} className={v.level === l.id ? "on" : ""} onClick={() => set({ level: l.id })} aria-pressed={v.level === l.id} title={l.cap}>
            {l.id}
          </button>
        ))}
      </fieldset>
      <label>Tax regime
        <select value={v.regime} onChange={(e) => set({ regime: e.target.value as Inputs["regime"] })} name="regime">
          <option value="new">New</option>
          <option value="old">Old</option>
        </select>
      </label>
      <label>Other income a year (₹)
        <input type="number" min={0} step={50000} value={v.other_income} onChange={(e) => set({ other_income: Number(e.target.value) })} name="other_income" />
      </label>
      <label>At the end
        <select value={v.end_convention} onChange={(e) => set({ end_convention: e.target.value as Inputs["end_convention"] })} name="end_convention">
          <option value="sell">Sell everything and pay the tax</option>
          <option value="hold">Still holding</option>
        </select>
      </label>
      <label className="check">
        <input type="checkbox" checked={v.slippage} onChange={(e) => set({ slippage: e.target.checked })} /> Model pays slippage (assumed)
      </label>
      <label>Estimate for the next {v.horizon} years
        <input type="range" min={1} max={20} value={v.horizon} onChange={(e) => set({ horizon: Number(e.target.value) })} name="horizon" />
      </label>
      <fieldset className="compare">
        <legend>Compare with</legend>
        {OPTIONS.map((o) => (
          <label key={o.id} className="chip">
            <input type="checkbox" checked={v.compare.includes(o.id)}
              onChange={(e) => set({ compare: e.target.checked ? [...v.compare, o.id] : v.compare.filter((c) => c !== o.id) })} />
            {o.name}
          </label>
        ))}
      </fieldset>
    </section>
  );
}
