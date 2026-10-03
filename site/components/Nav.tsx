"use client";

import { motion, useMotionValueEvent, useScroll } from "motion/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

const PAGES = [
  { href: "/", label: "Overview" },
  { href: "/performance", label: "Performance" },
  { href: "/evidence", label: "Evidence" },
];

export function Nav() {
  const path = usePathname();
  const { scrollY } = useScroll();
  const [scrolled, setScrolled] = useState(false);
  useMotionValueEvent(scrollY, "change", (v) => setScrolled(v > 12));

  return (
    <header className={scrolled ? "nav scrolled" : "nav"}>
      <div className="wrap nav-inner">
        <Link href="/" className="brand">
          <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden>
            <path d="M3 16 L8.5 10.5 L12 13.5 L19 6" fill="none" stroke="var(--accent)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Intelligent Investment
        </Link>
        <nav>
          {PAGES.map((p) => {
            const on = p.href === "/" ? path === "/" : path.startsWith(p.href);
            return (
              <Link key={p.href} href={p.href} className={on ? "on" : ""}>
                {on && <motion.span layoutId="nav-pill" className="nav-pill" transition={{ type: "spring", stiffness: 380, damping: 34 }} />}
                <span>{p.label}</span>
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
