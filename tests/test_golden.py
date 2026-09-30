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
