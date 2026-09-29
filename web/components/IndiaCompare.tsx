"use client";

import { useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { OPTIONS, SLABS, inr, pct, site } from "@/lib/data";

/** Where ₹1 lakh went: every option ranked by rupees in hand, at the reader's tax slab. */
export default function IndiaCompare() {
  const [slab, setSlab] = useState("0.312");
  const reduce = useReducedMotion();
  const data = site.india[slab];
  const rows = OPTIONS.map((o) => ({ ...o, ...data[o.key] })).sort((a, b) => b.end - a.end);
  const top = rows[0].end;

  return (
    <div>
      <div className="mb-8 flex flex-wrap items-center gap-2 text-sm">
        <span className="mr-1 text-muted">Your income-tax slab</span>
        {SLABS.map(([v, label]) => (
          <button key={v} onClick={() => setSlab(v)} aria-pressed={slab === v}
            className={`num rounded-full px-3.5 py-1.5 text-[13px] transition-[background-color,box-shadow,transform] active:scale-[0.97] ${
              slab === v ? "bg-ink text-page" : "bg-surface text-muted ring-1 ring-line hover:text-ink"}`}>
            {label}
          </button>
        ))}
      </div>

      <ol className="space-y-5">
        {rows.map((r, i) => {
          const model = r.name === "DeepTrend model";
          return (
            <li key={r.key} className="grid grid-cols-[1fr_auto] items-center gap-x-6 gap-y-2 md:grid-cols-[13rem_1fr_7rem_6rem]">
              <p className={`text-[15px] ${model ? "font-semibold text-accent" : "text-ink"}`}>
                <span className="num mr-2 text-faint">{i + 1}</span>{r.name}
              </p>
              <div className="order-last col-span-2 h-2.5 md:order-none md:col-span-1">
                <motion.div
                  className="h-full rounded-full"
                  style={{ backgroundColor: model ? "var(--color-accent)" : r.color, opacity: model ? 1 : 0.55 }}
                  initial={reduce ? false : { width: 0 }}
                  animate={{ width: `${(r.end / top) * 100}%` }}
                  transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
                />
              </div>
              <p className={`num text-right text-[15px] ${model ? "font-semibold text-ink" : "text-ink"}`}>{inr(r.end)}</p>
              <p className="num hidden text-right text-sm text-muted md:block">
                {pct(r.per_year)}<span className="text-faint">/yr</span>
              </p>
            </li>
          );
        })}
      </ol>

      <div className="mt-10 grid gap-6 border-t border-line pt-6 text-sm md:grid-cols-3">
        {rows.filter((r) => ["DeepTrend model", "Gold ETF, India", "Nifty 50"].includes(r.name)).map((r) => (
          <p key={r.key} className="text-muted">
            <span className="text-ink">{r.name}</span> worst fall along the way{" "}
            <span className={`num ${r.worst_drop < -0.2 ? "text-loss" : "text-ink"}`}>{pct(r.worst_drop, 0)}</span>
          </p>
        ))}
      </div>
    </div>
  );
}
