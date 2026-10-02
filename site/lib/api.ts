import type { Answer, Inputs, Preview } from "./types";

async function post<T>(path: string, body: unknown): Promise<T | { error: string }> {
  try {
    const r = await fetch(path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
    return (await r.json()) as T | { error: string };
  } catch {
    return { error: "The calculator could not be reached. Try again in a moment." };
  }
}

export const calculate = (inputs: Inputs) => post<Answer>("/api/calc", inputs);
export const preview = (body: Record<string, unknown>) => post<{ order_days: string[]; preview: Preview }>("/api/preview", body);

export const OPTIONS: { id: string; name: string }[] = [
  { id: "NIFTYBEES", name: "Nifty 50 ETF" },
  { id: "JUNIORBEES", name: "Nifty Next 50 ETF" },
  { id: "BANKBEES", name: "Nifty Bank ETF" },
  { id: "GOLDBEES", name: "Gold ETF" },
  { id: "MOM100", name: "Midcap 100 ETF" },
  { id: "MON100", name: "Nasdaq 100 ETF" },
  { id: "NIFTY50_INDEX_FUND", name: "Nifty 50 index fund" },
  { id: "NEXT50_INDEX_FUND", name: "Next 50 index fund" },
  { id: "ARBITRAGE_FUND", name: "Arbitrage fund" },
  { id: "LIQUID_FUND", name: "Liquid fund" },
];

export const DEFAULTS: Inputs = {
  amount: 1000000,
  start: "2016-04-01",
  end: "2026-09-30",
  level: "Balanced",
  compare: OPTIONS.map((o) => o.id),
  regime: "new",
  other_income: 1500000,
  slippage: true,
  end_convention: "sell",
  horizon: 5,
};
