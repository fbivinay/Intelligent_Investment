// The calculator API's answer (calc/api.py), the parts this site reads.
export type Fig = { value: number; exact: string; trace: string };

export type Result = {
  id: string;
  name: string;
  kind: "product" | "etf" | "fund";
  headline: "sold" | "held";
  net: Fig;
  gross_end: Fig;
  charges: Fig;
  tax: Fig;
  growth: number;
  worst_fall: number;
  orders: number;
};

export type Series = { dates: string[]; values: number[] };

export type Answer = {
  inputs: Record<string, unknown> & { start: string; end: string; level: string; amount: number };
  stamps: { data_as_of: string; rules_verified_on: string; signal: string };
  results: Result[];
  messages: { id: string; text: string }[];
  series: Record<string, Series>;
  notes: string[];
};

export type Level = "Conservative" | "Balanced" | "Aggressive" | "Growth" | "Max";

export type Choice = {
  amount: number;
  start: string;
  level: Level;
  benchmark: string;
  regime: "new" | "old";
  other_income: number;
};
