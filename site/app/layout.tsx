import type { Metadata, Viewport } from "next";
import { Archivo } from "next/font/google";
import { Deck } from "@/components/Deck";
import { DataProvider } from "@/lib/data";
import "./globals.css";

// One family, used two ways: normal width for words, expanded width for money.
const archivo = Archivo({ subsets: ["latin", "latin-ext"], axes: ["wdth"], variable: "--font-archivo", display: "swap" });

const description = "What money invested in Indian markets could have become, after every real charge and every tax, set beside the ordinary ways to invest.";

export const metadata: Metadata = {
  metadataBase: new URL("https://intelligent-investment.vercel.app"),
  title: "Intelligent Investment",
  description,
  openGraph: {
    type: "website",
    url: "/",
    title: "Intelligent Investment",
    description,
    images: [{ url: "/og.png", width: 1440, height: 756 }],
  },
  twitter: { card: "summary_large_image", title: "Intelligent Investment", description, images: ["/og.png"] },
};

export const viewport: Viewport = { themeColor: "#F5F6F2" };

// Phones and tablets get the gate below instead of the deck (see .gate in globals.css). Inline in <head> so the flag is set before the
// first paint: by user agent, iPadOS by its touch points, and any touch-only screen whose "Desktop site" mode rewrote the user agent.
const DESKTOP_ONLY = `(function(){try{var n=navigator,ua=n.userAgent||"",mq=function(q){return!!(window.matchMedia&&matchMedia(q).matches)};
if((n.userAgentData&&n.userAgentData.mobile)||/Android|iPhone|iPad|iPod|Mobile|Tablet|Silk|Kindle|PlayBook|BlackBerry|BB10|Opera Mini|IEMobile|webOS/i.test(ua)||(/Macintosh/.test(ua)&&n.maxTouchPoints>1)||(mq("(pointer: coarse)")&&!mq("(any-pointer: fine)")))document.documentElement.setAttribute("data-desktop-only","")}catch(e){}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // suppressHydrationWarning: the inline script sets data-desktop-only before React hydrates.
    <html lang="en-IN" className={archivo.variable} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: DESKTOP_ONLY }} />
      </head>
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
