"use client";

import type { Projection } from "@/lib/types";
import { short } from "@/lib/format";

const COLORS = ["#2563eb", "#16a34a", "#dc2626", "#ca8a04", "#9333ea", "#0891b2", "#ea580c", "#64748b", "#db2777"];
const W = 900, H = 380, L = 70, R = 20, T = 20, B = 40;

type Series = { id: string; name: string; dates: string[]; values: number[] };

export function Chart({ series, fan, fanFrom }: { series: Series[]; fan?: Projection; fanFrom?: { date: string; value: number } }) {
  if (!series.length) return null;
  const ts = (d: string) => Date.parse(d);
  const year = 365.25 * 86400000;
  const x0 = Math.min(...series.map((s) => ts(s.dates[0])));
  let x1 = Math.max(...series.map((s) => ts(s.dates[s.dates.length - 1])));
  const fanPts = fan && fanFrom ? fan.fan.map((f) => ({ t: ts(fanFrom.date) + f.year * year, ...f })) : [];
  if (fanPts.length) x1 = fanPts[fanPts.length - 1].t;
  const all = series.flatMap((s) => s.values).concat(fanPts.flatMap((f) => [f.p10, f.p90]));
  const y0 = Math.min(...all) * 0.95, y1 = Math.max(...all) * 1.05;
  const X = (t: number) => L + ((t - x0) / (x1 - x0)) * (W - L - R);
  const Y = (v: number) => H - B - ((v - y0) / (y1 - y0)) * (H - T - B);
  const ticks = Array.from({ length: 5 }, (_, i) => y0 + ((y1 - y0) * i) / 4);
  const firstYear = new Date(x0).getFullYear() + 1, lastYear = new Date(x1).getFullYear();
  const step = Math.max(1, Math.ceil((lastYear - firstYear + 1) / 10));
  const years = Array.from({ length: Math.floor((lastYear - firstYear) / step) + 1 }, (_, i) => firstYear + i * step);
  return (
    <figure className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Value of each investment over time">
        {ticks.map((v, i) => (
          <g key={i}>
            <line x1={L} x2={W - R} y1={Y(v)} y2={Y(v)} className="grid" />
            <text x={L - 8} y={Y(v) + 4} textAnchor="end" className="axis">{short(v)}</text>
          </g>
        ))}
        {years.map((y) => (
          <text key={y} x={X(Date.UTC(y, 0, 1))} y={H - B + 18} textAnchor="middle" className="axis">{y}</text>
        ))}
        {fanPts.length > 0 && fanFrom && (
          <g className="fan">
            <polygon points={[...fanPts.map((f) => `${X(f.t)},${Y(f.p90)}`), ...[...fanPts].reverse().map((f) => `${X(f.t)},${Y(f.p10)}`)].join(" ")} />
            <polyline points={fanPts.map((f) => `${X(f.t)},${Y(f.p50)}`).join(" ")} className="fan-mid" />
            <text x={X(fanPts[fanPts.length - 1].t) - 6} y={Y(fanPts[fanPts.length - 1].p90) - 6} textAnchor="end" className="badge-text">ESTIMATE</text>
          </g>
        )}
        {series.map((s, i) => (
          <polyline key={s.id} points={s.dates.map((d, k) => `${X(ts(d))},${Y(s.values[k])}`).join(" ")} fill="none" stroke={COLORS[i % COLORS.length]}
            strokeWidth={i === 0 ? 2.6 : 1.4} opacity={i === 0 ? 1 : 0.85} />
        ))}
      </svg>
      <figcaption className="legend">
        {series.map((s, i) => (
          <span key={s.id}><i style={{ background: COLORS[i % COLORS.length] }} />{s.name}</span>
        ))}
        {fanPts.length > 0 && <span><i className="fan-key" />Model, estimated range (10th to 90th percentile), dashed: middle</span>}
      </figcaption>
    </figure>
  );
}
