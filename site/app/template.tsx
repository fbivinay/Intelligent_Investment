"use client";

import { motion, useReducedMotion } from "motion/react";
import { EASE } from "@/components/motion";

// Re-mounted on every navigation, so each page settles in rather than cutting in.
export default function PageIn({ children }: { children: React.ReactNode }) {
  const reduce = useReducedMotion();
  return (
    <motion.main initial={reduce ? false : { opacity: 0, y: 14, filter: "blur(4px)" }} animate={{ opacity: 1, y: 0, filter: "blur(0px)" }} transition={{ duration: 0.7, ease: EASE }}>
      {children}
    </motion.main>
  );
}
