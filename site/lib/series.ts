// Reading the API's daily series for charts: put them on one time grid, drawdowns, calendar-year returns, recoveries. No money is worked out here;
// every value comes from the calculator's series.
import type { Series } from "./types";

const ms = (iso: string) => Date.parse(iso + "T00:00:00Z");
export const iso = (t: number) => new Date(t).toISOString().slice(0, 10);

/** Values of each series at n evenly spaced times (the last known value on or before each time), so paths keep the same shape and can morph. */
export function align(all: Record<string, Series>, ids: string[], n = 240) {
  const used = ids.filter((id) => all[id]?.dates.length);
  if (!used.length) return { times: [] as number[], values: {} as Record<string, number[]> };
  const t0 = Math.min(...used.map((id) => ms(all[id].dates[0])));
  const t1 = Math.max(...used.map((id) => ms(all[id].dates.at(-1)!)));
  const times = Array.from({ length: n }, (_, i) => t0 + ((t1 - t0) * i) / (n - 1));
  const values: Record<string, number[]> = {};
  for (const id of used) {
    const d = all[id].dates.map(ms), v = all[id].values;
    let j = 0;
    values[id] = times.map((t) => {
      while (j + 1 < d.length && d[j + 1] <= t) j++;
      return v[j];
    });
  }
  return { times, values };
}

export function drawdown(v: number[]) {
  let peak = -Infinity;
  return v.map((x) => ((peak = Math.max(peak, x)), x / peak - 1));
}

export type YearReturn = { year: number; value: number; partial: boolean };

/** Change in value over each calendar year (from the last value of the year before, or the first value), marked partial for the first and last years. */
export function yearly(s: Series): YearReturn[] {
  const out: YearReturn[] = [];
  let base = s.values[0];
  for (let i = 0; i < s.dates.length; i++) {
    const y = +s.dates[i].slice(0, 4);
    const last = i === s.dates.length - 1 || +s.dates[i + 1].slice(0, 4) !== y;
    if (!last) continue;
    const partial = (out.length === 0 && s.dates[0].slice(5) > "01-07") || (i === s.dates.length - 1 && s.dates[i].slice(5) < "12-24");
    out.push({ year: y, value: s.values[i] / base - 1, partial });
    base = s.values[i];
  }
  return out;
}

export type Fall = { peak: string; trough: string; recovered: string | null; depth: number; days: number };

/** The deepest fall, peak to bottom, and when the value first got back to that peak (null if it has not). */
export function deepestFall(s: Series): Fall | null {
  let peakI = 0, best: { p: number; t: number; depth: number } | null = null;
  for (let i = 1; i < s.values.length; i++) {
    if (s.values[i] >= s.values[peakI]) peakI = i;
    const depth = s.values[i] / s.values[peakI] - 1;
    if (!best || depth < best.depth) best = { p: peakI, t: i, depth };
  }
  if (!best || best.depth >= 0) return null;
  const r = s.values.findIndex((x, i) => i > best!.t && x >= s.values[best!.p]);
  const end = r < 0 ? s.dates.at(-1)! : s.dates[r];
  return { peak: s.dates[best.p], trough: s.dates[best.t], recovered: r < 0 ? null : s.dates[r], depth: best.depth, days: Math.round((ms(end) - ms(s.dates[best.p])) / 864e5) };
}

/** The longest stretch below an earlier peak, in days. */
export function longestUnderwater(s: Series) {
  let peakI = 0, longest = 0;
  for (let i = 1; i < s.values.length; i++) {
    if (s.values[i] >= s.values[peakI]) peakI = i;
    else longest = Math.max(longest, (ms(s.dates[i]) - ms(s.dates[peakI])) / 864e5);
  }
  return Math.round(longest);
}

// Smallest checks of the logic above; run with `npx tsx lib/series.ts`.
if (typeof process !== "undefined" && process.argv?.[1]?.endsWith("series.ts")) {
  const s = { dates: ["2020-01-01", "2020-06-01", "2020-12-31", "2021-03-01", "2021-12-31"], values: [100, 80, 110, 99, 121] };
  const y = yearly(s);
  console.assert(y.length === 2 && Math.abs(y[0].value - 0.1) < 1e-9 && Math.abs(y[1].value - 0.1) < 1e-9 && !y[0].partial, "yearly");
  const f = deepestFall(s)!;
  console.assert(f.peak === "2020-01-01" && f.trough === "2020-06-01" && f.recovered === "2020-12-31" && Math.abs(f.depth + 0.2) < 1e-9, "deepestFall");
  console.assert(drawdown(s.values)[3] === 99 / 110 - 1, "drawdown");
  const a = align({ x: s }, ["x"], 3);
  console.assert(a.values.x[0] === 100 && a.values.x[2] === 121, "align");
  console.log("series checks done");
}
