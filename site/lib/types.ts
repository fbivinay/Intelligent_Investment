// The calculator API's answer (calc/api.py, asked with lean: true) and the repository facts (tools/site_data.py), as this site reads them.

export type Fig = { value: number; exact: string; trace: string | null };
export type Line = Fig & { label?: string; fy?: string };

export type YearReturn = { year: number; value: number; partial: boolean };
export type Fall = { peak: string; trough: string; recovered: string | null; depth: number; days: number };

export type Result = {
  id: string;
  name: string;
  kind: "product" | "etf" | "fund";
  headline: "sold" | "held";
  net: Fig;
  gross_end: Fig;
  charges: Fig;
  tax: Fig;
  invested: number;
  profit: number;
  charges_by_kind: Line[];
  tax_by_fy: Line[];
  growth: number;                // a year: plain growth for one payment, XIRR for a monthly plan
  worst_fall: number;
  orders: number;
  years: YearReturn[];
  fall: Fall | null;
};

export type Series = { dates: string[]; values: number[]; invested: number[]; drawdown: number[] };

export type TradeDay = {
  date: string;
  buys: number;
  sells: number;
  bought: Record<string, number>;
  sold: Record<string, number>;
  in: string[];
  out: string[];
};

export type Activity = {
  groups: string[];
  allocation: { dates: string[]; shares: Record<string, number[]>; stocks_held: number[] | null };
  days: TradeDay[];
  holdings: { asset: string; group: string; value: number }[];
  totals: { orders: number; buys: number; sells: number; trade_days: number; stocks_traded: number };
};

export type Answer = {
  inputs: Request & { model: string };
  stamps: { data_as_of: string; rules_verified_on: string; signal: string };
  results: Result[];
  messages: { id: string; text: string }[];
  series: Record<string, Series>;
  activity: Activity | null;
  check: { product_books_less_fast_simulator_rupees?: number };
  notes: string[];
};

export type Mode = "lump" | "sip";
export type Level = "Max" | "Growth" | "Aggressive" | "Balanced" | "Conservative" | "LSTM";

export type Request = {
  mode: Mode;
  amount: number;
  start: string;
  end: string;
  level: Level;
  levels: Level[];
  compare: string[];
  regime: "new" | "old";
  other_income: number;
  lean: true;
};

export type Facts = {
  stocks: { symbols: number; funds: number; rows: number; from: string; to: string; fields: string[] };
  etfs: { symbols: string[]; rows: number; from: string; to: string };
  max: { momentum: number; fixed: Record<string, number>; trend_days: number };
  ranking: { day: string; ranked: number; held: number; decisions: number; switch_days: number;
             top: { symbol: string; score: number; r6: number; r12: number; vol: number }[] };
  sample: { date: string; symbol: string; open: number; high: number; low: number; close: number; qty: number; value: number }[];
  lstm: {
    from: string; to: string; capital: number; final: number; cagr: number; worst_fall: number; orders: number; tax: number; charges: number;
    average_mix: Record<string, number>; choice: { from: string; chosen: string }[]; gpu: string | null; series: { dates: string[]; values: number[] };
    inputs: number; per_asset: number; market: number; flags: number; assets: string[]; seq_lens: number[]; hidden: number[]; seeds: number; cost: number;
    version: string; tried: { version: string; etfs: number; cagr: number; worst_fall: number }[];
    codes?: { per_asset: string[]; market: string[]; flags: string[] };
  };
};

/** Invest today (calc/future.py via tools/site_data.py): each option's past yearly return after charges and tax, and value factors for 1 to 30 years. */
export type Future = {
  label: string;
  from: string;
  to: string;
  amount: number;
  regime: string;
  other_income: number;
  rates: Record<string, { rate: number; worst_fall: number }>;
  factors: Record<string, { lump: number[]; sip: number[] }>;
};
