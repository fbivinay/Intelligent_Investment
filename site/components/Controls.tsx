"use client";

import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { DATA_END, FIRST_DAY, LEVELS, OPTIONS } from "@/lib/api";
import { day, inr, inrShort } from "@/lib/format";
import type { Level } from "@/lib/types";
import { Segmented } from "./motion";

const MIN = 10000, MAX = 1e9;
const QUICK = [100000, 500000, 1000000, 2500000, 10000000];

export function AmountField({ value, onChange, inputRef }: { value: number; onChange: (n: number) => void; inputRef?: React.Ref<HTMLInputElement> }) {
  const [text, setText] = useState(inr(value).slice(1));
  useEffect(() => setText(inr(value).slice(1)), [value]);
  const n = Number(text.replace(/[^\d]/g, ""));
  const bad = !n || n < MIN || n > MAX;
  return (
    <div className="field">
      <label className="label" htmlFor="amount">You invest</label>
      <div className={bad ? "amount bad" : "amount"}>
        <span>₹</span>
        <input id="amount" ref={inputRef} inputMode="numeric" value={text} aria-invalid={bad}
          onChange={(e) => {
            const v = Number(e.target.value.replace(/[^\d]/g, ""));
            setText(v ? inr(v).slice(1) : "");
            if (v >= MIN && v <= MAX) onChange(v);
          }} />
      </div>
      {bad && <p className="hint">Between ₹10,000 and ₹100 crore.</p>}
      <div className="chips">
        {QUICK.map((q) => (
          <motion.button key={q} whileTap={{ scale: 0.95 }} className={q === value ? "chip on" : "chip"} onClick={() => onChange(q)}>{inrShort(q).replace(".00", "")}</motion.button>
        ))}
      </div>
    </div>
  );
}

export function DateField({ value, level, onChange }: { value: string; level: Level; onChange: (d: string) => void }) {
  const last = "2026-09-29";
  return (
    <div className="field">
      <label className="label" htmlFor="start">Invested on</label>
      <input id="start" type="date" className="input" value={value} min={FIRST_DAY[level]} max={last}
        onChange={(e) => e.target.value >= FIRST_DAY[level] && e.target.value <= last && onChange(e.target.value)} />
      <p className="hint">Held until {day(DATA_END)}, the last day of the data.</p>
    </div>
  );
}

export function StrategyList({ value, onChange }: { value: Level; onChange: (l: Level) => void }) {
  return (
    <div className="field">
      <span className="label">Strategy</span>
      <div className="levels" role="radiogroup">
        {LEVELS.map((l) => (
          <button key={l.id} role="radio" aria-checked={value === l.id} className={value === l.id ? "level on" : "level"} onClick={() => onChange(l.id)}>
            {value === l.id && <motion.span layoutId="level-bg" className="level-bg" transition={{ type: "spring", stiffness: 420, damping: 38 }} />}
            <span className="level-name">{l.name}</span>
            <motion.span className="level-line" initial={false} animate={{ height: value === l.id ? "auto" : 0, opacity: value === l.id ? 1 : 0 }}
              transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}>{l.line}</motion.span>
          </button>
        ))}
      </div>
    </div>
  );
}

export function BenchmarkSelect({ value, onChange, label = "Compared with" }: { value: string; onChange: (id: string) => void; label?: string }) {
  return (
    <div className="field">
      <label className="label" htmlFor="bench">{label}</label>
      <select id="bench" className="input" value={value} onChange={(e) => onChange(e.target.value)}>
        {OPTIONS.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
      </select>
    </div>
  );
}

const INCOMES = [0, 500000, 1000000, 1200000, 1500000, 2500000, 5000000];

export function TaxFields({ regime, income, onChange }: { regime: "new" | "old"; income: number; onChange: (p: { regime?: "new" | "old"; other_income?: number }) => void }) {
  return (
    <div className="field">
      <span className="label">Your tax</span>
      <div className="tax-row">
        <Segmented id="regime" size="sm" value={regime} onChange={(r) => onChange({ regime: r })} options={[{ id: "new", label: "New regime" }, { id: "old", label: "Old regime" }]} />
        <select className="input input-sm" aria-label="Other income a year" value={income} onChange={(e) => onChange({ other_income: Number(e.target.value) })}>
          {INCOMES.map((i) => <option key={i} value={i}>{i ? `${inrShort(i).replace(".00", "")} other income` : "No other income"}</option>)}
        </select>
      </div>
    </div>
  );
}
