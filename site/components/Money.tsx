"use client";

import type { Fig, InfoTarget } from "@/lib/types";
import { rupees } from "@/lib/format";
import { InfoButton } from "./Info";

/** A rupee figure from the engine, with the ⓘ that opens its trace. */
export function Money({ fig, title, big }: { fig: Fig; title: string; big?: boolean }) {
  return (
    <span className={big ? "money big" : "money"} data-money={fig.exact} title={`exactly Rs ${fig.exact}`}>
      {rupees(fig.value)}
      <InfoButton target={{ trace: fig.trace, title }} label={title} />
    </span>
  );
}

/** A number worked out here (a percentage, an estimate), with the ⓘ that explains how. */
export function Derived({ text, target }: { text: string; target: InfoTarget }) {
  return (
    <span className="money" data-money="derived">
      {text}
      <InfoButton target={target} />
    </span>
  );
}
