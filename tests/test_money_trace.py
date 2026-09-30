import json
from datetime import date
from decimal import Decimal

import pytest

from engine.money import D, round_step
from engine.trace import (Node, RuleRef, add, assert_balanced, cite, const, flags, from_rule, maxn, minn, mul,
                          rnd, rules_used, sub, to_dict, walk)


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


def test_to_dict_carries_the_note_of_each_rule():
    a = RuleRef("u[k=v]", date(2010, 4, 1), None, "guess", date(2026, 1, 1), "assumed", "stand-in, see the rule file")
    assert to_dict(from_rule("a", "2", a))["rules"][0]["note"] == "stand-in, see the rule file"


def test_flags_leave_out_a_weak_rule_that_cannot_move_the_number():
    w = RuleRef("w[k=v]", date(2010, 4, 1), None, "guess", date(2026, 1, 1), "assumed")
    p = RuleRef("p[k=v]", date(2010, 4, 1), None, "act", date(2026, 1, 1), "primary")
    unused_max = maxn("larger", from_rule("chosen", "5", p), sub("negative", const("z", "0"), from_rule("weak, not chosen", "3", w)))
    unused_min = minn("smaller", from_rule("chosen", "1", p), from_rule("weak, not chosen", "3", w))
    times_zero = mul("nothing", const("zero", "0"), from_rule("weak, times zero", "0.1", w))
    assert flags(add("total", unused_max, unused_min, times_zero)) == []
    assert rules_used(add("total", unused_max)) >= {w, p}                                        # still read, and still visible to the gates


def test_flags_keep_a_weak_rule_that_decides_a_number():
    w = RuleRef("w[k=v]", date(2010, 4, 1), None, "guess", date(2026, 1, 1), "assumed")
    p = RuleRef("p[k=v]", date(2010, 4, 1), None, "act", date(2026, 1, 1), "primary")
    chosen = maxn("larger", from_rule("weak, chosen", "5", w), from_rule("other", "3", p))
    fee = mul("fee", const("turnover", "1000"), from_rule("weak rate", "0.001", w))
    assert [f.rule_id for f in flags(chosen)] == ["w[k=v]"] and [f.rule_id for f in flags(fee)] == ["w[k=v]"]
    assert [f.rule_id for f in flags(add("zero fee", from_rule("weak zero fee", "0", w)))] == ["w[k=v]"]   # an assumed zero can still be wrong
