"use client";

// The small moving parts: numbers that count to their value, headlines that rise line by line, a segmented switch, chips, the main button.
import { animate, motion, useReducedMotion } from "motion/react";
import { useEffect, useRef, type ReactNode } from "react";

export const EASE = [0.16, 1, 0.3, 1] as const;          // settling: entrances, numbers
export const SWEEP = [0.76, 0, 0.24, 1] as const;        // deliberate: slides, morphs
export const ENTER = 0.42;                               // when a slide's own entrance starts, as the new slide finishes covering the old

/** A number that counts from where it was (from `from` the first time) to `value`, so a changed result visibly travels. */
export function Counter({ value, format, from = 0, delay = ENTER, duration = 1.4, className }: {
  value: number; format: (n: number) => string; from?: number; delay?: number; duration?: number; className?: string;
}) {
  const el = useRef<HTMLSpanElement>(null);
  const shown = useRef<number | null>(null);
  const fmt = useRef(format);
  fmt.current = format;
  const reduce = useReducedMotion();
  useEffect(() => {
    const node = el.current;
    if (!node) return;
    const start = shown.current ?? from;
    if (reduce || start === value) {
      node.textContent = fmt.current(value);
      shown.current = value;
      return;
    }
    const first = shown.current === null;
    const a = animate(start, value, {
      duration: first ? duration : 0.9, delay: first ? delay : 0, ease: EASE,
      onUpdate: (v) => { node.textContent = fmt.current(v); shown.current = v; },
    });
    return () => a.stop();
  }, [value, reduce]); // eslint-disable-line react-hooks/exhaustive-deps
  return <span ref={el} className={className}>{format(shown.current ?? (reduce ? value : from))}</span>;
}

/** Lines that rise out of a mask one after another. */
export function Rise({ lines, delay = ENTER, className, as: Tag = "h1" }: { lines: ReactNode[]; delay?: number; className?: string; as?: "h1" | "h2" | "p" }) {
  const reduce = useReducedMotion();
  return (
    <Tag className={className}>
      {lines.map((line, i) => (
        <span key={i} className="mask">
          <motion.span className="mask-in" initial={reduce ? false : { y: "108%" }} animate={{ y: "0%" }}
            transition={{ duration: 1.05, ease: EASE, delay: delay + i * 0.09 }}>{line}</motion.span>
        </span>
      ))}
    </Tag>
  );
}

/** A block that settles in after the slide arrives. */
export function Appear({ children, delay = 0, className, y = 18 }: { children: ReactNode; delay?: number; className?: string; y?: number }) {
  const reduce = useReducedMotion();
  return (
    <motion.div className={className} initial={reduce ? false : { opacity: 0, y }} animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.9, ease: EASE, delay: ENTER + delay }}>
      {children}
    </motion.div>
  );
}

export function Segmented<T extends string>({ id, options, value, onChange, label }: {
  id: string; options: { id: T; label: string }[]; value: T; onChange: (v: T) => void; label: string;
}) {
  return (
    <div className="seg" role="radiogroup" aria-label={label}>
      {options.map((o) => (
        <button key={o.id} type="button" role="radio" aria-checked={value === o.id} className={value === o.id ? "seg-b on" : "seg-b"} onClick={() => onChange(o.id)}>
          {value === o.id && <motion.span layoutId={`seg-${id}`} className="seg-pill" transition={{ type: "spring", stiffness: 420, damping: 38 }} />}
          <span className="seg-t">{o.label}</span>
        </button>
      ))}
    </div>
  );
}

export function Chip({ on, color, disabled, onClick, children, title }: {
  on: boolean; color?: string; disabled?: boolean; onClick: () => void; children: ReactNode; title?: string;
}) {
  return (
    <motion.button type="button" className={on ? "chip on" : "chip"} aria-pressed={on} disabled={disabled} onClick={onClick} title={title}
      whileTap={disabled ? undefined : { scale: 0.96 }} layout="position">
      {color && <span className="chip-key" style={{ background: color, opacity: on ? 1 : 0.45 }} />}
      {children}
    </motion.button>
  );
}

export function Key({ color, dot }: { color: string; dot?: boolean }) {
  return <span className={dot ? "key dot" : "key"} style={{ background: color }} aria-hidden />;
}

export function Arrow({ dir = "down" }: { dir?: "down" | "right" | "up" }) {
  const r = { down: 0, right: -90, up: 180 }[dir];
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden style={{ transform: `rotate(${r}deg)` }}>
      <path d="M9 3.5v11M4.5 10 9 14.5 13.5 10" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Primary({ children, onClick, dir = "right" }: { children: ReactNode; onClick: () => void; dir?: "down" | "right" }) {
  return (
    <motion.button type="button" className="primary" onClick={onClick} whileHover="hover" whileTap={{ scale: 0.97 }}>
      <span>{children}</span>
      <motion.span className="primary-arrow" variants={{ hover: dir === "right" ? { x: 4 } : { y: 3 } }} transition={{ type: "spring", stiffness: 380, damping: 18 }}>
        <Arrow dir={dir} />
      </motion.span>
    </motion.button>
  );
}
