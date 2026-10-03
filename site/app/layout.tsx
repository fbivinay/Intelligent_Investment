import type { Metadata } from "next";
import { Geist, Instrument_Serif } from "next/font/google";
import { Nav } from "@/components/Nav";
import { ScenarioProvider } from "@/lib/scenario";
import "./globals.css";

const sans = Geist({ subsets: ["latin"], variable: "--font-sans" });
const serif = Instrument_Serif({ subsets: ["latin"], weight: "400", variable: "--font-serif" });

export const metadata: Metadata = {
  title: "Intelligent Investment",
  description: "What your money could have become in Indian markets, after every real charge and every tax, compared with the ordinary ways to invest.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-IN" className={`${sans.variable} ${serif.variable}`}>
      <body>
        <div className="gate" role="note">
          <svg className="gate-art" viewBox="0 0 160 110" aria-hidden>
            <rect className="gate-screen" x="22" y="10" width="116" height="74" rx="6" />
            <path className="gate-base" d="M6 92h148l-8 8H14z" />
            <path className="gate-line" d="M34 70 L52 58 L66 64 L84 44 L100 50 L124 26" />
          </svg>
          <h1>This experience is designed for a larger screen.</h1>
          <p>Open Intelligent Investment on a laptop or desktop for the full experience.</p>
        </div>
        <div className="app">
          <ScenarioProvider>
            <Nav />
            {children}
            <footer className="foot wrap">
              <span>Intelligent Investment</span>
              <span>Past results, not a promise. Not investment advice. No orders are ever sent.</span>
            </footer>
          </ScenarioProvider>
        </div>
      </body>
    </html>
  );
}
