"use client";

import { createContext, useContext, type ComponentType } from "react";

export type SlideDef = { id: string; title: string; Slide: ComponentType };
export type SectionId = "overview" | "performance" | "evidence";

type Deck = {
  section: number;
  slide: number;
  go: (section: SectionId | number, slide?: number) => void;
  next: () => void;
  prev: () => void;
};

export const DeckCtx = createContext<Deck | null>(null);

export function useDeck() {
  const d = useContext(DeckCtx);
  if (!d) throw new Error("useDeck outside Deck");
  return d;
}
