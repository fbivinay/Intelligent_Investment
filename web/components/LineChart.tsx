"use client";

import { useEffect, useRef } from "react";
import { createChart, LineSeries, type IChartApi, type Time } from "lightweight-charts";

export type Line = { name: string; color: string; values: number[]; bold?: boolean };

/** Light, quiet line chart. The first line is drawn on top and thicker. */
export default function LineChart({ dates, lines, currency = "₹", height = 340 }:
  { dates: string[]; lines: Line[]; currency?: "₹" | "$"; height?: number }) {
  const box = useRef<HTMLDivElement>(null);
  const chart = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!box.current) return;
    const fmt = (v: number) =>
      currency === "₹" ? `₹${(v / 100000).toFixed(2)}L` : `$${Math.round(v).toLocaleString("en-US")}`;
    const c = createChart(box.current, {
      height,
      autoSize: true,
      layout: { background: { color: "transparent" }, textColor: "#71717a", fontSize: 11,
                fontFamily: "var(--font-geist-mono), ui-monospace", attributionLogo: false },
      grid: { vertLines: { visible: false }, horzLines: { color: "#f0f0f1" } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, fixLeftEdge: true, fixRightEdge: true },
      crosshair: { vertLine: { color: "#d4d4d8", labelBackgroundColor: "#18181b" },
                   horzLine: { color: "#d4d4d8", labelBackgroundColor: "#18181b" } },
      localization: { priceFormatter: fmt },
      handleScroll: false,
      handleScale: false,
    });
    [...lines].reverse().forEach((l) => {
      const s = c.addSeries(LineSeries, {
        color: l.color, lineWidth: l.bold ? 3 : 2, priceLineVisible: false,
        lastValueVisible: !!l.bold, crosshairMarkerRadius: l.bold ? 4 : 3,
      });
      s.setData(dates.map((d, i) => ({ time: d as Time, value: l.values[i] })));
    });
    c.timeScale().fitContent();
    chart.current = c;
    return () => { c.remove(); chart.current = null; };
  }, [dates, lines, currency, height]);

  return <div ref={box} style={{ height }} className="w-full" role="img"
              aria-label={`Chart: ${lines.map((l) => l.name).join(", ")}`} />;
}
