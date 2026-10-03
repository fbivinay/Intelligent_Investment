"use client";

// One scenario shared by the calculator (Overview) and the Performance page: the choice, and the API's answer to it.
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { calculate, DEFAULT_CHOICE, FIRST_DAY, savedAnswer } from "./api";
import type { Answer, Choice } from "./types";

type Scenario = { choice: Choice; answer: Answer | null; busy: boolean; error: string | null; set: (p: Partial<Choice>) => void };

const Ctx = createContext<Scenario | null>(null);

export function ScenarioProvider({ children }: { children: ReactNode }) {
  const [choice, setChoice] = useState<Choice>(DEFAULT_CHOICE);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // The default choice is answered by the saved run (same inputs), so the first result needs no wait.
    if (choice === DEFAULT_CHOICE) {
      savedAnswer().then(setAnswer, (e) => setError(e.message)).finally(() => setBusy(false));
      return;
    }
    const ac = new AbortController();
    setBusy(true);
    const t = setTimeout(() => {
      calculate(choice, ac.signal).then(
        (a) => { setAnswer(a); setError(null); setBusy(false); },
        (e) => { if (e.name !== "AbortError") { setError(e.message); setBusy(false); } },
      );
    }, 550);
    return () => { clearTimeout(t); ac.abort(); };
  }, [choice]);

  const set = useCallback((p: Partial<Choice>) => setChoice((c) => {
    const next = { ...c, ...p };
    if (next.start < FIRST_DAY[next.level]) next.start = FIRST_DAY[next.level];
    return next;
  }), []);

  return <Ctx.Provider value={{ choice, answer, busy, error, set }}>{children}</Ctx.Provider>;
}

export function useScenario() {
  const s = useContext(Ctx);
  if (!s) throw new Error("useScenario outside ScenarioProvider");
  return s;
}
