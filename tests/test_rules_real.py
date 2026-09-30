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


def test_surcharge_section_names_are_names_the_engine_can_meet():
    # a mistyped section in test_excludes or cap_sections would silently leave out or cap nothing
    known = {"dividend", "115BBDA"}
    for row in RULES.tables["tax.capital_gains"].all_rows():
        known |= {row.data[f] for f in ("st_section", "lt_section", "lt_alt_section") if f in row.data}
    for row in RULES.tables["tax.surcharge"].all_rows():
        named = set(row.data.get("cap_sections", []))
        for tier in row.data["tiers"]:
            named |= set(tier.get("test_excludes", []))
        assert named <= known, f"{row.ref.rule_id} from {row.valid_from} names {sorted(named - known)}, which no gain or dividend is called"


def test_every_source_id_a_row_mentions_is_listed_in_sources_md():
    for row in RULES.all_rows():
        for sid in re.findall(r"\bS\d+\b", row.ref.source):
            assert sid in SOURCE_IDS, f"{row.ref.rule_id} from {row.valid_from} cites {sid}, which rules/SOURCES.md does not list"


def test_a_row_with_no_usable_source_is_assumed():
    for row in RULES.all_rows():
        if re.match(r"S0\b", row.ref.source):
            assert row.ref.confidence == "assumed", f"{row.ref.rule_id} from {row.valid_from} has source S0, so it can only be assumed"


ADMISSIONS = ("not researched", "stand-in", "assumed", "not found", "extrapolat", "back-fill", "were not checked", "not checked")


def test_a_row_that_says_in_its_note_that_it_is_a_stand_in_or_an_assumption_is_marked_assumed():
    for row in RULES.all_rows():
        note = row.ref.note.lower()
        if row.ref.confidence != "assumed":
            said = [w for w in ADMISSIONS if w in note]
            assert not said, f"{row.ref.rule_id} from {row.valid_from} is {row.ref.confidence} but its note says {said}: mark it assumed"
