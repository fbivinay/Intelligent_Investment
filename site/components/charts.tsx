"use client";

import { AnimatePresence, motion, useInView, useReducedMotion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { EASE } from "./motion";
import { day, signedPct } from "@/lib/format";
import { iso } from "@/lib/series";

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [w, setW] = useState(0);
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([e]) => setW(e.contentRect.width));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}

function niceTicks(lo: number, hi: number, count = 5) {
  const raw = (hi - lo) / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw)!;
  const out: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(10));
  return out;
}

export type Line = { id: string; label: string; color: string; values: number[]; emphasis?: boolean };

const M = { top: 20, right: 84, bottom: 34, left: 8 };

/**
 * Lines on a shared time grid. Every line has the same number of points, so a change of data (new inputs, growth to drawdown, a line shown or hidden and the
 * scale moving with it) morphs the paths instead of redrawing them. Lines draw themselves the first time the chart is seen.
 */
export function LineChart({ times, lines, hidden = new Set(), format, height = 440, baseline, baselineLabel, kind = "value" }: {
  times: number[]; lines: Line[]; hidden?: Set<string>; format: (n: number) => string; height?: number; baseline?: number; baselineLabel?: string; kind?: "value" | "drawdown";
}) {
  const [box, width] = useWidth<HTMLDivElement>();
  const seen = useInView(box, { once: true, margin: "-15% 0px" });
  const reduce = useReducedMotion();
  const [hover, setHover] = useState<number | null>(null);
  const drawn = useRef(false);
  useEffect(() => {
    if (!seen) return;
    const t = setTimeout(() => (drawn.current = true), 2400);
    return () => clearTimeout(t);
  }, [seen]);

  const shown = lines.filter((l) => !hidden.has(l.id));
  const n = times.length;
  const iw = Math.max(1, width - M.left - M.right), ih = height - M.top - M.bottom;

  const { lo, hi, ticks } = useMemo(() => {
    const all = (shown.length ? shown : lines).flatMap((l) => l.values);
    if (baseline !== undefined) all.push(baseline);
    let lo = Math.min(...all), hi = Math.max(...all);
    if (kind === "drawdown") { hi = 0; lo = lo * 1.1 || -0.01; }
    else { const pad = (hi - lo) * 0.06; lo = Math.max(0, lo - pad); hi += pad; }
    return { lo, hi, ticks: niceTicks(lo, hi) };
  }, [shown, lines, baseline, kind]);

  const x = (i: number) => M.left + (n > 1 ? (i / (n - 1)) * iw : 0);
  const y = (v: number) => M.top + (1 - (v - lo) / (hi - lo || 1)) * ih;
  const path = (vals: number[]) => vals.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");
  const bottom = M.top + ih;

  const years = useMemo(() => {
    if (!n) return [];
    const y0 = new Date(times[0]).getUTCFullYear() + 1, y1 = new Date(times[n - 1]).getUTCFullYear();
    const every = y1 - y0 > 9 ? 2 : 1;
    const out: { label: number; at: number }[] = [];
    for (let yr = y0; yr <= y1; yr += every) out.push({ label: yr, at: (Date.UTC(yr, 0, 1) - times[0]) / (times[n - 1] - times[0]) });
    return out;
  }, [times, n]);

  const ease = { duration: reduce ? 0 : 0.9, ease: EASE };
  const onMove = (e: React.PointerEvent<SVGRectElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    setHover(Math.max(0, Math.min(n - 1, Math.round(((e.clientX - r.left) / r.width) * (n - 1)))));
  };
  const tipLeft = hover !== null && x(hover) > width * 0.62;

  return (
    <div className="chart" ref={box} style={{ height }}>
      {width > 0 && n > 1 && (
        <svg width={width} height={height} role="img" aria-label={`Chart of ${shown.map((l) => l.label).join(", ")}`}>
          <defs>
            {lines.filter((l) => l.emphasis).map((l) => (
              <linearGradient key={l.id} id={`fill-${l.id}`} x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor={l.color} stopOpacity={kind === "drawdown" ? 0.02 : 0.16} />
                <stop offset="100%" stopColor={l.color} stopOpacity={kind === "drawdown" ? 0.16 : 0} />
              </linearGradient>
            ))}
          </defs>

          <AnimatePresence initial={false}>
            {ticks.map((t) => (
              <motion.g key={t} initial={{ opacity: 0 }} animate={{ opacity: 1, y: y(t) }} exit={{ opacity: 0 }} transition={ease}>
                <line x1={M.left} x2={M.left + iw} className="grid" />
                <text x={M.left + iw + 14} dy="0.32em" className="tick">{format(t)}</text>
              </motion.g>
            ))}
          </AnimatePresence>
          {years.map((yr) => (
            <text key={yr.label} x={M.left + yr.at * iw} y={height - 10} className="tick" textAnchor="middle">{yr.label}</text>
          ))}

          {baseline !== undefined && (
            <motion.g initial={false} animate={{ y: y(baseline) }} transition={ease}>
              <line x1={M.left} x2={M.left + iw} className="baseline" />
              {baselineLabel && <text x={M.left + 4} y={-8} className="tick">{baselineLabel}</text>}
            </motion.g>
          )}

          {lines.filter((l) => l.emphasis).map((l) => (
            <motion.path key={`a-${l.id}`} fill={`url(#fill-${l.id})`} stroke="none" initial={{ opacity: 0, d: `${path(l.values)}L${x(n - 1)},${bottom}L${x(0)},${bottom}Z` }}
              animate={{ opacity: seen && !hidden.has(l.id) ? 1 : 0, d: kind === "drawdown" ? `${path(l.values)}L${x(n - 1)},${y(0)}L${x(0)},${y(0)}Z` : `${path(l.values)}L${x(n - 1)},${bottom}L${x(0)},${bottom}Z` }}
              transition={{ d: ease, opacity: { duration: reduce ? 0 : 1.2, delay: drawn.current ? 0 : 0.9 } }} />
          ))}

          {lines.map((l, i) => {
            const on = seen && !hidden.has(l.id);
            return (
              <motion.path key={l.id} fill="none" stroke={l.color} strokeWidth={l.emphasis ? 2.4 : 1.5} strokeLinejoin="round" strokeLinecap="round"
                initial={{ pathLength: 0, d: path(l.values) }} animate={{ pathLength: on ? 1 : 0, opacity: on ? 1 : 0, d: path(l.values) }}
                transition={{ d: ease, pathLength: { duration: reduce ? 0 : drawn.current ? 0.7 : 1.8, ease: EASE, delay: drawn.current || reduce ? 0 : 0.15 + i * 0.12 },
                              opacity: { duration: reduce ? 0 : 0.35 } }} />
            );
          })}

          <AnimatePresence>
            {hover !== null && (
              <motion.g initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
                <motion.line y1={M.top} y2={bottom} className="cursor" initial={false} animate={{ x1: x(hover), x2: x(hover) }} transition={{ type: "spring", stiffness: 600, damping: 45 }} />
                {shown.map((l) => (
                  <motion.circle key={l.id} r={l.emphasis ? 4.5 : 3.5} fill="var(--surface)" stroke={l.color} strokeWidth={2}
                    initial={false} animate={{ cx: x(hover), cy: y(l.values[hover]) }} transition={{ type: "spring", stiffness: 600, damping: 45 }} />
                ))}
              </motion.g>
            )}
          </AnimatePresence>
          <rect x={M.left} y={M.top} width={iw} height={ih} fill="transparent" onPointerMove={onMove} onPointerLeave={() => setHover(null)} />
        </svg>
      )}
      <AnimatePresence>
        {hover !== null && (
          <motion.div className="tip" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0, x: tipLeft ? x(hover) - 266 : x(hover) + 16 }} exit={{ opacity: 0, y: 6 }}
            transition={{ x: { type: "spring", stiffness: 500, damping: 40 }, default: { duration: 0.18 } }}>
            <div className="tip-date">{day(iso(times[hover]))}</div>
            {[...shown].sort((a, b) => b.values[hover] - a.values[hover]).map((l) => (
              <div key={l.id} className="tip-row">
                <i style={{ background: l.color }} />
                <span>{l.label}</span>
                <b className="num">{format(l.values[hover])}</b>
              </div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export type BarGroup = { id: string; label: string; color: string; values: (number | null)[] };

/** Side-by-side bars per year that grow from the zero line and slide to new heights when the data changes. */
export function BarChart({ years, groups, format, height = 440, partial = [] }: { years: number[]; groups: BarGroup[]; format: (n: number) => string; height?: number; partial?: boolean[] }) {
  const [box, width] = useWidth<HTMLDivElement>();
  const seen = useInView(box, { once: true });
  const reduce = useReducedMotion();
  const [hover, setHover] = useState<number | null>(null);
  const all = groups.flatMap((g) => g.values.filter((v): v is number => v !== null));
  const hi = Math.max(0.05, ...all) * 1.12, lo = Math.min(-0.05, ...all) * 1.12;
  const ticks = niceTicks(lo, hi, 6);
  const iw = Math.max(1, width - M.left - M.right), ih = height - M.top - M.bottom;
  const y = (v: number) => M.top + (1 - (v - lo) / (hi - lo)) * ih;
  const band = iw / Math.max(1, years.length), gap = band * 0.28, bw = (band - gap) / Math.max(1, groups.length);
  const tipLeft = hover !== null && (hover + 0.5) * band > width * 0.62;

  return (
    <div className="chart" ref={box} style={{ height }}>
      {width > 0 && (
        <svg width={width} height={height} role="img" aria-label="Returns by calendar year">
          <AnimatePresence initial={false}>
            {ticks.map((t) => (
              <motion.g key={t} initial={{ opacity: 0 }} animate={{ opacity: 1, y: y(t) }} exit={{ opacity: 0 }} transition={{ duration: 0.6, ease: EASE }}>
                <line x1={M.left} x2={M.left + iw} className={t === 0 ? "zero" : "grid"} />
                <text x={M.left + iw + 14} dy="0.32em" className="tick">{format(t)}</text>
              </motion.g>
            ))}
          </AnimatePresence>
          {years.map((yr, i) => (
            <g key={yr} onPointerEnter={() => setHover(i)} onPointerLeave={() => setHover(null)}>
              <rect x={M.left + i * band} y={M.top} width={band} height={ih} className={hover === i ? "band on" : "band"} />
              {groups.map((g, k) => {
                const v = g.values[i];
                if (v === null) return null;
                const top = Math.min(y(v), y(0)), h = Math.abs(y(v) - y(0));
                return (
                  // keyed by value: a changed bar grows again from the zero line (motion would turn an animated y or height into CSS, which SVG rects ignore)
                  <motion.rect key={`${g.id}${v}`} x={M.left + i * band + gap / 2 + k * bw} y={top} height={Math.max(0.5, h)} width={Math.max(1, bw - 2)} rx={2} fill={g.color}
                    opacity={partial[i] ? 0.55 : 1} initial={{ scaleY: 0 }} animate={{ scaleY: seen ? 1 : 0 }}
                    transition={{ duration: reduce ? 0 : 0.8, ease: EASE, delay: reduce ? 0 : i * 0.035 + k * 0.05 }}
                    style={{ pointerEvents: "none", transformBox: "fill-box", originY: v >= 0 ? 1 : 0 }} />
                );
              })}
              <text x={M.left + (i + 0.5) * band} y={height - 10} className="tick" textAnchor="middle">{partial[i] ? `${yr}*` : yr}</text>
            </g>
          ))}
        </svg>
      )}
      <AnimatePresence>
        {hover !== null && (
          <motion.div className="tip" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0, x: tipLeft ? (hover + 0.5) * band - 266 : (hover + 0.5) * band + 24 }} exit={{ opacity: 0 }}
            transition={{ x: { type: "spring", stiffness: 500, damping: 40 }, default: { duration: 0.18 } }}>
            <div className="tip-date">{years[hover]}{partial[hover] ? " (part of the year)" : ""}</div>
            {groups.map((g) => (
              <div key={g.id} className="tip-row">
                <i style={{ background: g.color }} />
                <span>{g.label}</span>
                <b className="num">{g.values[hover] === null ? "–" : signedPct(g.values[hover]!)}</b>
              </div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/** The key to a chart: each entry shows or hides its line; the last shown line cannot be hidden. */
export function Legend({ items, hidden, onToggle }: { items: { id: string; label: string; color: string; sub?: React.ReactNode }[]; hidden: Set<string>; onToggle: (id: string) => void }) {
  return (
    <div className="legend">
      {items.map((it) => {
        const off = hidden.has(it.id);
        return (
          <motion.button key={it.id} layout="position" className={off ? "key off" : "key"} onClick={() => onToggle(it.id)} aria-pressed={!off} whileTap={{ scale: 0.97 }}>
            <motion.i style={{ background: it.color }} animate={{ scale: off ? 0.6 : 1, opacity: off ? 0.35 : 1 }} transition={{ type: "spring", stiffness: 500, damping: 30 }} />
            <span className="key-text">
              <span className="key-label">{it.label}</span>
              {it.sub && <span className="key-sub">{it.sub}</span>}
            </span>
          </motion.button>
        );
      })}
    </div>
  );
}

/** Hidden-line state for a Legend: toggling never leaves the chart empty. */
export function useHidden(initial: string[] = []) {
  const [hidden, setHidden] = useState(() => new Set(initial));
  const toggle = (id: string, all: string[]) => setHidden((h) => {
    const next = new Set(h);
    if (next.has(id)) next.delete(id);
    else if (all.filter((a) => !next.has(a)).length > 1) next.add(id);
    return next;
  });
  return [hidden, toggle] as const;
}
