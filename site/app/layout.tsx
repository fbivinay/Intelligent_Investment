import type { Metadata, Viewport } from "next";
import { Archivo } from "next/font/google";
import { Deck } from "@/components/Deck";
import { DataProvider } from "@/lib/data";
import "./globals.css";

// One family, used two ways: normal width for words, expanded width for money.
const archivo = Archivo({ subsets: ["latin", "latin-ext"], axes: ["wdth"], variable: "--font-archivo", display: "swap" });

export const metadata: Metadata = {
  title: "Intelligent Investment",
  description: "What money invested in Indian markets could have become, after every real charge and every tax, set beside the ordinary ways to invest.",
};

export const viewport: Viewport = { themeColor: "#F5F6F2" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-IN" className={archivo.variable}>
      <body>
        <div className="gate" role="note">
          <svg width="120" height="84" viewBox="0 0 120 84" aria-hidden>
            <rect x="14" y="6" width="92" height="58" rx="7" fill="none" stroke="currentColor" strokeWidth="2" />
            <path d="M4 72h112l-6 6H10z" fill="currentColor" opacity=".18" />
            <path d="M26 50 42 38l10 6 16-18 12 6 14-14" fill="none" stroke="var(--model)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <h1>This experience is designed for a larger screen.</h1>
          <p>Open Intelligent Investment on a laptop or desktop for the full experience.</p>
        </div>
        <div className="app">
          <DataProvider>
            <Deck />
          </DataProvider>
          {children}
        </div>
      </body>
    </html>
  );
}
