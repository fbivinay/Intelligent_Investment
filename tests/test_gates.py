"""Gates that keep the golden cases honest. FAMILIES grows as the engine tasks land."""
from datetime import date
from pathlib import Path

from engine.rules import Rules
from tests.golden_runner import KINDS, load_cases, run_case

ROOT = Path(__file__).resolve().parents[1]
RULES = Rules.load(ROOT / "rules")
CASES = load_cases(ROOT / "tests" / "golden")
FAMILIES = ("fyers.", "charges.", "tax.")
# Rows no engine case can reach. Indexation ended for sales on or after 2024-07-23 and no modelled asset class is indexed
# after that, so the inflation index of the years from 2025-26 is stored for completeness but never read.
UNREACHABLE = {("tax.cii[series=2001]", date(2025, 4, 1)), ("tax.cii[series=2001]", date(2026, 4, 1))}


def _used():
    used = set()
    for c in CASES:
        if c["kind"] != "rule_value" and c["kind"] in KINDS:
            used |= {(r.rule_id, r.valid_from) for r in run_case(RULES, c)}
    return used


def test_every_row_is_exercised_by_a_hand_worked_engine_case():
    rows = {(r.ref.rule_id, r.valid_from) for r in RULES.all_rows() if r.table.startswith(FAMILIES)}
    missing = rows - _used() - UNREACHABLE
    assert not missing, f"rows no engine case exercises: {sorted(missing)[:25]}"


def test_the_unreachable_list_holds_only_rows_that_really_are_unused():
    assert not UNREACHABLE & _used(), "an engine case now reads a row listed as unreachable: remove it from UNREACHABLE"


def test_no_case_uses_a_kind_the_runner_lacks():
    assert {c["kind"] for c in CASES} <= set(KINDS)
