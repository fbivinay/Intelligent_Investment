"""Futures trading income: the audit test and its cost. The income itself is taxed in tax.py."""
from __future__ import annotations

from engine.rules import Rules
from engine.tax import ZERO_N
from engine.trace import Node, add, from_row, from_rule, maxn, sub


def futures_turnover(pnls: list[Node]) -> Node:
    """Audit turnover for futures: the sum of the absolute profit or loss of each closed trade (ICAI guidance note, S77)."""
    return add("Futures turnover", *[maxn(f"Size of {n.label}", n, sub("Negative", ZERO_N, n)) for n in pnls])


def audit_fee(rules: Rules, fy: int, turnover: Node) -> Node:
    """The audit fee if turnover is above the year's limit, else zero."""
    row = rules.at_fy("tax.audit", fy)
    limit = row.dec("turnover_limit")
    seen = f"turnover {turnover.value:,.2f} against the limit {limit:,.0f}"
    if turnover.value > limit:
        return from_row("Tax audit fee (turnover above the limit)", row, "fee", note=seen)
    return from_rule("No tax audit needed (turnover within the limit)", 0, row.ref, note=seen)
