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
