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
