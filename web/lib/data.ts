// Static data, rebuilt daily by ml/etf_daily.py and committed by GitHub Actions.
// Pages import it at build time, so the site needs no database and no API.
import siteJson from "@/data/site.json";
import researchJson from "@/data/research.json";

export type Stats = { end: number; total: number; per_year: number; worst_drop: number; years: Record<string, number> };
type Series = { values: number[] } & Stats;

export type Site = {
  generated_at: string;
  last_close: string;
  first_live: string | null;
  decision: {
    date: string; live: boolean; btc_votes: number; btc_vol: number; gold_votes: number; gold_vol: number;
    w_btc: number; w_gold: number; w_cash: number; btc_close: number; gold_close: number; tbill: number; usdinr: number;
  };
  last_alert: { date: string } | null;
  dates: string[];
  usd: Record<string, { model: number[]; hold: number[]; model_stats: Stats; hold_stats: Stats }>;
  usd_gross: { model: number[]; hold: number[]; model_stats: Stats; hold_stats: Stats };
  india: Record<string, Record<string, Series>>;
  trades: { date: string; etf: string; side: "BUY" | "SELL"; units: number; price: number; value: number; gain: number }[];
};

export type Research = {
  chosen: string;
  why: string;
  rows: { name: string; kind: "deep" | "rule" | "benchmark"; dev_cagr: number; dev_dd: number; dev_score: number;
          real_cagr: number; real_dd: number; real_gross: number }[];
  pool: { markets: string[]; market_days: number; first_year: number; features: string[] };
};

export const site = siteJson as unknown as Site;
export const research = researchJson as unknown as Research;

// Slab values carry the 4% cess; the label is the slab people know.
export const SLABS: [string, string][] = [
  ["0.312", "30%"], ["0.26", "25%"], ["0.208", "20%"], ["0.156", "15%"], ["0.104", "10%"], ["0.052", "5%"],
];

// Short names and one colour each; the model is the only line in the accent colour.
export const OPTIONS: { key: string; name: string; color: string }[] = [
  { key: "Our model (IBIT + gold, via LRS)", name: "DeepTrend model", color: "#2447d6" },
  { key: "Gold ETF in India (GOLDBEES)", name: "Gold ETF, India", color: "#b45309" },
  { key: "IBIT, bought and held (via LRS)", name: "Bitcoin ETF, held", color: "#71717a" },
  { key: "Bitcoin on an Indian exchange", name: "Bitcoin, Indian exchange", color: "#a1a1aa" },
  { key: "Bank FD (SBI, 1 year, renewed)", name: "Bank FD", color: "#0f766e" },
  { key: "Nifty 50 ETF (NIFTYBEES)", name: "Nifty 50", color: "#18181b" },
];

export const pct = (x: number, d = 1) => `${x > 0 ? "+" : ""}${(x * 100).toFixed(d)}%`;

export const inr = (x: number) => {
  // Indian grouping: 2,11,131
  const s = Math.round(x).toString();
  const last3 = s.slice(-3), rest = s.slice(0, -3);
  return "₹" + (rest ? rest.replace(/\B(?=(\d{2})+(?!\d))/g, ",") + "," : "") + last3;
};

export const lakh = (x: number) => `₹${(x / 100000).toFixed(2)} lakh`;

export const fmtDate = (iso: string) =>
  new Date(iso + "T00:00:00Z").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
