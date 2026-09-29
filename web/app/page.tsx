import Link from "next/link";
import { ArrowRight, ArrowUpRight } from "@phosphor-icons/react/dist/ssr";
import LineChart from "@/components/LineChart";
import IndiaCompare from "@/components/IndiaCompare";
import Reveal from "@/components/Reveal";
import { OPTIONS, fmtDate, lakh, pct, research, site } from "@/lib/data";

export default function Home() {
  const top = site.india["0.312"];
  const model = top[OPTIONS[0].key];
  const nifty = top["Nifty 50 ETF (NIFTYBEES)"];
  const held = top["IBIT, bought and held (via LRS)"];
  const d = site.decision;
  const lines = OPTIONS.filter((o) => o.name !== "Bitcoin, Indian exchange").map((o, i) => ({
    name: o.name, color: o.color, values: top[o.key].values, bold: i === 0,
  }));

  return (
    <>
      {/* Hero: the one result, and the chart that proves it */}
      <section className="mx-auto grid max-w-6xl items-center gap-12 px-5 pt-16 pb-20 lg:grid-cols-[5fr_7fr] lg:pt-24">
        <div className="space-y-7">
          <h1 className="text-4xl font-semibold leading-[1.05] tracking-tighter md:text-5xl lg:text-[3.4rem]">
            ₹1 lakh became {lakh(model.end)}. Nifty&nbsp;50 made {lakh(nifty.end)}.
          </h1>
          <p className="max-w-[44ch] text-lg leading-relaxed text-muted">
            A deep-learning trend model for Bitcoin and gold ETFs, measured in rupees after every Indian tax.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <Link href="/model"
              className="group inline-flex items-center gap-2 rounded-full bg-accent px-5 py-3 text-sm font-medium text-white transition-[background-color,box-shadow,transform] hover:bg-accent-deep active:scale-[0.98]">
              How the model works
              <ArrowRight aria-hidden size={16} weight="bold" className="transition-transform group-hover:translate-x-0.5" />
            </Link>
            <a href="#today" className="rounded-full px-5 py-3 text-sm font-medium text-ink ring-1 ring-line transition-colors hover:bg-surface">
              Today&apos;s decision
            </a>
          </div>
        </div>
        <div className="rounded-2xl bg-surface p-5 shadow-[0_1px_2px_rgba(24,24,27,0.04),0_12px_40px_-12px_rgba(24,24,27,0.10)] ring-1 ring-line/70">
          <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2 px-1">
            <p className="text-sm font-medium">₹1 lakh invested on {fmtDate(site.dates[0])}, value in hand after tax</p>
            <p className="num text-xs text-faint">30% slab</p>
          </div>
          <LineChart dates={site.dates} lines={lines} />
          <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 px-1 text-xs text-muted">
            {lines.map((l) => (
              <span key={l.name} className="inline-flex items-center gap-1.5">
                <span className="h-[3px] w-4 rounded-full" style={{ backgroundColor: l.color }} />{l.name}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* The comparison no one else shows: every Indian option, in rupees, after tax */}
      <section className="mx-auto max-w-6xl px-5 py-20">
        <Reveal>
          <div className="mb-12 max-w-[60ch] space-y-4">
            <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">Where ₹1 lakh went, after tax</h2>
            <p className="leading-relaxed text-muted">
              Every rupee figure is what you would get back if you sold that day and paid the tax. The rupee&apos;s
              fall from ₹83 to ₹96 a dollar counts too, because the taxman counts it.
            </p>
          </div>
          <IndiaCompare />
        </Reveal>
      </section>

      {/* Today's decision */}
      <section id="today" className="scroll-mt-20 bg-surface py-20 ring-1 ring-line/70">
        <Reveal className="mx-auto grid max-w-6xl gap-12 px-5 lg:grid-cols-[1fr_1.2fr]">
          <div className="space-y-4">
            <p className="text-sm font-medium text-accent">Decision for the next US open</p>
            <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">Hold {Math.round(d.w_btc * 100)}% in the Bitcoin ETF</h2>
            <p className="max-w-[46ch] leading-relaxed text-muted">
              Decided after the {fmtDate(d.date)} close{d.live ? " and recorded before the next open" : ""}.
              {site.first_live ? ` Every decision since ${fmtDate(site.first_live)} is written to a public log the moment it is made.` : ""}
            </p>
          </div>
          <div>
            <div className="flex h-14 overflow-hidden rounded-2xl">
              {[{ k: "Bitcoin ETF", w: d.w_btc, c: "bg-accent text-white" },
                { k: "Gold ETF", w: d.w_gold, c: "bg-amber-600 text-white" },
                { k: "T-bills", w: d.w_cash, c: "bg-line text-ink" }].map((p) => p.w > 0.01 && (
                <div key={p.k} className={`${p.c} num flex items-center justify-center text-sm font-medium`}
                     style={{ width: `${p.w * 100}%` }}>
                  {p.w >= 0.1 ? `${Math.round(p.w * 100)}%` : ""}
                </div>
              ))}
            </div>
            <dl className="mt-8 grid grid-cols-3 gap-6">
              {([["Bitcoin ETF (IBIT)", d.w_btc], ["Gold ETF (GLD)", d.w_gold], ["US T-bills", d.w_cash]] as const).map(([k, w]) => (
                <div key={k}>
                  <dt className="text-sm text-muted">{k}</dt>
                  <dd className="num mt-1 text-3xl font-medium tracking-tight">{Math.round(w * 100)}%</dd>
                </div>
              ))}
            </dl>
          </div>
        </Reveal>
      </section>

      {/* Proof: asymmetric, three things that make the result believable */}
      <section className="mx-auto max-w-6xl px-5 py-24">
        <Reveal className="grid gap-5 md:grid-cols-[1.4fr_1fr]">
          <div className="flex flex-col justify-between gap-10 rounded-2xl bg-accent p-8 text-white md:row-span-2">
            <p className="max-w-[30ch] text-lg leading-snug text-white/85">
              The hard part of Bitcoin is not the gains. It is sitting through the falls.
            </p>
            <div className="grid grid-cols-2 gap-6">
              <div>
                <p className="num text-5xl font-medium tracking-tight">{pct(model.worst_drop, 0)}</p>
                <p className="mt-2 text-sm text-white/75">worst fall, DeepTrend</p>
              </div>
              <div>
                <p className="num text-5xl font-medium tracking-tight text-white/60">{pct(held.worst_drop, 0)}</p>
                <p className="mt-2 text-sm text-white/75">worst fall, Bitcoin ETF held</p>
              </div>
            </div>
          </div>
          <Link href="/data" className="group rounded-2xl bg-surface p-7 ring-1 ring-line transition-shadow hover:shadow-[0_12px_40px_-16px_rgba(24,24,27,0.18)]">
            <p className="num text-4xl font-medium tracking-tight">{research.pool.market_days.toLocaleString("en-IN")}</p>
            <p className="mt-2 text-muted">days of prices from {research.pool.markets.length} markets taught the network</p>
            <p className="mt-6 inline-flex items-center gap-1 text-sm font-medium text-accent">
              The datasets <ArrowUpRight aria-hidden size={14} weight="bold" className="transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
            </p>
          </Link>
          <a href="https://github.com/fbivinay/btc-paper-trader/blob/main/web/data/decisions.csv"
             className="group rounded-2xl bg-surface p-7 ring-1 ring-line transition-shadow hover:shadow-[0_12px_40px_-16px_rgba(24,24,27,0.18)]">
            <p className="text-2xl font-medium tracking-tight">Nothing can be edited later</p>
            <p className="mt-2 text-muted">Each daily decision is committed to git before the market opens.</p>
            <p className="mt-6 inline-flex items-center gap-1 text-sm font-medium text-accent">
              See the log <ArrowUpRight aria-hidden size={14} weight="bold" className="transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
            </p>
          </a>
        </Reveal>
      </section>
    </>
  );
}
