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
