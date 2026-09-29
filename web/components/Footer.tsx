import Link from "next/link";
import { site } from "@/lib/data";

export default function Footer() {
  return (
    <footer className="mt-32 border-t border-line">
      <div className="mx-auto grid max-w-6xl gap-8 px-5 py-12 text-sm text-muted md:grid-cols-[2fr_1fr_1fr]">
        <div className="max-w-[48ch] space-y-3">
          <p className="font-medium text-ink">DeepTrend</p>
          <p>
            A final-year deep learning project. Paper trading on real market prices; not investment advice.
            Indian tax treatment as understood in 2026, confirm with a Chartered Accountant.
          </p>
        </div>
        <div className="space-y-2">
          <p className="font-medium text-ink">Project</p>
          <Link href="/model" className="block hover:text-ink">How the model works</Link>
          <Link href="/data" className="block hover:text-ink">Datasets</Link>
          <Link href="/go-live" className="block hover:text-ink">Going live</Link>
        </div>
        <div className="space-y-2">
          <p className="font-medium text-ink">Record</p>
          <a href="https://github.com/fbivinay/btc-paper-trader" className="block hover:text-ink">Source code</a>
          <a href="https://github.com/fbivinay/btc-paper-trader/blob/main/web/data/decisions.csv" className="block hover:text-ink">
            Every decision, timestamped
          </a>
          <p className="num text-faint">Updated {new Date(site.generated_at).toUTCString().slice(5, 22)} UTC</p>
        </div>
      </div>
    </footer>
  );
}
