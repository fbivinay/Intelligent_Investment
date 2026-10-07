"use client";

// The presentation: three sections of full-screen slides. A slide is replaced, never scrolled to: the next one wipes up over it (down within a
// section, sideways between sections) while the old one recedes. Wheel, arrow keys and the next button move one slide per gesture.
import { AnimatePresence, motion, MotionConfig, useReducedMotion, type Variants } from "motion/react";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { DeckCtx, type SectionId, type SlideDef } from "@/lib/deck";
import { useData } from "@/lib/data";
import { EVIDENCE, EvidenceRail } from "./slides/evidence";
import { OVERVIEW } from "./slides/overview";
import { PERFORMANCE } from "./slides/performance";
import { Arrow, SWEEP } from "./ui";

const SECTIONS: { id: SectionId; name: string; path: string; slides: SlideDef[] }[] = [
  { id: "overview", name: "Overview", path: "/", slides: OVERVIEW },
  { id: "performance", name: "Performance", path: "/performance", slides: PERFORMANCE },
  { id: "evidence", name: "Evidence", path: "/evidence", slides: EVIDENCE },
];
const LOCK_MS = 950;

type Dir = { axis: "x" | "y"; sign: 1 | -1 };
const clipFrom = (d: Dir) =>
  d.axis === "y" ? (d.sign > 0 ? "inset(100% 0% 0% 0%)" : "inset(0% 0% 100% 0%)") : (d.sign > 0 ? "inset(0% 0% 0% 100%)" : "inset(0% 100% 0% 0%)");
const along = (d: Dir, by: number) => ({ x: d.axis === "x" ? `${by}%` : "0%", y: d.axis === "y" ? `${by}%` : "0%" });
// Both sets rest on the same style, so the server's first render matches the browser's whichever set the viewer's motion setting picks.
const REST = { clipPath: "inset(0% 0% 0% 0%)", x: "0%", y: "0%", scale: 1, opacity: 1, borderRadius: 0, zIndex: 2 };
const MOVE: Variants = {
  enter: (d: Dir) => ({ ...REST, clipPath: clipFrom(d), ...along(d, d.sign * 9) }),
  center: { ...REST, transition: { duration: 1.05, ease: SWEEP } },
  exit: (d: Dir) => ({ ...REST, ...along(d, -d.sign * 6), scale: 0.9, opacity: 0.5, borderRadius: 28, zIndex: 1, transition: { duration: 1.05, ease: SWEEP } }),
};
const FADE: Variants = {
  enter: { ...REST, opacity: 0 },
  center: { ...REST, transition: { duration: 0.3 } },
  exit: { ...REST, opacity: 0, zIndex: 1, transition: { duration: 0.2 } },
};

const sectionOf = (path: string) => Math.max(0, SECTIONS.findIndex((s) => s.path === path));

export function Deck() {
  const pathname = usePathname();
  const router = useRouter();
  const reduce = useReducedMotion();
  const { failed } = useData();
  const [pos, setPos] = useState<{ s: number; i: number; dir: Dir }>(() => ({ s: sectionOf(pathname), i: 0, dir: { axis: "y", sign: 1 } }));
  const [moved, setMoved] = useState(false);
  const [mounted, setMounted] = useState(false);   // defer motion to avoid SSR hydration mismatch
  const lockUntil = useRef(0);
  const posRef = useRef(pos);
  posRef.current = pos;

  useEffect(() => { setMounted(true); }, []);

  useEffect(() => {
    const s = SECTIONS.findIndex((x) => x.path === pathname);
    if (s >= 0 && s !== posRef.current.s) setPos((p) => ({ s, i: 0, dir: { axis: "x", sign: s > p.s ? 1 : -1 } }));
  }, [pathname]);

  const go = useCallback((section: SectionId | number, slide = 0) => {
    const s = typeof section === "number" ? section : SECTIONS.findIndex((x) => x.id === section);
    const p = posRef.current;
    const i = Math.max(0, Math.min(slide, SECTIONS[s].slides.length - 1));
    if ((p.s === s && p.i === i) || performance.now() < lockUntil.current) return;
    lockUntil.current = performance.now() + LOCK_MS;
    const dir: Dir = p.s === s ? { axis: "y", sign: i > p.i ? 1 : -1 } : { axis: "x", sign: s > p.s ? 1 : -1 };
    setPos({ s, i, dir });
    setMoved(true);
    if (s !== p.s) router.push(SECTIONS[s].path, { scroll: false });
  }, [router]);

  const next = useCallback(() => {
    const p = posRef.current;
    if (p.i < SECTIONS[p.s].slides.length - 1) go(p.s, p.i + 1);
    else go((p.s + 1) % SECTIONS.length, 0);
  }, [go]);

  const prev = useCallback(() => {
    const p = posRef.current;
    if (p.i > 0) go(p.s, p.i - 1);
    else if (p.s > 0) go(p.s - 1, SECTIONS[p.s - 1].slides.length - 1);
  }, [go]);

  useEffect(() => {
    const typing = (el: EventTarget | null) => el instanceof HTMLElement && (el.isContentEditable || /^(INPUT|SELECT|TEXTAREA)$/.test(el.tagName));
    const pressable = (el: EventTarget | null) => el instanceof HTMLElement && /^(BUTTON|A|SUMMARY)$/.test(el.tagName);
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey || typing(e.target)) return;
      if ((e.key === " " || e.key === "Enter") && pressable(e.target)) return;          // Space and Enter press the focused button
      if (["ArrowDown", "PageDown", "ArrowRight"].includes(e.key) || (e.key === " " && !e.shiftKey)) { e.preventDefault(); next(); }
      else if (["ArrowUp", "PageUp", "ArrowLeft"].includes(e.key) || (e.key === " " && e.shiftKey)) { e.preventDefault(); prev(); }
    };
    // One slide per gesture: a trackpad's momentum keeps sending small wheel events, so a gesture ends only after a short quiet spell.
    let acc = 0, last = 0, used = false;
    const onWheel = (e: WheelEvent) => {
      const now = performance.now();
      if (now - last > 220) { acc = 0; used = false; }
      last = now;
      const dy = e.deltaMode === 1 ? e.deltaY * 16 : e.deltaY;
      const box = (e.target as HTMLElement).closest?.("[data-scroll]") as HTMLElement | null;
      if (box && (dy > 0 ? box.scrollTop + box.clientHeight < box.scrollHeight - 1 : box.scrollTop > 0)) return;
      if (used || now < lockUntil.current) return;
      acc += dy;
      if (Math.abs(acc) > 40) { used = true; acc > 0 ? next() : prev(); }
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("wheel", onWheel, { passive: true });
    return () => { window.removeEventListener("keydown", onKey); window.removeEventListener("wheel", onWheel); };
  }, [next, prev]);

  const sec = SECTIONS[pos.s];
  const def = sec.slides[pos.i];
  const atEnd = pos.i === sec.slides.length - 1;
  const lastOfAll = atEnd && pos.s === SECTIONS.length - 1;
  const nextLabel = lastOfAll ? "Back to the start" : atEnd ? SECTIONS[pos.s + 1].name : sec.slides[pos.i + 1].title;
  const ctx = useMemo(() => ({ section: pos.s, slide: pos.i, go, next, prev }), [pos.s, pos.i, go, next, prev]);
  const Slide = def.Slide;

  return (
    <DeckCtx.Provider value={ctx}>
      <MotionConfig reducedMotion="user">
        <div className="deck">
          <header className="top">
            <a className="brand" href="/" onClick={(e) => { e.preventDefault(); go(0, 0); }}>
              <svg width="30" height="30" viewBox="0 0 22 22" aria-hidden><rect width="22" height="22" rx="6" fill="var(--model)" /><path d="M5 15.5 9.2 11l3 2.6L17 7" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
              <span>Intelligent Investment</span>
            </a>
            <nav className="tabs" aria-label="Sections">
              {SECTIONS.map((s, k) => (
                <a key={s.id} href={s.path} className={k === pos.s ? "tab on" : "tab"} aria-current={k === pos.s ? "page" : undefined}
                  onClick={(e) => { e.preventDefault(); go(k, 0); }}>
                  {s.name}
                  {k === pos.s && (
                    <motion.span layoutId="tab-line" className="tab-line" transition={{ type: "spring", stiffness: 300, damping: 34 }}>
                      <motion.span className="tab-fill" initial={false} animate={{ scaleX: (pos.i + 1) / s.slides.length }} transition={{ duration: 0.9, ease: SWEEP }} />
                    </motion.span>
                  )}
                </a>
              ))}
            </nav>
            <span className="top-note">Past results, not a promise. Not investment advice.</span>
          </header>

          <main className="stage">
            {failed ? (
              <div className="failed" role="alert"><p>{failed}</p></div>
            ) : !mounted ? (
              <section className={`slide s-${sec.id}`} aria-roledescription="slide" aria-label={`${def.title}, ${pos.i + 1} of ${sec.slides.length}`}>
                <Slide />
              </section>
            ) : (
              <AnimatePresence initial={false} custom={pos.dir}>
                <motion.section key={`${pos.s}-${pos.i}`} className={`slide s-${sec.id}`} custom={pos.dir} variants={reduce ? FADE : MOVE} initial="enter" animate="center"
                  exit="exit" aria-roledescription="slide" aria-label={`${def.title}, ${pos.i + 1} of ${sec.slides.length}`}>
                  <Slide />
                </motion.section>
              </AnimatePresence>
            )}
            <AnimatePresence>{sec.id === "evidence" && <EvidenceRail key="rail" slide={pos.i} />}</AnimatePresence>
          </main>

          <footer className="bottom">
            <div className="progress">
              <button type="button" className="step-btn" onClick={prev} disabled={pos.s === 0 && pos.i === 0} aria-label="Previous slide"><Arrow dir="up" /></button>
              <div className="dots" role="tablist" aria-label={`${sec.name} slides`}>
                {sec.slides.map((sl, k) => (
                  <button key={sl.id} type="button" role="tab" aria-selected={k === pos.i} aria-label={sl.title} className={k === pos.i ? "dot on" : "dot"} onClick={() => go(pos.s, k)}>
                    {k === pos.i && <motion.span layoutId="dot-on" className="dot-fill" transition={{ type: "spring", stiffness: 380, damping: 32 }} />}
                  </button>
                ))}
              </div>
              <AnimatePresence mode="wait" initial={false}>
                <motion.span key={def.id} className="here" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.3 }}>
                  <b>{String(pos.i + 1).padStart(2, "0")}</b> {def.title}
                </motion.span>
              </AnimatePresence>
            </div>
            <div className="next-wrap">
              {!moved && <motion.span className="hint" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 2.6, duration: 0.8 }}>Scroll or press ↓</motion.span>}
              <AnimatePresence mode="wait" initial={false}>
                <motion.span key={nextLabel} className="next-label" initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -8 }} transition={{ duration: 0.3 }}>
                  {nextLabel}
                </motion.span>
              </AnimatePresence>
              <motion.button type="button" className="next" onClick={next} aria-label={`Next: ${nextLabel}`} whileHover={{ scale: 1.06 }} whileTap={{ scale: 0.94 }}>
                <Arrow dir={lastOfAll ? "up" : atEnd ? "right" : "down"} />
              </motion.button>
            </div>
          </footer>
        </div>
      </MotionConfig>
    </DeckCtx.Provider>
  );
}
