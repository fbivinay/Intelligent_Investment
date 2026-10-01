"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import type { InfoTarget, TraceNode } from "@/lib/types";
import { TraceTree } from "./TraceTree";

type Ctx = { open: (t: InfoTarget) => void };
const InfoCtx = createContext<Ctx>({ open: () => {} });

/** Holds the traces of the current answer and the one ⓘ panel that shows them. */
export function InfoProvider({ traces, children }: { traces: Record<string, TraceNode>; children: ReactNode }) {
  const [target, setTarget] = useState<InfoTarget | null>(null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setTarget(null);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  const tree = target && "trace" in target ? traces[target.trace] : undefined;
  return (
    <InfoCtx.Provider value={{ open: setTarget }}>
      {children}
      {target && (
        <div className="modal-back" onClick={() => setTarget(null)}>
          <div className="modal" role="dialog" aria-modal="true" aria-label={target.title} onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <h2>{target.title}</h2>
              <button className="close" onClick={() => setTarget(null)} aria-label="Close">×</button>
            </div>
            {"lines" in target ? (
              <ul className="explain">{target.lines.map((l, i) => <li key={i}>{l}</li>)}</ul>
            ) : tree ? (
              <TraceTree node={tree} />
            ) : (
              <p>This trace is not in the answer.</p>
            )}
          </div>
        </div>
      )}
    </InfoCtx.Provider>
  );
}

export function InfoButton({ target, label }: { target: InfoTarget; label?: string }) {
  const { open } = useContext(InfoCtx);
  return (
    <button className="info" data-info={"trace" in target ? target.trace : "explain"} aria-label={`How ${label ?? target.title} is worked out`}
      onClick={() => open(target)}>
      ⓘ
    </button>
  );
}
