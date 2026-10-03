"use client";

import { animate, motion, useInView, useReducedMotion, useSpring, useTransform } from "motion/react";
import { useEffect, useRef, type ReactNode } from "react";

export const EASE = [0.22, 1, 0.36, 1] as const;

/** A number that glides to each new value. With `fromZero` it starts at 0 and counts up the first time it scrolls into view. */
export function Counter({ value, format, fromZero = false, className }: { value: number; format: (n: number) => string; fromZero?: boolean; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const seen = useInView(ref, { once: true, margin: "-10% 0px" });
  const reduce = useReducedMotion();
  const mv = useSpring(fromZero ? 0 : value, { stiffness: 70, damping: 20, mass: 0.9 });
  const text = useTransform(mv, format);
  useEffect(() => {
    if (fromZero && !seen) return;
    if (reduce) mv.jump(value);
    else mv.set(value);
  }, [value, seen, fromZero, reduce, mv]);
  return <motion.span ref={ref} className={`num ${className ?? ""}`}>{text}</motion.span>;
}

/** Fades and lifts its children into place when they scroll into view. */
export function Reveal({ children, delay = 0, y = 18, className, as = "div" }: { children: ReactNode; delay?: number; y?: number; className?: string; as?: "div" | "section" | "li" }) {
  const reduce = useReducedMotion();
  const M = motion[as];
  return (
    <M className={className} initial={reduce ? false : { opacity: 0, y }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-8% 0px" }}
       transition={{ duration: 0.9, ease: EASE, delay }}>
      {children}
    </M>
  );
}

/** A pill switch whose highlight slides between options. */
export function Segmented<T extends string>({ value, options, onChange, id, size = "md" }: { value: T; options: { id: T; label: string }[]; onChange: (v: T) => void; id: string; size?: "sm" | "md" }) {
  return (
    <div className={`seg seg-${size}`} role="radiogroup">
      {options.map((o) => (
        <button key={o.id} role="radio" aria-checked={value === o.id} className={value === o.id ? "on" : ""} onClick={() => onChange(o.id)}>
          {value === o.id && <motion.span layoutId={`seg-${id}`} className="seg-pill" transition={{ type: "spring", stiffness: 420, damping: 36 }} />}
          <span className="seg-label">{o.label}</span>
        </button>
      ))}
    </div>
  );
}

/** Scroll the window to an element with an eased glide (instant with reduced motion). */
export function glideTo(el: HTMLElement | null, offset = 72) {
  if (!el) return Promise.resolve();
  const target = el.getBoundingClientRect().top + window.scrollY - offset;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    window.scrollTo(0, target);
    return Promise.resolve();
  }
  const distance = Math.abs(target - window.scrollY);
  return new Promise<void>((done) => {
    animate(window.scrollY, target, { duration: Math.min(1.6, 0.7 + distance / 2400), ease: [0.65, 0, 0.35, 1], onUpdate: (v) => window.scrollTo(0, v), onComplete: done });
  });
}

/** A thin bar that runs while the calculator is working. */
export function Working({ on }: { on: boolean }) {
  return (
    <div className="working" aria-hidden>
      <motion.div className="working-bar" initial={false} animate={on ? { opacity: 1, x: ["-100%", "250%"] } : { opacity: 0 }}
        transition={on ? { x: { duration: 1.4, ease: "easeInOut", repeat: Infinity }, opacity: { duration: 0.2 } } : { duration: 0.4 }} />
    </div>
  );
}
