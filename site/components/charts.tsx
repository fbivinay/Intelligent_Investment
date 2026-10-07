"use client";

// Charts drawn as plain SVG and HTML with motion: lines that draw in and morph between views, ranked bars, the model's mix through time, its trading
// days, yearly columns. They read values from the calculator's answer; none of them works out money.
import { animate, motion, useReducedMotion } from "motion/react";
import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { day, month } from "@/lib/format";
import { domain, lerp, ms, ticks, years as yearMarks } from "@/lib/scale";
import { EASE, ENTER, SWEEP } from "./ui";

function useSize<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setSize({ w: Math.round(e.contentRect.width), h: Math.round(e.contentRect.height) }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, size] as const;
}

/** 0 -> 1 each time `key` changes (the frame of a morph; already 0 in the render that sees the new key), 1 when motion is reduced. */
function useMorph(key: string) {
  const [t, setT] = useState(1);
  const reduce = useReducedMotion();
  const seen = useRef(key);
  const changed = seen.current !== key;
  useEffect(() => {
    if (seen.current === key) return;
    seen.current = key;
    if (reduce) { setT(1); return; }
    setT(0);
    const a = animate(0, 1, { duration: 0.95, ease: SWEEP, onUpdate: setT });
    return () => a.stop();
  }, [key, reduce]);
  return changed && !reduce ? 0 : t;
}

function linePath(xs: number[], ys: number[]) {
  let d = "", open = false;
  for (let i = 0; i < xs.length; i++) {
    if (!Number.isFinite(ys[i])) { open = false; continue; }
    d += `${open ? "L" : "M"}${xs[i].toFixed(1)},${ys[i].toFixed(1)}`;
    open = true;
  }
  return d;
}

function areaPath(xs: number[], ys: number[], base: number) {
  const idx = ys.map((y, i) => (Number.isFinite(y) ? i : -1)).filter((i) => i >= 0);
  if (!idx.length) return "";
  const a = idx[0], b = idx[idx.length - 1];
  return `M${xs[a].toFixed(1)},${base.toFixed(1)}` + idx.map((i) => `L${xs[i].toFixed(1)},${ys[i].toFixed(1)}`).join("") + `L${xs[b].toFixed(1)},${base.toFixed(1)}Z`;
}

/** Labels at the right edge, nudged apart, each remembering where its line ends. */
function spread(items: { id: string; y: number }[], gap: number, lo: number, hi: number) {
  const s = [...items].sort((a, b) => a.y - b.y).map((x) => ({ ...x, at: x.y }));
  for (let i = 1; i < s.length; i++) s[i].at = Math.max(s[i].at, s[i - 1].at + gap);
  const over = s.length ? s[s.length - 1].at - hi : 0;
  if (over > 0) for (const x of s) x.at -= over;
  for (let i = s.length - 2; i >= 0; i--) s[i].at = Math.min(s[i].at, s[i + 1].at - gap);
  for (const x of s) x.at = Math.max(lo, x.at);
  return Object.fromEntries(s.map((x) => [x.id, x.at]));
}

export type LineSeries = { id: string; label: string; color: string; values: number[]; strong?: boolean; quiet?: boolean };

type LineProps = {
  times: number[];
  series: LineSeries[];
  format: (v: number) => string;
  axis?: (v: number) => string;
  include?: number[];
  baseline?: { value: number; label: string };
  ends?: Record<string, { value: number; text: string }>;
  area?: "wash" | "zero";
  hidden?: Set<string>;
  focus?: string | null;
  view?: string;
  className?: string;
};

export function LineChart({ times, series, format, axis = format, include = [], baseline, ends, area, hidden, focus, view = "", className }: LineProps) {
  const [ref, { w, h }] = useSize<HTMLDivElement>();
  const reduce = useReducedMotion();
  const shown = series.filter((s) => !hidden?.has(s.id));
  const labelled = !!ends || shown.length > 1;
  const pad = { l: 72, r: labelled ? 224 : 28, t: 18, b: 38 };
  const target = useMemo(() => {
    const keep = Object.entries(ends ?? {}).filter(([id]) => !hidden?.has(id)).map(([, e]) => e.value);
    return { dom: domain(shown.flatMap((s) => s.values).concat(keep), include), vals: Object.fromEntries(series.map((s) => [s.id, s.values])) as Record<string, number[]> };
  }, [series, hidden, ends]); // eslint-disable-line react-hooks/exhaustive-deps
  const morphKey = view + "|" + series.map((s) => s.id + ":" + s.values.length + ":" + (s.values.at(-1) ?? 0)).join(",") + "|" + target.dom.join(",");
  const from = useRef(target), live = useRef(target), lastKey = useRef(morphKey);
  if (lastKey.current !== morphKey) { from.current = live.current; lastKey.current = morphKey; }     // a morph starts from what is on screen now
  const t = useMorph(morphKey);
  const lo = lerp(from.current.dom[0], target.dom[0], t), hi = lerp(from.current.dom[1], target.dom[1], t);
  const vals: Record<string, number[]> = {};
  for (const s of series) {
    const a = from.current.vals[s.id], b = s.values;
    vals[s.id] = a && a.length === b.length ? b.map((v, i) => (Number.isFinite(a[i]) && Number.isFinite(v) ? lerp(a[i], v, t) : v)) : b;
  }
  live.current = { dom: [lo, hi], vals };

  const [hover, setHover] = useState<number | null>(null);
  if (!times.length) return <div ref={ref} className={`chart ${className ?? ""}`} />;
  const iw = Math.max(1, w - pad.l - pad.r), ih = Math.max(1, h - pad.t - pad.b);
  const t0 = times[0], t1 = times[times.length - 1];
  const X = (tm: number) => pad.l + ((tm - t0) / (t1 - t0 || 1)) * iw;
  const Y = (v: number) => pad.t + (1 - (v - lo) / (hi - lo || 1)) * ih;
  const xs = times.map(X);
  const yt = ticks(target.dom[0], target.dom[1], Math.max(3, Math.round(ih / 70)));
  const marks = yearMarks(t0, t1, iw);
  const xEnd = xs[xs.length - 1];
  const lastOf = (v: number[]) => { for (let i = v.length - 1; i >= 0; i--) if (Number.isFinite(v[i])) return v[i]; return NaN; };
  const last = (id: string) => lastOf(vals[id]);                                      // where the line ends now (mid-morph too)
  const endY = Object.fromEntries(shown.map((s) => [s.id, Y(ends?.[s.id] ? ends[s.id].value : last(s.id))]));
  // At most four names at the line ends (fewer if the chart is short): the strong line, the one in focus, then the rest in the order given.
  const room = Math.max(1, Math.min(4, Math.floor((ih - 12) / 48) + 1));
  const named = new Set([...new Set([...shown.filter((s) => s.strong), ...shown.filter((s) => s.id === focus), ...shown].map((s) => s.id))].slice(0, room));
  const at = spread(shown.filter((s) => named.has(s.id)).map((s) => ({ id: s.id, y: endY[s.id] })), 48, pad.t + 8, pad.t + ih - 4);

  const move = (e: React.PointerEvent) => {
    const r = (e.currentTarget as SVGRectElement).getBoundingClientRect();
    const x = e.clientX - r.left;
    let i = Math.round(((x / r.width) * (times.length - 1)));
    i = Math.max(0, Math.min(times.length - 1, i));
    setHover(i);
  };
  const tip = hover !== null ? shown.map((s) => ({ s, v: vals[s.id][hover] })).filter((r) => Number.isFinite(r.v)).sort((a, b) => b.v - a.v) : [];

  return (
    <div ref={ref} className={`chart ${className ?? ""}`}>
      {w > 0 && h > 0 && (
        <svg width={w} height={h} role="img" aria-label={series.map((s) => s.label).join(", ")}>
          {yt.map((v) => (
            <g key={v} className="grid" opacity={t < 1 ? Math.max(0, (t - 0.6) / 0.4) : 1}>{/* the new scale shows once the morph has nearly arrived */}
              <line x1={pad.l} x2={pad.l + iw} y1={Y(v)} y2={Y(v)} />
              <text x={pad.l - 12} y={Y(v)} dy="0.35em" textAnchor="end">{axis(v)}</text>
            </g>
          ))}
          {marks.map((m) => (
            <text key={m} className="xtick" x={X(m)} y={pad.t + ih + 24} textAnchor="middle">{new Date(m).getUTCFullYear()}</text>
          ))}
          {baseline && Number.isFinite(Y(baseline.value)) && (
            <g className="baseline">
              <line x1={pad.l} x2={pad.l + iw} y1={Y(baseline.value)} y2={Y(baseline.value)} />
              <text x={pad.l + iw - 6} y={Y(baseline.value) - 8} textAnchor="end">{baseline.label}</text>
            </g>
          )}
          {area && shown.filter((s) => s.strong).map((s) => (
            <motion.path key={"a" + s.id} d={areaPath(xs, vals[s.id].map(Y), area === "zero" ? Y(0) : pad.t + ih)} fill={s.color} className="wash"
              initial={reduce ? false : { opacity: 0 }} animate={{ opacity: focus && focus !== s.id ? 0.03 : area === "zero" ? 0.1 : 0.07 }}
              transition={{ duration: 1.2, delay: ENTER + 0.9 }} />
          ))}
          {series.map((s) => {
            const off = hidden?.has(s.id);
            const dim = focus && focus !== s.id;
            return (
              <motion.path key={s.id} d={linePath(xs, vals[s.id].map(Y))} fill="none" stroke={s.color} strokeWidth={s.strong ? 2.75 : s.quiet ? 1.5 : 1.75}
                strokeLinejoin="round" strokeLinecap="round" initial={reduce ? false : { pathLength: 0 }}
                animate={{ pathLength: 1, opacity: off ? 0 : dim ? 0.18 : s.quiet ? 0.7 : 1 }}
                transition={{ pathLength: { duration: s.strong ? 2.1 : 1.8, ease: [0.45, 0, 0.2, 1], delay: ENTER + (s.strong ? 0.25 : 0.1) }, opacity: { duration: 0.35 } }} />
            );
          })}
          {labelled && shown.map((s) => {
            const yLine = Y(last(s.id)), yEnd = endY[s.id], yLab = at[s.id];
            const dim = focus && focus !== s.id;
            return (
              <motion.g key={"e" + s.id} initial={reduce ? false : { opacity: 0 }} animate={{ opacity: dim ? 0.25 : 1 }}
                transition={{ duration: 0.6, delay: hover === null ? ENTER + 1.6 : 0 }}>
                {ends?.[s.id] && <line x1={xEnd + 10} x2={xEnd + 10} y1={yLine} y2={yEnd} stroke={s.color} strokeWidth={2} opacity={0.35} />}
                {ends?.[s.id] && <line x1={xEnd} x2={xEnd + 10} y1={yLine} y2={yLine} stroke={s.color} strokeWidth={2} opacity={0.35} />}
                <circle cx={ends?.[s.id] ? xEnd + 10 : xEnd} cy={yEnd} r={5} fill={s.color} className="ring" />
                {named.has(s.id) && Math.abs(yLab - yEnd) > 2 && <path d={`M${xEnd + 16},${yEnd} L${xEnd + 26},${yLab}`} className="leader" />}
                {named.has(s.id) && (
                  <text x={xEnd + 30} y={yLab} className="end-label">
                    <tspan dy="-0.15em">{ends?.[s.id]?.text ?? format(lastOf(s.values))}</tspan>
                    <tspan x={xEnd + 30} dy="1.25em" className="end-name">{s.label}</tspan>
                  </text>
                )}
              </motion.g>
            );
          })}
          {hover !== null && (
            <g className="cross">
              <line x1={xs[hover]} x2={xs[hover]} y1={pad.t} y2={pad.t + ih} />
              {tip.map(({ s, v }) => <circle key={s.id} cx={xs[hover]} cy={Y(v)} r={4.5} fill={s.color} className="ring" />)}
            </g>
          )}
          <rect x={pad.l} y={pad.t} width={iw} height={ih} fill="transparent" onPointerMove={move} onPointerLeave={() => setHover(null)} />
        </svg>
      )}
      {hover !== null && tip.length > 0 && (
        <div className="tip" style={{ left: xs[hover], top: pad.t, transform: xs[hover] > w * 0.62 ? "translateX(calc(-100% - 14px))" : "translateX(14px)" }}>
          <div className="tip-date">{day(new Date(times[hover]).toISOString().slice(0, 10))}</div>
          {tip.map(({ s, v }) => (
            <div key={s.id} className="tip-row"><span className="key" style={{ background: s.color }} /><span>{s.label}</span><b>{format(v)}</b></div>
          ))}
        </div>
      )}
    </div>
  );
}

/** Rows of bars from one baseline, longest first: where each option ended. */
export function RankedBars({ rows, label, version = "" }: {
  rows: { id: string; name: string; sub?: string; color: string; value: number; text: ReactNode; aside?: ReactNode; strong?: boolean }[]; label: string;
  version?: string;
}) {
  const reduce = useReducedMotion();
  const first = useRef(version);
  const fresh = version === first.current;             // the first showing comes in with the slide; a new ranking moves at once, rows gliding to their places
  const max = Math.max(...rows.map((r) => r.value), 1e-9);
  return (
    <div className="ranked" role="list" aria-label={label}>
      {rows.map((r, i) => (
        <motion.div key={r.id} role="listitem" className={r.strong ? "rk strong" : "rk"} layout initial={reduce ? false : { opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, ease: EASE, delay: ENTER + 0.25 + i * 0.06, layout: { duration: 0.75, ease: SWEEP } }}>
          <div className="rk-name"><span>{r.name}</span>{r.sub && <small>{r.sub}</small>}</div>
          <div className="rk-track">
            <motion.div className="rk-bar" style={{ background: r.color }} initial={reduce ? false : { width: "0%" }} animate={{ width: `${(r.value / max) * 70}%` }}
              transition={{ duration: fresh ? 1.3 : 0.8, ease: EASE, delay: fresh ? ENTER + 0.4 + i * 0.06 : i * 0.025 }} />
            <span className="rk-val">{r.text}</span>
          </div>
          {r.aside && <div className="rk-aside">{r.aside}</div>}
        </motion.div>
      ))}
    </div>
  );
}

/** The model's mix through time: each group's share of the account, stacked to 100%, revealed left to right. */
export function StackArea({ dates, shares, order, color, name, height }: {
  dates: string[]; shares: Record<string, number[]>; order: string[]; color: (g: string) => string; name: (g: string) => string; height?: number;
}) {
  const [ref, { w, h }] = useSize<HTMLDivElement>();
  const reduce = useReducedMotion();
  const [hover, setHover] = useState<number | null>(null);
  const times = useMemo(() => dates.map(ms), [dates]);
  const pad = { l: 72, r: 24, t: 8, b: 32 };
  const iw = Math.max(1, w - pad.l - pad.r), ih = Math.max(1, h - pad.t - pad.b);
  const X = (tm: number) => pad.l + ((tm - times[0]) / (times[times.length - 1] - times[0] || 1)) * iw;
  const Y = (v: number) => pad.t + (1 - v) * ih;
  const xs = times.map(X);
  const layers = useMemo(() => {
    const acc = new Array(dates.length).fill(0);
    return order.map((g) => {
      const lo = [...acc];
      shares[g].forEach((v, i) => (acc[i] += v));
      return { g, lo, hi: [...acc] };
    });
  }, [dates, shares, order]);
  const path = (lo: number[], hi: number[]) =>
    "M" + xs.map((x, i) => `${x.toFixed(1)},${Y(hi[i]).toFixed(1)}`).join("L") + "L" + xs.map((x, i) => `${x.toFixed(1)},${Y(lo[i]).toFixed(1)}`).reverse().join("L") + "Z";
  const marks = times.length ? yearMarks(times[0], times[times.length - 1], iw) : [];
  const move = (e: React.PointerEvent) => {
    const r = (e.currentTarget as SVGRectElement).getBoundingClientRect();
    const tm = times[0] + ((e.clientX - r.left) / r.width) * (times[times.length - 1] - times[0]);
    let i = times.findIndex((x) => x >= tm);
    if (i < 0) i = times.length - 1;
    setHover(i);
  };
  return (
    <div ref={ref} className="chart" style={height ? { height } : undefined}>
      {w > 0 && h > 0 && (
        <svg width={w} height={h} role="img" aria-label="The model's mix through time">
          <defs>
            <clipPath id="sweep"><motion.rect x={pad.l} y={0} height={h} initial={reduce ? false : { width: 0 }} animate={{ width: iw }}
              transition={{ duration: 1.8, ease: [0.45, 0, 0.2, 1], delay: ENTER + 0.2 }} /></clipPath>
          </defs>
          {[0, 0.5, 1].map((v) => (
            <g key={v} className="grid"><text x={pad.l - 12} y={Y(v)} dy="0.35em" textAnchor="end">{Math.round(v * 100)}%</text></g>
          ))}
          <g clipPath="url(#sweep)">
            {layers.map(({ g, lo, hi }) => (
              <path key={g} d={path(lo, hi)} fill={color(g)} opacity={hover === null ? 0.9 : 0.9} className="layer" />
            ))}
          </g>
          {marks.map((m) => <text key={m} className="xtick" x={X(m)} y={pad.t + ih + 20} textAnchor="middle">{new Date(m).getUTCFullYear()}</text>)}
          {hover !== null && <line className="cross-line" x1={xs[hover]} x2={xs[hover]} y1={pad.t} y2={pad.t + ih} />}
          <rect x={pad.l} y={pad.t} width={iw} height={ih} fill="transparent" onPointerMove={move} onPointerLeave={() => setHover(null)} />
        </svg>
      )}
      {hover !== null && (
        <div className="tip" style={{ left: xs[hover], top: pad.t, transform: xs[hover] > w * 0.62 ? "translateX(calc(-100% - 14px))" : "translateX(14px)" }}>
          <div className="tip-date">{month(dates[hover], true)}</div>
          {[...order].reverse().filter((g) => shares[g][hover] > 0.004).map((g) => (
            <div key={g} className="tip-row"><span className="key" style={{ background: color(g) }} /><span>{name(g)}</span><b>{Math.round(shares[g][hover] * 100)}%</b></div>
          ))}
        </div>
      )}
    </div>
  );
}

/** Each trading day as a stem: money bought above the line, money sold below, on the same years as the mix above it. */
export function TradeStrip({ days, from, to, onPick, picked }: {
  days: { date: string; bought: number; sold: number; orders: number }[]; from: string; to: string; onPick?: (date: string | null) => void; picked?: string | null;
}) {
  const [ref, { w, h }] = useSize<HTMLDivElement>();
  const reduce = useReducedMotion();
  const pad = { l: 72, r: 24, t: 6, b: 6 };
  const iw = Math.max(1, w - pad.l - pad.r), mid = h / 2, room = Math.max(1, mid - pad.t - 2);
  const t0 = ms(from), t1 = ms(to);
  const X = (d: string) => pad.l + ((ms(d) - t0) / (t1 - t0 || 1)) * iw;
  const top = Math.max(...days.map((d) => Math.max(d.bought, d.sold)), 1);
  const H = (v: number) => (v > 0 ? Math.max(2, Math.sqrt(v / top) * room) : 0);
  const near = (x: number) => {
    let best: string | null = null, gap = 8;
    for (const d of days) { const g = Math.abs(X(d.date) - x); if (g < gap) { gap = g; best = d.date; } }
    return best;
  };
  return (
    <div ref={ref} className="chart strip">
      {w > 0 && h > 0 && (
        <svg width={w} height={h} role="img" aria-label="Every day the model traded">
          <line className="strip-axis" x1={pad.l} x2={pad.l + iw} y1={mid} y2={mid} />
          <text className="strip-lab" x={pad.l - 12} y={mid - room / 2} dy="0.35em" textAnchor="end">Bought</text>
          <text className="strip-lab" x={pad.l - 12} y={mid + room / 2} dy="0.35em" textAnchor="end">Sold</text>
          {days.map((d, i) => {
            const x = X(d.date), on = picked === d.date;
            return (
              <motion.g key={d.date} initial={reduce ? false : { opacity: 0, scaleY: 0 }} animate={{ opacity: picked && !on ? 0.35 : 1, scaleY: 1 }}
                style={{ originY: `${mid}px` }} transition={{ duration: 0.7, ease: EASE, delay: ENTER + 0.4 + (i / days.length) * 1.4 }}>
                {d.bought > 0 && <rect x={x - 1.5} y={mid - H(d.bought)} width={3} height={H(d.bought)} rx={1.5} className="buy" />}
                {d.sold > 0 && <rect x={x - 1.5} y={mid} width={3} height={H(d.sold)} rx={1.5} className="sell" />}
              </motion.g>
            );
          })}
          <rect x={pad.l} y={0} width={iw} height={h} fill="transparent" style={{ cursor: "pointer" }}
            onPointerMove={(e) => onPick?.(near(e.clientX - (e.currentTarget as SVGRectElement).getBoundingClientRect().left + pad.l))}
            onPointerLeave={() => onPick?.(null)} />
        </svg>
      )}
    </div>
  );
}
