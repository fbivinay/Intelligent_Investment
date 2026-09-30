"""Writes docs/verification/assumed-rows.md: every rule row that is not backed by an official text, with its note and what it
could change. Run from the repo root:  python docs/verification/assumed_rows.py

The facts (confidence, rule, dates, source, note) are read from rules/*.toml. The "could change" sentences are written by hand
below, one per group of rows; a row with no matching group makes the script stop, so a new assumed row cannot go unexplained."""
import sys
import tomllib
from pathlib import Path

RULES, OUT = Path("rules"), Path("docs/verification/assumed-rows.md")

# (rule id prefix, material?, what this could change). Material: could move a result by over 0.01% of turnover or 0.5% of tax.
GROUPS = [
    ("charges.clearing[segment=delivery]", False, "A real delivery clearing charge would add well under 0.001% of turnover."),
    ("charges.clearing[segment=futures]", False, "The futures clearing charge is 0.0005% of turnover (Rs 5 on Rs 10 lakh); an older value could differ by less than that."),
    ("charges.dp_depository", False, "The depository part of a sale is about Rs 5.5 + GST; a different old tariff moves a Rs 1 lakh sale by under 0.005% (a Rs 10,000 sale by about 0.02%)."),
    ("charges.exchange_txn", False, "NSE transaction charge (0.00325% delivery, 0.0019% futures of turnover) is held back to 2010; an older rate could differ by under 0.002% of turnover."),
    ("charges.gst", False, "The rates are statutory; only the pre-2017 taxed base is assumed, worth under 0.001% of turnover. The 2023 SEBI-fee base is Rs 10 per crore."),
    ("charges.ipft", False, "Rs 0.0001 per lakh of turnover: immaterial."),
    ("charges.sebi", False, "Rs 20 or Rs 15 per crore (0.0002% of turnover); the old value or the cut date is worth under 0.0005% of turnover."),
    ("charges.stamp[segment=mf", False, "Stamp duty on fund purchases is 0.005% from 2020-07-01 and none before: under 0.01% of turnover."),
    ("charges.stamp[", True, "Before 2020-07-01 stamp duty depends on the state. Maharashtra (delivery 0.01%, futures 0.002% of the purchase value) is used; another state could differ by up to about 0.01% of each delivery purchase. Ask the user for their state."),
    ("charges.stt[", True, "0.125% a side on Nifty ETF units is used for 2010 to mid-2012 from one memorandum sentence about March 2012; if it had been 0.1%, 0.025% of turnover a side would be overcharged. Low doubt."),
    ("fyers.account_opening", False, "Fyers says it charged nothing to open an account before 2020; a Rs 400 + GST fee would be 0.47% of Rs 1 lakh once. Low doubt."),
    ("fyers.amc[cohort=legacy] 2010", True, "Rs 400 + GST a year (Rs 472, 0.47% of Rs 1 lakh a year) is charged on accounts opened before 2019-11-15, from 2010 onward, though it was seen on Fyers pages only from 2018-09."),
    ("fyers.amc", True, "Which yearly AMC an account pays depends on when it was opened; dates inferred from archived pages can be off by up to two months, so a new account could pay Rs 354 a year (0.35% of Rs 1 lakh) that it should not, or the other way round."),
    ("fyers.brokerage[product=delivery] 2010", True, "Fyers did not exist before 2015; its earliest schedule (0.1% a leg) stands in for whatever broker a person would have used then. The true cost could differ by up to about 0.1% of turnover a leg."),
    ("fyers.brokerage[product=futures] 2010", True, "Fyers did not exist before 2015; its earliest schedule (0.01% a leg) stands in for whatever broker a person would have used then. The true cost could differ by about 0.01% of turnover a leg."),
    ("fyers.brokerage", False, "Schedule dates are inferred from archived copies and can be off by weeks or months; only orders placed in such a gap are affected, and one could be off by up to about 0.1% of its value."),
    ("fyers.dp[] 2010", True, "Rs 20 + Rs 5.5 + GST (about Rs 30 a sale, 0.03% of a Rs 1 lakh sale) is used for all years before 2018-09, when no page was archived."),
    ("fyers.dp", False, "Dates of the fee changes (Rs 20, then Rs 10 + 5.5, then Rs 7 + 5.5) are inferred from archived copies; only a sale in the gap is affected, by a few rupees."),
    ("tax.audit", True, "The audit fee (Rs 25,000 a year, all-in) applies only to a futures trader whose turnover is above the limit; the true fee could be Rs 10,000 to 35,000 different, and the higher limit assumes cash receipts and payments are each within 5%. No effect on ETF or fund investors."),
    ("tax.capital_gains", True, "For sales from 2026-04-01 (Income-tax Act 2025) rates are read from its text but the 12-month holding period, the 2018 grandfathering and the deemed short-term rule are assumed unchanged; if one changed, a gain could move between short term and long term (up to 7.5 points of rate). Low doubt."),
    ("tax.cii", False, "A wrong index value by 1 would shift an indexed cost by about 0.3% and the tax by under 0.1% of cost; only sales up to 2024-07-22 use it."),
    ("tax.conventions[name=setoff_order]", True, "The order in which losses are set off can change the tax by the difference between two rates (up to 7.5% of the loss) for an investor with losses and gains at different rates."),
    ("tax.conventions[name=shortfall_order]", True, "Where the unused basic exemption is applied first can change the tax by up to 12.5% of the exemption used (Rs 15,625 in the example of S69) for a low-income investor with more than one kind of long-term gain."),
    ("tax.conventions[name=business_loss_setoff]", True, "A futures loss is set off only against interest and income taxed at slab rates, never against the other income given (it may be salary) or gains at special rates; a user whose other income is not salary gets the set-off a year later, and a user with special-rate gains in a loss year pays up to 20% more on the gain the loss could have covered."),
    ("tax.conventions[name=marginal_relief_order]", True, "The law does not say which income the part above a surcharge threshold is taken from; the engine takes slab income first, then the lowest-rate gains (the least relief). Matters only just above a threshold when most of the income is gains; the relief can differ by the gap between two rates on the excess."),
    ("tax.lt_exemption", True, "In FY2024-25 the order in which the Rs 1.25 lakh exemption is used against gains before and after 2024-07-23 can change the tax by up to Rs 3,125 for an investor with long-term gains on both sides of that date."),
    ("tax.rebate_87a", True, "For FY2023-24 and FY2024-25 the department's reading (no rebate on tax at special rates) is used; if the ITAT view holds, an investor with total income up to Rs 7 lakh and short-term equity gains pays up to Rs 25,000 less."),
]

NOT_MODELLED = [
    "Fyers Prime (a paid yearly plan with lower brokerage) and women or mutual-fund-ISIN discounts on depository charges.",
    "Total income is not rounded to the nearest Rs 10 (section 288A): moves tax by at most Rs 1.5.",
    "ISSL demat holders who may have paid the old AMC until January 2021; the Rs 225 first-year AMC of accounts opened from 2020-12-01.",
    "A business loss is kept only if the return is filed on time (section 80).",
    "The audit route of section 44AB(e) and 44AD (a trader with presumptive-tax history and profit under 6% may need an audit below the turnover limit).",
    "The women's higher basic exemption of FY2010-11 (Rs 1.9 lakh).",
    "Alternative minimum tax, advance-tax interest (234B, 234C), deductions (other income is taken after deductions), non-residents and non-individuals.",
]


def load():
    rows = []
    for path in sorted(RULES.rglob("*.toml")):
        d = tomllib.loads(path.read_text(encoding="utf-8"))
        table = ".".join(path.relative_to(RULES).with_suffix("").parts)
        keys = d.get("meta", {}).get("keys", [])
        for r in d["row"]:
            rid = f"{table}[{','.join(f'{k}={r[k]}' for k in keys)}]"
            rows.append(dict(rid=rid, frm=r["from"], conf=r["confidence"], source=r["source"], note=str(r.get("note", "")).strip()))
    return rows


def group_of(row):
    for prefix, material, text in GROUPS:
        head, _, year = prefix.partition(" ")  # "fyers.dp[] 2010" means only the rows from 2010
        if row["rid"].startswith(head) and (not year or str(row["frm"]).startswith(year)):
            return material, text
    sys.exit(f"no explanation written for {row['rid']} from {row['frm']}: add a group in GROUPS")


def main():
    rows = load()
    weak = sorted((r for r in rows if r["conf"] != "primary"), key=lambda r: (r["conf"], r["rid"], str(r["frm"])))
    flags = [(r, *group_of(r)) for r in weak]
    counts = {c: sum(r["conf"] == c for r in rows) for c in ("primary", "secondary", "assumed")}
    out = ["# Rules not backed by an official source", "",
           f"Written by `python docs/verification/assumed_rows.py` from `rules/*.toml`. Rule rows in total: {len(rows)}; "
           f"primary (official text) {counts['primary']}, secondary (an archived copy or non-official sources that agree) {counts['secondary']}, "
           f"assumed (a stand-in, said in the note) {counts['assumed']}. Rows below: {len(weak)}.", "",
           "MATERIAL means the row could move a result by more than 0.01% of turnover or 0.5% of tax if it is wrong. "
           "Rows with a different assumed *fee or convention* are listed with the sources for their limits, which are official.", "",
           "## For you to accept or fix", "",
           "1. **Stamp duty before July 2020.** Which state? Maharashtra is used (delivery 0.01%, futures 0.002% of the purchase value).",
           "2. **Conventions.** Do you accept: losses set off in the coded order (`setoff_order`); the unused basic exemption applied to the "
           "highest-rate gain first, after the yearly exemption (`shortfall_order`); a futures loss set off against slab income only "
           "(`business_loss_setoff`); the income above a surcharge threshold taken from slab income first, then the lowest-rate gains (`marginal_relief_order`)?",
           "3. **Fyers before it existed.** Brokerage and demat charges from 2010 to 2015 use Fyers' earliest known schedule, and the "
           "old AMC (Rs 400 + GST) is used for accounts opened before 2019-11-15. Accept, or name the broker to copy?",
           "4. **Futures audit.** Fee Rs 25,000 a year, and the higher limit (cash receipts and payments each within 5%). Accept?", "",
           "## Material rows", ""]
    grouped = {}
    for r, mat, text in flags:
        if mat:
            grouped.setdefault(text, []).append(r)
    for text, rs in grouped.items():
        names = sorted({r["conf"] for r in rs})
        ids = ", ".join(f"`{r['rid']}` from {r['frm']}" for r in rs)
        out.append(f"- **{'/'.join(names)}**, {len(rs)} row{'s' if len(rs) > 1 else ''} ({ids}): {text}")
    out += ["", "## All rows, one line each (assumed first)", ""]
    for r, mat, text in flags:
        out.append(f"- **{r['conf']}**{' MATERIAL' if mat else ''} `{r['rid']}` from {r['frm']} - source: {r['source']} - note: "
                   f"{r['note'] or 'none'} - could change: {text}")
    out += ["", "## Modelling limits that are not rows", ""] + [f"- {x}" for x in NOT_MODELLED]
    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"{len(weak)} rows written to {OUT}; {sum(m for _, m, _ in flags)} material")


if __name__ == "__main__":
    main()
