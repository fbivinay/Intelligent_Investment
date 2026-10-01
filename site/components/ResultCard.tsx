"use client";

import type { Projection, Result } from "@/lib/types";
import { pct, rupees, years } from "@/lib/format";
import { Derived, Money } from "./Money";

export function ResultCard({ r, amount, start, end, projection }: { r: Result; amount: number; start: string; end: string; projection?: Projection }) {
  const sold = r.headline === "sold";
  const head = sold ? r.net : r.held_net;
  const growth = sold ? r.growth : r.growth_held;
  const yrs = years(start, end);
  return (
    <article className={r.kind === "product" ? "card product" : "card"} data-option={r.id}>
      <header>
        <h3>{r.name}</h3>
        <span className="plan">{r.plan}</span>
      </header>
      <div className="headline">
        <Money fig={head} title={`${r.name}: ${sold ? "final amount after selling everything" : "final amount if still holding"}`} big />
        <Derived text={`${pct(growth, 2)} a year`} target={{ title: `${r.name}: growth a year`, lines: [
          `Growth a year = (final amount ÷ money invested)^(1 ÷ years) − 1`,
          `= (${rupees(head.value)} ÷ ${rupees(amount)})^(1 ÷ ${yrs.toFixed(2)}) − 1 = ${pct(growth, 2)}`,
          "After every charge and tax, as the final amount is.",
        ] }} />
      </div>
      <dl>
        <dt>{sold ? "If still holding" : "If everything is sold at the end"}</dt>
        <dd><Money fig={sold ? r.held_net : r.net} title={`${r.name}: ${sold ? "if still holding" : "after selling everything"}`} /></dd>
        <dt>Gross end value</dt>
        <dd><Money fig={r.gross_end} title={`${r.name}: gross end value, before any charge or tax`} /></dd>
        <dt>All charges</dt>
        <dd><Money fig={r.charges} title={`${r.name}: all charges`} /></dd>
        <dt>All tax</dt>
        <dd><Money fig={sold ? r.tax : r.held_tax} title={`${r.name}: all income tax caused by this investment`} /></dd>
        <dt>Worst fall</dt>
        <dd><Derived text={pct(r.worst_fall)} target={{ title: `${r.name}: worst fall`, lines: [
          "The largest fall of the value from an earlier high, at the daily close, before tax.",
          r.kind === "product" ? "Your own account: the model's drawdown guard acts on its reference account, so yours can differ." : "Bought and held.",
        ] }} /></dd>
        {projection && (
          <>
            <dt>In {projection.years} years (estimate, after tax)</dt>
            <dd>
              <Derived text={`${rupees(projection.after_tax.p10)} to ${rupees(projection.after_tax.p90)}`} target={{ title: `${r.name}: estimate for ${projection.years} years`, lines: [
                projection.label,
                `${projection.paths} futures made by resampling this option's own past daily returns in blocks of about a month.`,
                `Middle: ${rupees(projection.after_tax.p50)}; 1 in 10 ended below ${rupees(projection.after_tax.p10)}, 1 in 10 above ${rupees(projection.after_tax.p90)}.`,
                `Before tax: ${rupees(projection.p10)} to ${rupees(projection.p90)}. Chance of ending below what you start with: ${pct(projection.chance_of_loss)}.`,
                "The tax is one sale at the end on today's rules and your profile; the final sale's charges are left out.",
              ] }} />
            </dd>
          </>
        )}
      </dl>
      {r.kind === "product" && (
        <details>
          <summary>Charges by kind and tax by year</summary>
          <table className="lines">
            <tbody>
              {r.charges_by_kind.map((c) => (
                <tr key={c.trace}><td>{c.label}</td><td><Money fig={c} title={`${r.name}: ${c.label}`} /></td></tr>
              ))}
              {r.tax_by_fy.map((t) => (
                <tr key={t.trace}><td>Tax for {t.fy}</td><td><Money fig={t} title={`${r.name}: tax for ${t.fy}`} /></td></tr>
              ))}
            </tbody>
          </table>
          {r.strategies && <p className="small">Held in these years: {r.strategies.map((s) => s.split("|")[0]).filter((s, i, a) => a.indexOf(s) === i).join(", ")}. {r.orders} orders.</p>}
        </details>
      )}
      {r.kind !== "product" && (
        <details>
          <summary>Charges</summary>
          <table className="lines">
            <tbody>
              {r.charges_by_kind.map((c) => (
                <tr key={c.trace}><td>{c.label}</td><td><Money fig={c} title={`${r.name}: ${c.label}`} /></td></tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
    </article>
  );
}
