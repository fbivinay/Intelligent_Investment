import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Intelligent Investment: after every cost and tax",
  description: "What ₹X invested on a date would have become after every Indian charge and tax, against the main alternatives, with every number traced.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-IN">
      <body>
        <header className="top">
          <a href="/" className="brand">Intelligent Investment</a>
          <nav>
            <a href="/">Calculator</a>
            <a href="/fyers">How it would run on Fyers</a>
          </nav>
        </header>
        <main>{children}</main>
        <footer className="foot">
          For information only, not investment advice. Past results and estimates, never guarantees. Every number is worked out by one engine from dated tax and
          charge rules; open any ⓘ to see how.
        </footer>
      </body>
    </html>
  );
}
