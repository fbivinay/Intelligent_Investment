# Rules and Costs Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sub-project 1 of the India algo system: an exact, traced engine that prices every Indian tax and every Fyers, exchange and statutory charge by the rules in force on each transaction's date, verified by hand-worked golden cases, ending in a first visible result: ₹1 lakh in a Nifty ETF, after every cost and tax.

**Architecture:** Rules are dated TOML tables under `rules/`, read by one loader that rejects gaps, overlaps and unsourced rows. Every number is a `Node` whose value is derived from its inputs, so its ⓘ trace cannot drift from the result. Charges, FIFO lots and per-financial-year tax are separate modules that read rules only through the loader. Golden cases, typed by hand from the sources, must probe both sides of every rule change.

**Tech Stack:** Python 3.11 or newer (3.13.1 is installed), standard library only inside `engine/`, pytest 8 for tests, `urllib` for one price download.

**Spec:** `docs/superpowers/specs/2026-09-29-india-algo-system-design.md`

**How this plan was prepared:** all code below was first written and run against made-up round-number rules (over 100 tests passing) in a scratch folder, replayed task by task in a fresh folder, then pasted here. The real rates do not exist yet: Tasks 5 to 8 and 14 research them. The order is deliberate: the user asked for research before any calculation.

**Commits:** every task ends with a commit on branch `v3/rules-engine`. End each commit message with the attribution lines the harness specifies. Nothing is pushed.

## Plan at a glance

| # | Task | Deliverable | Done when |
|---|---|---|---|
| 1 | Branch and skeleton | branch, `pytest.ini`, folders, `.gitignore` fix | pytest runs |
| 2 | Money and trace | `engine/money.py`, `engine/trace.py` | trace tests pass |
| 3 | Rule loader | `engine/rules.py`, sources check | loader tests pass |
| 4 | Golden harness | `tests/golden_runner.py`, boundary gate, case skeleton printer | harness tests pass |
| 5 | Research: Fyers fees | `rules/fyers/*.toml`, cases | loader and boundary gate green |
| 6 | Research: statutory and exchange charges | `rules/charges/*.toml`, cases | same |
| 7 | Research: capital-gains tax rules | six tables under `rules/tax/`, cases | same |
| 8 | Research: slabs, rebate, surcharge, cess | five tables under `rules/tax/`, cases | same |
| 9 | Charges engine | `engine/charges.py`, composition cases | tests and row gate green |
| 10 | FIFO lots | `engine/lots.py` | tests pass |
| 11 | Tax: gain classification | `engine/tax.py` part 1 | tests pass |
| 12 | Tax: year computation | `engine/tax.py` part 2, composition cases | tests and row gate green |
| 13 | Checkpoint 1 | price fetch, scenario, report | ₹1L Nifty ETF report, checked by hand and against Fyers' calculator |
| 14 | Futures business income | `Business`, audit rules, code | tests and row gate green |
| 15 | Final gates | every row exercised, assumed rows reviewed | all green, user has seen every assumed row |

Tasks 9 to 12 need only Tasks 1 to 4 for their unit tests (they use made-up rules). Their golden cases need Tasks 5 to 8. Task 13 needs everything before it. Task 14 is independent of 13: stop after 13 if the user wants to look at the checkpoint first.

**Left out on purpose, with the reason:**
- Mutual-fund exit loads. The spec lists them under costs, but they are set by each scheme, not by the market, so they belong with the fund data in sub-project 4.
- Commodity transaction tax (CTT) and BSE charges. The v1 universe has no commodity derivatives and every instrument trades on NSE.
- A one-time Fyers account-opening fee, if there is one (Task 5 records it and tells the user).
- Intraday and options charges (not in the v1 universe).

**Not in this plan (ask the user first):** archiving the old Bitcoin-ETF code, and turning off the old daily GitHub Actions job, Vercel site and ntfy alerts. The old files live in `ml/`, `models/`, `web/`, `.github/workflows/` and are left untouched. New code uses `engine/`, `rules/`, `data/`, `tests/`, `docs/` only, so nothing collides.

## Global Constraints

Copied from the spec, and binding on every task:

- "Every transaction is taxed and charged by the rules of its own date. The same holds for every comparison."
- "Start dates | 2010-04-01 onward."
- "Decimal arithmetic, exact. Rounding is display-only. The ⓘ shows the exact value. Where the law or a contract note rounds (for example, tax to the nearest rupee), that rounding is its own trace step."
- "Every row: `from`, `to`, `value` (string, parsed as Decimal), `source` (URL or Act section), `verified_on`, `confidence` (`primary` = official text, `secondary` = broker or reputable explainer, `assumed` = stand-in), `note`. The engine never hard-codes a rate. Any `secondary` or `assumed` row shows a flag in every trace that uses it."
- "A test checks that every node equals its formula applied to its children."
- "A row needs one primary source or two independent secondary sources. Otherwise it is `assumed` and flagged."
- "Fyers likely has no fee history before about 2015 to 2016; earlier years use a labelled stand-in."
- "Stamp duty (state-wise before July 2020, uniform after; one default state before that, labelled)."
- "FIFO lots. Tax for each financial year is settled at year end from portfolio cash (labelled assumption)."
- "Advance-tax interest is ignored (labelled)."
- "The user starts with no carried-forward losses."
- "Future years use today's rules (labelled on every projection)."
- "Verification: hand-worked golden cases on both sides of each rule-change date ... Charges are compared with Fyers' own calculator. Property tests: tax is never negative, lots are conserved, every trace node balances."
- "No real orders are ever sent." No credentials in code or in tests.

Plan-level constraints:

- Inside `engine/`, use the standard library only. Money is `decimal.Decimal`; floats are refused by `D()`.
- Tests never touch the network. The one price download (Task 13) is tested with a fixture.
- A rate, date threshold or fee appears in a `rules/` table, never in `engine/` code. The only dates in `engine/` code are the statutory event 31 Jan 2018 in `scenario.py` and the financial-year boundary on 1 April.

## Review Focus

Input classes the spec implies but no happy-path test exercises. Each has a pinning test in the task named.

1. **A sale exactly 12 months after purchase, or a purchase on 29 February.** Short-term until the day after; month arithmetic clamps to month end. Pinned in Task 11 (`test_holding_period_boundaries`).
2. **A date with no rule row** (before 2010-04-01, or a key never defined). Raise `RuleNotFound` naming the table, key and date. Never default to zero. Pinned in Task 3 (`test_missing_date_or_key_raises_instead_of_guessing`) and Task 9 (`test_a_date_with_no_rule_raises`).
3. **Selling more than held, zero or negative quantity or price, or units bought before 31 Jan 2018 with no 2018 value supplied.** Raise `ValueError`; no negative lots; no silent skip of grandfathering. Pinned in Tasks 9, 10 and 11.
4. **A losing year.** Tax is never negative; a loss carries forward for 8 years and then expires; a loss on an exempt sale is not carried. Pinned in Task 12 (`test_unused_loss_is_carried_forward_then_used`, `test_losses_expire_after_eight_years`, `test_a_loss_on_an_exempt_sale_is_not_carried_forward`).
5. **A student with no other income, and incomes just either side of a rebate or surcharge threshold.** Unused basic exemption shelters gains; tax never falls or jumps by more than the extra income across a threshold. Pinned in Task 12 (`test_basic_exemption_shelters_gains_when_other_income_is_zero`, `test_tax_never_falls_and_never_jumps_across_the_surcharge_threshold`).

## Rule table catalogue

One file per table under `rules/`, named by table (`rules/charges/stt.toml` is table `charges.stt`). The engine reads exactly these fields. If research shows a rule cannot be expressed here, stop and amend this plan with the user before improvising.

| Table | Key fields | Payload fields | Read by |
|---|---|---|---|
| `fyers.brokerage` | `product` (`delivery`, `futures`) | `mode` (`zero`, `flat`, `pct`, `min_flat_pct`), `flat` ₹, `pct` fraction, optional `round_step` | `charges._brokerage` |
| `fyers.dp` | none | `value` ₹ per delivery sale per ISIN per day, before GST | `charges.dp_charge` |
| `fyers.account` | `fee` (`amc_annual`) | `value` ₹ per year, before GST | `charges.amc_fee` |
| `charges.stt` | `instrument_class`, `side` | `value` fraction of turnover, optional `round_step` | `charges.order_charges` |
| `charges.exchange_txn` | `exchange` (`NSE`), `segment` (`delivery`, `futures`) | `value` fraction | same |
| `charges.sebi` | none | `value` fraction | same |
| `charges.ipft` | `exchange`, `segment` | `value` fraction | same |
| `charges.clearing` | `segment` | `value` fraction | same |
| `charges.stamp` | `segment` (`delivery`, `futures`, `mf`), `side` | `value` fraction | same |
| `charges.gst` | none | `value` fraction, `applies_to` list of line names (`brokerage`, `exchange_txn`, `sebi`, `ipft`, `clearing`, `dp`, `amc`) | `charges._gst` |
| `charges.dp_depository` | none | `value` ₹ per delivery sale per ISIN per day | `charges.dp_charge` |
| `tax.buckets` | `asset_class` | `bucket` name; the row's dates are **acquisition** dates | `tax.classify` |
| `tax.capital_gains` | `bucket` | `lt_months` int, `always_short` bool, `st_treatment`, `st_rate`, `st_section`, `lt_treatment`, `lt_rate`, `lt_section` (treatment is `special`, `slab` or `exempt`; rates are strings), `indexation` bool, `lt_exemption_group`, `grandfather_acq_upto` date; the row's dates are **sale** dates | `tax.classify` |
| `tax.cii` | none | `value` (cost inflation index); one row per financial year | `tax.classify` |
| `tax.lt_exemption` | `group` | `value` ₹ per financial year, `order` (`lowest_rate_first` or `highest_rate_first`) | `tax.fy_tax` |
| `tax.dividend` | none | `mode` (`exempt`, `slab`, `above_threshold`), `threshold` ₹, `rate` | same |
| `tax.loss_rules` | `kind` (`capital`, `business`) | `value` years a loss may be carried forward | same |
| `tax.slabs` | `regime` (`old`, `new`) | `brackets`: list of `{upto, rate}` in order, last `upto = ""` | same |
| `tax.rebate_87a` | `regime` | `income_limit`, `max_rebate`, `applies_to_special` bool, optional `marginal_relief` bool | same |
| `tax.surcharge` | `regime` | `tiers`: list of `{above, rate}` ascending, optional `cap_special` | same |
| `tax.cess` | none | `value` fraction | same |
| `tax.conventions` | `name` (`setoff_order`, `shortfall_order`, `tax_round_step`) | `value` | same |
| `tax.audit` | none | `turnover_limit` ₹, `fee` ₹ | `business.audit_fee` |

`instrument_class` and `asset_class` share one vocabulary: `etf_equity` (equity-oriented ETF such as Nifty BeES), `etf_gold`, `mf_equity` (equity-oriented fund, arbitrage funds included), `mf_debt` (debt and liquid funds), `fut_index` (index futures). Tables with a second regime that started later (`new` regime from FY2020-21) declare it in `[meta]` with `late_keys`.

## Research protocol

Used by Tasks 5, 6, 7, 8 and 14.

**Tools.** Load with ToolSearch query `select:WebSearch,WebFetch`. Pages that block WebFetch or need JavaScript: load `select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__get_page_text` and read the page in a real browser tab. Old versions of a web page: list them with `https://web.archive.org/cdx/search/cdx?url=<page>*&output=json&fl=timestamp,original,statuscode,digest&collapse=digest&filter=statuscode:200`, then read `https://web.archive.org/web/<timestamp>id_/<original>`.

**Source ranking.** Primary: the Act or a Finance Act (incometaxindia.gov.in, indiacode.nic.in), CBDT and CBIC notifications and circulars, SEBI circulars (sebi.gov.in), exchange circulars (nseindia.com, bseindia.com), and Fyers' own published pages. Secondary: another broker's fee page, an explainer from ClearTax, Groww or an ICAI body, a news report.

**Writing rows.** Every key combination needs rows from `coverage_from` (2010-04-01) with no gap. Where a charge or rule did not exist, write an explicit row with `value = "0"` and say so in `note`. Template (fill every field from a source you have read; never from memory):

```toml
[meta]
keys = ["instrument_class", "side"]   # the key field names, in order; [] for a keyless table
coverage_from = 2010-04-01

[[row]]
instrument_class = "etf_equity"
side = "sell"
from = 2010-04-01
to = 2016-05-31                        # omit `to` on the last, open-ended row
value = "0.00001"                      # always a string
source = "S12 Finance Act 2004 s.98"  # an id listed in rules/SOURCES.md, then a pinpoint
verified_on = 2026-10-01               # the day you read the source
confidence = "primary"                 # primary | secondary | assumed
note = ""                              # required if assumed; also say when a date is inferred from a window
```

A key that legitimately starts later (the new tax regime from FY2020-21) is declared in `[meta]` with `late_keys = [{ regime = "new", from = 2020-04-01 }]`. A table whose last row must end (for example a table of years that stops) sets `open_ended = false` in `[meta]`.

The values in the template are placeholders for shape only. `confidence`: `primary` for official text, `secondary` for two independent non-official sources that agree, `assumed` otherwise (then `source = "S0"` or the best source, and `note` says what was tried and why the stand-in was chosen). Add each source to `rules/SOURCES.md` before citing it: id, document, URL, retrieval date, what it supports.

**Writing golden cases.** After the tables load, run `python -m tests.golden_skeleton <table> [field ...]`. It prints a tagged `rule_value` case for the day before and the day of every rule change, and one case for any key with a single row. Save the output into `tests/golden/<name>.toml`, then fill `source` and every `expect` by typing **from the source document, not from the rules file**. That second typing is what catches a wrong rate or a wrong date. For a table with several payload fields, pass them all (`python -m tests.golden_skeleton tax.capital_gains lt_months st_rate lt_rate`) and delete the fields that do not apply to a row.

**Stop rule.** If a source cannot be reached after 3 attempts, or two sources disagree and no primary source exists, do not guess silently: write the row as `assumed` and record what was tried. Tell the user at once about any `assumed` row that could move a result by more than 0.01% of turnover or 0.5% of tax. List every `assumed` and `secondary` row in the task's commit message body.

**Leads.** Each research task lists leads written from memory. They are unverified and may be wrong. Use them only to know what to look for.

---

## Task 1: Branch and skeleton

**Files:**
- Create: `pytest.ini`, `requirements-dev.txt`, `engine/__init__.py`, `rules/SOURCES.md`, `tests/golden/.gitkeep`, `tests/test_smoke.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: nothing.
- Produces: the folders and config every later task assumes; the `tests` and `data` folders importable as namespace packages through `pythonpath = .`.

- [ ] **Step 1: Create the branch**

Run: `git switch -c v3/rules-engine`
Expected: `Switched to a new branch 'v3/rules-engine'`. The untracked `docs/` folder (spec and this plan) comes along.

- [ ] **Step 2: Write the config and skeleton files**

`pytest.ini`:

```ini
[pytest]
pythonpath = .
testpaths = tests
```

`requirements-dev.txt`:

```text
pytest>=8
```

`engine/__init__.py` and `tests/golden/.gitkeep`: empty files.

`rules/SOURCES.md`:

```markdown
# Rule sources

Every rule row's `source` starts with an id from this table (for example `S12 s.111A`). Add the source here first.
`S0` is for rows with no usable source: those rows must be `assumed` and say why in `note`.

| id | document | URL | retrieved | supports |
|---|---|---|---|---|
| S0 | No source found | | | `assumed` rows only |
```

`tests/test_smoke.py`:

```python
def test_engine_is_a_regular_package():
    import engine
    assert engine.__file__ is not None  # a namespace package (no __init__.py) has no __file__
```

- [ ] **Step 3: Make `.gitignore` track processed data**

The old `.gitignore` ignores all of `/data/`. The spec commits `data/manifest.json` and small processed files, and ignores only raw downloads. In `.gitignore`, replace

```text
# Local caches and backups; the daily job fetches fresh prices every run.
/data/
/artifacts/
```

with

```text
# Local caches. Raw downloads are ignored; processed slices and data/manifest.json are committed.
/data/raw/
/artifacts/
/out/
```

- [ ] **Step 4: Run pytest**

Run: `python -m pytest -q`
Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add .gitignore pytest.ini requirements-dev.txt engine rules tests docs
git commit -m "chore: skeleton for the rules and costs engine"
```

---

## Task 2: Money and trace

**Files:**
- Create: `engine/money.py`, `engine/trace.py`
- Test: `tests/test_money_trace.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `engine.money`: `ZERO`, `D(x) -> Decimal` (refuses floats), `round_step(x, step, floor=False) -> Decimal`.
  - `engine.trace`: dataclasses `RuleRef(rule_id, valid_from, valid_to, source, verified_on, confidence)` and `Node(label, value, op, inputs, rules, note, tags)` with a derived `.formula`; constructors `const`, `from_rule`, `add`, `sub`, `mul`, `div`, `maxn`, `minn`, `rnd(label, x, step_node, floor=False)`, `cite(node, *refs)`; helpers `recompute`, `walk`, `assert_balanced`, `rules_used`, `flags`, `to_dict(node, depth=None)`, `render(node)`.

- [ ] **Step 1: Write the failing test**

`tests/test_money_trace.py`:

```python
import json
from datetime import date
from decimal import Decimal

import pytest

from engine.money import D, round_step
from engine.trace import (Node, RuleRef, add, assert_balanced, cite, const, flags, from_rule, mul,
                          rnd, sub, to_dict, walk)


def test_floats_are_refused():
    with pytest.raises(TypeError):
        D(0.1)


def test_round_step_paise_rupee_ten():
    assert round_step(Decimal("1234.565"), Decimal("0.01")) == Decimal("1234.57")
    assert round_step(Decimal("2.5"), Decimal("1")) == Decimal("3")
    assert round_step(Decimal("1235"), Decimal("10")) == Decimal("1240")
    assert round_step(Decimal("1239.99"), Decimal("10"), floor=True) == Decimal("1230")


def test_value_is_derived_and_balances():
    turnover = mul("Turnover", const("Qty", "100"), const("Price", "850.55"))
    fee = rnd("Fee", mul("Fee raw", turnover, const("Rate", "0.00025")), const("Step", "0.01"))
    total = add("Total", turnover, fee)
    assert turnover.value == Decimal("85055.00")
    assert fee.value == Decimal("21.26")
    assert total.value == Decimal("85076.26")
    assert_balanced(total)
    assert total.formula == "Turnover + Fee"


def test_balance_check_catches_a_forged_value():
    good = add("Total", const("a", "1"), const("b", "2"))
    forged = Node("Total", Decimal("4"), "add", good.inputs)
    with pytest.raises(AssertionError, match="Total"):
        assert_balanced(forged)


def test_flags_list_only_non_primary_rules():
    p = RuleRef("t[k=v]", date(2010, 4, 1), None, "act", date(2026, 1, 1), "primary")
    a = RuleRef("u[k=v]", date(2010, 4, 1), None, "guess", date(2026, 1, 1), "assumed")
    n = add("x", from_rule("p", "1", p), from_rule("a", "2", a))
    assert [r.rule_id for r in flags(n)] == ["u[k=v]"]


def test_to_dict_is_json_ready_and_depth_limited():
    n = sub("d", const("a", "5"), const("b", "3"))
    assert json.loads(json.dumps(to_dict(n)))["value"] == "2"
    assert "inputs" not in to_dict(n, depth=0)
    assert len(list(walk(n))) == 3


def test_cite_attaches_a_rule_without_changing_the_value():
    a = RuleRef("u[k=v]", date(2010, 4, 1), None, "guess", date(2026, 1, 1), "assumed")
    n = cite(const("x", "1"), a)
    assert n.value == 1 and [r.rule_id for r in flags(n)] == ["u[k=v]"]
```

- [ ] **Step 2: Run it to see it fail**

Run: `python -m pytest tests/test_money_trace.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'engine.money'`.

- [ ] **Step 3: Implement**

`engine/money.py`:

```python
"""Exact money maths. Floats are refused; rounding is always an explicit step."""
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal

ZERO = Decimal(0)


def D(x) -> Decimal:
    if isinstance(x, float):
        raise TypeError(f"float {x!r} refused: pass a str, int or Decimal")
    return x if isinstance(x, Decimal) else Decimal(x)


def round_step(x: Decimal, step: Decimal, floor: bool = False) -> Decimal:
    """Round x to a multiple of step: 0.01 paise, 1 rupee, 10 statutory tax rounding."""
    mode = ROUND_FLOOR if floor else ROUND_HALF_UP
    return (x / step).quantize(Decimal(1), rounding=mode) * step
```

`engine/trace.py`:

```python
"""Every number is a Node: a value plus how it was made.

A node's value is derived from its inputs by its op, never typed in, so an
explanation cannot drift from the number. `assert_balanced` re-derives every
value and fails on any mismatch.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Iterator

from engine.money import ZERO, D, round_step


@dataclass(frozen=True)
class RuleRef:
    rule_id: str
    valid_from: date
    valid_to: date | None
    source: str
    verified_on: date
    confidence: str  # primary | secondary | assumed


@dataclass(frozen=True)
class Node:
    label: str
    value: Decimal
    op: str  # const | rule | add | sub | mul | div | max | min | round | floor
    inputs: tuple[Node, ...] = ()
    rules: tuple[RuleRef, ...] = ()
    note: str = ""
    tags: frozenset[str] = frozenset()

    @property
    def formula(self) -> str:
        names = [i.label for i in self.inputs]
        sym = {"add": " + ", "sub": " − ", "mul": " × ", "div": " ÷ "}
        if self.op in sym:
            return sym[self.op].join(names)
        return f"{self.op}({', '.join(names)})" if names else self.op


def _n(label, value, op, inputs=(), rules=(), note="", tags=()) -> Node:
    return Node(label, value, op, tuple(inputs), tuple(rules), note, frozenset(tags))


def const(label, value, note="", tags=()) -> Node:
    return _n(label, D(value), "const", note=note, tags=tags)


def from_rule(label, value, ref: RuleRef, note="", tags=()) -> Node:
    return _n(label, D(value), "rule", rules=(ref,), note=note, tags=tags)


def add(label, *xs, note="", tags=()) -> Node:
    return _n(label, sum((x.value for x in xs), ZERO), "add", xs, note=note, tags=tags)


def sub(label, a, b, note="", tags=()) -> Node:
    return _n(label, a.value - b.value, "sub", (a, b), note=note, tags=tags)


def mul(label, a, b, note="", tags=()) -> Node:
    return _n(label, a.value * b.value, "mul", (a, b), note=note, tags=tags)


def div(label, a, b, note="", tags=()) -> Node:
    return _n(label, a.value / b.value, "div", (a, b), note=note, tags=tags)


def maxn(label, *xs, note="", tags=()) -> Node:
    return _n(label, max(x.value for x in xs), "max", xs, note=note, tags=tags)


def minn(label, *xs, note="", tags=()) -> Node:
    return _n(label, min(x.value for x in xs), "min", xs, note=note, tags=tags)


def rnd(label, x: Node, step: Node, floor=False, note="", tags=()) -> Node:
    return _n(label, round_step(x.value, step.value, floor), "floor" if floor else "round",
              (x, step), note=note, tags=tags)


def cite(n: Node, *refs: RuleRef) -> Node:
    """Same node, with extra rules attached (so their confidence flags surface)."""
    return replace(n, rules=n.rules + tuple(r for r in refs if r not in n.rules))


def recompute(n: Node) -> Decimal | None:
    v = [i.value for i in n.inputs]
    if n.op == "add":
        return sum(v, ZERO)
    if n.op == "sub":
        return v[0] - v[1]
    if n.op == "mul":
        return v[0] * v[1]
    if n.op == "div":
        return v[0] / v[1]
    if n.op == "max":
        return max(v)
    if n.op == "min":
        return min(v)
    if n.op == "round":
        return round_step(v[0], v[1])
    if n.op == "floor":
        return round_step(v[0], v[1], floor=True)
    return None  # const / rule: a leaf


def walk(n: Node) -> Iterator[Node]:
    seen: set[int] = set()
    stack = [n]
    while stack:
        x = stack.pop()
        if id(x) in seen:
            continue
        seen.add(id(x))
        yield x
        stack.extend(reversed(x.inputs))


def assert_balanced(n: Node) -> None:
    for x in walk(n):
        r = recompute(x)
        if r is not None and r != x.value:
            raise AssertionError(f"{x.label}: value {x.value} != recomputed {r} ({x.formula})")


def rules_used(n: Node) -> set[RuleRef]:
    return {r for x in walk(n) for r in x.rules}


def flags(n: Node) -> list[RuleRef]:
    """Rules under this number that are not backed by a primary source."""
    return sorted((r for r in rules_used(n) if r.confidence != "primary"),
                  key=lambda r: (r.rule_id, r.valid_from))


def to_dict(n: Node, depth: int | None = None) -> dict:
    d = {"label": n.label, "value": str(n.value), "op": n.op, "formula": n.formula,
         "note": n.note, "tags": sorted(n.tags),
         "rules": [{"id": r.rule_id, "from": r.valid_from.isoformat(),
                    "to": r.valid_to.isoformat() if r.valid_to else None,
                    "source": r.source, "verified_on": r.verified_on.isoformat(),
                    "confidence": r.confidence} for r in n.rules]}
    if depth is None or depth > 0:
        d["inputs"] = [to_dict(i, None if depth is None else depth - 1) for i in n.inputs]
    return d


def render(n: Node, indent: int = 0) -> str:
    line = f"{'  ' * indent}{n.label} = {n.value}  [{n.formula}]"
    return "\n".join([line] + [render(i, indent + 1) for i in n.inputs])
```

- [ ] **Step 4: Run the tests**

Run: `python -m pytest tests/test_money_trace.py -q`
Expected: `7 passed`.

- [ ] **Step 5: Commit**

```bash
git add engine/money.py engine/trace.py tests/test_money_trace.py
git commit -m "feat: exact money maths and self-checking calculation trace"
```

---

## Task 3: Rule loader

**Files:**
- Create: `engine/rules.py`, `tests/helpers.py`, `tests/test_rules.py`, `tests/test_rules_real.py`

**Interfaces:**
- Consumes: `engine.trace.RuleRef`, `engine.money.D`.
- Produces: `Rules.load(root: Path) -> Rules`; `Rules.at(table, on: date, **key) -> Row`; `Rules.has(table, on, **key) -> bool`; `Rules.all_rows()`; `Row` with `table`, `key`, `valid_from`, `valid_to`, `data: dict`, `ref: RuleRef`, `.dec(field) -> Decimal`, `.value`; `Table` (in `Rules.tables`) with `.groups: dict[key, list[Row]]`; exceptions `RuleTableError` (bad file, raised at load) and `RuleNotFound` (no row for that date and key). Test helpers `table(keys, rows, coverage="2010-04-01", extra_meta="")` and `make_rules(tmp_path, {name: toml_text}) -> Rules` that write made-up tables for engine tests.

- [ ] **Step 1: Write the failing tests**

`tests/helpers.py`:

```python
"""Test-only helpers: write throwaway rule tables so engine logic is tested without real rates."""
from pathlib import Path

from engine.rules import Rules

STAMP = 'source = "test fixture"\nverified_on = 2026-01-01\nconfidence = "primary"\n'


def table(keys: list[str], rows: list[str], coverage: str = "2010-04-01", extra_meta: str = "") -> str:
    """rows: `field = value` lines. A row that sets its own `confidence` also sets source and verified_on."""
    head = f"[meta]\nkeys = {keys!r}\ncoverage_from = {coverage}\n{extra_meta}\n".replace("'", '"')
    body = "".join(f"[[row]]\n{r.strip()}\n{'' if 'confidence' in r else STAMP}\n" for r in rows)
    return head + body


def make_rules(tmp_path: Path, files: dict[str, str]) -> Rules:
    for name, text in files.items():
        p = tmp_path / (name.replace(".", "/") + ".toml")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return Rules.load(tmp_path)
```

`tests/test_rules.py`:

```python
from datetime import date
from decimal import Decimal

import pytest

from engine.rules import RuleNotFound, RuleTableError
from tests.helpers import make_rules, table


def two_rows():
    return table(["seg"], [
        'seg = "eq"\nfrom = 2010-04-01\nto = 2016-05-31\nvalue = "0.001"',
        'seg = "eq"\nfrom = 2016-06-01\nvalue = "0.0005"',
    ])


def test_lookup_is_inclusive_on_both_ends(tmp_path):
    r = make_rules(tmp_path, {"charges.stt": two_rows()})
    assert r.at("charges.stt", date(2016, 5, 31), seg="eq").value == Decimal("0.001")
    assert r.at("charges.stt", date(2016, 6, 1), seg="eq").value == Decimal("0.0005")
    assert r.at("charges.stt", date(2010, 4, 1), seg="eq").ref.rule_id == "charges.stt[seg=eq]"


def test_missing_date_or_key_raises_instead_of_guessing(tmp_path):
    r = make_rules(tmp_path, {"charges.stt": two_rows()})
    with pytest.raises(RuleNotFound, match="2009-12-31"):
        r.at("charges.stt", date(2009, 12, 31), seg="eq")
    with pytest.raises(RuleNotFound):
        r.at("charges.stt", date(2020, 1, 1), seg="other")
    with pytest.raises(RuleNotFound, match="no rule table"):
        r.at("nope", date(2020, 1, 1))
    with pytest.raises(TypeError):
        r.at("charges.stt", date(2020, 1, 1))


@pytest.mark.parametrize("second_from, why", [("2016-06-02", "gap"), ("2016-05-31", "overlap")])
def test_gap_or_overlap_is_rejected(tmp_path, second_from, why):
    text = table(["seg"], [
        'seg = "eq"\nfrom = 2010-04-01\nto = 2016-05-31\nvalue = "1"',
        f'seg = "eq"\nfrom = {second_from}\nvalue = "2"',
    ])
    with pytest.raises(RuleTableError, match="gap or overlap"):
        make_rules(tmp_path, {"t": text})


def test_each_bad_row_is_named(tmp_path):
    base = 'seg = "eq"\nfrom = 2010-04-01\nvalue = "1"\n'
    cases = {
        "missing source": (base + 'verified_on = 2026-01-01\nconfidence = "primary"\n', "missing `source`"),
        "bad confidence": (base + 'source = "x"\nverified_on = 2026-01-01\nconfidence = "sure"\n', "confidence must be"),
        "assumed without note": (base + 'source = "x"\nverified_on = 2026-01-01\nconfidence = "assumed"\n', "note"),
        "future verified_on": (base + 'source = "x"\nverified_on = 2999-01-01\nconfidence = "primary"\n', "future"),
        "starts late": ('seg = "eq"\nfrom = 2011-01-01\nvalue = "1"\nsource = "x"\nverified_on = 2026-01-01\nconfidence = "primary"\n', "must start on or before"),
    }
    for name, (row, msg) in cases.items():
        text = '[meta]\nkeys = ["seg"]\ncoverage_from = 2010-04-01\n[[row]]\n' + row
        with pytest.raises(RuleTableError, match=msg):
            make_rules(tmp_path / name.replace(" ", "_"), {"t": text})


def test_last_row_must_be_open_ended_unless_declared(tmp_path):
    closed = table(["seg"], ['seg = "eq"\nfrom = 2010-04-01\nto = 2011-03-31\nvalue = "1"'])
    with pytest.raises(RuleTableError, match="open-ended"):
        make_rules(tmp_path / "a", {"t": closed})
    ok = table(["seg"], ['seg = "eq"\nfrom = 2010-04-01\nto = 2011-03-31\nvalue = "1"'],
               extra_meta="open_ended = false")
    make_rules(tmp_path / "b", {"t": ok})


def test_late_keys_may_start_after_coverage(tmp_path):
    text = table(["regime"], [
        'regime = "old"\nfrom = 2010-04-01\nvalue = "1"',
        'regime = "new"\nfrom = 2020-04-01\nvalue = "2"',
    ], extra_meta='late_keys = [{ regime = "new", from = 2020-04-01 }]')
    r = make_rules(tmp_path, {"tax.slabs": text})
    assert r.has("tax.slabs", date(2021, 1, 1), regime="new")
    assert not r.has("tax.slabs", date(2019, 1, 1), regime="new")


def test_rows_carry_confidence_and_payload(tmp_path):
    text = table(["seg"], ['seg = "eq"\nfrom = 2010-04-01\nvalue = "1"\nlist = [ "a", "b" ]'])
    row = make_rules(tmp_path, {"t": text}).at("t", date(2020, 1, 1), seg="eq")
    assert row.ref.confidence == "primary" and row.data["list"] == ["a", "b"]
```

`tests/test_rules_real.py` checks the real `rules/` folder and that every row cites a logged source:

```python
import re
from pathlib import Path

from engine.rules import Rules

ROOT = Path(__file__).resolve().parents[1]
RULES = Rules.load(ROOT / "rules")  # raises RuleTableError on any malformed table
SOURCE_IDS = set(re.findall(r"^\|\s*(S\d+)\s*\|", (ROOT / "rules" / "SOURCES.md").read_text(encoding="utf-8"), re.M))


def test_every_row_cites_a_source_listed_in_sources_md():
    for row in RULES.all_rows():
        m = re.match(r"(S\d+)\b", row.ref.source)
        assert m and m.group(1) in SOURCE_IDS, (
            f"{row.ref.rule_id} from {row.valid_from}: source {row.ref.source!r} "
            "must start with an id listed in rules/SOURCES.md")
```

- [ ] **Step 2: Run them to see them fail**

Run: `python -m pytest tests/test_rules.py tests/test_rules_real.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'engine.rules'`.

- [ ] **Step 3: Implement**

`engine/rules.py`:

```python
"""Dated rule tables loaded from rules/**/*.toml. Nothing else in the engine knows a rate."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Iterator

from engine.money import D
from engine.trace import RuleRef

CONFIDENCE = {"primary", "secondary", "assumed"}
RESERVED = {"from", "to", "source", "verified_on", "confidence", "note"}
ONE_DAY = timedelta(days=1)


class RuleTableError(ValueError):
    """A rules file is malformed. Raised while loading, never at lookup time."""


class RuleNotFound(LookupError):
    """No row covers this date and key. The engine never guesses a default."""


def rule_id(table: str, key: tuple[tuple[str, str], ...]) -> str:
    return f"{table}[{','.join(f'{k}={v}' for k, v in key)}]"


@dataclass(frozen=True)
class Row:
    table: str
    key: tuple[tuple[str, str], ...]
    valid_from: date
    valid_to: date | None
    data: dict
    ref: RuleRef

    def dec(self, field: str) -> Decimal:
        return D(self.data[field])

    @property
    def value(self) -> Decimal:
        return self.dec("value")

    def covers(self, on: date) -> bool:
        return self.valid_from <= on and (self.valid_to is None or on <= self.valid_to)


class Table:
    def __init__(self, name: str, raw: dict, path: Path):
        meta = raw.get("meta")
        if not isinstance(meta, dict) or "keys" not in meta or type(meta.get("coverage_from")) is not date:
            raise RuleTableError(f"{path}: [meta] needs keys=[...] and coverage_from=<date>")
        self.name, self.path = name, path
        self.keys: list[str] = list(meta["keys"])
        self.open_ended: bool = meta.get("open_ended", True)
        late = [({k: str(v) for k, v in e.items() if k != "from"}, e["from"])
                for e in meta.get("late_keys", [])]
        self.groups: dict[tuple, list[Row]] = {}
        for i, r in enumerate(raw.get("row", [])):
            row = self._row(r, i)
            self.groups.setdefault(row.key, []).append(row)
        if not self.groups:
            raise RuleTableError(f"{path}: table has no [[row]] entries")
        for key, rows in self.groups.items():
            rows.sort(key=lambda r: r.valid_from)
            start = next((f for d, f in late if d == dict(key)), meta["coverage_from"])
            if rows[0].valid_from > start:
                raise RuleTableError(f"{path} {dict(key)}: first row starts {rows[0].valid_from}, "
                                     f"must start on or before {start}")
            for a, b in zip(rows, rows[1:]):
                if a.valid_to is None or b.valid_from != a.valid_to + ONE_DAY:
                    raise RuleTableError(f"{path} {dict(key)}: gap or overlap between "
                                         f"{a.valid_from}..{a.valid_to} and {b.valid_from}")
            if self.open_ended and rows[-1].valid_to is not None:
                raise RuleTableError(f"{path} {dict(key)}: last row must be open-ended (no `to`)")

    def _row(self, r: dict, i: int) -> Row:
        at = f"{self.path} row {i}"
        for f in ("from", "source", "verified_on", "confidence"):
            if f not in r:
                raise RuleTableError(f"{at}: missing `{f}`")
        for f in ("from", "verified_on", *(("to",) if "to" in r else ())):
            if type(r[f]) is not date:
                raise RuleTableError(f"{at}: `{f}` must be a TOML date")
        if r["confidence"] not in CONFIDENCE:
            raise RuleTableError(f"{at}: confidence must be one of {sorted(CONFIDENCE)}")
        if not str(r["source"]).strip():
            raise RuleTableError(f"{at}: `source` is empty")
        if r["confidence"] == "assumed" and not str(r.get("note", "")).strip():
            raise RuleTableError(f"{at}: assumed rows need a `note` saying why")
        if "to" in r and r["to"] < r["from"]:
            raise RuleTableError(f"{at}: `to` is before `from`")
        if r["verified_on"] > date.today():
            raise RuleTableError(f"{at}: `verified_on` is in the future")
        missing = [k for k in self.keys if k not in r]
        if missing:
            raise RuleTableError(f"{at}: missing key field(s) {missing}")
        key = tuple((k, str(r[k])) for k in self.keys)
        data = {k: v for k, v in r.items() if k not in RESERVED and k not in self.keys}
        ref = RuleRef(rule_id(self.name, key), r["from"], r.get("to"), r["source"],
                      r["verified_on"], r["confidence"])
        return Row(self.name, key, r["from"], r.get("to"), data, ref)

    def _key(self, key: dict) -> tuple[tuple[str, str], ...]:
        if set(key) != set(self.keys):
            raise TypeError(f"{self.name} needs key fields {self.keys}, got {sorted(key)}")
        return tuple((k, str(key[k])) for k in self.keys)

    def has(self, on: date, **key) -> bool:
        return any(r.covers(on) for r in self.groups.get(self._key(key), ()))

    def at(self, on: date, **key) -> Row:
        k = self._key(key)
        for row in self.groups.get(k, ()):
            if row.covers(on):
                return row
        raise RuleNotFound(f"{self.name} {dict(k)} on {on}: no rule covers this date")

    def all_rows(self) -> Iterator[Row]:
        for rows in self.groups.values():
            yield from rows


class Rules:
    def __init__(self, tables: dict[str, Table]):
        self.tables = tables

    @classmethod
    def load(cls, root: Path) -> "Rules":
        root = Path(root)
        tables = {}
        for p in sorted(root.rglob("*.toml")):
            name = ".".join(p.relative_to(root).with_suffix("").parts)
            try:
                raw = tomllib.loads(p.read_text(encoding="utf-8"))
            except tomllib.TOMLDecodeError as e:
                raise RuleTableError(f"{p}: {e}") from e
            tables[name] = Table(name, raw, p)
        return cls(tables)

    def _t(self, table: str) -> Table:
        if table not in self.tables:
            raise RuleNotFound(f"no rule table named {table!r}")
        return self.tables[table]

    def at(self, table: str, on: date, **key) -> Row:
        return self._t(table).at(on, **key)

    def has(self, table: str, on: date, **key) -> bool:
        return self._t(table).has(on, **key)

    def all_rows(self) -> Iterator[Row]:
        for t in self.tables.values():
            yield from t.all_rows()
```

- [ ] **Step 4: Run the tests**

Run: `python -m pytest -q`
Expected: all pass (the real `rules/` folder holds only `SOURCES.md`, so the real-rules test passes with no rows).

- [ ] **Step 5: Commit**

```bash
git add engine/rules.py tests/helpers.py tests/test_rules.py tests/test_rules_real.py
git commit -m "feat: dated rule tables with gap, overlap and source checks"
```

---

## Task 4: Golden harness

**Files:**
- Create: `tests/golden_runner.py`, `tests/golden_skeleton.py`, `tests/test_golden_runner.py`, `tests/test_golden.py`

**Interfaces:**
- Consumes: `engine.rules.Rules`, `engine.money.D`.
- Produces: `KINDS` registry and `@kind(name)` decorator (later tasks register `charges`, `dp`, `amc`, `tax_fy`, `audit`); `load_cases(folder) -> list[dict]`; `run_case(rules, case) -> set[RuleRef]`; `check_boundary_tags(case, refs)`; `all_boundaries(rules)`; `missing_coverage(rules, cases) -> list[str]`; `same(actual, expected)`; `tests.golden_skeleton.skeleton(rules, table, fields)` and `changes(rules, prefixes)`. A golden case is a `[[case]]` in `tests/golden/*.toml` with `id`, `kind`, `source`, optional `boundary = ["<rule_id>@<date>:before|after"]`. Kind `rule_value` has `table`, `on`, optional `key = {...}` and a `[case.expect]` table of field = value.

- [ ] **Step 1: Write the failing tests**

`tests/test_golden_runner.py`:

```python
from datetime import date

import pytest

from tests.golden_runner import (all_boundaries, check_boundary_tags, load_cases, missing_coverage,
                                 run_case, same)
from tests.golden_skeleton import changes, skeleton
from tests.helpers import make_rules, table


@pytest.fixture
def rules(tmp_path):
    text = table(["seg"], [
        'seg = "eq"\nfrom = 2010-04-01\nto = 2016-05-31\nvalue = "0.001"',
        'seg = "eq"\nfrom = 2016-06-01\nvalue = "0.0005"\nlist = [ "a", "b" ]',
    ])
    return make_rules(tmp_path, {"charges.stt": text})


def write(tmp_path, body):
    (tmp_path / "golden").mkdir(exist_ok=True)
    (tmp_path / "golden" / "a.toml").write_text(body, encoding="utf-8")
    return load_cases(tmp_path / "golden")


CASE = '''
[[case]]
id = "stt-before"
kind = "rule_value"
source = "S1 test"
table = "charges.stt"
on = 2016-05-31
key = { seg = "eq" }
boundary = ["charges.stt[seg=eq]@2016-06-01:before"]
[case.expect]
value = "0.001"
'''


def test_rule_value_case_passes_and_reports_the_row_used(rules, tmp_path):
    (c,) = write(tmp_path, CASE)
    check_boundary_tags(c, run_case(rules, c))


def test_wrong_typed_value_fails(rules, tmp_path):
    (c,) = write(tmp_path, CASE.replace('value = "0.001"', 'value = "0.002"'))
    with pytest.raises(AssertionError, match="source says '0.002'"):
        run_case(rules, c)


def test_several_fields_and_non_numbers_are_compared(rules, tmp_path):
    body = CASE.replace("2016-05-31", "2016-06-01").replace('value = "0.001"', 'value = "0.00050"\nlist = [ "a", "b" ]')
    (c,) = write(tmp_path, body.replace('boundary = ["charges.stt[seg=eq]@2016-06-01:before"]\n', ""))
    run_case(rules, c)
    assert same("0.15", "0.150") and same(["a"], ["a"]) and not same(["a"], ["b"]) and same(True, True)


def test_a_case_on_the_wrong_side_fails_its_boundary_tag(rules, tmp_path):
    body = CASE.replace("on = 2016-05-31", "on = 2016-06-01").replace('value = "0.001"', 'value = "0.0005"')
    (c,) = write(tmp_path, body)
    with pytest.raises(AssertionError, match="did not use that row"):
        check_boundary_tags(c, run_case(rules, c))


def test_coverage_lists_every_missing_side_of_every_change(rules, tmp_path):
    assert list(all_boundaries(rules)) == [("charges.stt[seg=eq]", date(2016, 6, 1))]
    (c,) = write(tmp_path, CASE)
    assert missing_coverage(rules, [c]) == ["charges.stt[seg=eq]@2016-06-01:after"]


def test_cases_need_id_kind_source_and_unique_ids(tmp_path):
    with pytest.raises(ValueError, match="missing `source`"):
        write(tmp_path, '[[case]]\nid = "a"\nkind = "rule_value"\n')
    (tmp_path / "golden" / "a.toml").write_text(CASE + CASE, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_cases(tmp_path / "golden")


def test_skeleton_prints_a_tagged_case_on_each_side_of_a_change(rules):
    text = skeleton(rules, "charges.stt", ["value"])
    assert "on = 2016-05-31" in text and "on = 2016-06-01" in text
    assert 'boundary = ["charges.stt[seg=eq]@2016-06-01:before"]' in text
    assert 'value = ""' in text and text.count("[[case]]") == 2


def test_changes_lists_each_date_with_the_rules_that_change(rules):
    assert changes(rules, ("charges.",)) == ["2016-06-01: charges.stt[seg=eq]"]
    assert changes(rules, ("tax.",)) == []
```

`tests/test_golden.py` runs every real case and gates coverage of rule changes:

```python
"""Runs every hand-worked case in tests/golden against the real rules, and gates rule-change coverage."""
from pathlib import Path

import pytest

from engine.rules import Rules
from tests.golden_runner import KINDS, check_boundary_tags, load_cases, missing_coverage, run_case

ROOT = Path(__file__).resolve().parents[1]
RULES = Rules.load(ROOT / "rules")
CASES = load_cases(ROOT / "tests" / "golden")


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_golden_case(case):
    if case["kind"] not in KINDS:
        pytest.skip(f"kind {case['kind']!r} is not implemented yet")
    check_boundary_tags(case, run_case(RULES, case))


def test_every_rule_change_is_probed_on_both_sides():
    assert missing_coverage(RULES, CASES) == []
```

- [ ] **Step 2: Run them to see them fail**

Run: `python -m pytest tests/test_golden_runner.py tests/test_golden.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'tests.golden_runner'`.

- [ ] **Step 3: Implement**

`tests/golden_runner.py`:

```python
"""Golden cases: hand-worked expected values, checked against the engine and against the rule rows.

A case is a [[case]] table in tests/golden/*.toml. Every case needs `id`, `kind`, `source`.
Kinds register themselves below; a case's `boundary = ["<rule_id>@<YYYY-MM-DD>:before|after"]` says it
probes one side of a rule change, and the runner checks that the engine really used that row.
"""
from __future__ import annotations

import tomllib
from datetime import date, timedelta
from pathlib import Path

from engine.money import D
from engine.rules import Rules

KINDS: dict = {}


def kind(name):
    def deco(fn):
        KINDS[name] = fn
        return fn
    return deco


def load_cases(folder: Path) -> list[dict]:
    cases = []
    for p in sorted(Path(folder).glob("*.toml")):
        for c in tomllib.loads(p.read_text(encoding="utf-8")).get("case", []):
            for f in ("id", "kind", "source"):
                if f not in c:
                    raise ValueError(f"{p.name}: a case is missing `{f}`: {c}")
            c["file"] = p.name
            cases.append(c)
    ids = [c["id"] for c in cases]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate golden case ids: {sorted(dupes)}")
    return cases


def same(actual, expected) -> bool:
    """Numbers compare as exact decimals; anything else (text, dates, lists) by equality."""
    try:
        return D(actual) == D(expected)
    except (ArithmeticError, TypeError, ValueError):
        return actual == expected


@kind("rule_value")
def _rule_value(rules: Rules, c: dict):
    """Fields of a rule row on a date equal the values typed from the source. Returns the rule refs used."""
    row = rules.at(c["table"], c["on"], **c.get("key", {}))
    for field, want in c["expect"].items():
        assert same(row.data.get(field), want), f"{c['id']}: {field} is {row.data.get(field)!r}, source says {want!r}"
    return {row.ref}


def run_case(rules: Rules, c: dict):
    return KINDS[c["kind"]](rules, c)


def check_boundary_tags(c: dict, refs) -> None:
    """A tagged case must really have used the row on the named side of the change."""
    for tag in c.get("boundary", []):
        rid_day, phase = tag.rsplit(":", 1)
        rid, day = rid_day.rsplit("@", 1)
        d = date.fromisoformat(day)
        if phase == "after":
            ok = any(r.rule_id == rid and r.valid_from == d for r in refs)
        else:
            ok = any(r.rule_id == rid and r.valid_to == d - timedelta(days=1) for r in refs)
        assert ok, f"{c['id']}: tagged {tag} but the engine did not use that row"


def all_boundaries(rules: Rules):
    """Every (rule_id, change date) where one row ends and the next begins."""
    for t in rules.tables.values():
        for rows in t.groups.values():
            for a, b in zip(rows, rows[1:]):
                yield a.ref.rule_id, b.valid_from


def missing_coverage(rules: Rules, cases: list[dict]) -> list[str]:
    """Rule changes lacking a case on the day before or on the day of the change."""
    tagged = {t for c in cases for t in c.get("boundary", [])}
    return [f"{rid}@{d}:{phase}" for rid, d in all_boundaries(rules) for phase in ("before", "after")
            if f"{rid}@{d}:{phase}" not in tagged]
```

`tests/golden_skeleton.py`:

```python
"""Print skeleton golden cases for a rule table: structure filled in, values left for a human.

Usage: python -m tests.golden_skeleton charges.stt [field ...]   cases for one table
       python -m tests.golden_skeleton --changes fyers. charges.  every rule-change date, for planning cases
For every key it prints one case on each side of every rule change (tagged), or one case if the key has a
single row. Type the `expect` values from the SOURCE document, not from the rules file: that second typing
is what catches a wrong rate or a wrong date.
"""
from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

from engine.rules import Rules
from tests.golden_runner import all_boundaries

ROOT = Path(__file__).resolve().parents[1]


def skeleton(rules: Rules, name: str, fields: list[str]) -> str:
    out = []
    for key, rows in rules.tables[name].groups.items():
        kv = ", ".join(f'{k} = "{v}"' for k, v in key)
        rid = rows[0].ref.rule_id
        probes = [(rows[0].valid_from, None)] if len(rows) == 1 else []
        for a, b in zip(rows, rows[1:]):
            probes += [(b.valid_from - timedelta(days=1), f"{rid}@{b.valid_from}:before"),
                       (b.valid_from, f"{rid}@{b.valid_from}:after")]
        for on, tag in probes:
            cid = f"{name}-{'-'.join(v for _, v in key)}-{on}".replace("--", "-")
            tags = f'boundary = ["{tag}"]\n' if tag else ""
            exp = "".join(f'{f} = ""\n' for f in fields)
            out.append(f'[[case]]\nid = "{cid}"\nkind = "rule_value"\nsource = ""\ntable = "{name}"\n'
                       f'on = {on}\nkey = {{ {kv} }}\n{tags}[case.expect]\n{exp}')
    return "\n".join(out)


def changes(rules: Rules, prefixes: tuple[str, ...]) -> list[str]:
    """Each change date with the rules that change on it."""
    by_date: dict = {}
    for rid, d in all_boundaries(rules):
        if rid.startswith(prefixes):
            by_date.setdefault(d, []).append(rid)
    return [f"{d}: {', '.join(sorted(r))}" for d, r in sorted(by_date.items())]


if __name__ == "__main__":
    rules = Rules.load(ROOT / "rules")
    if sys.argv[1] == "--changes":
        print("\n".join(changes(rules, tuple(sys.argv[2:]))))
    else:
        print(skeleton(rules, sys.argv[1], sys.argv[2:] or ["value"]))
```

- [ ] **Step 4: Run the tests**

Run: `python -m pytest -q`
Expected: all pass; `tests/test_golden.py::test_golden_case` shows one skipped (no cases yet).

- [ ] **Step 5: Commit**

```bash
git add tests/golden_runner.py tests/golden_skeleton.py tests/test_golden_runner.py tests/test_golden.py
git commit -m "test: golden-case harness with a both-sides-of-every-change gate"
```

---

## Task 5: Research: Fyers fees

**Files:**
- Create: `rules/fyers/brokerage.toml`, `rules/fyers/dp.toml`, `rules/fyers/account.toml`, `tests/golden/fyers.toml`
- Modify: `rules/SOURCES.md`

**Interfaces:**
- Consumes: the loader and harness from Tasks 3 and 4; the Research protocol above.
- Produces: tables `fyers.brokerage[product]` (fields `mode`, `flat`, `pct`), `fyers.dp` (`value`), `fyers.account[fee]` (`value`), each covering 2010-04-01 onward with no gap, plus hand-typed `rule_value` cases on both sides of every change.

**Leads (unverified, from memory):** delivery brokerage is believed to be ₹0 today; futures believed ₹20 per executed order or 0.03%, whichever is lower (that is `mode = "min_flat_pct"`); a DP fee is charged per scrip on a delivery sale; the demat AMC may be zero or a yearly fee; Fyers likely began serving customers around 2015 to 2016.

- [ ] **Step 1: Load the web tools**

Run ToolSearch with `select:WebSearch,WebFetch`. Re-read the Research protocol.

- [ ] **Step 2: Record today's schedule**

Open `https://fyers.in/pricing/` (or search "Fyers pricing brokerage charges" if it moved). For equity delivery and index futures write down: brokerage rule, DP fee per scrip on sale, demat AMC, account-opening fee. Add a row to `rules/SOURCES.md` for the page with today's date as `retrieved`. If the page needs JavaScript, read it in a browser tab (protocol, Tools).

- [ ] **Step 3: Recover the history**

List snapshots: `https://web.archive.org/cdx/search/cdx?url=fyers.in/pricing*&output=json&fl=timestamp,original,statuscode,digest&collapse=digest&filter=statuscode:200`. Repeat for `fyers.in/brokerage*` and `fyers.in/charges*`. Read one snapshot per distinct page content and note the schedule and its timestamp. Search for Fyers announcements of fee changes to pin exact dates. Add each source to `rules/SOURCES.md` (the snapshot URL with its timestamp counts as the source).

- [ ] **Step 4: Find when Fyers started**

Find the date Fyers began serving customers (SEBI stock-broker registration date in SEBI's intermediary list, NSE membership date, company history). Everything before that date is a stand-in.

- [ ] **Step 5: Write the three tables**

Rows run from 2010-04-01 with no gap, per the template in the Research protocol.
- Before Fyers started: the earliest schedule found, `confidence = "assumed"`, note "Fyers not yet operating; earliest known schedule used as a stand-in".
- After: `primary` when Fyers itself states the date, `secondary` when the date is inferred from a snapshot window. For an inferred date set `from` to the first snapshot showing the new schedule and put the window (last snapshot with the old schedule, first with the new) in `note`.
- GST is not part of these rows; `charges.gst` adds it in Task 6. If Fyers' quoted DP fee already includes the depository's share, say so in the `note` of `fyers.dp`, so Task 6 sets `charges.dp_depository` to zero and nothing is counted twice.
- A one-time account-opening fee is not modelled in v1. If it is not zero, write it down in `rules/SOURCES.md` and tell the user.

- [ ] **Step 6: Write the golden cases**

Run each of `python -m tests.golden_skeleton fyers.brokerage mode flat pct`, `python -m tests.golden_skeleton fyers.dp`, `python -m tests.golden_skeleton fyers.account`. Save the output to `tests/golden/fyers.toml`. Fill `source` and every `expect` by typing from the source documents, not the rules files. Delete `flat` or `pct` lines that do not apply to a row's `mode`.

- [ ] **Step 7: Run the whole suite**

Run: `python -m pytest -q`
Expected: all pass (loader, source-id check, every case, and the both-sides-of-every-change gate). A failure names the row or the missing case.

- [ ] **Step 8: Commit**

```bash
git add rules tests/golden/fyers.toml
git commit -m "research: Fyers brokerage, DP and account fees by date"
```
Put every `assumed` and `secondary` row in the message body.

---

## Task 6: Research: statutory and exchange charges

**Files:**
- Create: `rules/charges/stt.toml`, `rules/charges/exchange_txn.toml`, `rules/charges/sebi.toml`, `rules/charges/ipft.toml`, `rules/charges/clearing.toml`, `rules/charges/stamp.toml`, `rules/charges/gst.toml`, `rules/charges/dp_depository.toml`, `tests/golden/charges_rules.toml`
- Modify: `rules/SOURCES.md`

**Interfaces:**
- Consumes: the loader, harness and protocol; the note in `fyers.dp` about depository fees.
- Produces: the eight `charges.*` tables in the catalogue, each gapless from 2010-04-01, with `rule_value` cases on both sides of every change. Fractions are of turnover: `0.00025` means 0.025%.

**Leads (unverified, from memory):**
- STT began 2004-10-01. Dates to check: 2012-07-01, 2013-06-01, 2016-06-01, 2024-10-01, 2026-04-01. Sales of equity-oriented fund units on an exchange are believed to carry 0.001%. Gold ETFs are believed to carry none.
- Service tax and GST on the broker's fees: 10.3% to 2012-03-31, 12.36% from 2012-04-01, 14% from 2015-06-01, 14.5% from 2015-11-15, 15% from 2016-06-01, GST at 18% from 2017-07-01.
- Stamp duty: uniform national rates from 2020-07-01 (believed 0.015% on a delivery buy, 0.002% on a futures buy, 0.005% on a mutual fund purchase); state-wise before.
- SEBI turnover fee is believed to be ₹10 per crore recently; earlier values differ. The exchange investor-protection charge (IPFT) began somewhere between 2019 and 2023. NSE transaction charges have been revised many times, and the SEBI reform of October 2024 to January 2025 changed how they are structured.

- [ ] **Step 1: Load the web tools and re-read the protocol**

Run ToolSearch with `select:WebSearch,WebFetch`. If NSE, SEBI or India Code block WebFetch, use the browser tools.

- [ ] **Step 2: Gather each table's full history from 2010-04-01**

- `charges.stt` (keys `instrument_class`, `side`): a row set for each of `etf_equity`, `etf_gold`, `mf_equity`, `mf_debt`, `fut_index` on `buy` and `sell`, with explicit `0` rows where no STT applies. Add `round_step` (`"1"` if the amount is rounded to the nearest rupee on contract notes; check).
- `charges.exchange_txn` (keys `exchange` = `NSE`, `segment` = `delivery` or `futures`): NSE cash-market and index-futures transaction charge as a fraction of turnover.
- `charges.sebi` (no key): SEBI turnover fee as a fraction.
- `charges.ipft` (keys `exchange`, `segment`): investor protection fund charge; explicit `0` rows before it existed.
- `charges.clearing` (key `segment`): clearing corporation charges, or explicit `0` rows.
- `charges.stamp` (keys `segment` = `delivery`, `futures`, `mf`; `side`): buy side carries the duty. Before 2020-07-01 duty was state-wise: use Maharashtra as the default state, `confidence = "assumed"`, and say so in `note`, unless the user names a state.
- `charges.gst` (no key): rate for each period and `applies_to`, the list of line names in the taxed base (from `brokerage`, `exchange_txn`, `sebi`, `ipft`, `clearing`, `dp`, `amc`). The base may differ before and after 2017-07-01.
- `charges.dp_depository` (no key): the depository's charge per delivery sale per ISIN per day, or `0` with a note if `fyers.dp` already includes it.
- CTT and BSE rates are not needed (see "Left out on purpose"). If you meet one that applies to an `etf_*` or `fut_index` order, stop and tell the user.

- [ ] **Step 3: Write the eight tables and add every source to `rules/SOURCES.md`**

Use the template in the Research protocol. Remember `coverage_from = 2010-04-01` and gapless rows per key.

- [ ] **Step 4: Write the golden cases**

For each table run `python -m tests.golden_skeleton <table> value` (for `charges.gst` use `value applies_to`; for `charges.stt` also pass `round_step`). Save the output into `tests/golden/charges_rules.toml`. Fill `source` and every `expect` from the source documents, typing them fresh.

- [ ] **Step 5: Run the whole suite**

Run: `python -m pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add rules tests/golden/charges_rules.toml
git commit -m "research: STT, exchange, SEBI, IPFT, clearing, stamp, GST and depository charges by date"
```
List every `assumed` and `secondary` row in the message body.

---

## Task 7: Research: capital-gains tax rules

**Files:**
- Create: `rules/tax/buckets.toml`, `rules/tax/capital_gains.toml`, `rules/tax/cii.toml`, `rules/tax/lt_exemption.toml`, `rules/tax/dividend.toml`, `rules/tax/loss_rules.toml`, `tests/golden/tax_gains_rules.toml`
- Modify: `rules/SOURCES.md`

**Interfaces:**
- Consumes: the loader, harness and protocol.
- Produces: the six `tax.*` tables named, gapless from 2010-04-01. `tax.buckets` rows are dated by **acquisition** date; `tax.capital_gains` rows by **sale** date. `tax.loss_rules` holds only `kind = "capital"` now (Task 14 adds `business`).

**Leads (unverified, from memory):**
- Section 10(38) exempted long-term gains on STT-paid equity until 2018-03-31. Section 112A taxed them from 2018-04-01 at 10% above ₹1 lakh, with grandfathering to the value on 2018-01-31 (section 55(2)(ac); for listed units the highest price quoted that day). From 2024-07-23 the rates changed: short-term 20%, long-term 12.5% above ₹1.25 lakh.
- Short-term rate under section 111A is believed to have been 15% before 2024-07-23 (an earlier 10% rate predates 2010; check). Holding period for listed equity and equity funds: more than 12 months.
- Gold ETFs and other non-equity units: long-term after 36 months with indexation at 20% before 2024-07-23; new period and rate after (check whether 12 or 24 months). Debt funds bought on or after 2023-04-01: section 50AA, taxed as short-term at slab rates whatever the holding period (the definition of a specified fund changed from 2025-04-01).
- Dividends: company-paid tax era to FY2019-20, with section 115BBDA (10% on the part above ₹10 lakh) for FY2016-17 to FY2019-20; slab rates from FY2020-21. Losses carry forward 8 years.

- [ ] **Step 1: Load the web tools and re-read the protocol**

Run ToolSearch with `select:WebSearch,WebFetch`.

- [ ] **Step 2: Gather**

- The capital-gains regime by asset class and sale date for the five classes: `etf_equity` and `mf_equity` (equity-oriented), `etf_gold`, `mf_debt` (and note that `fut_index` is not a capital asset, so it is not here). For each period: `lt_months`, whether the asset is `always_short`, short-term and long-term treatment (`special`, `slab`, `exempt`), rates, section names, whether indexation applies, the exemption group, and the grandfathering cutoff date.
- Which bucket each class falls in by acquisition date (for example debt funds before and after 2023-04-01).
- The yearly long-term-gains exemption in rupees by financial year, and **the order it is applied against gains taxed at two different rates in one year** (financial year 2024-25). Look for a CBDT circular, the ITR utility's behaviour or an authoritative explainer. If nothing is found, use `lowest_rate_first` (the less favourable to the taxpayer) as `assumed`, and tell the user.
- The cost inflation index for every financial year from FY2010-11 (CBDT notifications).
- The dividend-tax rule by year: `mode` `exempt`, `above_threshold` (with `threshold` and `rate`) or `slab`.
- Years a capital loss may be carried forward.

- [ ] **Step 3: Write the six tables and add sources**

Naming: bucket names are yours to choose (`equity`, `gold`, `debt_pre_apr2023`, `debt_post_apr2023`, or others the research needs). Every bucket named in `tax.buckets` must have `tax.capital_gains` rows covering all sale dates from 2010-04-01. `tax.cii` has one row per financial year, dated 1 April to 31 March, the last one open-ended. Use TOML native booleans (`indexation = true`) and native dates (`grandfather_acq_upto = 2018-01-31`); rates and rupee amounts stay strings.

- [ ] **Step 4: Write the golden cases**

Run the skeleton for each table and fill from the sources:

```text
python -m tests.golden_skeleton tax.buckets bucket
python -m tests.golden_skeleton tax.capital_gains lt_months always_short st_treatment st_rate st_section lt_treatment lt_rate lt_section indexation lt_exemption_group grandfather_acq_upto
python -m tests.golden_skeleton tax.cii value
python -m tests.golden_skeleton tax.lt_exemption value order
python -m tests.golden_skeleton tax.dividend mode threshold rate
python -m tests.golden_skeleton tax.loss_rules value
```
Delete the `expect` lines a row does not have (a row with no `indexation` field must not list it). Save to `tests/golden/tax_gains_rules.toml`.

- [ ] **Step 5: Run the whole suite**

Run: `python -m pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add rules tests/golden/tax_gains_rules.toml
git commit -m "research: capital-gains, indexation, exemption, dividend and loss-carry rules by date"
```
List every `assumed` and `secondary` row in the message body.

---

## Task 8: Research: slabs, rebate, surcharge, cess, conventions

**Files:**
- Create: `rules/tax/slabs.toml`, `rules/tax/rebate_87a.toml`, `rules/tax/surcharge.toml`, `rules/tax/cess.toml`, `rules/tax/conventions.toml`, `tests/golden/tax_slab_rules.toml`
- Modify: `rules/SOURCES.md`

**Interfaces:**
- Consumes: the loader, harness and protocol.
- Produces: the five tables, gapless from 2010-04-01. Rows are dated by **financial year** (1 April to 31 March). `regime = "new"` exists only from FY2020-21: declare it with `late_keys` in `[meta]` (syntax in the Research protocol).

**Leads (unverified, from memory):** cess 3% to FY2017-18 and 4% from FY2018-19. The new tax regime began in FY2020-21 and became the default later; its slabs and the section 87A rebate limit were raised in several budgets. Surcharge on gains taxed at special rates is capped at 15%; the new regime's top surcharge is capped at 25% from FY2023-24. Section 288B rounds tax to the nearest ₹10.

- [ ] **Step 1: Load the web tools and re-read the protocol**

Run ToolSearch with `select:WebSearch,WebFetch`.

- [ ] **Step 2: Gather, for a resident individual under 60**

- Slab brackets for each financial year, old regime and (from FY2020-21) new regime, including later revisions. Record as `brackets = [ {upto = "250000", rate = "0"}, ..., {upto = "", rate = "0.30"} ]` in order, the last with `upto = ""`. The first bracket must be the nil-rate band (its limit is the basic exemption used by the engine).
- Section 87A rebate by year and regime: `income_limit`, `max_rebate`, whether it applies against tax on special-rate gains (`applies_to_special`), and whether marginal relief applies just above the limit (`marginal_relief`).
- Surcharge tiers by regime and year (`tiers = [ {above = "5000000", rate = "0.10"}, ... ]`, ascending) and any cap on the surcharge for special-rate gains (`cap_special`).
- Health and education cess rate (a `value` fraction).
- Conventions (`tax.conventions`, key `name`): `tax_round_step` = `"10"` with the section 288B source (`primary`); `setoff_order` and `shortfall_order` describe what `engine/tax.py` does, `confidence = "assumed"`, `value = "as coded in engine/tax.py"` and a `note` in words: for `setoff_order`, "this year's short-term loss on short-term gains, long-term loss on long-term gains, leftover short-term loss on long-term gains, then losses brought forward, highest special rate first, then slab-taxed gains"; for `shortfall_order`, "a resident's unused basic exemption is applied to special-rate gains, highest rate first". If a source settles either order, cite it as `primary`; if it contradicts the code, stop and tell the user before Task 12.

- [ ] **Step 3: Write the five tables and add sources**

Rows are per financial year or per run of unchanged years. Every regime/year must be covered, and `late_keys` marks `new`.

- [ ] **Step 4: Write the golden cases**

```text
python -m tests.golden_skeleton tax.slabs brackets
python -m tests.golden_skeleton tax.rebate_87a income_limit max_rebate applies_to_special marginal_relief
python -m tests.golden_skeleton tax.surcharge tiers cap_special
python -m tests.golden_skeleton tax.cess value
python -m tests.golden_skeleton tax.conventions value
```
Type brackets and tiers as TOML lists of inline tables inside `[case.expect]`, from the source. Save to `tests/golden/tax_slab_rules.toml`.

- [ ] **Step 5: Run the whole suite**

Run: `python -m pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add rules tests/golden/tax_slab_rules.toml
git commit -m "research: slabs, rebate, surcharge, cess and tax conventions by financial year"
```
List every `assumed` and `secondary` row in the message body.

---

## Task 9: Charges engine

**Files:**
- Create: `engine/charges.py`, `tests/synth_charges.py`, `tests/test_charges.py`, `tests/test_golden_kinds_charges.py`, `tests/test_gates.py`, `tests/golden/charges_engine.toml`
- Modify: `tests/golden_runner.py` (append three kinds)

**Interfaces:**
- Consumes: `Rules.at(table, on, **key) -> Row` (Task 3); `Node`, `const`, `from_rule`, `add`, `mul`, `minn`, `rnd` (Task 2); `KINDS`, `kind`, `same`, `D` (Task 4); real tables from Tasks 5 and 6.
- Produces: `Order(on, instrument_class, side, qty, price)` (frozen, validated); `Charges(total, lines, deductible, turnover)` where `lines` maps `brokerage`, `stt`, `exchange_txn`, `sebi`, `ipft`, `clearing`, `stamp`, `gst` to `Node`s (mutual funds have only `stt`, `stamp`, `gst`); `order_charges(rules, order) -> Charges`; `dp_charge(rules, on) -> Node`; `amc_fee(rules, on) -> Node`; tag constant `DEDUCTIBLE = "cg_deductible"` (every line except STT, which a capital gain may not deduct); golden kinds `charges` (`[case.input]` `on`, `instrument_class`, `side`, `qty`, `price`; `[case.expect]` any line name, `total`, `deductible` or `turnover`), `dp` and `amc` (`[case.input]` `on`; `[case.expect]` `total`).

- [ ] **Step 1: Write the failing tests**

`tests/synth_charges.py` (made-up round-number rules, used only by tests):

```python
"""Made-up round-number charge rules. They test the engine's logic, never real rates."""
from tests.helpers import table

GST_ALL = '["brokerage", "exchange_txn", "sebi", "ipft", "clearing", "dp", "amc"]'

CHARGES = {
    "fyers.brokerage": table(["product"], [
        'product = "delivery"\nfrom = 2010-04-01\nmode = "zero"',
        'product = "futures"\nfrom = 2010-04-01\nmode = "min_flat_pct"\nflat = "20"\npct = "0.0003"',
    ]),
    "charges.stt": table(["instrument_class", "side"], [
        'instrument_class = "etf_equity"\nside = "buy"\nfrom = 2010-04-01\nvalue = "0"\nround_step = "1"',
        'instrument_class = "etf_equity"\nside = "sell"\nfrom = 2010-04-01\nto = 2015-12-31\nvalue = "0.001"\nround_step = "1"',
        'instrument_class = "etf_equity"\nside = "sell"\nfrom = 2016-01-01\nvalue = "0.0005"\nround_step = "1"',
        'instrument_class = "fut_index"\nside = "buy"\nfrom = 2010-04-01\nvalue = "0"\nround_step = "1"',
        'instrument_class = "fut_index"\nside = "sell"\nfrom = 2010-04-01\nvalue = "0.0002"\nround_step = "1"',
        'instrument_class = "mf_equity"\nside = "buy"\nfrom = 2010-04-01\nvalue = "0"\nround_step = "1"',
        'instrument_class = "mf_equity"\nside = "sell"\nfrom = 2010-04-01\nvalue = "0.00001"\nround_step = "0.01"',
    ]),
    "charges.exchange_txn": table(["exchange", "segment"], [
        'exchange = "NSE"\nsegment = "delivery"\nfrom = 2010-04-01\nvalue = "0.00003"',
        'exchange = "NSE"\nsegment = "futures"\nfrom = 2010-04-01\nvalue = "0.00002"',
    ]),
    "charges.sebi": table([], ['from = 2010-04-01\nvalue = "0.000001"']),
    "charges.ipft": table(["exchange", "segment"], [
        'exchange = "NSE"\nsegment = "delivery"\nfrom = 2010-04-01\nvalue = "0"',
        'exchange = "NSE"\nsegment = "futures"\nfrom = 2010-04-01\nvalue = "0"',
    ]),
    "charges.clearing": table(["segment"], [
        'segment = "delivery"\nfrom = 2010-04-01\nvalue = "0"',
        'segment = "futures"\nfrom = 2010-04-01\nvalue = "0"',
    ]),
    "charges.stamp": table(["segment", "side"], [
        'segment = "delivery"\nside = "buy"\nfrom = 2010-04-01\nvalue = "0.00015"',
        'segment = "delivery"\nside = "sell"\nfrom = 2010-04-01\nvalue = "0"',
        'segment = "futures"\nside = "buy"\nfrom = 2010-04-01\nvalue = "0.00002"',
        'segment = "futures"\nside = "sell"\nfrom = 2010-04-01\nvalue = "0"',
        'segment = "mf"\nside = "buy"\nfrom = 2010-04-01\nvalue = "0.00005"',
        'segment = "mf"\nside = "sell"\nfrom = 2010-04-01\nvalue = "0"',
    ]),
    "charges.gst": table([], [f'from = 2010-04-01\nvalue = "0.18"\napplies_to = {GST_ALL}']),
    "fyers.dp": table([], ['from = 2010-04-01\nvalue = "13"']),
    "charges.dp_depository": table([], ['from = 2010-04-01\nvalue = "3.5"']),
    "fyers.account": table(["fee"], ['fee = "amc_annual"\nfrom = 2010-04-01\nvalue = "300"']),
}
```

`tests/test_charges.py`:

```python
from datetime import date
from decimal import Decimal as Dc

import pytest

from engine.charges import Order, amc_fee, dp_charge, order_charges
from engine.rules import RuleNotFound
from engine.trace import assert_balanced
from tests.helpers import make_rules
from tests.synth_charges import CHARGES


@pytest.fixture
def rules(tmp_path):
    return make_rules(tmp_path, CHARGES)


def order(on, cls, side, qty, price):
    return Order(date.fromisoformat(on), cls, side, Dc(qty), Dc(price))


def test_etf_sell_lines_and_totals(rules):
    c = order_charges(rules, order("2015-06-01", "etf_equity", "sell", "100", "850.55"))
    assert c.turnover.value == Dc("85055.00")
    assert {k: v.value for k, v in c.lines.items()} == {
        "brokerage": Dc("0.00"), "stt": Dc("85"),          # 0.001 x 85055 = 85.055 -> rupee
        "exchange_txn": Dc("2.55"), "sebi": Dc("0.09"),    # 2.55165 / 0.085055 -> paise
        "ipft": Dc("0.00"), "clearing": Dc("0.00"), "stamp": Dc("0.00"),
        "gst": Dc("0.48"),                                  # 18% of (2.55 + 0.09) = 0.4752
    }
    assert c.total.value == Dc("88.12")
    assert c.deductible.value == Dc("3.12")  # everything except STT
    assert_balanced(c.total)


def test_rate_change_takes_effect_on_its_date(rules):
    before = order_charges(rules, order("2015-12-31", "etf_equity", "sell", "100", "1000"))
    after = order_charges(rules, order("2016-01-01", "etf_equity", "sell", "100", "1000"))
    assert before.lines["stt"].value == Dc("100") and after.lines["stt"].value == Dc("50")


def test_buy_side_pays_stamp_not_stt(rules):
    c = order_charges(rules, order("2020-01-01", "etf_equity", "buy", "100", "850.55"))
    assert c.lines["stt"].value == 0 and c.lines["stamp"].value == Dc("12.76")


@pytest.mark.parametrize("price, expect", [("1000", "20"), ("200", "6")])
def test_futures_brokerage_is_lower_of_flat_and_percent(rules, price, expect):
    c = order_charges(rules, order("2020-01-01", "fut_index", "buy", "100", price))
    assert c.lines["brokerage"].value == Dc(expect)  # 0.03% of 100000 = 30 -> 20 ; of 20000 = 6


def test_mutual_fund_has_no_broker_or_exchange_lines(rules):
    c = order_charges(rules, order("2021-01-01", "mf_equity", "sell", "10.5", "250"))
    assert set(c.lines) == {"stt", "stamp", "gst"}
    assert c.lines["stt"].value == Dc("0.03")  # 0.00001 x 2625 = 0.02625


def test_dp_and_amc_include_gst(rules):
    assert dp_charge(rules, date(2020, 1, 1)).value == Dc("19.47")   # (13 + 3.5) x 1.18
    assert amc_fee(rules, date(2020, 3, 31)).value == Dc("354.00")   # 300 x 1.18


@pytest.mark.parametrize("bad", [
    dict(qty="0", price="10"), dict(qty="-1", price="10"), dict(qty="1", price="0"),
])
def test_non_positive_inputs_are_refused(bad):
    with pytest.raises(ValueError):
        order("2020-01-01", "etf_equity", "buy", **bad)


def test_unknown_class_and_side_are_refused():
    with pytest.raises(ValueError):
        order("2020-01-01", "bitcoin", "buy", "1", "1")
    with pytest.raises(ValueError):
        order("2020-01-01", "etf_equity", "hold", "1", "1")


def test_a_date_with_no_rule_raises(rules):
    with pytest.raises(RuleNotFound):
        order_charges(rules, order("2009-01-01", "etf_equity", "buy", "1", "1"))
```

`tests/test_golden_kinds_charges.py`:

```python
import pytest

from tests.golden_runner import check_boundary_tags, load_cases, run_case
from tests.helpers import make_rules
from tests.synth_charges import CHARGES

CHARGES_CASE = '''
[[case]]
id = "etf-sell-after-stt-cut"
kind = "charges"
source = "test"
work = "turnover 100 x 1000 = 100000; STT 0.0005 x 100000 = 50"
boundary = ["charges.stt[instrument_class=etf_equity,side=sell]@2016-01-01:after"]
[case.input]
on = 2016-01-01
instrument_class = "etf_equity"
side = "sell"
qty = "100"
price = "1000"
[case.expect]
stt = "50"
'''

def load(tmp_path, body):
    (tmp_path / "golden").mkdir()
    (tmp_path / "golden" / "a.toml").write_text(body, encoding="utf-8")
    return load_cases(tmp_path / "golden")


def test_charges_case_runs_and_its_boundary_tag_checks(tmp_path):
    rules = make_rules(tmp_path / "r", CHARGES)
    (c,) = load(tmp_path, CHARGES_CASE)
    check_boundary_tags(c, run_case(rules, c))


def test_a_wrong_hand_calculation_fails(tmp_path):
    rules = make_rules(tmp_path / "r", CHARGES)
    (c,) = load(tmp_path, CHARGES_CASE.replace('stt = "50"', 'stt = "51"'))
    with pytest.raises(AssertionError, match="hand-worked 51"):
        run_case(rules, c)


DP_AMC_CASE = '''
[[case]]
id = "dp-2020"
kind = "dp"
source = "test"
[case.input]
on = 2020-01-01
[case.expect]
total = "19.47"

[[case]]
id = "amc-2020"
kind = "amc"
source = "test"
[case.input]
on = 2020-03-31
[case.expect]
total = "354"
'''


def test_dp_and_amc_cases_run(tmp_path):
    rules = make_rules(tmp_path / "r", CHARGES)
    for c in load(tmp_path, DP_AMC_CASE):
        run_case(rules, c)
```

- [ ] **Step 2: Run them to see them fail**

Run: `python -m pytest tests/test_charges.py tests/test_golden_kinds_charges.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'engine.charges'`.

- [ ] **Step 3: Implement the engine**

`engine/charges.py`:

```python
"""Charges on one order, each line a trace node. Rates come only from rules/."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from engine.rules import Rules
from engine.trace import Node, add, const, from_rule, minn, mul, rnd

SEGMENT = {"etf_equity": "delivery", "etf_gold": "delivery", "fut_index": "futures",
           "mf_equity": "mf", "mf_debt": "mf"}
EXCHANGE = "NSE"
DEDUCTIBLE = "cg_deductible"  # tag: may be deducted from a capital gain (STT may not)
PAISE = "0.01"


@dataclass(frozen=True)
class Order:
    on: date
    instrument_class: str
    side: str  # buy | sell
    qty: Decimal
    price: Decimal

    def __post_init__(self):
        if self.instrument_class not in SEGMENT:
            raise ValueError(f"unknown instrument_class {self.instrument_class!r}")
        if self.side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        if self.qty <= 0 or self.price <= 0:
            raise ValueError("qty and price must be positive")


@dataclass(frozen=True)
class Charges:
    total: Node
    lines: dict[str, Node]
    deductible: Node
    turnover: Node


def _step(row) -> Node:
    return from_rule("Rounding step", row.data.get("round_step", PAISE), row.ref)


def _rate_line(rules: Rules, table: str, on: date, label: str, base: Node, tags, **key) -> Node:
    row = rules.at(table, on, **key)
    raw = mul(f"{label} before rounding", base, from_rule(f"{label} rate", row.value, row.ref))
    return rnd(label, raw, _step(row), tags=tags)


def _brokerage(rules: Rules, on: date, product: str, turnover: Node) -> Node:
    row = rules.at("fyers.brokerage", on, product=product)
    mode = row.data["mode"]

    def flat():
        return from_rule("Brokerage flat fee per order", row.dec("flat"), row.ref)

    def pct():
        return mul("Brokerage at % of turnover", turnover,
                   from_rule("Brokerage rate", row.dec("pct"), row.ref))

    if mode == "zero":
        raw = from_rule("Brokerage (none on this plan)", 0, row.ref)
    elif mode == "flat":
        raw = flat()
    elif mode == "pct":
        raw = pct()
    elif mode == "min_flat_pct":
        raw = minn("Brokerage: lower of flat fee and % of turnover", flat(), pct())
    else:
        raise ValueError(f"unknown brokerage mode {mode!r} in {row.ref.rule_id}")
    return rnd("Brokerage", raw, _step(row), tags={DEDUCTIBLE})


def _gst(rules: Rules, on: date, lines: dict[str, Node]) -> Node:
    row = rules.at("charges.gst", on)
    base = add("GST base", *[lines[k] for k in row.data["applies_to"] if k in lines])
    raw = mul("GST before rounding", base, from_rule("GST rate", row.value, row.ref))
    return rnd("GST", raw, _step(row), tags={DEDUCTIBLE})


def order_charges(rules: Rules, o: Order) -> Charges:
    seg = SEGMENT[o.instrument_class]
    turnover = mul("Turnover", const("Quantity", o.qty), const("Price", o.price))
    lines: dict[str, Node] = {}
    if seg != "mf":  # mutual funds are bought from the fund house: no broker, no exchange
        lines["brokerage"] = _brokerage(rules, o.on, seg, turnover)
    lines["stt"] = _rate_line(rules, "charges.stt", o.on, "STT", turnover, {"stt"},
                              instrument_class=o.instrument_class, side=o.side)
    if seg != "mf":
        lines["exchange_txn"] = _rate_line(rules, "charges.exchange_txn", o.on,
                                           "Exchange transaction charges", turnover, {DEDUCTIBLE},
                                           exchange=EXCHANGE, segment=seg)
        lines["sebi"] = _rate_line(rules, "charges.sebi", o.on, "SEBI turnover fee", turnover,
                                   {DEDUCTIBLE})
        lines["ipft"] = _rate_line(rules, "charges.ipft", o.on, "Investor protection fund charge",
                                   turnover, {DEDUCTIBLE}, exchange=EXCHANGE, segment=seg)
        lines["clearing"] = _rate_line(rules, "charges.clearing", o.on, "Clearing charges",
                                       turnover, {DEDUCTIBLE}, segment=seg)
    lines["stamp"] = _rate_line(rules, "charges.stamp", o.on, "Stamp duty", turnover, {DEDUCTIBLE},
                                segment=seg, side=o.side)
    lines["gst"] = _gst(rules, o.on, lines)
    total = add("Total charges", *lines.values())
    deductible = add("Charges deductible from capital gains",
                     *[n for n in lines.values() if DEDUCTIBLE in n.tags])
    return Charges(total, lines, deductible, turnover)


def dp_charge(rules: Rules, on: date) -> Node:
    """Depository fees for one delivery sale of one ISIN on one day, GST included."""
    broker, depo = rules.at("fyers.dp", on), rules.at("charges.dp_depository", on)
    fees = add("DP fees", from_rule("Broker DP fee", broker.value, broker.ref),
               from_rule("Depository fee", depo.value, depo.ref))
    return add("DP charges on this sale", fees, _gst(rules, on, {"dp": fees}), tags={DEDUCTIBLE})


def amc_fee(rules: Rules, on: date) -> Node:
    """Yearly demat account maintenance fee, GST included."""
    row = rules.at("fyers.account", on, fee="amc_annual")
    fee = from_rule("Demat AMC for the year", row.value, row.ref)
    return add("Demat AMC with GST", fee, _gst(rules, on, {"amc": fee}))
```

- [ ] **Step 4: Register the golden kinds**

Append this to the end of `tests/golden_runner.py`, after two blank lines:

```python

@kind("charges")
def _charges(rules: Rules, c: dict):
    """Order charges: each named line, `total`, `deductible` or `turnover` equals the hand-worked value."""
    from engine.charges import Order, order_charges
    from engine.trace import assert_balanced, rules_used
    i = c["input"]
    ch = order_charges(rules, Order(i["on"], i["instrument_class"], i["side"], D(i["qty"]), D(i["price"])))
    named = {**ch.lines, "total": ch.total, "deductible": ch.deductible, "turnover": ch.turnover}
    for name, want in c["expect"].items():
        assert same(named[name].value, want), f"{c['id']}: {name} is {named[name].value}, hand-worked {want}"
    assert_balanced(ch.total)
    return rules_used(ch.total)


@kind("dp")
def _dp(rules: Rules, c: dict):
    from engine.charges import dp_charge
    from engine.trace import assert_balanced, rules_used
    n = dp_charge(rules, c["input"]["on"])
    assert same(n.value, c["expect"]["total"]), f"{c['id']}: total is {n.value}, hand-worked {c['expect']['total']}"
    assert_balanced(n)
    return rules_used(n)


@kind("amc")
def _amc(rules: Rules, c: dict):
    from engine.charges import amc_fee
    from engine.trace import assert_balanced, rules_used
    n = amc_fee(rules, c["input"]["on"])
    assert same(n.value, c["expect"]["total"]), f"{c['id']}: total is {n.value}, hand-worked {c['expect']['total']}"
    assert_balanced(n)
    return rules_used(n)
```

- [ ] **Step 5: Run the tests**

Run: `python -m pytest -q`
Expected: all pass.

- [ ] **Step 6: Write the row-coverage gate**

`tests/test_gates.py`:

```python
"""Gates that keep the golden cases honest. FAMILIES grows as the engine tasks land."""
from pathlib import Path

from engine.rules import Rules
from tests.golden_runner import KINDS, load_cases, run_case

ROOT = Path(__file__).resolve().parents[1]
RULES = Rules.load(ROOT / "rules")
CASES = load_cases(ROOT / "tests" / "golden")
FAMILIES = ("fyers.", "charges.")  # Task 12 adds "tax."


def test_every_row_is_exercised_by_a_hand_worked_engine_case():
    used = set()
    for c in CASES:
        if c["kind"] != "rule_value" and c["kind"] in KINDS:
            used |= {(r.rule_id, r.valid_from) for r in run_case(RULES, c)}
    rows = {(r.ref.rule_id, r.valid_from) for r in RULES.all_rows() if r.table.startswith(FAMILIES)}
    assert not rows - used, f"rows no engine case exercises: {sorted(rows - used)[:25]}"


def test_no_case_uses_a_kind_the_runner_lacks():
    assert {c["kind"] for c in CASES} <= set(KINDS)
```

Run: `python -m pytest tests/test_gates.py -q`
Expected: FAIL, listing the `fyers.*` and `charges.*` rows that no engine case exercises. This list is your work list for Step 7.

- [ ] **Step 7: Write the composition cases**

These check that the engine composes the real rates correctly. Each is worked by hand from the source rates (type the rates fresh from `rules/SOURCES.md` documents). Create `tests/golden/charges_engine.toml`. Format (rates here are made up):

```toml
[[case]]
id = "etf-sell-2016-05-31"
kind = "charges"
source = "S3 rate card; hand-worked"
work = "turnover 100 x 1000 = 100000; STT 0.0005 x 100000 = 50 -> Rs 50; exchange 0.00003 x 100000 = 3.00; ..."
[case.input]
on = 2016-05-31
instrument_class = "etf_equity"
side = "sell"
qty = "100"
price = "1000"
[case.expect]
stt = "50"
exchange_txn = "3.00"
total = "56.10"
```

Print every change date with `python -m tests.golden_skeleton --changes fyers. charges.`. It lists each date with the rules that change on it. Write:
- **Change-date pairs.** For each date D and each rule id listed for D: one case on the day before D and one on D, using an order that reads that rule (for `charges.stt[instrument_class=etf_equity,side=sell]` an `etf_equity` sell; qty 100, price 1000, so turnover is ₹1,00,000). In `expect` list only the line the rule feeds (`stt`, `exchange_txn`, `sebi`, `ipft`, `clearing`, `stamp`, `brokerage`, or `gst` for a `charges.gst` change). The runner accepts a partial `expect`.
- **Full-line cases.** About ten cases with every line and `total` in `expect`, for `etf_equity` and `fut_index`, buy and sell, spread across 2010 to 2026 and including a day either side of 2017-07-01 (service tax to GST) and 2020-07-01 (stamp duty), whichever of those the rules show as change dates.
- **`dp` and `amc` pairs.** A case on the day before and the day of each change of `fyers.dp`, `charges.dp_depository`, `fyers.account` and `charges.gst`.
- Put the arithmetic in `work` so a reviewer can follow it.

Re-run `python -m pytest tests/test_gates.py tests/test_golden.py -q` until it passes. If a hand-worked value disagrees with the engine, find out which is wrong: check the rule row against its source first. Never edit an `expect` to match the engine without a source that says so.

- [ ] **Step 8: Commit**

```bash
git add engine/charges.py tests
git commit -m "feat: per-order charges with a trace line for each, and golden composition cases"
```

---

## Task 10: FIFO lots

**Files:**
- Create: `engine/lots.py`
- Test: `tests/test_lots.py`

**Interfaces:**
- Consumes: `Node`, `const`, `div`, `mul`, `sub` (Task 2).
- Produces: `Lot`, `Slice(acq_date, qty, cost: Node)`, `Inventory` with `units(instrument) -> Decimal`, `buy(instrument, acq_date, qty, cost: Node)`, `sell(instrument, qty) -> list[Slice]` (oldest first, raises `ValueError` on zero, negative or more than held), `split(instrument, ratio)`.

- [ ] **Step 1: Write the failing test**

`tests/test_lots.py`:

```python
from datetime import date
from decimal import Decimal as Dc

import pytest

from engine.lots import Inventory
from engine.trace import assert_balanced, const


def inv_with_two_lots():
    inv = Inventory()
    inv.buy("X", date(2020, 1, 1), Dc("10"), const("cost1", "1000"))
    inv.buy("X", date(2021, 1, 1), Dc("10"), const("cost2", "3000"))
    return inv


def test_fifo_takes_oldest_first_and_splits_cost_exactly():
    inv = inv_with_two_lots()
    first = inv.sell("X", Dc("4"))
    assert [(s.acq_date, s.qty, s.cost.value) for s in first] == [(date(2020, 1, 1), Dc("4"), Dc("400"))]
    second = inv.sell("X", Dc("8"))   # 6 left of lot 1, then 2 of lot 2
    assert [(s.acq_date, s.qty) for s in second] == [(date(2020, 1, 1), Dc("6")), (date(2021, 1, 1), Dc("2"))]
    assert [s.cost.value for s in second] == [Dc("600"), Dc("600")]
    assert inv.units("X") == Dc("8")
    for s in first + second:
        assert_balanced(s.cost)


def test_cost_of_sold_plus_kept_equals_original_even_when_not_divisible():
    inv = Inventory()
    inv.buy("X", date(2020, 1, 1), Dc("3"), const("cost", "100"))
    sold = inv.sell("X", Dc("1"))[0].cost.value
    kept = inv.sell("X", Dc("2"))[0].cost.value
    assert sold + kept == Dc("100")


def test_cannot_sell_more_than_held_or_zero():
    inv = inv_with_two_lots()
    with pytest.raises(ValueError, match="only 20"):
        inv.sell("X", Dc("21"))
    with pytest.raises(ValueError):
        inv.sell("X", Dc("0"))
    with pytest.raises(ValueError):
        Inventory().sell("nothing", Dc("1"))


def test_split_multiplies_units_and_keeps_cost_and_dates():
    inv = inv_with_two_lots()
    inv.split("X", Dc("2"))
    s = inv.sell("X", Dc("20"))[0]
    assert (s.acq_date, s.qty, s.cost.value) == (date(2020, 1, 1), Dc("20"), Dc("1000"))
```

- [ ] **Step 2: Run it to see it fail**

Run: `python -m pytest tests/test_lots.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'engine.lots'`.

- [ ] **Step 3: Implement**

`engine/lots.py`:

```python
"""FIFO lots. Cost is a trace node, so a sale's cost basis can be explained."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from engine.trace import Node, const, div, mul, sub


@dataclass(frozen=True)
class Lot:
    acq_date: date
    qty: Decimal
    cost: Node  # total cost of acquisition of `qty` units, buy-side deductible charges included


@dataclass(frozen=True)
class Slice:
    acq_date: date
    qty: Decimal
    cost: Node


class Inventory:
    def __init__(self):
        self._lots: dict[str, list[Lot]] = {}

    def units(self, instrument: str) -> Decimal:
        return sum((lot.qty for lot in self._lots.get(instrument, [])), Decimal(0))

    def buy(self, instrument: str, acq_date: date, qty: Decimal, cost: Node) -> None:
        if qty <= 0:
            raise ValueError("qty must be positive")
        self._lots.setdefault(instrument, []).append(Lot(acq_date, qty, cost))

    def sell(self, instrument: str, qty: Decimal) -> list[Slice]:
        """Take `qty` units oldest-first. Raises rather than going short."""
        if qty <= 0:
            raise ValueError("qty must be positive")
        held = self.units(instrument)
        if qty > held:
            raise ValueError(f"cannot sell {qty} {instrument}: only {held} held")
        lots, out, need = self._lots[instrument], [], qty
        while need > 0:
            lot = lots[0]
            if lot.qty <= need:
                out.append(Slice(lot.acq_date, lot.qty, lot.cost))
                need -= lot.qty
                lots.pop(0)
                continue
            share = div("Share of lot sold", const("Units sold", need), const("Units in lot", lot.qty))
            sold = mul(f"Cost of {need} units from the {lot.acq_date} lot", lot.cost, share)
            lots[0] = Lot(lot.acq_date, lot.qty - need, sub("Cost of units kept", lot.cost, sold))
            out.append(Slice(lot.acq_date, need, sold))
            need = Decimal(0)
        return out

    def split(self, instrument: str, ratio: Decimal) -> None:
        """A split: `ratio` new units per old unit; total cost and dates unchanged. Bonus units are new lots at zero cost via `buy`."""
        self._lots[instrument] = [Lot(l.acq_date, l.qty * ratio, l.cost) for l in self._lots[instrument]]
```

- [ ] **Step 4: Run the tests**

Run: `python -m pytest tests/test_lots.py -q`
Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add engine/lots.py tests/test_lots.py
git commit -m "feat: FIFO lots with exact cost split"
```

---

## Task 11: Tax: gain classification

**Files:**
- Create: `engine/tax.py` (part 1), `tests/synth_tax.py`, `tests/tax_helpers.py`, `tests/test_tax_classify.py`

**Interfaces:**
- Consumes: `Rules` (Task 3); trace constructors (Task 2).
- Produces: `fy_of(date) -> int` (financial year as its starting calendar year), `fy_end(fy) -> date`, `fy_label(fy) -> str`, `add_months(date, n) -> date`; dataclasses `TaxProfile(regime, other_income)`, `CGEvent(label, sale_date, asset_class, acq_date, proceeds: Node, sale_costs: Node, cost: Node, fmv_2018: Node | None)`, `Carry(st, lt)`, `FYTax`, `InvestmentTax`, `Pot`; `ZERO_N`; `classify(rules, event) -> (gain: Node, key: (term, kind, rate, section, group), ref: RuleRef)` where `term` is `short` or `long` and `kind` is `special`, `slab` or `exempt`. Made-up tax tables `TAX` (dict of table name to TOML text) for tests, and `ev(...)` to build events from ISO dates and plain numbers.

- [ ] **Step 1: Write the failing tests**

`tests/synth_tax.py` (made-up round-number rules; the `tax.audit` table and business `loss_rules` row are used from Task 14):

```python
"""Made-up round-number tax rules. They test the engine's logic, never real rates."""
from tests.helpers import table

OLD = '[ {upto = "250000", rate = "0"}, {upto = "500000", rate = "0.05"}, {upto = "1000000", rate = "0.20"}, {upto = "", rate = "0.30"} ]'
NEW = '[ {upto = "300000", rate = "0"}, {upto = "600000", rate = "0.05"}, {upto = "900000", rate = "0.10"}, {upto = "", rate = "0.30"} ]'
TIERS = '[ {above = "5000000", rate = "0.10"}, {above = "10000000", rate = "0.15"} ]'
ASSUMED = 'source = "test fixture"\nverified_on = 2026-01-01\nconfidence = "assumed"\nnote = "test convention"'
LATE_NEW = 'late_keys = [{ regime = "new", from = 2020-04-01 }]'

EQ_COMMON = 'lt_months = 12\nst_treatment = "special"\nst_rate = "0.15"\nst_section = "111A"'
SLAB_LT20 = ('lt_months = 36\nst_treatment = "slab"\nst_section = "slab"\n'
             'lt_treatment = "special"\nlt_rate = "0.20"\nlt_section = "112"\nindexation = true')

TAX = {
    "tax.buckets": table(["asset_class"], [
        'asset_class = "etf_equity"\nfrom = 2010-04-01\nbucket = "equity"',
        'asset_class = "mf_equity"\nfrom = 2010-04-01\nbucket = "equity"',
        'asset_class = "etf_gold"\nfrom = 2010-04-01\nbucket = "gold"',
        'asset_class = "mf_debt"\nfrom = 2010-04-01\nto = 2023-03-31\nbucket = "debt_pre"',
        'asset_class = "mf_debt"\nfrom = 2023-04-01\nbucket = "debt_post"',
    ]),
    "tax.capital_gains": table(["bucket"], [
        f'bucket = "equity"\nfrom = 2010-04-01\nto = 2018-03-31\n{EQ_COMMON}\nlt_treatment = "exempt"\nlt_section = "10(38)"',
        f'bucket = "equity"\nfrom = 2018-04-01\n{EQ_COMMON}\nlt_treatment = "special"\nlt_rate = "0.10"\nlt_section = "112A"\n'
        'lt_exemption_group = "112a"\ngrandfather_acq_upto = 2018-01-31',
        f'bucket = "gold"\nfrom = 2010-04-01\n{SLAB_LT20}',
        f'bucket = "debt_pre"\nfrom = 2010-04-01\n{SLAB_LT20}',
        'bucket = "debt_post"\nfrom = 2010-04-01\nlt_months = 0\nalways_short = true\n'
        'st_treatment = "slab"\nst_section = "50AA"\nlt_treatment = "slab"\nlt_section = "50AA"',
    ]),
    "tax.cii": table([], [
        f'from = {fy}-04-01\n' + (f'to = {fy + 1}-03-31\n' if fy < 2025 else '') + f'value = "{200 + 10 * (fy - 2010)}"'
        for fy in range(2010, 2026)
    ]),
    "tax.lt_exemption": table(["group"], [
        'group = "112a"\nfrom = 2010-04-01\nto = 2024-03-31\nvalue = "100000"\norder = "lowest_rate_first"',
        'group = "112a"\nfrom = 2024-04-01\nvalue = "125000"\norder = "lowest_rate_first"',
    ]),
    "tax.slabs": table(["regime"], [
        f'regime = "old"\nfrom = 2010-04-01\nbrackets = {OLD}',
        f'regime = "new"\nfrom = 2020-04-01\nbrackets = {NEW}',
    ], extra_meta=LATE_NEW),
    "tax.rebate_87a": table(["regime"], [
        'regime = "old"\nfrom = 2010-04-01\nincome_limit = "500000"\nmax_rebate = "12500"\napplies_to_special = true',
        'regime = "new"\nfrom = 2020-04-01\nincome_limit = "700000"\nmax_rebate = "25000"\n'
        'applies_to_special = false\nmarginal_relief = true',
    ], extra_meta=LATE_NEW),
    "tax.surcharge": table(["regime"], [
        f'regime = "old"\nfrom = 2010-04-01\ntiers = {TIERS}\ncap_special = "0.15"',
        f'regime = "new"\nfrom = 2020-04-01\ntiers = {TIERS}\ncap_special = "0.15"',
    ], extra_meta=LATE_NEW),
    "tax.cess": table([], ['from = 2010-04-01\nvalue = "0.04"']),
    "tax.dividend": table([], [
        'from = 2010-04-01\nto = 2016-03-31\nmode = "exempt"',
        'from = 2016-04-01\nto = 2020-03-31\nmode = "above_threshold"\nthreshold = "1000000"\nrate = "0.10"',
        'from = 2020-04-01\nmode = "slab"',
    ]),
    "tax.loss_rules": table(["kind"], [
        'kind = "capital"\nfrom = 2010-04-01\nvalue = "8"',
        'kind = "business"\nfrom = 2010-04-01\nvalue = "8"',
    ]),
    "tax.audit": table([], ['from = 2010-04-01\nturnover_limit = "10000000"\nfee = "25000"']),
    "tax.conventions": table(["name"], [
        f'name = "setoff_order"\nfrom = 2010-04-01\nvalue = "as coded"\n{ASSUMED}',
        f'name = "shortfall_order"\nfrom = 2010-04-01\nvalue = "as coded"\n{ASSUMED}',
        'name = "tax_round_step"\nfrom = 2010-04-01\nvalue = "10"',
    ]),
}
```

`tests/tax_helpers.py`:

```python
from datetime import date

from engine.tax import CGEvent
from engine.trace import const


def ev(acq, sale, cost, proceeds, cls="etf_equity", sale_costs="0", fmv=None, label="X"):
    """A capital-gains sale built from ISO dates and plain numbers."""
    return CGEvent(label, date.fromisoformat(sale), cls, date.fromisoformat(acq),
                   const("Proceeds", proceeds), const("Sale costs", sale_costs), const("Cost", cost),
                   const("Value on 31 Jan 2018", fmv) if fmv else None)
```

`tests/test_tax_classify.py`:

```python
from datetime import date
from decimal import Decimal as Dc

import pytest

from engine.rules import RuleNotFound
from engine.tax import add_months, classify, fy_of
from engine.trace import assert_balanced
from tests.helpers import make_rules
from tests.synth_tax import TAX
from tests.tax_helpers import ev


@pytest.fixture
def rules(tmp_path):
    return make_rules(tmp_path, TAX)


def gain(rules, *a, **kw):
    node, key, _ = classify(rules, ev(*a, **kw))
    assert_balanced(node)
    return node.value, key


@pytest.mark.parametrize("acq, sale, term", [
    ("2020-01-15", "2021-01-15", "short"),   # exactly 12 months is still short-term
    ("2020-01-15", "2021-01-16", "long"),
    ("2016-02-29", "2017-02-28", "short"),   # leap day: 12 months ends 28 Feb
    ("2016-02-29", "2017-03-01", "long"),
    ("2020-01-31", "2021-01-31", "short"),
])
def test_holding_period_boundaries(rules, acq, sale, term):
    assert gain(rules, acq, sale, "1", "2")[1][0] == term


def test_add_months_clamps_to_month_end_and_fy_starts_in_april():
    assert add_months(date(2020, 1, 31), 1) == date(2020, 2, 29)
    assert fy_of(date(2021, 3, 31)) == 2020 and fy_of(date(2021, 4, 1)) == 2021


def test_pot_follows_the_rule_of_the_sale_date(rules):
    assert gain(rules, "2019-06-01", "2019-12-01", "10000", "20000") == (Dc("10000"), ("short", "special", Dc("0.15"), "111A", ""))
    assert gain(rules, "2015-01-01", "2017-06-01", "1", "2")[1] == ("long", "exempt", None, "10(38)", "")
    assert gain(rules, "2018-03-01", "2019-06-01", "1", "2")[1] == ("long", "special", Dc("0.10"), "112A", "112a")


def test_grandfathering_raises_cost_to_the_value_on_31_jan_2018(rules):
    assert gain(rules, "2016-01-01", "2019-06-01", "1000000", "2500000", fmv="2000000")[0] == Dc("500000")


def test_grandfathering_cannot_push_cost_above_the_sale_value(rules):
    assert gain(rules, "2016-01-01", "2019-06-01", "1000000", "2500000", fmv="3000000")[0] == 0


def test_missing_2018_value_is_an_error_not_a_silent_skip(rules):
    with pytest.raises(ValueError, match="fmv_2018"):
        gain(rules, "2016-01-01", "2019-06-01", "1", "2")


def test_grandfathering_is_not_needed_for_short_term_sales(rules):
    assert gain(rules, "2018-01-15", "2018-06-01", "1", "2")[0] == 1


def test_indexation_scales_cost_by_the_inflation_index(rules):
    g, key = gain(rules, "2012-06-01", "2016-08-01", "100000", "200000", cls="etf_gold")
    assert key == ("long", "special", Dc("0.20"), "112", "")
    assert abs(g - (Dc(200000) - Dc(100000) * (Dc(260) / Dc(220)))) < Dc("1e-20")   # index 220 -> 260


def test_debt_fund_bought_after_march_2023_is_short_term_at_slab_rates(rules):
    assert gain(rules, "2023-05-01", "2025-06-01", "100000", "200000", cls="mf_debt")[1] == ("short", "slab", None, "50AA", "")


def test_sale_costs_reduce_the_gain(rules):
    assert gain(rules, "2019-06-01", "2019-12-01", "10000", "20000", sale_costs="150")[0] == Dc("9850")


def test_unknown_asset_class_raises(rules):
    with pytest.raises(RuleNotFound):
        classify(rules, ev("2019-01-01", "2019-06-01", "1", "2", cls="bitcoin"))
```

- [ ] **Step 2: Run them to see them fail**

Run: `python -m pytest tests/test_tax_classify.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'engine.tax'`.

- [ ] **Step 3: Implement part 1**

`engine/tax.py` (part 2 is appended in Task 12; some imports are unused until then):

```python
"""Income tax for one financial year on investment items. Every rate comes from rules/."""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from engine.money import D
from engine.rules import Rules
from engine.trace import (Node, RuleRef, add, cite, const, div, from_rule, maxn, minn, mul, rnd,
                          sub)

ZERO_N = const("Zero", 0)


def fy_of(d: date) -> int:
    """Financial year as its starting calendar year: 1 Apr 2024 to 31 Mar 2025 is 2024."""
    return d.year if d.month >= 4 else d.year - 1


def fy_end(fy: int) -> date:
    return date(fy + 1, 3, 31)


def fy_label(fy: int) -> str:
    return f"FY{fy}-{str(fy + 1)[2:]}"


def add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    y, m = d.year + y, m + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


@dataclass(frozen=True)
class TaxProfile:
    regime: str            # "old" | "new"; "old" is used in years before the new regime existed
    other_income: Decimal  # other taxable income for the year, after deductions


@dataclass(frozen=True)
class CGEvent:
    label: str
    sale_date: date
    asset_class: str
    acq_date: date
    proceeds: Node                 # full value of consideration
    sale_costs: Node               # transfer costs deductible from the gain (never STT)
    cost: Node                     # cost of acquisition, buy-side costs included
    fmv_2018: Node | None = None   # value of these units on 31 Jan 2018 (needed if bought on or before it)


@dataclass(frozen=True)
class Carry:
    st: tuple[tuple[int, Node], ...] = ()  # (financial year the loss arose, amount), oldest first
    lt: tuple[tuple[int, Node], ...] = ()


@dataclass(frozen=True)
class FYTax:
    fy: int
    tax: Node
    parts: dict[str, Node]
    carry_out: Carry


@dataclass(frozen=True)
class InvestmentTax:
    extra: Node
    with_items: FYTax
    without_items: FYTax


@dataclass
class Pot:
    term: str          # short | long | income
    kind: str          # special | slab | exempt
    rate: Decimal | None
    section: str
    group: str         # exemption group, "" if none
    ref: RuleRef
    gains: list[Node]
    net: Node | None = None
    left: Node | None = None  # still to tax after loss set-off and exemption
    loss: Node | None = None


def classify(rules: Rules, e: CGEvent):
    """Gain of one sale, and which pot it belongs to: (gain node, (term, kind, rate, section, group), rule ref)."""
    bucket = rules.at("tax.buckets", e.acq_date, asset_class=e.asset_class).data["bucket"]
    cg = rules.at("tax.capital_gains", e.sale_date, bucket=bucket)
    months = int(cg.data["lt_months"])
    long_ = not cg.data.get("always_short", False) and e.sale_date > add_months(e.acq_date, months)
    cost = e.cost
    gf = cg.data.get("grandfather_acq_upto")
    if long_ and gf is not None and e.acq_date <= gf:
        if e.fmv_2018 is None:
            raise ValueError(f"{e.label}: bought {e.acq_date} (on or before {gf}), so fmv_2018 is required")
        cost = maxn("Cost after 31 Jan 2018 grandfathering", cost,
                    minn("Lower of value on 31 Jan 2018 and sale value", e.fmv_2018, e.proceeds))
    if long_ and cg.data.get("indexation", False):
        f = div("Indexation factor",
                from_rule("Cost inflation index, year of sale", *_cii(rules, e.sale_date)),
                from_rule("Cost inflation index, year of purchase", *_cii(rules, e.acq_date)))
        cost = mul("Indexed cost of acquisition", cost, f)
    net_sale = sub("Net sale value", e.proceeds, e.sale_costs)
    held = f"held {e.acq_date} to {e.sale_date}; long-term needs more than {months} months"
    gain = cite(sub(f"Taxable gain: {e.label}", net_sale, cost, note=held), cg.ref)
    side = "lt" if long_ else "st"
    kind = cg.data[f"{side}_treatment"]
    rate = cg.dec(f"{side}_rate") if kind == "special" else None
    section = cg.data[f"{side}_section"]
    group = cg.data.get("lt_exemption_group", "") if long_ and kind == "special" else ""
    return gain, ("long" if long_ else "short", kind, rate, section, group), cg.ref


def _cii(rules: Rules, on: date):
    row = rules.at("tax.cii", on)
    return row.value, row.ref
```

- [ ] **Step 4: Run the tests**

Run: `python -m pytest tests/test_tax_classify.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add engine/tax.py tests/synth_tax.py tests/tax_helpers.py tests/test_tax_classify.py
git commit -m "feat: classify a sale as short or long term, with grandfathering and indexation"
```

---

## Task 12: Tax: year computation

**Files:**
- Modify: `engine/tax.py` (append part 2), `tests/golden_runner.py` (append the `tax_fy` kind), `tests/test_gates.py` (add `"tax."` to `FAMILIES`)
- Create: `tests/test_tax_fy.py`, `tests/test_golden_kinds_tax.py`, `tests/golden/tax_engine.toml`

**Interfaces:**
- Consumes: everything in `engine/tax.py` part 1; real tables from Tasks 7 and 8.
- Produces: `fy_tax(rules, fy, profile, events, carry_in=Carry(), dividends=None, interest=None) -> FYTax` (`tax: Node`, `parts: dict[str, Node]` with keys `ordinary_income`, `ordinary_tax`, `special_tax`, `total_income`, `rebate`, `surcharge`, `cess`, `before_rounding`; `carry_out: Carry`); `investment_tax(rules, fy, profile, events, carry_in, dividends, interest) -> InvestmentTax` (`extra` = tax with the investments minus tax without; `with_items`, `without_items`); golden kind `tax_fy` (see Step 6).

- [ ] **Step 1: Write the failing tests**

`tests/test_tax_fy.py`:

```python
from decimal import Decimal as Dc

import pytest

from engine.tax import Carry, TaxProfile, fy_tax, investment_tax
from engine.trace import assert_balanced, const, flags
from tests.helpers import make_rules
from tests.synth_tax import TAX
from tests.tax_helpers import ev


@pytest.fixture
def rules(tmp_path):
    return make_rules(tmp_path, TAX)


def extra(rules, fy, events, income="1000000", regime="old", **kw):
    r = investment_tax(rules, fy, TaxProfile(regime, Dc(income)), events, **kw)
    assert_balanced(r.extra)
    return r


# ---- capital gains --------------------------------------------------------

def test_short_term_gain_is_taxed_at_the_special_rate_on_top_of_slab_income(rules):
    r = extra(rules, 2019, [ev("2019-06-01", "2019-12-01", "10000", "20000")])
    assert r.extra.value == Dc("1560")       # 10,000 x 15% x 1.04 cess
    assert flags(r.extra) == []              # nothing assumed was used


def test_basic_exemption_shelters_gains_when_other_income_is_zero(rules):
    r = extra(rules, 2019, [ev("2019-06-01", "2019-12-01", "10000", "20000")], income="0")
    assert r.extra.value == 0
    assert [f.rule_id for f in flags(r.with_items.tax)] == ["tax.conventions[name=shortfall_order]"]


def test_new_regime_rebate_does_not_cover_special_rate_tax(rules):
    r = extra(rules, 2021, [ev("2021-06-01", "2021-12-01", "10000", "20000")], income="295000", regime="new")
    assert r.extra.value == Dc("780")        # 5,000 left after basic exemption x 15% x 1.04


def test_long_term_gain_uses_the_yearly_exemption(rules):
    r = extra(rules, 2019, [ev("2018-03-01", "2019-06-01", "100000", "250000")])
    assert r.extra.value == Dc("5200")       # (150,000 - 100,000) x 10% x 1.04


def test_long_term_gain_before_2018_is_exempt(rules):
    assert extra(rules, 2017, [ev("2015-01-01", "2017-06-01", "100000", "250000")]).extra.value == 0


def test_grandfathering_raises_cost_to_the_value_on_31_jan_2018(rules):
    e = ev("2016-01-01", "2019-06-01", "1000000", "2500000", fmv="2000000")
    assert extra(rules, 2019, [e]).extra.value == Dc("41600")   # (500,000 - 100,000) x 10% x 1.04


def test_grandfathering_cannot_push_cost_above_the_sale_value(rules):
    e = ev("2016-01-01", "2019-06-01", "1000000", "2500000", fmv="3000000")
    assert extra(rules, 2019, [e]).extra.value == 0


def test_indexation_scales_cost_by_the_inflation_index(rules):
    e = ev("2012-06-01", "2016-08-01", "100000", "200000", cls="etf_gold")
    r = extra(rules, 2016, [e])
    # cost 100,000 x 260/220; gain 81,818.18; tax 20% x 1.04; both totals rounded to Rs 10
    assert r.extra.value == Dc("17020")


def test_debt_fund_bought_after_march_2023_is_always_short_term_at_slab_rates(rules):
    e = ev("2023-05-01", "2025-06-01", "100000", "200000", cls="mf_debt")
    assert extra(rules, 2025, [e]).extra.value == Dc("31200")   # 100,000 x 30% x 1.04


def test_sale_outside_the_year_is_refused(rules):
    with pytest.raises(ValueError, match="not in FY2019-20"):
        fy_tax(rules, 2019, TaxProfile("old", Dc(0)), [ev("2019-06-01", "2020-06-01", "1", "2")])


# ---- losses ---------------------------------------------------------------

def test_short_term_loss_is_set_off_against_long_term_gain(rules):
    loss = ev("2019-01-10", "2019-06-01", "100000", "70000", label="loss")
    gain = ev("2018-03-01", "2019-07-01", "100000", "250000", label="gain")
    r = extra(rules, 2019, [loss, gain])
    assert r.extra.value == Dc("2080")       # (150,000 - 30,000 - 100,000 exemption) x 10% x 1.04
    assert r.with_items.carry_out == Carry()
    assert "tax.conventions[name=setoff_order]" in [f.rule_id for f in flags(r.with_items.tax)]


def test_unused_loss_is_carried_forward_then_used(rules):
    y1 = extra(rules, 2018, [ev("2018-05-01", "2018-09-01", "100000", "60000")])
    assert y1.extra.value == 0
    assert [(o, n.value) for o, n in y1.with_items.carry_out.st] == [(2018, Dc("40000"))]
    y2 = extra(rules, 2019, [ev("2019-05-01", "2019-09-01", "100000", "200000")], carry_in=y1.with_items.carry_out)
    assert y2.extra.value == Dc("9360")      # (100,000 - 40,000) x 15% x 1.04
    assert y2.with_items.carry_out == Carry()


@pytest.mark.parametrize("origin, expected", [(2011, "9360"), (2010, "15600")])
def test_losses_expire_after_eight_years(rules, origin, expected):
    carry = Carry(st=((origin, const("old loss", "40000")),))
    r = extra(rules, 2019, [ev("2019-05-01", "2019-09-01", "100000", "200000")], carry_in=carry)
    assert r.extra.value == Dc(expected)


def test_a_loss_on_an_exempt_sale_is_not_carried_forward(rules):
    r = extra(rules, 2017, [ev("2015-01-01", "2017-06-01", "200000", "100000")])
    assert r.with_items.carry_out == Carry()


# ---- dividends ------------------------------------------------------------

@pytest.mark.parametrize("fy, dividends, expected", [
    (2013, "1200000", "0"),        # company-paid tax era: exempt
    (2017, "1200000", "20800"),    # only the part above Rs 10 lakh, at 10% x 1.04
    (2021, "100000", "31200"),     # slab rate 30% x 1.04
])
def test_dividend_tax_follows_the_rule_of_the_year(rules, fy, dividends, expected):
    r = extra(rules, fy, [], dividends=const("Dividends", dividends))
    assert r.extra.value == Dc(expected)


# ---- slabs, rebate, surcharge, cess ---------------------------------------

def test_new_regime_falls_back_to_old_before_it_existed(rules):
    assert fy_tax(rules, 2018, TaxProfile("new", Dc("1000000")), []).tax.value == Dc("117000")
    assert fy_tax(rules, 2021, TaxProfile("new", Dc("1000000")), []).tax.value == Dc("78000")


@pytest.mark.parametrize("income, expected", [("700000", "0"), ("710000", "10400")])
def test_new_regime_rebate_and_its_marginal_relief(rules, income, expected):
    assert fy_tax(rules, 2021, TaxProfile("new", Dc(income)), []).tax.value == Dc(expected)


def test_surcharge_marginal_relief_just_above_the_threshold(rules):
    p = fy_tax(rules, 2019, TaxProfile("old", Dc("5010000")), []).parts
    assert p["surcharge"].value == Dc("7000")   # tax + surcharge capped at tax at 50 lakh + the 10,000 above it
    assert fy_tax(rules, 2019, TaxProfile("old", Dc("6000000")), []).parts["surcharge"].value == Dc("161250")


def test_tax_never_falls_and_never_jumps_across_the_surcharge_threshold(rules):
    prev = None
    for income in range(4_995_000, 5_005_001, 250):
        t = fy_tax(rules, 2019, TaxProfile("old", Dc(income)), []).parts["before_rounding"].value
        if prev is not None:
            assert 0 <= t - prev <= Dc("1.04") * 250
        prev = t


def test_zero_income_and_no_events_is_zero_tax(rules):
    assert fy_tax(rules, 2019, TaxProfile("old", Dc(0)), []).tax.value == 0


@pytest.mark.parametrize("income", ["0", "1", "249999", "250000", "499999", "500001", "1000000", "5000001", "20000000"])
@pytest.mark.parametrize("regime, fy", [("old", 2015), ("old", 2019), ("new", 2021)])
def test_tax_is_never_negative(rules, income, regime, fy):
    assert fy_tax(rules, fy, TaxProfile(regime, Dc(income)), []).tax.value >= 0
```

- [ ] **Step 2: Run them to see them fail**

Run: `python -m pytest tests/test_tax_fy.py -q`
Expected: FAIL with `ImportError: cannot import name 'fy_tax' from 'engine.tax'`.

- [ ] **Step 3: Append part 2 to `engine/tax.py`**

Add this after the end of part 1, after two blank lines:

```python
def _apply(label: str, loss: Node, pots: list[Pot]) -> Node:
    """Set `loss` off against each pot in turn; returns what is still unused."""
    for p in pots:
        if loss.value <= 0:
            break
        if p.left.value <= 0:
            continue
        used = minn(f"{label} used against {p.section}", loss, p.left)
        p.left = sub(f"{p.section} gain after {label.lower()}", p.left, used)
        loss = sub(f"{label}, unused", loss, used)
    return loss


def _order(pots: list[Pot]) -> list[Pot]:
    """Highest special rate first, then slab-taxed pots."""
    return sorted((p for p in pots if p.kind == "special"), key=lambda p: -p.rate) + \
        [p for p in pots if p.kind == "slab"]


def _slab_tax(brackets: list[dict], income: Node, ref: RuleRef) -> Node:
    pieces, lower = [], ZERO_N
    for i, b in enumerate(brackets, 1):
        rate = from_rule(f"Slab {i} rate", b["rate"], ref)
        if b["upto"] == "":
            piece = maxn(f"Income in slab {i}", sub(f"Income above slab {i - 1} limit", income, lower), ZERO_N)
        else:
            upper = from_rule(f"Slab {i} upper limit", b["upto"], ref)
            top = minn(f"Income up to slab {i} limit", income, upper)
            piece = maxn(f"Income in slab {i}", sub(f"Slab {i} income before flooring", top, lower), ZERO_N)
            lower = upper
        pieces.append(mul(f"Tax in slab {i}", piece, rate))
    return add("Tax at slab rates", *pieces)


def fy_tax(rules: Rules, fy: int, profile: TaxProfile, events: list[CGEvent],
           carry_in: Carry = Carry(), dividends: Node | None = None,
           interest: Node | None = None) -> FYTax:
    start, end = date(fy, 4, 1), fy_end(fy)
    for e in events:
        if fy_of(e.sale_date) != fy:
            raise ValueError(f"{e.label!r} sold {e.sale_date} is not in {fy_label(fy)}")
    years = int(rules.at("tax.loss_rules", end, kind="capital").value)
    conv_setoff = rules.at("tax.conventions", end, name="setoff_order")
    conv_short = rules.at("tax.conventions", end, name="shortfall_order")
    conv_round = rules.at("tax.conventions", end, name="tax_round_step")
    reg = profile.regime if rules.has("tax.slabs", start, regime=profile.regime) else "old"

    pots: dict[tuple, Pot] = {}
    for e in events:
        gain, key, ref = classify(rules, e)
        pots.setdefault(key, Pot(*key, ref=ref, gains=[])).gains.append(gain)
    live: list[Pot] = []
    for p in pots.values():
        p.net = add(f"Net {p.section} gains ({p.term}-term)", *p.gains)
        if p.kind == "exempt":  # neither taxed nor available to set off
            continue
        p.left = maxn(f"{p.section} gain to tax", p.net, ZERO_N)
        p.loss = maxn(f"{p.section} loss", sub("Net gain below zero", ZERO_N, p.net), ZERO_N)
        live.append(p)

    before = {id(p): p.left.value for p in live}

    # Loss set-off. Order: this year's ST loss on ST gains, LT loss on LT gains, leftover ST loss on LT
    # gains, then losses brought forward (LT, then ST), oldest first.
    st, lt = [p for p in live if p.term == "short"], [p for p in live if p.term == "long"]
    st_o, lt_o = _order(st), _order(lt)
    st_loss = _apply("Short-term loss this year", add("Short-term losses this year", *[p.loss for p in st]), st_o)
    lt_loss = _apply("Long-term loss this year", add("Long-term losses this year", *[p.loss for p in lt]), lt_o)
    st_loss = _apply("Short-term loss this year, leftover", st_loss, lt_o)
    new_st: list[tuple[int, Node]] = []
    new_lt: list[tuple[int, Node]] = []
    for origin, amt in sorted(carry_in.lt, key=lambda t: t[0]):
        if fy - origin > years:
            continue
        rem = _apply(f"Long-term loss brought forward from {fy_label(origin)}", amt, lt_o)
        if rem.value > 0:
            new_lt.append((origin, rem))
    for origin, amt in sorted(carry_in.st, key=lambda t: t[0]):
        if fy - origin > years:
            continue
        rem = _apply(f"Short-term loss brought forward from {fy_label(origin)}", amt, st_o)
        rem = _apply(f"Short-term loss brought forward from {fy_label(origin)}, leftover", rem, lt_o)
        if rem.value > 0:
            new_st.append((origin, rem))
    if lt_loss.value > 0:
        new_lt.append((fy, lt_loss))
    if st_loss.value > 0:
        new_st.append((fy, st_loss))
    setoff_happened = any(p.left.value != before[id(p)] for p in live)

    # Yearly exemption on long-term gains, per group.
    groups: dict[str, list[Pot]] = {}
    for p in lt:
        if p.group:
            groups.setdefault(p.group, []).append(p)
    for g, ps in groups.items():
        ex = rules.at("tax.lt_exemption", end, group=g)
        room = from_rule(f"Yearly long-term gains exemption ({g})", ex.value, ex.ref)
        for p in sorted(ps, key=lambda p: p.rate, reverse=ex.data["order"] == "highest_rate_first"):
            if room.value <= 0:
                break
            used = minn(f"Exemption used against {p.section} at {p.rate}", room, p.left)
            p.left = sub(f"{p.section} gain after exemption", p.left, used)
            room = sub("Exemption unused", room, used)

    # Income taxed at slab rates, and gains taxed at special rates.
    parts = [const("Other taxable income", profile.other_income)]
    parts += [p.left for p in live if p.kind == "slab"]
    if interest is not None:
        parts.append(interest)
    specials = [p for p in live if p.kind == "special"]
    if dividends is not None:
        drow = rules.at("tax.dividend", end)
        mode = drow.data["mode"]
        if mode == "slab":
            parts.append(cite(dividends, drow.ref))
        elif mode == "above_threshold":
            over = maxn("Dividends above the threshold",
                        sub("Dividends less threshold", dividends,
                            from_rule("Dividend threshold", drow.dec("threshold"), drow.ref)), ZERO_N)
            specials.append(Pot("income", "special", drow.dec("rate"), "115BBDA", "", drow.ref, [], left=over))
        elif mode != "exempt":
            raise ValueError(f"unknown dividend mode {mode!r}")
    ordinary = add("Income taxed at slab rates", *parts)
    slab = rules.at("tax.slabs", start, regime=reg)
    brackets = slab.data["brackets"]
    ordinary_tax = _slab_tax(brackets, ordinary, slab.ref)

    # A resident individual's unused basic exemption shelters gains taxed at special rates.
    basic = from_rule("Basic exemption limit", brackets[0]["upto"] if D(brackets[0]["rate"]) == 0 else 0, slab.ref)
    shortfall = maxn("Basic exemption unused by slab income", sub("Basic exemption less slab income", basic, ordinary), ZERO_N)
    taxable: dict[int, Node] = {}
    for p in sorted(specials, key=lambda p: -p.rate):
        cur = p.left
        if shortfall.value > 0 and cur.value > 0:
            used = minn(f"Shortfall used against {p.section}", shortfall, cur)
            cur = sub(f"{p.section} gain after basic-exemption adjustment", cur, used)
            shortfall = sub("Shortfall unused", shortfall, used)
        taxable[id(p)] = cur
    shortfall_used = any(taxable[id(p)].value != p.left.value for p in specials)
    special_tax = add("Tax at special rates", *[
        mul(f"Tax on {p.section} at {p.rate}", taxable[id(p)], from_rule(f"{p.section} rate", p.rate, p.ref))
        for p in sorted(specials, key=lambda p: -p.rate)])

    total = add("Total income", ordinary, *[p.left for p in specials])
    tax_before = add("Tax before rebate", ordinary_tax, special_tax)

    reb = rules.at("tax.rebate_87a", start, regime=reg)
    limit = from_rule("Rebate income limit", reb.dec("income_limit"), reb.ref)
    base = tax_before if reb.data["applies_to_special"] else ordinary_tax
    if total.value <= limit.value:
        rebate = minn("Section 87A rebate", from_rule("Maximum rebate", reb.dec("max_rebate"), reb.ref), base)
    elif reb.data.get("marginal_relief", False):
        over = sub("Income over the rebate limit", total, limit)
        rebate = maxn("Marginal relief at the rebate limit", sub("Tax above the income over the limit", base, over), ZERO_N)
    else:
        rebate = from_rule("No rebate: income above the limit", 0, reb.ref)
    after_rebate = sub("Tax after rebate", tax_before, rebate)

    sc = rules.at("tax.surcharge", start, regime=reg)
    crossed = [t for t in sc.data["tiers"] if total.value > D(t["above"])]
    if crossed:
        rate, prev = D(crossed[-1]["rate"]), (D(crossed[-2]["rate"]) if len(crossed) > 1 else D(0))
        cap = D(sc.data["cap_special"]) if sc.data.get("cap_special") else None

        def sur(r):  # (rate on slab tax, rate on special-rate tax)
            return r, (min(r, cap) if cap is not None else r)

        (r1, r2), (p1, p2) = sur(rate), sur(prev)
        surcharge = add("Surcharge", mul("Surcharge on slab tax", ordinary_tax, from_rule("Surcharge rate", r1, sc.ref)),
                        mul("Surcharge on special-rate tax", special_tax, from_rule("Surcharge rate on special-rate tax", r2, sc.ref)))
        threshold = from_rule("Surcharge threshold", crossed[-1]["above"], sc.ref)
        excess = sub("Income above the surcharge threshold", total, threshold)
        if excess.value <= ordinary.value:  # ponytail: relief only when the excess is slab income
            tax_t = _slab_tax(brackets, sub("Slab income at the threshold", ordinary, excess), slab.ref)
            at_t = add("Tax and surcharge at the threshold", tax_t, special_tax,
                       mul("Surcharge at the lower rate", tax_t, from_rule("Lower surcharge rate", p1, sc.ref)),
                       mul("Surcharge at the lower rate, special", special_tax, from_rule("Lower surcharge rate, special", p2, sc.ref)))
            ceiling = add("Most tax and surcharge may be", at_t, excess)
            now = add("Tax and surcharge now", ordinary_tax, special_tax, surcharge)
            relief = maxn("Marginal relief", sub("Tax and surcharge over the ceiling", now, ceiling), ZERO_N)
        else:
            relief = from_rule("No marginal relief computed", 0, sc.ref,
                               note="the income above the threshold is special-rate income; relief not computed")
        surcharge_final = sub("Surcharge after marginal relief", surcharge, relief)
    else:
        surcharge_final = from_rule("No surcharge", 0, sc.ref)

    cess_row = rules.at("tax.cess", start)
    cess = mul("Health and education cess", add("Tax and surcharge", after_rebate, surcharge_final),
               from_rule("Cess rate", cess_row.value, cess_row.ref))
    unrounded = add("Tax before rounding", after_rebate, surcharge_final, cess)
    tax = rnd(f"Income tax for {fy_label(fy)}", unrounded, from_rule("Tax rounding step", conv_round.value, conv_round.ref))
    if setoff_happened:
        tax = cite(tax, conv_setoff.ref)
    if shortfall_used:
        tax = cite(tax, conv_short.ref)
    return FYTax(fy, tax, {"ordinary_income": ordinary, "ordinary_tax": ordinary_tax, "special_tax": special_tax,
                           "total_income": total, "rebate": rebate, "surcharge": surcharge_final,
                           "cess": cess, "before_rounding": unrounded},
                 Carry(tuple(new_st), tuple(new_lt)))


def investment_tax(rules: Rules, fy: int, profile: TaxProfile, events: list[CGEvent],
                   carry_in: Carry = Carry(), dividends: Node | None = None,
                   interest: Node | None = None) -> InvestmentTax:
    """Tax caused by the investments: the year's tax with them minus the year's tax without."""
    w = fy_tax(rules, fy, profile, events, carry_in, dividends, interest)
    wo = fy_tax(rules, fy, profile, [], Carry(), None, None)
    return InvestmentTax(sub(f"Tax caused by your investments in {fy_label(fy)}", w.tax, wo.tax), w, wo)
```

- [ ] **Step 4: Run the tests**

Run: `python -m pytest tests/test_tax_classify.py tests/test_tax_fy.py -q`
Expected: all pass.

- [ ] **Step 5: Register the golden kind and test it**

Append to `tests/golden_runner.py`, after two blank lines:

```python

@kind("tax_fy")
def _tax_fy(rules: Rules, c: dict):
    """One year's tax: `extra` (caused by the investments), `tax_with`, `tax_without` or any part."""
    from engine.tax import CGEvent, TaxProfile, investment_tax
    from engine.trace import assert_balanced, const, rules_used
    i = c["input"]
    events = [CGEvent(e.get("label", "sale"), e["sale_date"], e["asset_class"], e["acq_date"],
                      const("Proceeds", e["proceeds"]), const("Sale costs", e.get("sale_costs", "0")),
                      const("Cost", e["cost"]),
                      const("Value on 31 Jan 2018", e["fmv_2018"]) if "fmv_2018" in e else None)
              for e in i.get("events", [])]
    r = investment_tax(rules, i["fy"], TaxProfile(i["regime"], D(i["other_income"])), events,
                       dividends=const("Dividends", i["dividends"]) if "dividends" in i else None,
                       interest=const("Interest", i["interest"]) if "interest" in i else None)
    named = {"extra": r.extra, "tax_with": r.with_items.tax, "tax_without": r.without_items.tax,
             **r.with_items.parts}
    for name, want in c["expect"].items():
        assert same(named[name].value, want), f"{c['id']}: {name} is {named[name].value}, hand-worked {want}"
    assert_balanced(r.extra)
    return rules_used(r.extra)
```

`tests/test_golden_kinds_tax.py`:

```python
from tests.golden_runner import load_cases, run_case
from tests.helpers import make_rules
from tests.synth_tax import TAX

TAX_CASE = '''
[[case]]
id = "stcg-2019"
kind = "tax_fy"
source = "test"
work = "10,000 x 15% = 1,500; x 1.04 cess = 1,560"
[case.input]
fy = 2019
regime = "old"
other_income = "1000000"
[[case.input.events]]
sale_date = 2019-12-01
acq_date = 2019-06-01
asset_class = "etf_equity"
proceeds = "20000"
cost = "10000"
[case.expect]
extra = "1560"
special_tax = "1500"
'''


def load(tmp_path, body):
    (tmp_path / "golden").mkdir()
    (tmp_path / "golden" / "a.toml").write_text(body, encoding="utf-8")
    return load_cases(tmp_path / "golden")


def test_tax_fy_case_runs(tmp_path):
    rules = make_rules(tmp_path / "r", TAX)
    (c,) = load(tmp_path, TAX_CASE)
    run_case(rules, c)
```

Run: `python -m pytest -q`
Expected: all pass.

- [ ] **Step 6: Write the composition cases**

Create `tests/golden/tax_engine.toml`. A case (numbers here are made up):

```toml
[[case]]
id = "stcg-2019"
kind = "tax_fy"
source = "S5 s.111A; hand-worked"
work = "10,000 x 15% = 1,500; x 1.04 cess = 1,560"
[case.input]
fy = 2019
regime = "old"
other_income = "1000000"
[[case.input.events]]
sale_date = 2019-12-01
acq_date = 2019-06-01
asset_class = "etf_equity"
proceeds = "20000"
sale_costs = "0"
cost = "10000"
# fmv_2018 = "..."   optional, needed for units bought on or before 2018-01-31
# dividends = "..."  optional; interest = "..." optional
[case.expect]
extra = "1560"
special_tax = "1500"
```

`expect` may name `extra`, `tax_with`, `tax_without`, or any of `ordinary_income`, `ordinary_tax`, `special_tax`, `total_income`, `rebate`, `surcharge`, `cess`, `before_rounding`. Print the change dates with `python -m tests.golden_skeleton --changes tax.` and write, each worked by hand from the sources:
- One case with no events for each slab, rebate and surcharge row (pick other income inside the band; both regimes; a case just above and just below each rebate limit and surcharge threshold).
- For each change date D: a sale on the day before D and on D, for the asset class the change affects.
- Indexation: enough sales that every `tax.cii` row is used (each case uses the sale-year and acquisition-year rows).
- Grandfathering: units bought before 2018-02-01 and sold after 2018-04-01, with `fmv_2018`.
- One case each for: loss set-off (uses `setoff_order`), a student with zero other income (uses `shortfall_order`), a dividend in each `tax.dividend` mode.

Then in `tests/test_gates.py` change `FAMILIES = ("fyers.", "charges.")  # Task 12 adds "tax."` to `FAMILIES = ("fyers.", "charges.", "tax.")`. Run `python -m pytest tests/test_gates.py tests/test_golden.py -q`. The gate lists rows no case exercises; keep adding cases until it passes. Rows of `tax.audit` and `tax.loss_rules[kind=business]` do not exist yet (Task 14).

- [ ] **Step 7: Commit**

```bash
git add engine/tax.py tests
git commit -m "feat: financial-year tax with loss set-off, exemption, slabs, rebate, surcharge and cess"
```

---

## Task 13: Checkpoint 1: ₹1 lakh in a Nifty ETF, fully traced

**Files:**
- Create: `data/fetch_yahoo.py`, `engine/scenario.py`, `engine/report.py`, `tests/test_fetch_yahoo.py`, `tests/test_scenario.py`, `tests/test_report.py`, `data/processed/NIFTYBEES.csv`, `data/processed/NIFTYBEES_dividends.csv`, `data/manifest.json`, `docs/verification/checkpoint-1.md`

**Interfaces:**
- Consumes: `order_charges`, `dp_charge`, `amc_fee`, `Order` (Task 9); `Inventory` (Task 10); `TaxProfile`, `CGEvent`, `Carry`, `investment_tax`, `fy_of`, `fy_end`, `fy_label` (Tasks 11 and 12); trace constructors.
- Produces:
  - `data.fetch_yahoo`: `fetch(symbol) -> bytes`, `parse(raw) -> (bars, dividends)` (refuses split-adjusted data), `save(symbol, raw, retrieved, root)` (writes CSVs and `manifest.json`), `load_bars(path) -> list[Bar]`, `load_dividends(path) -> dict[date, Decimal]`.
  - `engine.scenario`: `Bar(on, high, close)`, `Result(net, waterfall, units, bought_on, ended_on, sold)`, `buy_and_hold(rules, *, instrument, instrument_class, bars, dividends, amount, start, end, profile, sell_at_end=True) -> Result`.
  - `engine.report`: `render_html(title, sections, notes) -> str`, `main(argv) -> Path` (`python -m engine.report --amount 100000 --start 2014-01-01 --income 1500000 --regime new`).
- Simplifications (all printed on the report): buys and sells at the day's close, cash earns nothing, dividends are kept as cash, whole units only. The Yahoo Finance chart API is unofficial and, when this plan was written, returned no dividend records for NIFTYBEES.NS at all, so the source understates total return until the data layer replaces it.

- [ ] **Step 1: Write the failing tests**

`tests/test_fetch_yahoo.py`:

```python
import json
from datetime import date
from decimal import Decimal as Dc

import pytest

from data.fetch_yahoo import load_bars, load_dividends, parse, save


def payload(splits=None, divs=None):
    r = {"meta": {"gmtoffset": 19800},
         "timestamp": [1515024900, 1517357100, 1517443500],   # 03:45 UTC = 09:15 IST: 2018-01-04, 2018-01-31, 2018-02-01
         "indicators": {"quote": [{"high": [111.1234567, 113.8499984741211, None], "close": [110.9, 113.5439987, None]}]}}
    ev = {}
    if splits:
        ev["splits"] = splits
    if divs:
        ev["dividends"] = divs
    if ev:
        r["events"] = ev
    return json.dumps({"chart": {"result": [r]}}).encode()


def test_parse_uses_local_dates_two_decimals_and_skips_gaps():
    bars, divs = parse(payload())
    assert bars == [(date(2018, 1, 4), Dc("111.12"), Dc("110.90")), (date(2018, 1, 31), Dc("113.85"), Dc("113.54"))]
    assert divs == {}


def test_parse_reads_dividends_and_refuses_splits():
    _, divs = parse(payload(divs={"a": {"date": 1517357100, "amount": 0.35}}))
    assert divs == {date(2018, 1, 31): Dc("0.3500")}
    with pytest.raises(ValueError, match="split"):
        parse(payload(splits={"a": {"date": 1}}))


def test_save_writes_csv_manifest_and_round_trips(tmp_path):
    out = save("NIFTYBEES.NS", payload(), date(2026, 9, 29), root=tmp_path)
    assert out.name == "NIFTYBEES.csv"
    m = json.loads((tmp_path / "manifest.json").read_text())["NIFTYBEES.csv"]
    assert m["rows"] == 2 and m["first"] == "2018-01-04" and len(m["raw_sha256"]) == 64 and m["dividend_events"] == 0
    bars = load_bars(out)
    assert bars[1].high == Dc("113.85") and bars[1].on == date(2018, 1, 31)
    assert load_dividends(tmp_path / "processed" / "NIFTYBEES_dividends.csv") == {}
```

`tests/test_scenario.py` (made-up rules, the story worked by hand to the paisa):

```python
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal as Dc

import pytest

from engine.scenario import Bar, buy_and_hold
from engine.tax import TaxProfile
from engine.trace import assert_balanced
from tests.helpers import make_rules
from tests.synth_charges import CHARGES
from tests.synth_tax import TAX


@pytest.fixture
def rules(tmp_path):
    return make_rules(tmp_path, {**CHARGES, **TAX})


def bars():
    """Daily bars 2015-04-01 .. 2019-06-03, price 100 until 2018-01-31 (high 150), 300 after."""
    out, d = [], date(2015, 4, 1)
    while d <= date(2019, 6, 3):
        if d.weekday() < 5:
            price = Dc("100") if d < date(2018, 2, 1) else Dc("300")
            out.append(Bar(d, Dc("150") if d == date(2018, 1, 31) else price, price))
        d += timedelta(days=1)
    return out


def rnd(x, step):
    return (x / step).quantize(Dc(1), rounding=ROUND_HALF_UP) * step


def hand_calc(amount, dividend_per_unit=Dc(0)):
    """The same story worked by hand with the made-up rates typed in, sharing no code with the engine."""
    units = int(amount // 100)
    while True:  # whole units such that price + buy charges fit in the amount
        t = Dc(units) * 100
        stamp, exch, sebi = rnd(t * Dc("0.00015"), Dc("0.01")), rnd(t * Dc("0.00003"), Dc("0.01")), rnd(t * Dc("0.000001"), Dc("0.01"))
        gst = rnd((exch + sebi) * Dc("0.18"), Dc("0.01"))
        buy_total = stamp + exch + sebi + gst
        if t + buy_total <= amount:
            break
        units -= 1
    t_sell = Dc(units) * 300
    stt = rnd(t_sell * Dc("0.0005"), Dc(1))
    exch_s, sebi_s = rnd(t_sell * Dc("0.00003"), Dc("0.01")), rnd(t_sell * Dc("0.000001"), Dc("0.01"))
    gst_s = rnd((exch_s + sebi_s) * Dc("0.18"), Dc("0.01"))
    dp = rnd((Dc(13) + Dc("3.5")) * Dc("0.18"), Dc("0.01")) + Dc("16.5")
    sell_total = stt + exch_s + sebi_s + gst_s + dp
    amc = 5 * Dc("354")                                   # FY2015 .. FY2019
    cost = t + stamp + exch + sebi + gst
    fmv = Dc(units) * 150                                 # highest price on 31 Jan 2018
    cost_used = max(cost, min(fmv, t_sell))
    gain = t_sell - (exch_s + sebi_s + gst_s + dp) - cost_used
    taxable = max(Dc(0), gain - 100000)                   # 1 lakh exemption
    extra = rnd(Dc(117000) + taxable * Dc("0.10") * Dc("1.04"), Dc(10)) - Dc(117000)
    net = amount + (t_sell - t) + Dc(units) * dividend_per_unit - (buy_total + sell_total + amc) - extra
    return units, net, extra


def run(rules, amount, **kw):
    return buy_and_hold(rules, instrument="ETF", instrument_class="etf_equity", bars=bars(),
                        dividends=kw.pop("dividends", {}), amount=Dc(amount), start=date(2015, 4, 1),
                        end=date(2019, 6, 3), profile=TaxProfile("old", Dc("1000000")), **kw)


def test_matches_a_hand_calculation_to_the_paisa(rules):
    r = run(rules, "1000000")
    units, net, extra = hand_calc(Dc("1000000"))
    assert r.units == units
    assert r.waterfall["tax"].value == extra > 0
    assert r.net.value == net
    assert_balanced(r.net)


def test_dividends_add_to_gross_and_are_traced(rules):
    r = run(rules, "1000000", dividends={date(2016, 6, 1): Dc("2"), date(2015, 4, 1): Dc("9")})
    _, net, _ = hand_calc(Dc("1000000"), Dc(2))
    assert r.net.value == net                       # the 2015-04-01 ex-date is the buy day: not entitled
    assert r.waterfall["gross_profit"].value == (Dc(300) - 100) * r.units + 2 * r.units


def test_still_holding_pays_no_sale_charges_or_capital_gains_tax(rules):
    r = run(rules, "1000000", sell_at_end=False)
    assert r.waterfall["sale_charges"].value == 0 and r.waterfall["tax"].value == 0
    assert not r.sold


def test_amount_too_small_or_period_empty_is_an_error(rules):
    with pytest.raises(ValueError, match="too small"):
        run(rules, "50")
    with pytest.raises(ValueError, match="no usable price history"):
        buy_and_hold(rules, instrument="ETF", instrument_class="etf_equity", bars=bars(), dividends={},
                     amount=Dc("1000"), start=date(2030, 1, 1), end=date(2031, 1, 1),
                     profile=TaxProfile("old", Dc("0")))
```

`tests/test_report.py`:

```python
from datetime import date

from data.fetch_yahoo import save
from engine.report import main, render_html
from engine.scenario import Result
from engine.trace import const, sub
from tests.helpers import make_rules
from tests.synth_charges import CHARGES
from tests.synth_tax import TAX


def fake_result():
    a, b = const("<b>Cost</b>", "100.123456789"), const("Fee", "0.5")
    net = sub("Net", a, b)
    w = {k: net for k in ("initial", "gross_profit", "gross_end", "buy_charges", "sale_charges", "amc",
                          "charges", "tax", "net")}
    return Result(net, w, 10, date(2020, 1, 1), date(2021, 1, 1), True)


def test_report_shows_exact_values_behind_an_info_button_and_escapes_text():
    html = render_html("T & <script>", [("Sold", fake_result())], ["a note <i>"])
    assert "ⓘ" in html and "99.623456789" in html          # exact, unrounded value is in the trace
    assert "&lt;b&gt;Cost&lt;/b&gt;" in html and "<script>" not in html and "&lt;i&gt;" in html
    assert "None used." in html                             # no non-primary rules involved


def test_command_line_writes_a_report_with_both_views(tmp_path):
    import json
    ts = [1517357100 + 86400 * i for i in range(0, 900) if (i % 7) < 5]     # weekdays from 2018-01-31
    price = [100 + i * 0.05 for i in range(len(ts))]
    raw = json.dumps({"chart": {"result": [{"meta": {"gmtoffset": 19800}, "timestamp": ts,
                      "indicators": {"quote": [{"high": price, "close": price}]}}]}}).encode()
    save("ETF.NS", raw, date(2026, 9, 29), root=tmp_path)
    make_rules(tmp_path / "rules", {**CHARGES, **TAX})
    out = main(["--symbol", "ETF", "--amount", "100000", "--start", "2018-02-01", "--end", "2020-06-01",
                "--rules", str(tmp_path / "rules"), "--data", str(tmp_path / "processed"),
                "--out", str(tmp_path / "out" / "r.html")])
    html = out.read_text(encoding="utf-8")
    assert "If sold on the end date" in html and "If still holding" in html and "ⓘ" in html
    assert "Dividends in the source: 0" in html
```

- [ ] **Step 2: Run them to see them fail**

Run: `python -m pytest tests/test_fetch_yahoo.py tests/test_scenario.py tests/test_report.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'data.fetch_yahoo'`.

- [ ] **Step 3: Implement**

`data/fetch_yahoo.py`:

```python
"""Freeze one Yahoo Finance daily series as CSV plus a hashed manifest entry.

Yahoo's chart API is unofficial: fine for a first checkpoint, not a system of record.
Sub-project 2 replaces it with NSE files. Run:  python data/fetch_yahoo.py NIFTYBEES.NS
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).parent
URL = ("https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
       "?period1=0&period2={now}&interval=1d&events=div%7Csplit")


def fetch(symbol: str) -> bytes:
    req = urllib.request.Request(URL.format(symbol=symbol, now=int(time.time())),
                                 headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(3):
        try:
            return urllib.request.urlopen(req, timeout=30).read()
        except OSError:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))


def parse(raw: bytes) -> tuple[list[tuple[date, Decimal, Decimal]], dict[date, Decimal]]:
    """(bars of date, high, close), dividends per unit by ex-date. Refuses split-adjusted data."""
    r = json.loads(raw)["chart"]["result"][0]
    events = r.get("events", {})
    if events.get("splits"):
        raise ValueError("split events present: prices are adjusted, handle in the data layer first")
    tz = timezone(timedelta(seconds=r["meta"]["gmtoffset"]))
    q = r["indicators"]["quote"][0]
    bars = [(datetime.fromtimestamp(t, tz).date(), Decimal(f"{h:.2f}"), Decimal(f"{c:.2f}"))
            for t, h, c in zip(r["timestamp"], q["high"], q["close"]) if h is not None and c is not None]
    divs = {datetime.fromtimestamp(v["date"], tz).date(): Decimal(f"{v['amount']:.4f}")
            for v in events.get("dividends", {}).values()}
    return bars, divs


def save(symbol: str, raw: bytes, retrieved: date, root: Path = ROOT) -> Path:
    bars, divs = parse(raw)
    (root / "raw").mkdir(exist_ok=True)
    (root / "processed").mkdir(exist_ok=True)
    (root / "raw" / f"yahoo_{symbol}_{retrieved:%Y%m%d}.json").write_bytes(raw)
    out = root / "processed" / f"{symbol.split('.')[0]}.csv"
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "high", "close"])
        w.writerows(bars)
    with (root / "processed" / f"{symbol.split('.')[0]}_dividends.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ex_date", "per_unit"])
        w.writerows(sorted(divs.items()))
    mpath = root / "manifest.json"
    manifest = json.loads(mpath.read_text()) if mpath.exists() else {}
    manifest[out.name] = {"source": URL.format(symbol=symbol, now="<retrieval time>"), "retrieved": retrieved.isoformat(),
                          "raw_sha256": hashlib.sha256(raw).hexdigest(),
                          "csv_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
                          "rows": len(bars), "first": bars[0][0].isoformat(), "last": bars[-1][0].isoformat(),
                          "dividend_events": len(divs)}
    mpath.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return out


def load_bars(path: Path):
    from engine.scenario import Bar
    with Path(path).open(newline="") as f:
        return [Bar(date.fromisoformat(r["date"]), Decimal(r["high"]), Decimal(r["close"])) for r in csv.DictReader(f)]


def load_dividends(path: Path) -> dict[date, Decimal]:
    with Path(path).open(newline="") as f:
        return {date.fromisoformat(r["ex_date"]): Decimal(r["per_unit"]) for r in csv.DictReader(f)}


if __name__ == "__main__":
    sym = sys.argv[1]
    print(save(sym, fetch(sym), date.today()))
```

`engine/scenario.py`:

```python
"""Buy and hold one ETF, sell at the end: the first end-to-end scenario, every rupee traced.

Simplifications, all shown on the report: buys and sells at the day's close (the real fill model
comes with the strategy engine), cash earns nothing, and units are whole.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from engine.charges import Order, amc_fee, dp_charge, order_charges
from engine.lots import Inventory
from engine.rules import Rules
from engine.tax import CGEvent, Carry, TaxProfile, fy_end, fy_label, fy_of, investment_tax
from engine.trace import Node, add, const, mul, sub

GRANDFATHER_DATE = date(2018, 1, 31)  # value on this day is the floor for older units' cost (s.55(2)(ac))


@dataclass(frozen=True)
class Bar:
    on: date
    high: Decimal
    close: Decimal


@dataclass(frozen=True)
class Result:
    net: Node                    # what you end up with: the root of the whole trace
    waterfall: dict[str, Node]
    units: int
    bought_on: date
    ended_on: date
    sold: bool


def buy_and_hold(rules: Rules, *, instrument: str, instrument_class: str, bars: list[Bar],
                 dividends: dict[date, Decimal], amount: Decimal, start: date, end: date,
                 profile: TaxProfile, sell_at_end: bool = True) -> Result:
    buy = next((b for b in bars if b.on >= start), None)
    last = [b for b in bars if b.on <= end]
    if buy is None or not last or last[-1].on <= buy.on:
        raise ValueError(f"no usable price history between {start} and {end}")
    sell = last[-1]

    units = int(amount // buy.close)
    while units > 0:
        bc = order_charges(rules, Order(buy.on, instrument_class, "buy", Decimal(units), buy.close))
        if bc.turnover.value + bc.total.value <= amount:
            break
        units -= 1
    if units == 0:
        raise ValueError(f"{amount} is too small to buy one unit at {buy.close} after charges")
    q = Decimal(units)

    initial = const("Money invested", amount)
    cost = add("Cost of acquisition (price + buy charges you may deduct)", bc.turnover, bc.deductible)

    # dividends: paid on units held before the ex-date, up to the end date
    div_by_fy: dict[int, list[Node]] = {}
    for ex, per_unit in sorted(dividends.items()):
        if buy.on < ex <= sell.on:
            div_by_fy.setdefault(fy_of(ex), []).append(
                mul(f"Dividend paid on {ex}", const("Units held", q), const("Dividend per unit", per_unit)))
    div_fy = {fy: add(f"Dividends received in {fy_label(fy)}", *ns) for fy, ns in div_by_fy.items()}

    amc = [amc_fee(rules, min(fy_end(fy), sell.on)) for fy in range(fy_of(buy.on), fy_of(sell.on) + 1)]

    sale_value = mul("Value of units at the end", const("Units held", q), const("Closing price on the last day", sell.close))
    if sell_at_end:
        sc = order_charges(rules, Order(sell.on, instrument_class, "sell", q, sell.close))
        dp = dp_charge(rules, sell.on)
        inv = Inventory()
        inv.buy(instrument, buy.on, q, cost)
        piece = inv.sell(instrument, q)[0]
        fmv = None
        if buy.on <= GRANDFATHER_DATE:
            ref_bar = [b for b in bars if b.on <= GRANDFATHER_DATE]
            if ref_bar:
                fmv = mul("Value on 31 Jan 2018 (highest price that day)", const("Units held", q),
                          const("Highest price on 31 Jan 2018", ref_bar[-1].high))
        event = CGEvent(f"{units} units of {instrument}", sell.on, instrument_class, piece.acq_date,
                        sc.turnover, add("Sale costs you may deduct", sc.deductible, dp), piece.cost, fmv)
        sale_charges = add("Sale charges (incl. STT and depository fees)", sc.total, dp)
    else:
        event, sale_charges = None, add("Sale charges (none: still holding)")

    taxes, carry = [], Carry()
    for fy in range(fy_of(buy.on), fy_of(sell.on) + 1):
        events = [event] if event is not None and fy == fy_of(sell.on) else []
        r = investment_tax(rules, fy, profile, events, carry, dividends=div_fy.get(fy))
        carry = r.with_items.carry_out
        taxes.append(r.extra)

    price_gain = sub("Price gain before charges and tax", sale_value, bc.turnover)
    total_div = add("All dividends received", *div_fy.values())
    gross_profit = add("Gross profit (price gain + dividends)", price_gain, total_div)
    gross_end = add("Gross end value, before any charge or tax", initial, gross_profit)
    charges = add("All charges", bc.total, sale_charges, *amc)
    tax = add("All income tax caused by this investment", *taxes)
    net = sub("Final amount after all charges and tax", sub("Gross end value less all charges", gross_end, charges), tax)
    return Result(net, {"initial": initial, "gross_profit": gross_profit, "gross_end": gross_end,
                        "buy_charges": bc.total, "sale_charges": sale_charges, "amc": add("Demat AMC for all years", *amc),
                        "charges": charges, "tax": tax, "net": net},
                  units, buy.on, sell.on, sell_at_end)
```

`engine/report.py`:

```python
"""Static HTML report: the waterfall, and a trace under every number (native <details>, no JavaScript)."""
from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal
from html import escape
from pathlib import Path

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
"""


def exact(v: Decimal) -> str:
    return format(v, "f")


def money(v: Decimal) -> str:
    return f"₹{v:,.2f}"


def tree(n: Node) -> str:
    rules = "".join(
        f'<li class="rule {r.confidence}">rule {escape(r.rule_id)} valid from {r.valid_from}: '
        f"{escape(r.source)} (verified {r.verified_on}, {r.confidence})</li>" for r in n.rules)
    note = f'<div class="f">{escape(n.note)}</div>' if n.note else ""
    body = f'<div class="f">{escape(n.formula)}</div>{note}<ul>{rules}</ul>' + "".join(tree(i) for i in n.inputs)
    return f"<details><summary>{escape(n.label)} = {exact(n.value)}</summary>{body}</details>"


def row(label: str, n: Node) -> str:
    return (f'<tr><td>{escape(label)}</td><td class="n">{money(n.value)}</td><td>'
            f'<details class="root"><summary>ⓘ</summary>{tree(n)}</details></td></tr>')


def section(heading: str, r: Result) -> str:
    w = r.waterfall
    rows = [row("Money invested", w["initial"]), row("Gross profit (price gain + dividends)", w["gross_profit"]),
            row("Gross end value, before any charge or tax", w["gross_end"]),
            row("Charges on the buy", w["buy_charges"]), row("Charges on the sale", w["sale_charges"]),
            row("Demat account fees", w["amc"]), row("All charges", w["charges"]),
            row("Income tax caused by this investment", w["tax"]), row("Final amount", w["net"])]
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
                          f"{escape(f.source)}</li>")
    ns = "".join(f"<li>{escape(n)}</li>" for n in notes)
    return (f"<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
            f"<title>{escape(title)}</title><style>{CSS}</style><h1>{escape(title)}</h1>"
            f"{''.join(section(h, r) for h, r in sections)}"
            f"<h2>Rules that are not backed by an official source</h2><ul>{''.join(fl) or '<li>None used.</li>'}</ul>"
            f"<h2>Notes and known gaps</h2><ul>{ns}</ul></html>")


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
        f"Dividends in the source: {len(divs)}. If this is 0 the source has no dividend records for this ETF, "
        "so the result understates the true return.",
        "Buys and sells at the day's close. The real fill model (next open plus slippage) comes with the strategy engine.",
        "Cash earns nothing and dividends are kept as cash, not reinvested. Whole units only.",
        "Tax for each financial year is treated as paid from cash at year end. Advance-tax interest is ignored.",
        f"Tax profile: {a.regime} regime, other taxable income {money(Decimal(a.income))} a year, no losses brought forward.",
    ]
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(f"{a.symbol}: {money(Decimal(a.amount))} from {a.start} to {a.end}",
                               [("If sold on the end date (tax paid)", sold), ("If still holding (tax deferred)", held)],
                               notes), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(main())
```

- [ ] **Step 4: Run the tests**

Run: `python -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Freeze the real prices**

Run: `python data/fetch_yahoo.py NIFTYBEES.NS`
Then inspect `data/manifest.json` and the first and last rows of `data/processed/NIFTYBEES.csv`. Check: about 4,000 to 4,300 rows starting in 2009 or 2010; the last date is recent; `dividend_events` is probably `0`; the row for 2018-01-31 has the day's high (grandfathering uses the highest price quoted that day). If the fetch fails 3 times, stop and tell the user; do not hand-type prices.

- [ ] **Step 6: Check dividends against a second source**

Search for the Nifty BeES dividend history (Nippon India, NSE corporate actions). If the ETF paid dividends, add them by hand to `data/processed/NIFTYBEES_dividends.csv` (`ex_date,per_unit`), cite the source in `docs/verification/checkpoint-1.md`, and update the `dividend_events` count in `data/manifest.json`. If it paid none, say so in that file.

- [ ] **Step 7: Make the report**

Run both:

```text
python -m engine.report --income 0 --regime new --out out/checkpoint1_no_other_income.html
python -m engine.report --income 1500000 --regime new --out out/checkpoint1.html
```
Open a report and click ⓘ on each row.

- [ ] **Step 8: Verify by hand and against Fyers' calculator**

Write `docs/verification/checkpoint-1.md` with:
1. **Fyers calculator cross-check.** Open Fyers' brokerage calculator in a browser tab. Enter the report's buy order (NSE, delivery, the units and closing price from the report) and its sale order, using the calculator's current-year settings. Print the engine's lines for the same orders with `python -c "from datetime import date; from decimal import Decimal as D; from pathlib import Path; from engine.rules import Rules; from engine.charges import Order, order_charges; r = Rules.load(Path('rules')); c = order_charges(r, Order(date.today(), 'etf_equity', 'sell', D('100'), D('250'))); print({k: str(v.value) for k, v in c.lines.items()}, c.total.value)"` (change the order to match). Tabulate calculator against engine, line by line. A difference above ₹0.05 in any line must be explained, or fixed in the rule table (never by editing the engine to match).
2. **Hand check of the sale-year tax.** From the ⓘ trace of the last financial year's tax, recompute the gain, grandfathering floor, exemption, rate and cess on paper and show they agree.
3. **Sanity checks.** Tax is zero in years with no sale and no taxable dividend. "Still holding" is higher than "sold" by exactly the sale charges plus the capital-gains tax. The two profiles differ only where the slab matters.
4. **Data caveats.** Source, dividends finding from Step 6, and that prices are close-of-day.

- [ ] **Step 9: Show the user**

Send `out/checkpoint1.html` with SendUserFile (display `render`). In the message give, for both profiles: money invested, gross end value, all charges, all tax, final amount, in five short lines each. Say which rows used `assumed` or `secondary` rules (the report lists them). Ask the user to look at it before the plan continues.

- [ ] **Step 10: Commit**

```bash
git add data/fetch_yahoo.py data/manifest.json data/processed engine/scenario.py engine/report.py tests docs/verification
git commit -m "feat: checkpoint 1, a traced buy-and-hold report for a Nifty ETF"
```
`out/` is ignored by git; the report is regenerated by the command in Step 7.

---

## Task 14: Futures business income and the audit test

**Files:**
- Create: `engine/business.py`, `tests/test_business.py`, `rules/tax/audit.toml`, `tests/golden/business_rules.toml`, `tests/golden/business_engine.toml`
- Modify: `engine/tax.py` (six edits), `rules/tax/loss_rules.toml` (add `business` rows), `rules/SOURCES.md`, `tests/golden_runner.py` (one edit and one appended kind), `tests/test_golden_kinds_tax.py` (append)

**Interfaces:**
- Consumes: `fy_tax`, `investment_tax`, `Carry`, `ZERO_N` (Tasks 11 and 12); the Research protocol.
- Produces: `Business(pnl: Node, costs: Node)`; `Carry.biz`; `fy_tax(..., business=None)` and `investment_tax(..., business=None)`; `futures_turnover(pnls: list[Node]) -> Node` (sum of the absolute profit or loss of each closed trade); `audit_fee(rules, fy, turnover) -> Node`; table `tax.audit` (`turnover_limit`, `fee`); golden kinds `audit` and `tax_fy` with an optional `[case.input.business]` (`pnl`, `costs`).
- Convention (labelled, conservative): a business loss is set off against slab income only, never against capital gains, and the rest is carried forward for business income only.

**Leads (unverified, from memory):** index futures profits are non-speculative business income at slab rates; a tax audit (section 44AB) is needed above a turnover limit (₹1 crore, or ₹10 crore when almost all receipts and payments are digital; the turnover of futures is the sum of favourable and unfavourable differences); business losses carry forward 8 years against business income. The audit fee is not a legal number; treat it as `assumed`.

- [ ] **Step 1: Research the rows**

Follow the Research protocol. Find, by financial year from FY2010-11: the section 44AB turnover limit that applies to a person trading index futures; the turnover definition for futures (ICAI guidance note); the years a non-speculative business loss can be carried forward. Write:
- `rules/tax/audit.toml`: keyless, fields `turnover_limit` and `fee` (rupees, strings). `fee` is `assumed` (typical professional fee; say how you chose it) unless a source gives one.
- `rules/tax/loss_rules.toml`: add a `kind = "business"` row set beside the existing `capital` rows.
Add sources. Golden cases: `python -m tests.golden_skeleton tax.audit turnover_limit fee` and `python -m tests.golden_skeleton tax.loss_rules value` into `tests/golden/business_rules.toml` (delete the capital-kind cases already covered in `tax_gains_rules.toml` if the skeleton repeats them). Run `python -m pytest -q`: expect the loader and the boundary gate to pass; the row gate fails until Step 8.

- [ ] **Step 2: Write the failing tests**

`tests/test_business.py`:

```python
from decimal import Decimal as Dc

import pytest

from engine.business import audit_fee, futures_turnover
from engine.tax import Business, Carry, TaxProfile, investment_tax
from engine.trace import assert_balanced, const
from tests.helpers import make_rules
from tests.synth_tax import TAX


@pytest.fixture
def rules(tmp_path):
    return make_rules(tmp_path, TAX)


def biz(pnl, costs="0"):
    return Business(const("Futures P&L", pnl), const("Costs", costs))


def extra(rules, fy, business=None, income="1000000", **kw):
    r = investment_tax(rules, fy, TaxProfile("old", Dc(income)), [], business=business, **kw)
    assert_balanced(r.extra)
    return r


def test_profit_after_costs_is_taxed_at_slab_rates(rules):
    assert extra(rules, 2019, biz("150000", "50000")).extra.value == Dc("31200")   # 100,000 x 30% x 1.04


def test_loss_is_set_off_against_other_income(rules):
    assert extra(rules, 2019, biz("-200000")).extra.value == Dc("-41600")          # saves 200,000 x 20% x 1.04


def test_loss_bigger_than_income_is_carried_forward_not_refunded(rules):
    r = extra(rules, 2019, biz("-250000"), income="100000")
    assert r.extra.value == 0
    assert [(o, n.value) for o, n in r.with_items.carry_out.biz] == [(2019, Dc("150000"))]


def test_carried_loss_is_used_against_later_profit(rules):
    carry = Carry(biz=((2019, const("loss", "150000")),))
    r = extra(rules, 2020, biz("200000"), carry_in=carry)
    assert r.extra.value == Dc("15600")                                            # 50,000 x 30% x 1.04
    assert r.with_items.carry_out.biz == ()


@pytest.mark.parametrize("origin, expected", [(2011, "15600"), (2010, "62400")])
def test_business_losses_expire_after_eight_years(rules, origin, expected):
    carry = Carry(biz=((origin, const("loss", "150000")),))
    assert extra(rules, 2019, biz("200000"), carry_in=carry).extra.value == Dc(expected)


def test_unused_carried_loss_survives_a_year_with_no_business(rules):
    carry = Carry(biz=((2019, const("loss", "150000")),))
    r = extra(rules, 2020, None, carry_in=carry)
    assert [(o, n.value) for o, n in r.with_items.carry_out.biz] == [(2019, Dc("150000"))]


def test_audit_fee_only_above_the_turnover_limit(rules):
    turnover = futures_turnover([const("a", "-3000000"), const("b", "4000000"), const("c", "5000001")])
    assert turnover.value == Dc("12000001")
    assert audit_fee(rules, 2019, turnover).value == Dc("25000")
    assert audit_fee(rules, 2019, futures_turnover([const("a", "-3000000")])).value == 0
```

- [ ] **Step 3: Run them to see them fail**

Run: `python -m pytest tests/test_business.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'engine.business'`.

- [ ] **Step 4: Implement**

`engine/business.py`:

```python
"""Futures trading income: the audit test and its cost. The income itself is taxed in tax.py."""
from __future__ import annotations

from datetime import date

from engine.rules import Rules
from engine.trace import Node, add, from_rule, maxn, sub
from engine.tax import ZERO_N


def futures_turnover(pnls: list[Node]) -> Node:
    """Audit turnover for futures: the sum of the absolute profit or loss of each closed trade."""
    return add("Futures turnover", *[maxn(f"Size of {n.label}", n, sub("Negative", ZERO_N, n)) for n in pnls])


def audit_fee(rules: Rules, fy: int, turnover: Node) -> Node:
    """The audit fee if turnover is above the year's limit, else zero."""
    row = rules.at("tax.audit", date(fy, 4, 1))
    if turnover.value > row.dec("turnover_limit"):
        return from_rule("Tax audit fee (turnover above the limit)", row.dec("fee"), row.ref)
    return from_rule("No tax audit needed (turnover within the limit)", 0, row.ref)
```

Now apply these six edits to `engine/tax.py` (each old text appears exactly once):

**Edit 1: Carry gains a business-loss field, and a Business dataclass is added.**

Find:

```python
    lt: tuple[tuple[int, Node], ...] = ()


@dataclass(frozen=True)
class FYTax:
```

Replace with:

```python
    lt: tuple[tuple[int, Node], ...] = ()
    biz: tuple[tuple[int, Node], ...] = ()  # business losses, usable against business income only


@dataclass(frozen=True)
class Business:
    pnl: Node    # realised profit (+) or loss (-) on futures, before costs
    costs: Node  # every deductible cost: charges including STT, and any audit fee


@dataclass(frozen=True)
class FYTax:
```

**Edit 2: fy_tax takes a business argument.**

Find:

```python
           carry_in: Carry = Carry(), dividends: Node | None = None,
           interest: Node | None = None) -> FYTax:
```

Replace with:

```python
           carry_in: Carry = Carry(), dividends: Node | None = None,
           interest: Node | None = None, business: Business | None = None) -> FYTax:
```

**Edit 3: fy_tax adds business income or loss to slab income, before `ordinary` is summed.**

Find:

```python
    ordinary = add("Income taxed at slab rates", *parts)
```

Replace with:

```python
    # Futures income is business income at slab rates. A loss is set off against slab income only
    # (not against capital gains: conservative) and the rest is carried forward for business income.
    new_biz: list[tuple[int, Node]] = []
    if business is not None or carry_in.biz:
        biz_years = int(rules.at("tax.loss_rules", end, kind="business").value)
        old = [(o, a) for o, a in sorted(carry_in.biz, key=lambda t: t[0]) if fy - o <= biz_years]
        net = sub("Business income after costs", business.pnl, business.costs) if business else ZERO_N
        if net.value >= 0:
            left = net
            for o, a in old:
                if left.value <= 0:
                    new_biz.append((o, a))
                    continue
                used = minn(f"Business loss from {fy_label(o)} used", a, left)
                left = sub("Business income after that loss", left, used)
                rest = sub(f"Business loss from {fy_label(o)}, unused", a, used)
                if rest.value > 0:
                    new_biz.append((o, rest))
            parts.append(left)
        else:
            loss = sub("Business loss this year", ZERO_N, net)
            room = maxn("Slab income not below zero", add("Slab income before the business loss", *parts), ZERO_N)
            used = minn("Business loss set off against slab income", loss, room)
            parts.append(sub("Business loss set off", ZERO_N, used))
            rest = sub("Business loss carried forward", loss, used)
            new_biz = old + ([(fy, rest)] if rest.value > 0 else [])
    ordinary = add("Income taxed at slab rates", *parts)
```

**Edit 4: the business-loss carry-forward goes into carry_out.**

Find:

```python
Carry(tuple(new_st), tuple(new_lt)))
```

Replace with:

```python
Carry(tuple(new_st), tuple(new_lt), tuple(new_biz)))
```

**Edit 5: investment_tax takes and passes on a business argument (signature).**

Find:

```python
                   carry_in: Carry = Carry(), dividends: Node | None = None,
                   interest: Node | None = None) -> InvestmentTax:
```

Replace with:

```python
                   carry_in: Carry = Carry(), dividends: Node | None = None,
                   interest: Node | None = None, business: Business | None = None) -> InvestmentTax:
```

**Edit 6: investment_tax takes and passes on a business argument (call).**

Find:

```python
    w = fy_tax(rules, fy, profile, events, carry_in, dividends, interest)
```

Replace with:

```python
    w = fy_tax(rules, fy, profile, events, carry_in, dividends, interest, business)
```

- [ ] **Step 5: Run the tests**

Run: `python -m pytest tests/test_business.py tests/test_tax_fy.py tests/test_tax_classify.py -q`
Expected: all pass.

- [ ] **Step 6: Teach the golden runner about business input and the audit kind**

In `tests/golden_runner.py`, inside `_tax_fy`, change the import line

```python
    from engine.tax import CGEvent, TaxProfile, investment_tax
```
to
```python
    from engine.tax import Business, CGEvent, TaxProfile, investment_tax
```
and replace

```python
    r = investment_tax(rules, i["fy"], TaxProfile(i["regime"], D(i["other_income"])), events,
                       dividends=const("Dividends", i["dividends"]) if "dividends" in i else None,
                       interest=const("Interest", i["interest"]) if "interest" in i else None)
```
with
```python
    b = i.get("business")
    business = Business(const("Futures P&L", b["pnl"]), const("Costs", b["costs"])) if b else None
    r = investment_tax(rules, i["fy"], TaxProfile(i["regime"], D(i["other_income"])), events,
                       dividends=const("Dividends", i["dividends"]) if "dividends" in i else None,
                       interest=const("Interest", i["interest"]) if "interest" in i else None,
                       business=business)
```
Then append to the end of `tests/golden_runner.py`, after two blank lines:

```python
@kind("audit")
def _audit(rules: Rules, c: dict):
    """Audit fee for a year, from the profit or loss of each closed futures trade."""
    from engine.business import audit_fee, futures_turnover
    from engine.trace import assert_balanced, const, rules_used
    i = c["input"]
    fee = audit_fee(rules, i["fy"], futures_turnover([const("Trade", p) for p in i["trade_pnls"]]))
    assert same(fee.value, c["expect"]["fee"]), f"{c['id']}: fee is {fee.value}, hand-worked {c['expect']['fee']}"
    assert_balanced(fee)
    return rules_used(fee)
```

Append to `tests/test_golden_kinds_tax.py`, after two blank lines:

```python
BUSINESS_CASES = '''
[[case]]
id = "futures-profit"
kind = "tax_fy"
source = "test"
[case.input]
fy = 2019
regime = "old"
other_income = "1000000"
[case.input.business]
pnl = "150000"
costs = "50000"
[case.expect]
extra = "31200"

[[case]]
id = "audit-above-limit"
kind = "audit"
source = "test"
[case.input]
fy = 2019
trade_pnls = ["-3000000", "4000000", "5000001"]
[case.expect]
fee = "25000"
'''


def test_business_and_audit_cases_run(tmp_path):
    rules = make_rules(tmp_path / "r", TAX)
    for c in load(tmp_path, BUSINESS_CASES):
        run_case(rules, c)
```

Run: `python -m pytest -q`
Expected: all pass.

- [ ] **Step 7: Write the composition cases**

`tests/golden/business_engine.toml`, hand-worked from the real rows: `tax_fy` cases with `[case.input.business]` (a profit; a loss smaller than other income; a loss bigger than other income, expecting the rest to reduce nothing) and `audit` cases (`[case.input]` `fy`, `trade_pnls = [...]`; `[case.expect]` `fee`) on each side of every change of the audit limit and one above and one below the limit.

- [ ] **Step 8: Run the gates**

Run: `python -m pytest -q`
Expected: all pass, including the row gate (`tax.audit` and `tax.loss_rules[kind=business]` rows are now exercised). Add cases until it does.

- [ ] **Step 9: Commit**

```bash
git add engine rules tests
git commit -m "feat: futures business income, business-loss carry-forward and the audit test"
```
List every `assumed` and `secondary` row in the message body.

---

## Task 15: Final gates and hand-over

**Files:**
- Create: `docs/verification/assumed-rows.md`
- Modify: the project memory `project-goal-and-findings.md` under `C:\Users\rvina\.claude\projects\C--Users-rvina-Downloads-DL-Project\memory\`

**Interfaces:**
- Consumes: everything.
- Produces: a green suite with nothing skipped, and a written list of every rule that is not backed by an official source, for the user to accept or fix.

- [ ] **Step 1: Run everything, and look for skips**

Run: `python -m pytest -q -rs`
Expected: all pass, and no line saying `kind ... is not implemented yet`.

- [ ] **Step 2: List every non-primary rule**

Run:

```text
python -c "from pathlib import Path; from engine.rules import Rules; rows = sorted((r.ref.confidence, r.ref.rule_id, r.valid_from, r.ref.source) for r in Rules.load(Path('rules')).all_rows() if r.ref.confidence != 'primary'); print(len(rows)); [print(*x) for x in rows]"
```
Write the output into `docs/verification/assumed-rows.md`, one line per rule: confidence, rule, from date, source and the `note` from its TOML file, with a one-line "what this could change" for each. Flag the material ones (over 0.01% of turnover or 0.5% of tax).

- [ ] **Step 3: Review with the user**

Show the user the list. Ask in particular: which state's stamp duty to assume before July 2020 if not Maharashtra, and whether they accept the labelled conventions. Change rows the user corrects, adding the source they give.

- [ ] **Step 4: Update the project memory**

In `project-goal-and-findings.md` record: sub-project 1 status, the date rules were last verified, the branch name, and any open items from Step 3. Keep it short and in simple words.

- [ ] **Step 5: Commit and hand over**

```bash
git add docs/verification tests rules
git commit -m "docs: list of rules not backed by an official source"
git log --oneline v3/rules-engine ^main
```
Report to the user in a few lines: what is verified (with counts of rows, cases), what is assumed, the checkpoint file, and what comes next (sub-project 2, the data layer). Do not merge or push. Ask how they want to proceed.
