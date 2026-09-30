"""Static HTML report: the waterfall, and a trace under every number (native <details>). A derivation that several rows share is
written out once and linked from the others; a few lines of script open the closed rows above a link's target."""
from __future__ import annotations

import argparse
import json
from datetime import date
from decimal import Decimal
from html import escape
from pathlib import Path

from data.fetch_yahoo import verify
from engine.rules import Rules
from engine.scenario import Result, buy_and_hold
from engine.tax import TaxProfile
from engine.trace import Node, flags

ROOT = Path(__file__).resolve().parents[1]
CSS = """
body{font:16px/1.5 system-ui,sans-serif;max-width:52rem;margin:2rem auto;padding:0 1rem;color:#1a1a1a;background:#fff}
@media (prefers-color-scheme:dark){body{color:#eee;background:#151515}}
table{border-collapse:collapse;width:100%}td,th{padding:.4rem .5rem;border-bottom:1px solid #8884;text-align:left}
td.n{text-align:right;font-variant-numeric:tabular-nums}
details{margin:.15rem 0 .15rem 1rem}summary{cursor:pointer}
details.root{margin:0}details.root>summary{display:inline;list-style:none;color:#06c}
.f{color:#888;font-size:.9rem}.rule{font-size:.85rem}.assumed,.secondary{color:#b45309}
a.jump{font-size:.85rem;margin-left:.5rem}
"""
JS = ("document.addEventListener('click',function(e){var a=e.target.closest('a.jump');if(!a)return;"
      "var t=document.getElementById(a.getAttribute('href').slice(1));"
      "for(var p=t;p;p=p.parentElement){if(p.tagName==='DETAILS')p.open=true}});")


def exact(v: Decimal) -> str:
    return format(v, "f")


def money(v: Decimal) -> str:
    return f"₹{v:,.2f}"


def why(r) -> str:
    """The rule file's own words on why a row is only assumed or secondary; official rows need none."""
    return f'<div class="f">why: {escape(r.note)}</div>' if r.note and r.confidence != "primary" else ""


class Page:
    """What has been written out so far: the same derivation (same label, value, note, rules and inputs) is written once."""

    def __init__(self):
        self.ids: dict[tuple, int] = {}   # structural signature -> number
        self.memo: dict[int, int] = {}    # id(node) -> number
        self.written: set[int] = set()

    def number(self, n: Node) -> int:
        k = self.memo.get(id(n))
        if k is None:
            sig = (n.label, n.value, n.op, n.note, tuple((r.rule_id, r.valid_from, r.note) for r in n.rules),
                   tuple(self.number(i) for i in n.inputs))
            k = self.ids.setdefault(sig, len(self.ids))
            self.memo[id(n)] = k
        return k


def tree(n: Node, page: Page) -> str:
    k = page.number(n)
    if k in page.written:
        return (f'<details class="ref"><summary>{escape(n.label)} = {exact(n.value)}'
                f'<a class="jump" href="#n{k}">same derivation as above</a></summary></details>')
    page.written.add(k)
    rules = "".join(
        f'<li class="rule {r.confidence}">rule {escape(r.rule_id)} valid from {r.valid_from}: '
        f"{escape(r.source)} (verified {r.verified_on}, {r.confidence}){why(r)}</li>" for r in n.rules)
    note = f'<div class="f">{escape(n.note)}</div>' if n.note else ""
    body = f'<div class="f">{escape(n.formula)}</div>{note}<ul>{rules}</ul>' + "".join(tree(i, page) for i in n.inputs)
    return f'<details id="n{k}"><summary>{escape(n.label)} = {exact(n.value)}</summary>{body}</details>'


def row(label: str, n: Node, page: Page) -> str:
    return (f'<tr><td>{escape(label)}</td><td class="n">{money(n.value)}</td><td>'
            f'<details class="root"><summary>ⓘ</summary>{tree(n, page)}</details></td></tr>')


def section(heading: str, r: Result, page: Page) -> str:
    w = r.waterfall
    rows = [row("Money invested", w["initial"], page), row("Gross profit (price gain + dividends)", w["gross_profit"], page),
            row("Gross end value, before any charge or tax", w["gross_end"], page),
            row("Charges on the buy", w["buy_charges"], page), row("Charges on the sale", w["sale_charges"], page),
            row("Account opening fee", w["account_opening"], page), row("Demat account fees", w["amc"], page),
            row("All charges", w["charges"], page),
            row("Income tax caused by this investment", w["tax"], page), row("Final amount", w["net"], page)]
    return (f"<h2>{escape(heading)}</h2><p>{r.units} units bought on {r.bought_on}, "
            f"{'sold' if r.sold else 'valued, not sold'} on {r.ended_on}. Click ⓘ to see how any number was made.</p>"
            f"<table><tr><th>Step</th><th>Amount</th><th></th></tr>{''.join(rows)}</table>")


def render_html(title: str, sections: list[tuple[str, Result]], notes: list[str]) -> str:
    seen, fl = set(), []
    for _, r in sections:
        for f in flags(r.net):
            if (f.rule_id, f.valid_from) not in seen:
                seen.add((f.rule_id, f.valid_from))
                fl.append(f'<li class="{f.confidence}">{escape(f.rule_id)} from {f.valid_from} is {f.confidence}: '
                          f"{escape(f.source)}{why(f)}</li>")
    ns = "".join(f"<li>{escape(n)}</li>" for n in notes)
    page = Page()
    return (f"<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
            f"<title>{escape(title)}</title><style>{CSS}</style><h1>{escape(title)}</h1>"
            f"{''.join(section(h, r, page) for h, r in sections)}"
            f"<h2>Rules that are not backed by an official source</h2>"
            f"<p class='f'>Only rules that can move these numbers are listed; a rule that was read but decided nothing (the other side "
            f"of a comparison, a rate on a zero amount) is not, and still shows inside the derivations.</p>"
            f"<ul>{''.join(fl) or '<li>None used.</li>'}</ul>"
            f"<h2>Notes and known gaps</h2><ul>{ns}</ul><script>{JS}</script></html>")


def main(argv=None) -> Path:
    from data.fetch_yahoo import load_bars, load_dividends
    ap = argparse.ArgumentParser(description="Buy-and-hold report with every number traced")
    ap.add_argument("--symbol", default="NIFTYBEES")
    ap.add_argument("--amount", default="100000")
    ap.add_argument("--start", default="2014-01-01")
    ap.add_argument("--end", default=date.today().isoformat())
    ap.add_argument("--income", default="1500000", help="other taxable income per year, after deductions")
    ap.add_argument("--regime", default="new", choices=["old", "new"])
    ap.add_argument("--rules", default=str(ROOT / "rules"))
    ap.add_argument("--data", default=str(ROOT / "data" / "processed"))
    ap.add_argument("--out", default=str(ROOT / "out" / "checkpoint1.html"))
    a = ap.parse_args(argv)
    manifest_path = Path(a.data).parent / "manifest.json"
    if not manifest_path.exists():
        raise ValueError(f"no data manifest at {manifest_path}: refusing to report on data that cannot be checked")
    problems = verify(manifest_path.parent)
    if problems:
        raise ValueError("the data files do not match their manifest: " + "; ".join(problems))
    adjusted = [f"Prices are adjusted for {d}: {why}" for d, why in
                json.loads(manifest_path.read_text(encoding="utf-8")).get(f"{a.symbol}.csv", {}).get("adjusted", {}).items()]
    rules = Rules.load(Path(a.rules))
    bars = load_bars(Path(a.data) / f"{a.symbol}.csv")
    divs = load_dividends(Path(a.data) / f"{a.symbol}_dividends.csv")
    kw = dict(instrument=a.symbol, instrument_class="etf_equity", bars=bars, dividends=divs,
              amount=Decimal(a.amount), start=date.fromisoformat(a.start), end=date.fromisoformat(a.end),
              profile=TaxProfile(a.regime, Decimal(a.income)))
    sold, held = buy_and_hold(rules, sell_at_end=True, **kw), buy_and_hold(rules, sell_at_end=False, **kw)
    notes = [
        f"Prices: Yahoo Finance daily series for {a.symbol}, frozen in data/processed (see data/manifest.json). "
        "Unofficial source; the data layer replaces it later.",
        *adjusted,
        f"Dividends in the source: {len(divs)}. If this is 0 the source has no dividend records for this ETF, "
        "so the result understates the true return.",
        "Buys and sells at the day's close. The real fill model (next open plus slippage) comes with the strategy engine.",
        "Cash earns nothing and dividends are kept as cash, not reinvested. Whole units only.",
        "The demat account is taken as opened on the purchase day for this investment: its opening fee and one full yearly "
        "AMC for each financial year touched (the last one in full) are charged to it. A user with an older account would pay neither.",
        "Tax for each financial year is treated as paid from cash at year end. Advance-tax interest is ignored.",
        f"Tax profile: {a.regime} regime, other taxable income {money(Decimal(a.income))} a year, no losses brought forward.",
        "Not modelled: deductions (other income is taken after them), age-based slabs and the higher basic exemption for women in "
        "FY2010-11 (Rs 1.9 lakh), alternative minimum tax, interest on late or advance tax, non-residents. Every assumed rule and every "
        "other modelling limit is listed in docs/verification/assumed-rows.md.",
    ]
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(f"{a.symbol}: {money(Decimal(a.amount))} from {a.start} to {a.end}",
                               [("If sold on the end date (tax paid)", sold), ("If still holding (tax deferred)", held)],
                               notes), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(main())
