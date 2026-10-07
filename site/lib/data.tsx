"use client";

// Everything the slides read: the two saved calculator answers and the repository facts (tools/site_data.py), and the calculator's own form and answer.
// No money is worked out here: every figure comes from the calculator API (calc/api.py) or a saved answer of it.
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { ALTERNATIVES, DATA_END, isModel, levelOf } from "./names";
import type { Answer, Facts, Future, Level, Mode, Request } from "./types";

export type Form = {
  mode: Mode;
  lumpAmount: number;
  sipAmount: number;
  start: string;            // one payment: the day it is invested
  years: number | "all";    // monthly: this many years up to the data's last day, or since the level's first day
  level: Level;
  compare: string[];
  regime: "new" | "old";
  income: number;
  bench: string;            // the alternative the model is set beside on the cost and behaviour slides (not sent to the calculator)
};

export const LIMITS = { lump: [10_000, 1_000_000_000], sip: [1_000, 10_000_000] } as const;

const later = (a: string, b: string) => (a > b ? a : b);

/** The day N years before the data's last day, plus one: a 3-year plan pays from 1 Oct 2023 to 1 Sep 2026. */
export function yearsBefore(end: string, n: number) {
  const [y, m, d] = end.split("-").map(Number);
  return new Date(Date.UTC(y - n, m - 1, d + 1)).toISOString().slice(0, 10);
}

export function request(f: Form): Request {
  const first = levelOf(f.level).first;
  const start = f.mode === "lump" ? later(f.start, first) : f.years === "all" ? first : later(yearsBefore(DATA_END, f.years), first);
  const compare = ALTERNATIVES.filter((id) => f.compare.includes(id));
  return { mode: f.mode, amount: f.mode === "lump" ? f.lumpAmount : f.sipAmount, start, end: DATA_END, level: f.level, compare, regime: f.regime,
           other_income: f.income, lean: true };
}

const keyOf = (r: Request) => JSON.stringify(r);

/** The calculator starts with these beside the model; the other alternatives are one tap away (the Overview shows them all). */
const FIRST_COMPARE = ["NIFTYBEES", "GOLDBEES", "MON100", "LIQUID_FUND"];

function formOf(lump: Answer, sip: Answer): Form {
  const i = lump.inputs;
  return { mode: "lump", lumpAmount: i.amount, sipAmount: sip.inputs.amount, start: i.start, years: "all", level: i.level, compare: FIRST_COMPARE, regime: i.regime,
           income: i.other_income, bench: FIRST_COMPARE[0] };
}

/** An answer already worked out for the same question with more options beside the model, cut to the options asked for. Each option is worked out
 * on its own, so the cut is exactly what the calculator would answer. */
function cut(cache: Map<string, Answer>, req: Request): Answer | undefined {
  for (const [k, a] of cache) {
    const r: Request = JSON.parse(k);
    if (keyOf({ ...r, compare: req.compare }) !== keyOf(req) || !req.compare.every((id) => r.compare.includes(id))) continue;
    const keep = (id: string) => req.compare.includes(id) || isModel(id);
    return { ...a, inputs: { ...a.inputs, compare: req.compare }, results: a.results.filter((x) => keep(x.id)), messages: a.messages.filter((m) => keep(m.id)),
             series: Object.fromEntries(Object.entries(a.series).filter(([id]) => keep(id))) };
  }
}

async function ask(req: Request, signal: AbortSignal): Promise<Answer> {
  let r: Response;
  try {
    r = await fetch("/api/calc", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(req), signal });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new Error("The calculator could not be reached. Check the connection and try again.");
  }
  const body = await r.json().catch(() => null);
  if (!body) throw new Error("The calculator's answer could not be read. Try again.");
  if (body.error) throw new Error(body.error);
  return body as Answer;
}

type Saved = { lump: Answer; sip: Answer; facts: Facts; future: Future };
type Status = "loading" | "ready" | "error";
type Data = {
  saved: Saved | null;
  failed: string | null;
  form: Form | null;
  set: (p: Partial<Form>) => void;
  answer: Answer | null;          // the latest answer for the form's mode (the one on screen while a new one is worked out)
  status: Status;
  since: number;                  // when the current request started
  error: string | null;
  retry: () => void;
};

const Ctx = createContext<Data | null>(null);

export function DataProvider({ children }: { children: ReactNode }) {
  const [saved, setSaved] = useState<Saved | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [form, setForm] = useState<Form | null>(null);
  const [answers, setAnswers] = useState<Partial<Record<Mode, Answer>>>({});
  const [status, setStatus] = useState<Status>("loading");
  const [since, setSince] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const cache = useRef(new Map<string, Answer>());

  useEffect(() => {
    const get = (p: string) => fetch(p).then((r) => (r.ok ? r.json() : Promise.reject(new Error(`${p} ${r.status}`))));
    Promise.all([get("/data/lump.json"), get("/data/sip.json"), get("/data/facts.json"), get("/data/future.json")]).then(
      ([lump, sip, facts, future]) => {
        const f = formOf(lump, sip);
        cache.current.set(keyOf(request({ ...f, compare: lump.inputs.compare })), lump);
        cache.current.set(keyOf(request({ ...f, mode: "sip", compare: sip.inputs.compare })), sip);
        setSaved({ lump, sip, facts, future });
        setForm(f);
      },
      () => setFailed("The saved results could not be loaded. Reload the page to try again."),
    );
    // Wake the calculator while the visitor reads the Overview: it loads its data once, so their first question is answered at full speed.
    fetch("/api/calc", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ warm: true }) }).catch(() => {});
  }, []);

  const reqKey = form ? keyOf(request(form)) : "";       // the slides' own settings (bench) change the form, not the question
  const find = useCallback((key: string) => {
    let a = cache.current.get(key);
    if (!a) {
      a = cut(cache.current, JSON.parse(key));
      if (a) cache.current.set(key, a);
    }
    return a;
  }, []);
  useEffect(() => {
    if (!reqKey) return;
    const req: Request = JSON.parse(reqKey);
    const hit = find(reqKey);
    if (hit) {
      setAnswers((a) => ({ ...a, [req.mode]: hit }));
      setStatus("ready");
      setError(null);
      return;
    }
    const ac = new AbortController();
    setStatus("loading");
    setSince(Date.now());
    const t = setTimeout(() => {
      ask(req, ac.signal).then(
        (a) => {
          cache.current.set(reqKey, a);
          setAnswers((x) => ({ ...x, [req.mode]: a }));
          setStatus("ready");
          setError(null);
        },
        (e) => {
          if ((e as Error).name === "AbortError") return;
          setError((e as Error).message);
          setStatus("error");
        },
      );
    }, 450);
    return () => { clearTimeout(t); ac.abort(); };
  }, [reqKey, attempt, find]);

  const set = useCallback((p: Partial<Form>) => setForm((f) => (f ? { ...f, ...p } : f)), []);
  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  // An answer already worked out shows in the same render (the numbers on screen travel to it instead of starting again from zero).
  const hit = reqKey ? find(reqKey) : undefined;
  const answer = hit ?? (form ? answers[form.mode] ?? null : null);
  const shownStatus: Status = hit ? "ready" : status;
  const value = useMemo<Data>(() => ({ saved, failed, form, set, answer, status: shownStatus, since, error: hit ? null : error, retry }),
    [saved, failed, form, set, answer, shownStatus, since, error, hit, retry]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useData() {
  const d = useContext(Ctx);
  if (!d) throw new Error("useData outside DataProvider");
  return d;
}
