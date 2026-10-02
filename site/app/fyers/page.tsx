"use client";

import { useEffect, useState } from "react";
import { preview } from "@/lib/api";
import type { Preview } from "@/lib/types";
import { pct, rupees, rupeesExact } from "@/lib/format";

const NAMES: Record<string, string> = { NIFTYBEES: "Nifty BeES", JUNIORBEES: "Junior BeES", BANKBEES: "Bank BeES", GOLDBEES: "Gold BeES", MOM100: "Midcap 100 ETF", MON100: "Nasdaq 100 ETF", LIQUID_FUND: "Liquid fund" };

export default function Fyers() {
  const [form, setForm] = useState({ amount: 1000000, start: "2019-04-01", end: "2021-04-01", level: "Balanced", date: "" });
  const [days, setDays] = useState<string[]>([]);
  const [pv, setPv] = useState<Preview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);

  useEffect(() => {
    setBusy(true);
    const t = setTimeout(async () => {
      const body: Record<string, unknown> = { amount: form.amount, start: form.start, end: form.end, level: form.level };
      if (form.date) body.date = form.date;
      const a = await preview(body);
      setBusy(false);
      if ("error" in a) { setError(a.error); setPv(null); return; }
      setError(null);
      setDays(a.order_days);
      setPv(a.preview);
    }, 400);
    return () => clearTimeout(t);
  }, [form]);

  const set = (p: Partial<typeof form>) => setForm((f) => ({ ...f, ...p }));
  return (
    <>
      <section className="intro">
        <h1>How it would run on Fyers</h1>
        <p className="badge-line"><span className="badge">PREVIEW ONLY</span> No account, no keys, nothing is sent to Fyers. A past day of the model's account, replayed.
          A page of live buy and sell signals could count as investment advice under SEBI rules, so this shows past days only.</p>
      </section>
      <section className="controls">
        <label>Amount (₹)<input type="number" value={form.amount} onChange={(e) => set({ amount: Number(e.target.value), date: "" })} /></label>
        <label>Start<input type="date" min="2013-04-01" value={form.start} onChange={(e) => set({ start: e.target.value, date: "" })} /></label>
        <label>End<input type="date" max="2026-09-30" value={form.end} onChange={(e) => set({ end: e.target.value, date: "" })} /></label>
        <label>Risk level
          <select value={form.level} onChange={(e) => set({ level: e.target.value, date: "" })}>
            <option>Conservative</option><option>Balanced</option><option>Aggressive</option><option>Growth</option>
          </select>
        </label>
        <label>Day with orders
          <select value={form.date || pv?.fill_day || ""} onChange={(e) => set({ date: e.target.value })} name="day">
            {days.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </label>
      </section>
      <div className={busy ? "status busy" : "status"} aria-live="polite">{busy ? "Working it out…" : ""}</div>
      {error && <p className="error" role="alert">{error}</p>}
      {pv && (
        <section className="preview">
          <ol className="timeline">{pv.timeline.map((t, i) => <li key={i}>{t}</li>)}</ol>
          <div className="two">
            <table className="lines">
              <caption>Target weights decided after the close of {pv.decided_on}</caption>
              <tbody>{Object.entries(pv.targets).map(([k, w]) => <tr key={k}><td>{NAMES[k]}</td><td>{pct(w)}</td></tr>)}</tbody>
            </table>
            <table className="lines">
              <caption>Held after the close of {pv.decided_on}</caption>
              <tbody>{Object.entries(pv.holdings_before).map(([k, u]) => (
                <tr key={k}><td>{NAMES[k]}</td><td>{k === "LIQUID_FUND" ? rupees(pv.values_before[k]) : `${u.toFixed(0)} units · ${rupees(pv.values_before[k])}`}</td></tr>
              ))}</tbody>
            </table>
          </div>
          <h2>Orders filled on {pv.fill_day}</h2>
          {pv.orders.length === 0 && <p>No orders that day.</p>}
          {pv.orders.map((o, i) => (
            <article key={i} className="order">
              <header>
                <b>{o.trade.side === "buy" ? "Buy" : "Sell"} {o.trade.asset === "LIQUID_FUND" ? `${rupeesExact(Number(o.trade.turnover))} of` : `${o.trade.units}`} {NAMES[o.trade.asset]}</b>
                {o.trade.asset === "LIQUID_FUND" ? "" : ` at ${rupeesExact(Number(o.trade.price))}`} ·
                charges {rupeesExact(Number(o.fees))}{o.depository !== "0" ? ` + depository ${rupeesExact(Number(o.depository))}` : ""}
              </header>
              <p className="small">{o.how}</p>
              {o.payload && <pre>{JSON.stringify(o.payload, null, 2)}</pre>}
            </article>
          ))}
          {pv.orders.length > 0 && <p>Estimated charges for the day: {rupeesExact(pv.total_fees)}{pv.total_depository ? `, depository ${rupeesExact(pv.total_depository)}` : ""} (the engine's
            rules for that date).</p>}
        </section>
      )}
    </>
  );
}
