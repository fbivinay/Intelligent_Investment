import type { Metadata } from "next";
import { ArrowRight, ChartLineUp, Database, Brain, Scales, Timer, UsersThree } from "@phosphor-icons/react/dist/ssr";
import Reveal from "@/components/Reveal";
import { pct, research } from "@/lib/data";

export const metadata: Metadata = { title: "The model | DeepTrend" };

const STEPS = [
  { icon: Database, title: "Prices", body: "Daily closes from 18 markets, 2000 to today" },
  { icon: ChartLineUp, title: "8 features", body: "Returns and trend signals, scaled by each market's own volatility" },
  { icon: Brain, title: "Transformer", body: "Reads the last 63 trading days and outputs a position from 0 to 1" },
  { icon: UsersThree, title: "Second opinion", body: "Averaged with eight classic trend votes on the same prices" },
  { icon: Scales, title: "Risk", body: "Shrinks the position in wild markets; gold and T-bills take the rest" },
  { icon: Timer, title: "Trade", body: "Decided after the US close, traded at the next open" },
];

export default function Model() {
  const rows = [...research.rows].sort((a, b) => b.dev_score - a.dev_score);
  const years = Array.from({ length: 2027 - 2000 }, (_, i) => 2000 + i);

  return (
    <div className="mx-auto max-w-6xl px-5">
      <header className="max-w-[62ch] space-y-5 pt-16 pb-16 lg:pt-24">
        <h1 className="text-4xl font-semibold leading-[1.05] tracking-tighter md:text-5xl">
          A network trained to make money, not to guess
        </h1>
        <p className="text-lg leading-relaxed text-muted">
          A Deep Momentum Network, after Lim, Zohren and Roberts (University of Oxford, 2019). It learns how much to
          hold by maximising risk-adjusted return directly.
        </p>
      </header>

      {/* Why: the lesson from the first model */}
      <Reveal className="grid gap-5 md:grid-cols-2">
        <div className="rounded-2xl bg-surface p-8 ring-1 ring-line">
          <p className="text-sm font-medium text-muted">What we built first</p>
          <p className="mt-3 text-2xl font-medium leading-snug tracking-tight">
            An LSTM that guessed Bitcoin&apos;s 4-hour direction right <span className="tabular-nums">44.3%</span> of the time,
            against <span className="tabular-nums">37.6%</span> by chance.
          </p>
          <p className="mt-4 leading-relaxed text-muted">
            It still lost money. Its edge was <span className="font-medium text-ink">0.04%</span> a trade and the fees
            were <span className="font-medium text-ink">0.25%</span>. Being right more often is not the same as making money.
          </p>
        </div>
        <div className="rounded-2xl bg-accent p-8 text-white">
          <p className="text-sm font-medium text-white/75">What this model does instead</p>
          <p className="mt-3 text-2xl font-medium leading-snug tracking-tight">
            It is scored on profit per unit of risk, so every training step pushes toward better returns.
          </p>
          <p className="mt-4 leading-relaxed text-white/80">
            Bitcoin alone has too little history for a neural network, so it learns from 18 markets at once.
            Trends behave alike everywhere; the network learns the pattern, then applies it to Bitcoin and gold.
          </p>
        </div>
      </Reveal>

      {/* How it works */}
      <Reveal className="py-24">
        <h2 className="max-w-[30ch] text-3xl font-semibold tracking-tight md:text-4xl">How one decision is made</h2>
        <ol className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
          {STEPS.map((s, i) => (
            <li key={s.title} className="relative rounded-2xl bg-surface p-6 ring-1 ring-line">
              <s.icon aria-hidden size={26} weight="duotone" className="text-accent" />
              <p className="mt-5 font-medium">{s.title}</p>
              <p className="mt-2 text-sm leading-relaxed text-muted">{s.body}</p>
              {i < STEPS.length - 1 && (
                <ArrowRight aria-hidden size={16} className="absolute -right-3.5 top-1/2 z-10 hidden -translate-y-1/2 rounded-full bg-page text-faint lg:block" />
              )}
            </li>
          ))}
        </ol>

        <div className="mt-6 grid gap-5 md:grid-cols-[1.3fr_1fr]">
          <div className="rounded-2xl bg-ink p-8 text-page">
            <p className="text-sm text-page/60">The loss the network minimises</p>
            <p className="num mt-4 text-xl leading-relaxed md:text-2xl">
              L = − mean(p·r) / std(p·r) × √252
            </p>
            <p className="mt-4 max-w-[52ch] text-sm leading-relaxed text-page/70">
              p is the position the network chose, r the next day&apos;s return. Minus the annualised Sharpe ratio: the
              network gets better only by earning more for each unit of risk it takes.
            </p>
          </div>
          <div className="rounded-2xl bg-surface p-8 ring-1 ring-line">
            <p className="text-sm text-muted">Built in PyTorch, trained on a Kaggle GPU</p>
            <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-4 text-sm">
              {[["Network", "Transformer, 1 layer"], ["Attention", "2 heads, causal mask"], ["Memory", "63 trading days"],
                ["Output", "sigmoid, 0 to 1"], ["Calibration", "percentile of past 3 years"], ["Ensemble", "3 seeds averaged"]].map(([k, v]) => (
                <div key={k}><dt className="text-faint">{k}</dt><dd className="mt-0.5 font-medium">{v}</dd></div>
              ))}
            </dl>
          </div>
        </div>
      </Reveal>

      {/* Honesty: walk-forward */}
      <Reveal>
        <h2 className="max-w-[34ch] text-3xl font-semibold tracking-tight md:text-4xl">It never sees the year it is tested on</h2>
        <p className="mt-4 max-w-[62ch] leading-relaxed text-muted">
          Every January the network is retrained from scratch on everything before that year, then judged on the year
          ahead. The model was chosen on 2019 to 2023 alone; IBIT&apos;s real prices from 2024 are the exam.
        </p>
        <div className="mt-10 overflow-x-auto">
          <div className="grid min-w-[640px] grid-cols-[repeat(27,minmax(0,1fr))] gap-[3px]">
            {years.map((y) => (
              <div key={y} className={`h-10 rounded-[4px] ${y < 2019 ? "bg-line" : y < 2024 ? "bg-accent/60" : "bg-accent"}`}
                   title={`${y}`} />
            ))}
          </div>
          <div className="mt-3 grid min-w-[640px] grid-cols-[19fr_4fr_4fr] text-xs text-muted">
            <span>2000 to 2018: learning only</span>
            <span>2019 to 2023: choosing</span>
            <span className="text-right">2024 on: real exam</span>
          </div>
        </div>
      </Reveal>

      {/* The comparison */}
      <Reveal className="pt-24">
        <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">Every network, judged the same way</h2>
        <p className="mt-4 max-w-[62ch] leading-relaxed text-muted">{research.why}</p>
        <div className="mt-10 overflow-x-auto rounded-2xl bg-surface ring-1 ring-line">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="text-left text-muted">
                <th className="px-6 pt-5 pb-3 font-normal">Model</th>
                <th className="px-4 pt-5 pb-3 text-right font-normal">2019 to 2023 per year</th>
                <th className="px-4 pt-5 pb-3 text-right font-normal">worst fall</th>
                <th className="px-4 pt-5 pb-3 text-right font-normal">Real ETF per year</th>
                <th className="px-6 pt-5 pb-3 text-right font-normal">worst fall</th>
              </tr>
            </thead>
            <tbody className="num">
              {rows.map((r) => {
                const chosen = r.name === research.chosen;
                return (
                  <tr key={r.name} className={chosen ? "bg-accent-soft" : ""}>
                    <td className={`px-6 py-3.5 font-sans ${chosen ? "font-semibold text-accent" : r.kind === "benchmark" ? "text-muted" : ""}`}>
                      {r.name}{chosen && <span className="ml-2 rounded-full bg-accent px-2 py-0.5 text-[11px] font-medium text-white">chosen</span>}
                    </td>
                    <td className="px-4 py-3.5 text-right">{pct(r.dev_cagr)}</td>
                    <td className="px-4 py-3.5 text-right text-muted">{pct(r.dev_dd, 0)}</td>
                    <td className="px-4 py-3.5 text-right">{pct(r.real_cagr)}</td>
                    <td className="px-6 py-3.5 text-right text-muted">{pct(r.real_dd, 0)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="mt-4 text-sm text-faint">After Indian tax at the 30% slab and all charges, in US dollars. Ranked by return per unit of worst fall on 2019 to 2023, the only years used to choose. Best of each architecture shown.</p>
        <div className="mt-10 grid gap-5 md:grid-cols-2">
          <div className="rounded-2xl bg-surface p-7 ring-1 ring-line">
            <p className="font-medium">What the networks learned</p>
            <p className="mt-2 leading-relaxed text-muted">
              Trained for risk-adjusted return, every network turned cautious: it held too little Bitcoin in strong
              rallies. Calibration fixed most of that; averaging with the trend votes fixed the rest.
            </p>
          </div>
          <div className="rounded-2xl bg-surface p-7 ring-1 ring-line">
            <p className="font-medium">The honest result</p>
            <p className="mt-2 leading-relaxed text-muted">
              On real 2024 to 2026 prices the simple trend votes alone earned more. The hybrid gave up some return
              for a network that adapts as markets change. Both beat holding on the size of the falls.
            </p>
          </div>
        </div>
      </Reveal>
    </div>
  );
}
