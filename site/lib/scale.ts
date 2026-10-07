// Chart geometry: series on one time grid (so lines keep the same shape and can morph), clean ticks, year marks. Reads values; works out no money.
import type { Series } from "./types";

export const ms = (iso: string) => Date.parse(iso + "T00:00:00Z");

/** Each series' value on n evenly spaced days (the last known value on or before each), from the earliest first day to the latest last day. */
export function grid(all: Record<string, Series>, ids: string[], pick: (s: Series) => number[], n = 320) {
  const used = ids.filter((id) => all[id]?.dates.length);
  if (!used.length) return { times: [] as number[], values: {} as Record<string, number[]> };
  const t0 = Math.min(...used.map((id) => ms(all[id].dates[0])));
  const t1 = Math.max(...used.map((id) => ms(all[id].dates.at(-1)!)));
  const times = Array.from({ length: n }, (_, i) => t0 + ((t1 - t0) * i) / (n - 1));
  const values: Record<string, number[]> = {};
  for (const id of used) {
    const d = all[id].dates.map(ms), v = pick(all[id]);
    let j = 0;
    values[id] = times.map((t) => {
      while (j + 1 < d.length && d[j + 1] <= t) j++;
      return t < d[0] ? NaN : v[j];
    });
  }
  return { times, values };
}

/** Round tick values covering [lo, hi], about `count` of them. */
export function ticks(lo: number, hi: number, count = 5) {
  if (!(hi > lo)) return [lo];
  const raw = (hi - lo) / count, mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw)!;
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) out.push(+v.toFixed(10));
  return out;
}

/** A domain padded to round ticks, including `include` (a baseline such as 0 or the money invested). */
export function domain(values: number[], include: number[] = [], pad = 0.06): [number, number] {
  const v = values.filter(Number.isFinite);
  let lo = Math.min(...v, ...include), hi = Math.max(...v, ...include);
  if (lo === hi) { lo -= 1; hi += 1; }
  const p = (hi - lo) * pad;
  return [include.includes(lo) ? lo : lo - p, include.includes(hi) ? hi : hi + p];
}

/** 1 Jan of each year inside the range, thinned so marks stay at least `minGap` pixels apart. */
export function years(t0: number, t1: number, width: number, minGap = 64) {
  const out: number[] = [];
  for (let y = new Date(t0).getUTCFullYear() + 1; ; y++) {
    const t = Date.UTC(y, 0, 1);
    if (t > t1) break;
    out.push(t);
  }
  const per = width / Math.max(1, out.length);
  const every = Math.max(1, Math.ceil(minGap / per));
  return out.filter((t) => new Date(t).getUTCFullYear() % every === 0);
}

export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
