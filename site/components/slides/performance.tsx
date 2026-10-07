"use client";

// Performance: the calculator (one payment or every month) and what its answer shows: the outcome, where the money went, the path, the model's
// trades; then what the same plan could become from today. Every past figure is the calculator API's answer for the form (lib/data.tsx).
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { LIMITS, request, useData, type Form } from "@/lib/data";
import type { SlideDef } from "@/lib/deck";
import { count, day, inr, money, month, pct, signed, span, tick } from "@/lib/format";
import { ALTERNATIVES, colorOf, DATA_END, groupColor, groupName, isModel, LEVELS, levelOf, nameOf } from "@/lib/names";
import { grid } from "@/lib/scale";
import type { Answer, Level, Result, TradeDay } from "@/lib/types";
import { LineChart, RankedBars, StackArea, TradeStrip, type LineSeries } from "../charts";
import { Appear, Arrow, Chip, Counter, EASE, ENTER, Key, Rise, Segmented } from "../ui";
import { Loading } from "./overview";

const label = (id: string) => (isModel(id) ? "Intelligent Investment" : nameOf(id));
const perYear = (a: Answer) => (a.inputs.mode === "sip" ? "Per year (XIRR)" : "Per year");

/** The answer on screen, the model's result and the alternatives in palette order. */
function useAnswer() {
  const d = useData();
  const a = d.answer;
  const model = a?.results.find((r) => r.kind === "product") ?? null;
  const alts = a ? ALTERNATIVES.map((id) => a.results.find((r) => r.id === id)).filter((r): r is Result => !!r) : [];
  return { ...d, a, model, alts };
}

/** A thin bar and a line of text while the calculator works, or what went wrong and a way to try again. */
function Status() {
  const { status, since, error, retry } = useData();
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (status !== "loading") return;
    const t = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(t);
  }, [status]);
  const secs = Math.max(0, Math.round((now - since) / 1000));
  return (
    <div className="status" aria-live="polite">
      <AnimatePresence initial={false}>
        {status === "loading" && (
          <motion.div key="busy" className="busy" initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.3 }}>
            <span className="busy-bar"><span /></span>
            <span>{secs < 3 ? "Working it out" : `Replaying every order with its exact charges and tax, ${secs} s`}</span>
          </motion.div>
        )}
        {status === "error" && (
          <motion.div key="err" className="err" role="alert" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <span>{error}</span>
            <button type="button" onClick={retry}>Try again</button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function MoneyField({ id, mode, value, onChange }: { id: string; mode: "lump" | "sip"; value: number; onChange: (n: number) => void }) {
  const lump = mode === "lump";
  const [lo, hi] = LIMITS[mode];
  const [text, setText] = useState(inr(value).slice(1));
  const [bad, setBad] = useState(false);
  const focused = useRef(false);
  useEffect(() => { if (!focused.current) { setText(inr(value).slice(1)); setBad(false); } }, [value]);
  const take = (raw: string) => {
    const digits = raw.replace(/[^\d]/g, "");
    setText(digits ? inr(+digits).slice(1) : "");
    const n = +digits;
    const ok = n >= lo && n <= hi;
    setBad(!ok);
    if (ok) onChange(n);
  };
  const picks = lump ? [100_000, 500_000, 1_000_000, 2_500_000] : [2_000, 5_000, 10_000, 25_000];
  return (
    <div className="field">
      <label htmlFor={id}>{lump ? "Amount, once" : "Amount, every month"}</label>
      <div className={bad ? "money-input bad" : "money-input"}>
        <span>₹</span>
        <input id={id} inputMode="numeric" autoComplete="off" value={text} aria-invalid={bad}
          onFocus={() => (focused.current = true)} onBlur={() => { focused.current = false; if (bad || !text) { setText(inr(value).slice(1)); setBad(false); } }}
          onChange={(e) => take(e.target.value)} />
      </div>
      {bad && <p className="field-err">Between {money(lo)} and {money(hi)}.</p>}
      <div className="chips">
        {picks.map((p) => <Chip key={p} on={value === p} onClick={() => take(String(p))}>{money(p, 0)}</Chip>)}
      </div>
    </div>
  );
}

function AmountField({ form, set }: { form: Form; set: (p: Partial<Form>) => void }) {
  return <MoneyField id="amount" mode={form.mode} value={form.mode === "lump" ? form.lumpAmount : form.sipAmount}
    onChange={(n) => set(form.mode === "lump" ? { lumpAmount: n } : { sipAmount: n })} />;
}

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

function WhenField({ form, set }: { form: Form; set: (p: Partial<Form>) => void }) {
  const first = levelOf(form.level).first;
  const firstYear = +first.slice(0, 4);
  const start = request(form).start;
  if (form.mode === "lump") {
    // Any month from the strategy's first day to a month before the data ends, chosen as a month and a year; the start is that month's first day
    // (the first trading day on or after it), never before the strategy's first day.
    const fm = +first.slice(5, 7), ly = +DATA_END.slice(0, 4), lm = +DATA_END.slice(5, 7) - 1;
    const y = +start.slice(0, 4), m = +start.slice(5, 7);
    const lo = (yy: number) => (yy === firstYear ? fm : 1), hi = (yy: number) => (yy === ly ? lm : 12);
    const pick = (yy: number, mm: number) => {
      const s = `${yy}-${String(Math.min(Math.max(mm, lo(yy)), hi(yy))).padStart(2, "0")}-01`;
      set({ start: s < first ? first : s });
    };
    const years = Array.from({ length: ly - firstYear + 1 }, (_, k) => firstYear + k);
    const quick = [firstYear, firstYear + 2, firstYear + 4, firstYear + 6].filter((v) => v <= 2025);
    return (
      <div className="field">
        <span className="field-label">Invested in</span>
        <div className="date-pick">
          <div className="select">
            <select aria-label="Month" value={m} onChange={(e) => pick(y, +e.target.value)}>
              {MONTHS.map((_, k) => k + 1).filter((mm) => mm >= lo(y) && mm <= hi(y)).map((mm) => <option key={mm} value={mm}>{MONTHS[mm - 1]}</option>)}
            </select>
          </div>
          <div className="select">
            <select aria-label="Year" value={y} onChange={(e) => pick(+e.target.value, m)}>
              {years.map((yy) => <option key={yy} value={yy}>{yy}</option>)}
            </select>
          </div>
        </div>
        <div className="chips">
          {quick.map((yy) => <Chip key={yy} on={y === yy} onClick={() => pick(yy, yy === firstYear ? fm : 1)}>{yy === firstYear ? month(first) : String(yy)}</Chip>)}
        </div>
        <p className="field-hint">
          {form.level === "Max" ? "Max can start from April 2017: its share data begins in January 2016 and each pick needs a year of prices."
            : `This model can start from ${month(first, true)}, its first pick.`}
        </p>
      </div>
    );
  }
  const most = (Date.parse(DATA_END) - Date.parse(first)) / (365.25 * 864e5);
  const spans = [1, 3, 5, 7, 10].filter((n) => n < most);
  return (
    <div className="field">
      <span className="field-label">For</span>
      <div className="chips">
        {spans.map((n) => <Chip key={n} on={form.years === n} onClick={() => set({ years: n })}>{n} {n === 1 ? "year" : "years"}</Chip>)}
        <Chip on={form.years === "all"} onClick={() => set({ years: "all" })}>Since {month(first)}</Chip>
      </div>
      <p className="field-hint">Paid on the same day each month, up to {day(DATA_END)}.</p>
    </div>
  );
}

function Calculator() {
  const { form, set, a, model, alts, saved } = useAnswer();
  const [tax, setTax] = useState(false);
  if (!form || !saved) return <Loading text="Loading the calculator" />;
  const lvl = levelOf(form.level);
  const toggle = (id: string) => set({ compare: form.compare.includes(id) ? form.compare.filter((x) => x !== id) : [...form.compare, id] });
  return (
    <div className="calc">
      <Appear className="calc-form" delay={0.05}>
        <form onSubmit={(e) => e.preventDefault()} aria-label="Your scenario" data-scroll>
          <Segmented id="mode" label="How you invest" value={form.mode} onChange={(m) => set({ mode: m })}
            options={[{ id: "lump", label: "One-time" }, { id: "sip", label: "Monthly SIP" }]} />
          <AnimatePresence mode="popLayout" initial={false}>
            <motion.div key={form.mode} className="calc-fields" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.35, ease: EASE }}>
              <AmountField form={form} set={set} />
              <WhenField form={form} set={set} />
            </motion.div>
          </AnimatePresence>
          <div className="field">
            <label htmlFor="level">Strategy</label>
            <div className="select">
              <select id="level" value={form.level} onChange={(e) => set({ level: e.target.value as Form["level"] })}>
                {LEVELS.map((l) => <option key={l.id} value={l.id}>Intelligent Investment {l.name}</option>)}
              </select>
            </div>
            <p className="field-hint">{lvl.line}{lvl.id === "Max" ? ": the model in Evidence." : ": a simpler ETF model."}</p>
          </div>
          <div className="field">
            <span className="field-label">Compare with</span>
            <div className="chips">
              {ALTERNATIVES.map((id) => <Chip key={id} on={form.compare.includes(id)} color={colorOf(id)} onClick={() => toggle(id)}>{nameOf(id)}</Chip>)}
            </div>
          </div>
          <div className="field tax">
            <button type="button" className="tax-toggle" aria-expanded={tax} onClick={() => setTax((t) => !t)}>
              <span className="field-label">Your tax</span>
              <span>{form.regime === "new" ? "New" : "Old"} regime, {money(form.income, 0)} other income</span>
              <span className="tax-edit">{tax ? "Done" : "Change"}</span>
            </button>
            <AnimatePresence initial={false}>
              {tax && (
                <motion.div className="tax-body" initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.45, ease: EASE }}>
                  <Segmented id="regime" label="Tax regime" value={form.regime} onChange={(r) => set({ regime: r })}
                    options={[{ id: "new", label: "New regime" }, { id: "old", label: "Old regime" }]} />
                  <div className="chips">
                    {[0, 600_000, 1_200_000, 1_800_000, 3_000_000].map((n) => (
                      <Chip key={n} on={form.income === n} onClick={() => set({ income: n })}>{n ? money(n, 0) : "₹0"}</Chip>
                    ))}
                  </div>
                  <p className="field-hint">Other taxable income a year. It sets the slab on fund gains and whether the rebate applies.</p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </form>
      </Appear>
      <div className="calc-out">
        <Rise as="h2" className="title" lines={["How your money would have grown"]} />
        <Status />
        {a && model ? <Outcome a={a} model={model} alts={alts} /> : <Loading text="Working it out" />}
      </div>
    </div>
  );
}

function Outcome({ a, model, alts }: { a: Answer; model: Result; alts: Result[] }) {
  const { status } = useData();
  const i = a.inputs;
  const period = i.mode === "lump"
    ? <>{inr(i.amount)} on {day(i.start)}, valued on {day(i.end)}</>
    : <>{inr(i.amount)} every month from {month(i.start)} to {month(i.end)}, {money(model.invested)} put in</>;
  return (
    <motion.div className="outcome" animate={{ opacity: status === "loading" ? 0.55 : 1 }} transition={{ duration: 0.4 }}>
      <p className="period">{period}</p>
      <div className="headline-result">
        <div>
          <span className="cap"><Key color={colorOf(model.id)} />The model ({levelOf(i.level).name}), after charges and tax</span>
          <Counter className="big-figure" value={model.net.value} format={(n) => money(n)} />
        </div>
        <dl className="mini">
          <div><dt>Put in</dt><dd><Counter value={model.invested} format={(n) => money(n)} /></dd></div>
          <div><dt>Profit</dt><dd><Counter value={model.profit} format={(n) => money(n)} /></dd></div>
          <div><dt>Per year</dt><dd><Counter value={model.growth} format={(n) => pct(n)} /> <small>{a.inputs.mode === "sip" ? "XIRR" : "CAGR"}</small></dd></div>
          <div><dt>Charges and tax</dt><dd><Counter value={model.charges.value + model.tax.value} format={(n) => money(n)} /></dd></div>
        </dl>
      </div>
      <div className="table-wrap" data-scroll>
      <table className="compare">
        <thead><tr><th>Option</th><th>Final value</th><th>Profit</th><th>{perYear(a)}</th><th>Against the model</th></tr></thead>
        <tbody>
          {[model, ...alts].map((r, k) => {
            const d = r.net.value - model.net.value;
            return (
              <motion.tr key={r.id} className={isModel(r.id) ? "is-model" : ""} layout initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, ease: EASE, delay: ENTER + 0.1 + k * 0.05 }}>
                <td><Key color={colorOf(r.id)} />{label(r.id)}</td>
                <td><Counter value={r.net.value} format={(n) => money(n)} /></td>
                <td><Counter value={r.profit} format={(n) => money(n)} /></td>
                <td><Counter value={r.growth} format={(n) => pct(n)} /></td>
                <td className={isModel(r.id) ? "muted" : d >= 0 ? "more" : "less"}>{isModel(r.id) ? "—" : `${money(Math.abs(d))} ${d >= 0 ? "more" : "less"}`}</td>
              </motion.tr>
            );
          })}
        </tbody>
      </table>
      </div>
      {a.messages.length > 0 && <ul className="messages">{a.messages.map((m) => <li key={m.id}>{nameOf(m.id)}: {m.text}</li>)}</ul>}
      <p className="fine">
        Each option gets the same money on the same days and is sold on the last day; tax is worked out for your profile, year by year.
        {i.regime === "new" && i.other_income === 1_200_000 && <> {money(i.other_income)} of other income sits at the new regime&rsquo;s rebate limit, so the first gains from 2025-26 on are taxed heavily.</>}
      </p>
    </motion.div>
  );
}

function Bench({ alts }: { alts: Result[] }) {
  const { form, set } = useData();
  if (!form) return null;
  const bench = alts.find((r) => r.id === form.bench) ?? alts[0];
  return (
    <div className="field bench">
      <label htmlFor="bench">Set beside the model</label>
      <div className="select">
        <select id="bench" value={bench?.id} onChange={(e) => set({ bench: e.target.value })}>
          {alts.map((r) => <option key={r.id} value={r.id}>{nameOf(r.id)}</option>)}
        </select>
      </div>
    </div>
  );
}

function useBench(alts: Result[]) {
  const { form } = useData();
  return alts.find((r) => r.id === form?.bench) ?? alts[0] ?? null;
}

function Costs() {
  const { a, model, alts } = useAnswer();
  const bench = useBench(alts);
  if (!a || !model) return <Loading text="Working it out" />;
  const rows = [model, ...(bench ? [bench] : [])];
  const top = Math.max(...rows.map((r) => r.gross_end.value));
  const taxes = model.tax_by_fy.filter((t) => Math.abs(t.value) >= 1);
  const tmax = Math.max(...taxes.map((t) => Math.abs(t.value)), 1);
  const all = [...model.charges_by_kind].filter((c) => c.value >= 1).sort((x, y) => y.value - x.value);
  const kinds = all.length > 5 ? [...all.slice(0, 4), { label: "Everything else", value: all.slice(4).reduce((x, c) => x + c.value, 0) }] : all;
  const kmax = Math.max(...kinds.map((c) => c.value), 1);
  return (
    <div className="costs">
      <div className="costs-head">
        <Rise className="statement" lines={["Every charge.", "Every rupee of tax.", "Counted."]} />
        <Appear delay={0.3}><p className="lead">What each would have been worth before costs, and what was left once charges and tax were paid. Selling often pays tax every year; holding pays it once, at the sale.</p></Appear>
        <Appear delay={0.4}><Bench alts={alts} /></Appear>
      </div>
      <div className="splits">
        {rows.map((r, k) => {
          const parts = [
            { id: "kept", label: "You keep", value: r.net.value, cls: "kept" },
            { id: "tax", label: "Tax", value: r.tax.value, cls: "taxed" },
            { id: "chg", label: "Charges", value: r.charges.value, cls: "charged" },
          ];
          return (
            <Appear key={r.id} delay={0.35 + k * 0.12} className="split">
              <div className="split-head"><span><Key color={colorOf(r.id)} />{label(r.id)}</span><span>Before costs <b>{money(r.gross_end.value)}</b></span></div>
              <div className="split-bar" style={{ width: `${(r.gross_end.value / top) * 100}%` }}>
                {parts.map((p, j) => (
                  <motion.span key={p.id} className={`part ${p.cls}`} style={p.id === "kept" ? { background: colorOf(r.id) } : undefined}
                    initial={{ flexGrow: 0 }} animate={{ flexGrow: Math.max(p.value, 0) }} transition={{ duration: 1.2, ease: EASE, delay: ENTER + 0.5 + j * 0.15 }} />
                ))}
              </div>
              <div className="split-legend">
                {parts.map((p) => <span key={p.id} className={p.cls}><i style={p.id === "kept" ? { background: colorOf(r.id) } : undefined} />{p.label} <b>{money(p.value)}</b> <small>{pct(p.value / r.gross_end.value, 1)}</small></span>)}
              </div>
            </Appear>
          );
        })}
      </div>
      <div className="breakdowns">
        <Appear delay={0.6} className="breakdown">
          <h3>The model&rsquo;s charges, by kind</h3>
          <ul className="hbars">
            {kinds.map((c) => (
              <li key={c.label}><span>{c.label}</span><span className="hbar"><motion.i initial={{ width: 0 }} animate={{ width: `${(c.value / kmax) * 100}%` }} transition={{ duration: 1, ease: EASE, delay: ENTER + 0.8 }} /></span><b>{money(c.value)}</b></li>
            ))}
          </ul>
        </Appear>
        <Appear delay={0.7} className="breakdown">
          <h3>The model&rsquo;s tax, by financial year</h3>
          <div className="cols" role="list">
            {taxes.map((t, k) => (
              <div key={t.fy} className="col" role="listitem" title={`${t.fy}: ${inr(t.value)}`}>
                <span className="col-val">{tick(t.value)}</span>
                <motion.i className={t.value < 0 ? "neg" : ""} initial={{ height: 0 }} animate={{ height: `${(Math.abs(t.value) / tmax) * 100}%` }} transition={{ duration: 0.9, ease: EASE, delay: ENTER + 0.8 + k * 0.05 }} />
                <span className="col-lab">{(t.fy ?? "").replace("FY", "").replace(/^20/, "")}</span>
              </div>
            ))}
          </div>
        </Appear>
      </div>
    </div>
  );
}

type View = "value" | "return" | "fall";

function Journey() {
  const { a, model, alts } = useAnswer();
  const [view, setView] = useState<View>("value");
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [focus, setFocus] = useState<string | null>(null);
  const ids = useMemo(() => (a && model ? [model.id, ...alts.map((r) => r.id)] : []), [a, model, alts]);
  const g = useMemo(() => (a ? {
    value: grid(a.series, ids, (s) => s.values),
    paid: grid(a.series, ids, (s) => s.invested),
    fall: grid(a.series, ids, (s) => s.drawdown.map((x) => -x)),
  } : null), [a, ids]);
  if (!a || !model || !g) return <Loading text="Working it out" />;
  const sip = a.inputs.mode === "sip";
  const vals = (id: string) => view === "value" ? g.value.values[id] : view === "fall" ? g.fall.values[id]
    : g.value.values[id].map((v, i) => v / g.paid.values[id][i] - 1);
  const series: LineSeries[] = ids.map((id) => ({ id, label: label(id), color: colorOf(id), values: vals(id), strong: isModel(id), quiet: view === "fall" && !isModel(id) }));
  if (sip) series.push({ id: "PAID", label: "Money put in", color: "#8D9892", values: g.paid.values[model.id], quiet: true });
  const off = view === "value" ? hidden : new Set([...hidden, "PAID"]);
  const fmt = view === "value" ? (v: number) => money(v) : (v: number) => (view === "fall" ? pct(v, 1) : signed(v, 0));
  const toggle = (id: string) => setHidden((h) => { const n = new Set(h); n.has(id) ? n.delete(id) : n.add(id); return n; });
  return (
    <div className="journey">
      <div className="journey-head">
        <Rise className="statement" lines={["How the money moved,", "day by day."]} />
        <Appear delay={0.3} className="journey-controls">
          <Segmented id="view" label="Show" value={view} onChange={setView}
            options={[{ id: "value", label: "Value" }, { id: "return", label: "Return" }, { id: "fall", label: "Fall from peak" }]} />
          <div className="legend" role="group" aria-label="Show or hide">
            {ids.map((id) => (
              <button key={id} type="button" className={hidden.has(id) ? "lg off" : "lg"} aria-pressed={!hidden.has(id)} onClick={() => toggle(id)}
                onPointerEnter={() => setFocus(id)} onPointerLeave={() => setFocus(null)}>
                <Key color={colorOf(id)} />{label(id)}
              </button>
            ))}
          </div>
        </Appear>
      </div>
      <Appear delay={0.15} y={0} className="journey-chart">
        <LineChart times={g.value.times} series={series} format={fmt} axis={view === "value" ? tick : (v) => (view === "fall" ? pct(v, 0) : signed(v, 0))}
          include={view === "value" ? [] : [0]} hidden={off} focus={focus} view={view} area={view === "fall" ? "zero" : "wash"}
          ends={view === "value" ? Object.fromEntries([model, ...alts].map((r) => [r.id, { value: r.net.value, text: money(r.net.value) }])) : undefined}
          baseline={view === "value" && !sip ? { value: model.invested, label: `${money(model.invested, 0)} put in` } : undefined} />
      </Appear>
      <AnimatePresence mode="wait" initial={false}>
        <motion.p key={view} className="fine journey-note" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.3 }}>
          {view === "value" && <>Lines: worth on each day. Dots: what is left after the final sale and its tax. The model pays tax every year as it goes, so its line already carries most of it.</>}
          {view === "return" && <>Gain on the money put in so far, before the final sale and its tax.</>}
          {view === "fall" && <>How far each was below its own highest point, leaving out money paid in. Deepest: {[model, ...alts].map((r) => `${label(r.id)} ${pct(r.worst_fall, 0)}`).join(", ")}.</>}
        </motion.p>
      </AnimatePresence>
    </div>
  );
}

/** What a trading day of the model did, from the groups bought and sold. */
export function describe(d: TradeDay) {
  const b = d.bought, s = d.sold;
  const sIn = b.STOCKS ?? 0, sOut = s.STOCKS ?? 0, lIn = b.LIQUID_FUND ?? 0, lOut = s.LIQUID_FUND ?? 0;
  if (sOut > 0 && lIn > sOut * 0.5 && sIn < sOut * 0.1) return { title: "Switch to safety", text: `${d.out.length} shares sold, the money parked in the liquid fund` };
  if (sIn > 0 && lOut > sIn * 0.5 && sOut < sIn * 0.1) return { title: "Back into shares", text: `${d.in.length} shares bought with the money from the liquid fund` };
  if (sIn > 0 && sOut > 0) return { title: "Re-pick", text: `${d.out.length} shares out, ${d.in.length} in` };
  const names = (o: Record<string, number>) => Object.keys(o).map(groupName).join(", ");
  if (Object.keys(b).length && Object.keys(s).length) return { title: "Back to the target mix", text: `Sold ${names(s)}; bought ${names(b)}` };
  if (Object.keys(b).length) return { title: "Bought", text: names(b) + (d.in.length ? ` (${d.in.length} shares)` : "") };
  return { title: "Sold", text: names(s) + (d.out.length ? ` (${d.out.length} shares)` : "") };
}

function Trades() {
  const { a, model } = useAnswer();
  const [picked, setPicked] = useState<string | null>(null);
  if (!a || !model || !a.activity) return <Loading text="Working it out" />;
  const act = a.activity;
  const sum = (o: Record<string, number>) => Object.values(o).reduce((x, y) => x + y, 0);
  const days = act.days.map((d) => ({ date: d.date, bought: sum(d.bought), sold: sum(d.sold), orders: d.buys + d.sells }));
  const big = [...act.days].sort((x, y) => sum(y.bought) + sum(y.sold) - sum(x.bought) - sum(x.sold)).slice(0, 4).sort((x, y) => (x.date < y.date ? -1 : 1));
  const order = act.groups.filter((g) => act.allocation.shares[g]?.some((v) => v > 0.002));
  const end = act.holdings.reduce((x, h) => x + h.value, 0);
  const byGroup = Object.entries(act.holdings.reduce<Record<string, number>>((o, h) => ((o[h.group] = (o[h.group] ?? 0) + h.value), o), {})).sort((x, y) => y[1] - x[1]);
  const pick = picked ? act.days.find((d) => d.date === picked) : null;
  const first = act.allocation.dates[0], last = act.allocation.dates.at(-1)!;
  return (
    <div className="trades">
      <div className="trades-head">
        <Rise className="statement" lines={["What trades would the", "model have made?"]} />
        <Appear delay={0.3} className="kpis">
          <div><b><Counter value={act.totals.orders} format={(n) => count(Math.round(n))} /></b><span>orders</span></div>
          <div><b><Counter value={act.totals.buys} format={(n) => count(Math.round(n))} /></b><span>buys</span></div>
          <div><b><Counter value={act.totals.sells} format={(n) => count(Math.round(n))} /></b><span>sales</span></div>
          <div><b><Counter value={act.totals.trade_days} format={(n) => count(Math.round(n))} /></b><span>days with trades, in {span(first, last)}</span></div>
          {act.totals.stocks_traded > 0 && <div><b><Counter value={act.totals.stocks_traded} format={(n) => count(Math.round(n))} /></b><span>different picks held at some point</span></div>}
        </Appear>
      </div>
      <div className="trades-body">
        <div className="trades-charts">
          <Appear delay={0.15} y={0} className="mix">
            <div className="chart-title"><span>Where the money sat</span>
              <span className="mini-legend">{[...order].reverse().map((g) => <span key={g}><Key color={groupColor(g)} />{groupName(g)}</span>)}</span>
            </div>
            <StackArea dates={act.allocation.dates} shares={act.allocation.shares} order={order} color={groupColor} name={groupName} />
          </Appear>
          <Appear delay={0.25} y={0} className="tradestrip">
            <div className="chart-title"><span>Every day it traded</span><span className="mini-legend"><span><i className="sw buy" />Bought</span><span><i className="sw sell" />Sold</span></span></div>
            <TradeStrip days={days} from={first} to={last} onPick={setPicked} picked={picked} />
          </Appear>
        </div>
        <aside className="moves" data-scroll>
          <AnimatePresence mode="wait" initial={false}>
            {pick ? (
              <motion.div key={pick.date} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.25 }}>
                <h3>{day(pick.date)}</h3>
                <p className="move-title">{describe(pick).title}</p>
                <p className="move-text">{describe(pick).text}</p>
                <dl className="flows">
                  {Object.entries(pick.bought).map(([g, v]) => <div key={"b" + g}><dt><Key color={groupColor(g)} />Bought {groupName(g)}</dt><dd>{money(v)}</dd></div>)}
                  {Object.entries(pick.sold).map(([g, v]) => <div key={"s" + g}><dt><Key color={groupColor(g)} />Sold {groupName(g)}</dt><dd>{money(v)}</dd></div>)}
                </dl>
                {(pick.in.length > 0 || pick.out.length > 0) && (
                  <p className="names">{pick.in.length > 0 && <><b>In:</b> {pick.in.slice(0, 12).join(", ")}{pick.in.length > 12 ? ` and ${pick.in.length - 12} more` : ""}. </>}
                    {pick.out.length > 0 && <><b>Out:</b> {pick.out.slice(0, 12).join(", ")}{pick.out.length > 12 ? ` and ${pick.out.length - 12} more` : ""}.</>}</p>
                )}
              </motion.div>
            ) : (
              <motion.div key="list" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.25 }}>
                <h3>Its biggest days</h3>
                <ol className="big-moves">
                  {big.map((d) => {
                    const x = describe(d);
                    return <li key={d.date}><span className="when">{month(d.date)}</span><span className="what"><b>{x.title}</b>{x.text}</span></li>;
                  })}
                </ol>
                <h3>Holding on {day(last)}</h3>
                <ul className="holding">
                  {byGroup.map(([g, v]) => <li key={g}><Key color={groupColor(g)} /><span>{groupName(g)}</span><b>{pct(v / end, 0)}</b></li>)}
                </ul>
                <p className="fine">Point at a day in the strip to see what it bought and sold.</p>
              </motion.div>
            )}
          </AnimatePresence>
        </aside>
      </div>
    </div>
  );
}

type Plan = { mode: "lump" | "sip"; lump: number; sip: number; years: number; level: Level };

/** Invest today: the plan, then one step from money in, through the return each option earned after charges and tax, to what it could be worth.
 * The factors are the backend's (calc/future.py, saved by tools/site_data.py); the value is the factor times the payment. */
function Future() {
  const { saved } = useData();
  const [plan, setPlan] = useState<Plan>({ mode: "lump", lump: 1_000_000, sip: 5_000, years: 5, level: "Max" });
  if (!saved) return <Loading text="Loading the projection" />;
  return <FutureBody f={saved.future} plan={plan} set={(p) => setPlan((x) => ({ ...x, ...p }))} />;
}

function Step({ label, value, sub, strong }: { label: string; value: React.ReactNode; sub: React.ReactNode; strong?: boolean }) {
  return (
    <div className={strong ? "step strong" : "step"}>
      <span className="step-label">{label}</span>
      <span className="step-value">{value}</span>
      <span className="step-sub">{sub}</span>
    </div>
  );
}

function FutureBody({ f, plan, set }: { f: NonNullable<ReturnType<typeof useData>["saved"]>["future"]; plan: Plan; set: (p: Partial<Plan>) => void }) {
  const amount = plan.mode === "lump" ? plan.lump : plan.sip;
  const invested = plan.mode === "lump" ? amount : amount * 12 * plan.years;
  const worth = (id: string) => amount * f.factors[id][plan.mode][plan.years - 1];
  const modelId = `PRODUCT_${plan.level}`;
  const rows = [modelId, ...ALTERNATIVES].filter((id) => f.rates[id]).map((id) => ({ id, rate: f.rates[id].rate, value: worth(id) }))
    .sort((x, y) => y.value - x.value);
  const model = rows.find((r) => r.id === modelId)!;
  const span1 = `${plan.years} ${plan.years === 1 ? "year" : "years"}`;
  return (
    <div className="future">
      <Appear className="calc-form" delay={0.05}>
        <form onSubmit={(e) => e.preventDefault()} aria-label="Your plan" data-scroll>
          <Segmented id="future-mode" label="How you invest" value={plan.mode} onChange={(m) => set({ mode: m })}
            options={[{ id: "lump", label: "One-time" }, { id: "sip", label: "Monthly SIP" }]} />
          <MoneyField id="future-amount" mode={plan.mode} value={amount} onChange={(n) => set(plan.mode === "lump" ? { lump: n } : { sip: n })} />
          <div className="field">
            <label htmlFor="future-years">For <b>{span1}</b></label>
            <input id="future-years" className="range" type="range" min={1} max={20} step={1} value={plan.years} onChange={(e) => set({ years: +e.target.value })} />
            <div className="range-ends" aria-hidden><span>1 year</span><span>20 years</span></div>
          </div>
          <div className="field">
            <label htmlFor="future-level">Strategy</label>
            <div className="select">
              <select id="future-level" value={plan.level} onChange={(e) => set({ level: e.target.value as Level })}>
                {LEVELS.map((l) => <option key={l.id} value={l.id}>Intelligent Investment {l.name}</option>)}
              </select>
            </div>
          </div>
          <p className="field-hint future-note">An estimate from history, not a forecast: each option earns again what it made a year after charges and tax from
            {" "}{month(f.from)} to {month(f.to)} ({money(f.amount, 0)} once, {f.regime} tax regime).</p>
        </form>
      </Appear>
      <div className="future-out">
        <Rise as="h2" className="title" lines={["If you invest today, what could it become?"]} />
        <Appear delay={0.2} className="flow3">
          <Step label={plan.mode === "lump" ? "You invest today" : "You invest every month"} value={<Counter value={amount} format={(n) => money(n)} />}
            sub={plan.mode === "lump" ? "once" : <>{plan.years * 12} payments, <Counter value={invested} format={(n) => money(n)} /> in all</>} />
          <span className="flow-arrow" aria-hidden><Arrow dir="right" /></span>
          <Step label={`At its past return (${levelOf(plan.level).name})`} value={<Counter value={model.rate} format={(n) => `${pct(n)} a year`} />}
            sub={`after charges and tax, ${month(f.from)} to ${month(f.to)}`} />
          <span className="flow-arrow" aria-hidden><Arrow dir="right" /></span>
          <Step strong label={`It could be worth, after ${span1}`} value={<Counter value={model.value} format={(n) => money(n)} />}
            sub={<>a gain of <Counter value={model.value - invested} format={(n) => money(n)} /></>} />
        </Appear>
        <div className="chart-title"><span>The same plan in every option, at each one&rsquo;s past return</span></div>
        <div className="future-list" data-scroll>
          <RankedBars label="What each option could become" version={`${plan.mode}${plan.years}${amount}${plan.level}`} rows={rows.map((r) => ({
            id: r.id, name: r.id === modelId ? `Intelligent Investment ${levelOf(plan.level).name}` : label(r.id), color: colorOf(r.id), value: Math.max(r.value, 0),
            strong: r.id === modelId,
            text: <Counter value={r.value} format={(n) => money(n)} />,
            aside: <span><b>{pct(r.rate)}</b> a year</span>,
          }))} />
        </div>
      </div>
    </div>
  );
}

export const PERFORMANCE: SlideDef[] = [
  { id: "calculator", title: "Your money, your dates", Slide: Calculator },
  { id: "costs", title: "Where the money went", Slide: Costs },
  { id: "journey", title: "The journey", Slide: Journey },
  { id: "trades", title: "The model's trades", Slide: Trades },
  { id: "future", title: "If you invest today", Slide: Future },
];
