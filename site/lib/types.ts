export type Fig = { value: number; exact: string; trace: string };
export type Line = Fig & { label?: string; fy?: string };

export type Result = {
  id: string;
  name: string;
  kind: "product" | "etf" | "fund";
  plan: string;
  headline: "sold" | "held";
  net: Fig;
  gross_end: Fig;
  charges: Fig;
  tax: Fig;
  held_net: Fig;
  held_tax: Fig;
  charges_by_kind: Line[];
  tax_by_fy: Line[];
  growth: number;
  growth_held: number;
  worst_fall: number;
  orders: number;
  strategies?: string[];
};

export type Rule = { id: string; from: string; to: string | null; source: string; verified_on: string; confidence: string };
export type Flag = { id: string; confidence: string; note: string; source: string };
export type TraceNode = { label: string; value: string; op: string; formula: string; note?: string; rules?: Rule[]; inputs?: TraceNode[]; flags?: Flag[] };

export type Band = { p10: number; p50: number; p90: number };
export type Projection = Band & { label: string; years: number; paths: number; after_tax: Band; chance_of_loss: number; fan: (Band & { year: number })[] };

export type Answer = {
  inputs: Record<string, unknown>;
  stamps: { data_as_of: string; rules_verified_on: string; signal: string };
  results: Result[];
  messages: { id: string; text: string }[];
  traces: Record<string, TraceNode>;
  series: Record<string, { dates: string[]; values: number[] }>;
  projections: Record<string, Projection>;
  csv: { trades: string; tax_lines: string };
  check: Record<string, number>;
  notes: string[];
};

export type Inputs = {
  amount: number;
  start: string;
  end: string;
  level: "Conservative" | "Balanced" | "Aggressive" | "Growth" | "Max";
  compare: string[];
  regime: "new" | "old";
  other_income: number;
  slippage: boolean;
  end_convention: "sell" | "hold";
  horizon: number;
};

// What a little ⓘ can open: an engine trace by id, or an explanation of a number worked out here.
export type InfoTarget = { trace: string; title: string } | { title: string; lines: string[] };

export type Preview = {
  label: string;
  decided_on: string;
  fill_day: string;
  targets: Record<string, number>;
  holdings_before: Record<string, number>;
  values_before: Record<string, number>;
  orders: { trade: Record<string, string>; payload: Record<string, unknown> | null; how: string; fees: string; depository: string }[];
  total_fees: number;
  total_depository: number;
  timeline: string[];
};
