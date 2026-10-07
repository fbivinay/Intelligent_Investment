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
export type Level = "Max" | "Growth" | "Aggressive" | "Balanced" | "Conservative";

export type Request = {
  mode: Mode;
  amount: number;
  start: string;
  end: string;
  level: Level;
  compare: string[];
  regime: "new" | "old";
  other_income: number;
  lean: true;
};

export type Facts = {
  stocks: { symbols: number; rows: number; from: string; to: string };
  rules: { rows: number; from: string; verified_on: string };
  max: { momentum: number; fixed: Record<string, number>; trend_days: number };
  costs: { stock_half_spread: number; etf_half_spread: Record<string, number>; impact: number; max_slippage: number };
  universe_runs: { picks: number; universe: number; a_year: number; worst_fall: number; orders: number }[];
  mixes: { what: string; a_year: number; worst_fall: number }[];
};
