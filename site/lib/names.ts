import type { Level } from "./types";

// Each option keeps one colour everywhere. The first eight slots were validated with the dataviz palette checks on the page surface #F5F6F2
// (worst adjacent colour-blind ΔE 10.6, normal-vision 18.9, every hue >= 3:1). Past eight, each fund takes a lighter step of its nearest relative's hue
// (composite encoding: the related pair reads as related), never a new hue; the eleven together pass the same checks, and the three lighter steps, under
// 3:1 against the page, always appear with their name beside them.
export const OPTIONS: Record<string, { name: string; color: string; what: string }> = {
  PRODUCT: { name: "Intelligent Investment", color: "#087A52", what: "The model" },
  PRODUCT_Growth: { name: "Growth strategy", color: "#56B07F", what: "Six ETFs in equal parts" },     // a lighter step of the model's hue: our second strategy
  NIFTYBEES: { name: "Nifty 50 ETF", color: "#2F63B3", what: "India's 50 largest companies" },
  GOLDBEES: { name: "Gold ETF", color: "#A9770C", what: "Gold" },
  MON100: { name: "Nasdaq 100 ETF", color: "#C4467C", what: "100 large US companies, in rupees" },
  LIQUID_FUND: { name: "Liquid fund", color: "#0A87B4", what: "Short-term debt, close to cash" },
  MOM100: { name: "Midcap 100 ETF", color: "#CF5F23", what: "India's 100 mid-sized companies" },
  BANKBEES: { name: "Bank Nifty ETF", color: "#7B4CA3", what: "India's largest banks" },
  JUNIORBEES: { name: "Nifty Next 50 ETF", color: "#6E8A12", what: "The 50 companies after the Nifty 50" },
  NIFTY50_INDEX_FUND: { name: "Nifty 50 index fund", color: "#6B8FD3", what: "The Nifty 50 through a mutual fund, no demat account" },
  NEXT50_INDEX_FUND: { name: "Next 50 index fund", color: "#97AD45", what: "The Next 50 through a mutual fund" },
  ARBITRAGE_FUND: { name: "Arbitrage fund", color: "#3DA5D0", what: "Low-risk fund taxed like shares" },
};

/** The alternatives the calculator can set beside the model: every one calc/options.py supports, in palette order. */
export const ALTERNATIVES = ["NIFTYBEES", "GOLDBEES", "MON100", "LIQUID_FUND", "MOM100", "BANKBEES", "JUNIORBEES", "NIFTY50_INDEX_FUND", "NEXT50_INDEX_FUND",
  "ARBITRAGE_FUND"];

const key = (id: string) => (id in OPTIONS ? id : id.startsWith("PRODUCT_") ? "PRODUCT" : id);
export const nameOf = (id: string) => OPTIONS[key(id)]?.name ?? id;
export const colorOf = (id: string) => OPTIONS[key(id)]?.color ?? "#7A857F";
export const isModel = (id: string) => id.startsWith("PRODUCT_");

/** The two Intelligent Investment strategies the calculator works out side by side, the model (Max) first. */
export const STRATEGIES: Level[] = ["Max", "Growth"];

// The model's levels (calc/options.py); Max is the one the site presents.
export const LEVELS: { id: Level; name: string; line: string; first: string }[] = [
  { id: "Max", name: "Max", line: "Momentum shares, gold and Nasdaq 100", first: "2017-04-03" },
  { id: "Growth", name: "Growth", line: "Six ETFs in equal parts", first: "2013-04-01" },
  { id: "Aggressive", name: "Aggressive", line: "ETF mix, falls held near 30%", first: "2013-04-01" },
  { id: "Balanced", name: "Balanced", line: "ETF mix, falls held near 20%", first: "2013-04-01" },
  { id: "Conservative", name: "Conservative", line: "ETF mix, falls held near 10%", first: "2013-04-01" },
];
export const levelOf = (id: Level) => LEVELS.find((l) => l.id === id)!;

// The model's holdings by group (calc/api.py _activity): its momentum shares together, each ETF, the liquid fund, cash not yet invested.
export const GROUPS: Record<string, { name: string; color: string }> = {
  STOCKS: { name: "Momentum shares", color: OPTIONS.PRODUCT.color },
  CASH: { name: "Cash not yet invested", color: "#A3ACA6" },
};
export const groupName = (g: string) => GROUPS[g]?.name ?? nameOf(g);
export const groupColor = (g: string) => GROUPS[g]?.color ?? colorOf(g);

export const DATA_END = "2026-09-30";
