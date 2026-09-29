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
