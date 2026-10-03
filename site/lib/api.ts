import type { Answer, Choice, Level } from "./types";

export const DATA_END = "2026-09-30";
// The first day each model can start (calc/options.py: PRODUCT_START, MAX_START).
export const FIRST_DAY: Record<Level, string> = { Conservative: "2013-04-01", Balanced: "2013-04-01", Aggressive: "2013-04-01", Growth: "2013-04-01", Max: "2017-04-03" };

export const LEVELS: { id: Level; name: string; line: string }[] = [
  { id: "Conservative", name: "Conservative", line: "ETF mixes, falls held near 10%" },
  { id: "Balanced", name: "Balanced", line: "ETF mixes, falls held near 20%" },
  { id: "Aggressive", name: "Aggressive", line: "ETF mixes, falls held near 30%" },
  { id: "Growth", name: "Growth", line: "Six ETFs in equal parts, no fall guard" },
  { id: "Max", name: "Max", line: "Stock momentum half, gold and Nasdaq 100 a quarter each" },
];

export const OPTIONS: { id: string; name: string; color: string }[] = [
  { id: "NIFTYBEES", name: "Nifty 50 ETF", color: "#3E4A54" },
  { id: "GOLDBEES", name: "Gold ETF", color: "#B48A3C" },
  { id: "MON100", name: "Nasdaq 100 ETF", color: "#6F8396" },
  { id: "LIQUID_FUND", name: "Liquid fund", color: "#A3A79F" },
  { id: "JUNIORBEES", name: "Nifty Next 50 ETF", color: "#7A8A63" },
  { id: "BANKBEES", name: "Nifty Bank ETF", color: "#8F6E5A" },
  { id: "MOM100", name: "Midcap 100 ETF", color: "#A0715A" },
  { id: "NIFTY50_INDEX_FUND", name: "Nifty 50 index fund", color: "#56636E" },
  { id: "NEXT50_INDEX_FUND", name: "Next 50 index fund", color: "#8C9A75" },
  { id: "ARBITRAGE_FUND", name: "Arbitrage fund", color: "#8E9399" },
];
export const MODEL_COLOR = "#0E7A55";

// Always compared, so the chart has the same alternatives as the Overview; the chosen benchmark is added if it is not one of them.
const BASE = ["NIFTYBEES", "GOLDBEES", "MON100", "LIQUID_FUND"];

// Must match tools/site_data.py, whose saved answer stands in for the first request.
export const DEFAULT_CHOICE: Choice = { amount: 1000000, start: "2017-04-03", level: "Max", benchmark: "NIFTYBEES", regime: "new", other_income: 1200000 };

export const nameOf = (id: string) => (id.startsWith("PRODUCT_") ? `Intelligent Investment · ${id.slice(8)}` : OPTIONS.find((o) => o.id === id)?.name ?? id);
export const colorOf = (id: string) => (id.startsWith("PRODUCT_") ? MODEL_COLOR : OPTIONS.find((o) => o.id === id)?.color ?? "#999");

export function toInputs(c: Choice) {
  return { amount: c.amount, start: c.start, end: DATA_END, level: c.level, compare: [...new Set([...BASE, c.benchmark])], regime: c.regime,
           other_income: c.other_income, slippage: true, end_convention: "sell", horizon: 5 };
}

export async function calculate(c: Choice, signal?: AbortSignal): Promise<Answer> {
  let r: Response;
  try {
    r = await fetch("/api/calc", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(toInputs(c)), signal });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new Error("The calculator could not be reached. Try again in a moment.");
  }
  const body = await r.json().catch(() => ({ error: "The calculator sent an answer that could not be read." }));
  if ("error" in body) throw new Error(body.error);
  return body as Answer;
}

export async function savedAnswer(): Promise<Answer> {
  const r = await fetch("/history.json");
  if (!r.ok) throw new Error("The saved history could not be loaded.");
  return r.json();
}
