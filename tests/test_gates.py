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
