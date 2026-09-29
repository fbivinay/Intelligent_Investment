import type { Metadata } from "next";
import { BellRinging, Robot, ShieldCheck } from "@phosphor-icons/react/dist/ssr";
import Reveal from "@/components/Reveal";

export const metadata: Metadata = {
  title: "Go live | DeepTrend",
  description: "Running the model with real money from India: broker, LRS, automation, tax and safety.",
};

const ROUTES = [
  { icon: BellRinging, title: "Phone alerts, any app",
    body: "An alert arrives only when your split should change, about once a week. You place two to four orders in INDmoney, Vested or any broker you already use. No API needed.",
    how: "Install the free ntfy app and subscribe to your private topic (the NTFY_TOPIC secret)." },
  { icon: Robot, title: "Fully automatic",
    body: "The daily job places the orders itself, the morning after each decision, with every safety rule below enforced in code.",
    how: "Alpaca paper account first: add its keys as GitHub secrets and set SEND_ORDERS to on. Live keys and ALPACA_LIVE=yes later." },
];

const STEPS: [string, string][] = [
  ["Paper first", "Run on a paper account for one to three months and compare it with this site."],
  ["Make the repository private", "Actions logs of public repositories are public. Real money should not run in public."],
  ["Send money under LRS", "Up to $250,000 a year with PAN and Form A2. TCS of 20% above ₹10 lakh comes back against your income tax."],
  ["Switch to live keys, start small", "Set MAX_ORDER_USD to cap any single order."],
];

const RULES = [
  "Buys only from cash. Never margin, never leverage.",
  "Never sells more than it holds. No short selling.",
  "Each order is tagged with its decision date, so the broker rejects a second copy.",
  "Stale, missing or absurd prices stop the run instead of trading.",
  "One switch, SEND_ORDERS, turns every order off.",
];

export default function GoLive() {
  return (
    <div className="mx-auto max-w-6xl px-5">
      <header className="max-w-[58ch] space-y-5 pt-16 pb-14 lg:pt-24">
        <h1 className="text-4xl font-semibold leading-[1.05] tracking-tighter md:text-5xl">Going live with real money</h1>
        <p className="text-lg leading-relaxed text-muted">
          The automation already runs every trading day. Real money is a configuration change, not new code.
        </p>
      </header>

      <Reveal className="grid gap-5 md:grid-cols-2">
        {ROUTES.map((r) => (
          <div key={r.title} className="flex flex-col rounded-2xl bg-surface p-8 ring-1 ring-line">
            <r.icon aria-hidden size={28} weight="duotone" className="text-accent" />
            <p className="mt-6 text-xl font-medium tracking-tight">{r.title}</p>
            <p className="mt-3 leading-relaxed text-muted">{r.body}</p>
            <p className="mt-auto pt-6 text-sm text-ink">{r.how}</p>
          </div>
        ))}
      </Reveal>

      <Reveal className="grid gap-12 pt-24 md:grid-cols-[1fr_1fr]">
        <div>
          <h2 className="text-3xl font-semibold tracking-tight">Four steps</h2>
          <ol className="mt-8 space-y-6">
            {STEPS.map(([t, b], i) => (
              <li key={t} className="grid grid-cols-[2rem_1fr] gap-3">
                <span className="num grid h-7 w-7 place-items-center rounded-full bg-accent-soft text-sm text-accent">{i + 1}</span>
                <div>
                  <p className="font-medium">{t}</p>
                  <p className="mt-1 text-sm leading-relaxed text-muted">{b}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
        <div className="rounded-2xl bg-ink p-8 text-page">
          <ShieldCheck aria-hidden size={28} weight="duotone" className="text-page/80" />
          <p className="mt-6 text-xl font-medium tracking-tight">Enforced in code, whatever the model says</p>
          <ul className="mt-6 space-y-3.5 text-sm leading-relaxed text-page/75">
            {RULES.map((r) => <li key={r}>{r}</li>)}
          </ul>
        </div>
      </Reveal>

      <Reveal className="pt-24">
        <h2 className="text-3xl font-semibold tracking-tight">Tax in India</h2>
        <div className="mt-8 grid gap-x-10 gap-y-6 md:grid-cols-3">
          {[["Not crypto tax", "Gains on US-listed ETFs are capital gains on foreign securities, not the 30% VDA tax."],
            ["24 months", "Under 24 months, taxed at your slab. From 24 months, 12.5% plus cess."],
            ["Losses count", "Losses offset gains, and unused losses carry forward 8 years if you file on time."],
            ["Schedule FA", "Report the foreign account every year in ITR-2 or ITR-3."],
            ["Brokers", "Interactive Brokers accepts Indian residents and has an API. Check Alpaca's eligibility when you apply."],
            ["Estate tax", "US estate tax can apply above $60,000 of US assets. Take advice before investing large sums."]].map(([t, b]) => (
            <div key={t} className="border-t border-line pt-5">
              <p className="font-medium">{t}</p>
              <p className="mt-1.5 text-sm leading-relaxed text-muted">{b}</p>
            </div>
          ))}
        </div>
        <p className="mt-8 text-sm text-faint">Confirm with a Chartered Accountant before investing.</p>
      </Reveal>
    </div>
  );
}
