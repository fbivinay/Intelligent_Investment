import type { Metadata } from "next";
import { ArrowUpRight } from "@phosphor-icons/react/dist/ssr";
import Reveal from "@/components/Reveal";
import { fmtDate, research, site } from "@/lib/data";

export const metadata: Metadata = { title: "Data | DeepTrend" };

const GROUPS: [string, [string, string][]][] = [
  ["Stocks", [["SPY", "S&P 500"], ["QQQ", "Nasdaq-100"], ["IWM", "US small caps"], ["VNQ", "US real estate"]]],
  ["World", [["^NSEI", "Nifty 50"], ["^N225", "Nikkei 225"], ["^GDAXI", "DAX"], ["^FTSE", "FTSE 100"],
             ["EFA", "Developed markets"], ["EEM", "Emerging markets"]]],
  ["Bonds", [["TLT", "US 20+ year Treasuries"], ["IEF", "US 7-10 year Treasuries"]]],
  ["Commodities", [["GLD", "Gold"], ["SLV", "Silver"], ["USO", "Oil"], ["DBC", "Commodity basket"]]],
  ["Crypto", [["BTC", "Bitcoin"], ["ETH-USD", "Ethereum"]]],
];

const FEATURES: [string, string, string][] = [
  ["Returns", "1, 21, 63, 126, 252 days", "How far price moved over a day, a month, a quarter, half a year and a year, divided by that market's own volatility so Bitcoin and bonds speak the same language."],
  ["Trend signals", "MACD 8/24, 16/48, 32/96", "Gap between a fast and a slow average, at three speeds. Positive means the trend is up; the size says how firmly."],
];

const LIVE: [string, string, string][] = [
  ["IBIT", "iShares Bitcoin Trust", "The Bitcoin ETF traded, daily open and close since its launch on 11 Jan 2024"],
  ["GLD", "SPDR Gold Shares", "The gold ETF traded"],
  ["^IRX", "13-week US T-bill yield", "What idle money earns"],
  ["INR=X", "Rupees per dollar", "To measure everything in rupees"],
  ["Bitcoin before 2024", "Binance BTC/USDT", "Real Bitcoin prices at US market hours, standing in for the ETF before it existed"],
  ["NIFTYBEES, GOLDBEES", "NSE ETFs", "The Indian alternatives, plus Bitcoin in rupees and SBI FD rates"],
];

export default function Data() {
  const p = research.pool;
  return (
    <div className="mx-auto max-w-6xl px-5">
      <header className="max-w-[60ch] space-y-5 pt-16 pb-14 lg:pt-24">
        <h1 className="text-4xl font-semibold leading-[1.05] tracking-tighter md:text-5xl">The data behind it</h1>
        <p className="text-lg leading-relaxed text-muted">
          Free, public and real. Prices are fetched fresh every trading day; nothing is typed in by hand.
        </p>
      </header>

      <Reveal>
        <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl bg-line ring-1 ring-line md:grid-cols-4">
          {[[p.market_days.toLocaleString("en-IN"), "market-days of training data"],
            [String(p.markets.length), "markets pooled"],
            [`${new Date().getFullYear() - p.first_year} years`, `of history, from ${p.first_year}`],
            [String(p.features.length), "features per day"]].map(([v, k]) => (
            <div key={k} className="bg-surface p-7">
              <dt className="sr-only">{k}</dt>
              <dd className="num text-3xl font-medium tracking-tight md:text-4xl">{v}</dd>
              <p className="mt-2 text-sm text-muted">{k}</p>
            </div>
          ))}
        </dl>
      </Reveal>

      <Reveal className="pt-24">
        <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">What the network learns from</h2>
        <p className="mt-4 max-w-[60ch] leading-relaxed text-muted">
          Daily closes from Yahoo Finance, from 2000 where a market has that much history.
        </p>
        <div className="mt-10 grid gap-x-10 gap-y-8 md:grid-cols-[repeat(auto-fit,minmax(15rem,1fr))]">
          {GROUPS.map(([g, items]) => (
            <div key={g}>
              <p className="text-sm font-medium">{g}</p>
              <ul className="mt-3 flex flex-wrap gap-2">
                {items.map(([t, n]) => (
                  <li key={t} className="rounded-full bg-surface px-3 py-1.5 text-sm ring-1 ring-line">
                    {n} <span className="num text-xs text-faint">{t}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </Reveal>

      <Reveal className="pt-24">
        <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">Eight features a day</h2>
        <div className="mt-10 grid gap-5 md:grid-cols-2">
          {FEATURES.map(([name, which, body]) => (
            <div key={name} className="rounded-2xl bg-surface p-8 ring-1 ring-line">
              <p className="font-medium">{name}</p>
              <p className="num mt-1 text-sm text-accent">{which}</p>
              <p className="mt-4 leading-relaxed text-muted">{body}</p>
            </div>
          ))}
        </div>
        <p className="mt-4 text-sm text-faint">
          Target: the next day&apos;s return, divided by volatility. The network sees 63 days of these eight numbers at a time.
        </p>
      </Reveal>

      <Reveal className="pt-24">
        <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">What it trades on, live</h2>
        <div className="mt-10 grid gap-x-10 gap-y-6 md:grid-cols-2">
          {LIVE.map(([t, n, body]) => (
            <div key={t} className="border-t border-line pt-5">
              <p className="font-medium">{n} <span className="num text-sm text-faint">{t}</span></p>
              <p className="mt-1.5 text-sm leading-relaxed text-muted">{body}</p>
            </div>
          ))}
        </div>
        <a href="https://github.com/fbivinay/btc-paper-trader/blob/main/web/data/decisions.csv"
           className="group mt-12 inline-flex items-center gap-2 rounded-full bg-ink px-5 py-3 text-sm font-medium text-page transition-[background-color,box-shadow,transform] hover:bg-ink/85 active:scale-[0.98]">
          Every decision since {fmtDate(site.dates[0])}
          <ArrowUpRight aria-hidden size={15} weight="bold" className="transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
        </a>
      </Reveal>
    </div>
  );
}
