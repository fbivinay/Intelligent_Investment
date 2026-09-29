from datetime import date
from decimal import Decimal

import pytest

from engine.rules import RuleNotFound, RuleTableError
from tests.helpers import make_rules, table


def two_rows():
    return table(["seg"], [
        'seg = "eq"\nfrom = 2010-04-01\nto = 2016-05-31\nvalue = "0.001"',
        'seg = "eq"\nfrom = 2016-06-01\nvalue = "0.0005"',
    ])


def test_lookup_is_inclusive_on_both_ends(tmp_path):
    r = make_rules(tmp_path, {"charges.stt": two_rows()})
    assert r.at("charges.stt", date(2016, 5, 31), seg="eq").value == Decimal("0.001")
    assert r.at("charges.stt", date(2016, 6, 1), seg="eq").value == Decimal("0.0005")
    assert r.at("charges.stt", date(2010, 4, 1), seg="eq").ref.rule_id == "charges.stt[seg=eq]"


def test_missing_date_or_key_raises_instead_of_guessing(tmp_path):
    r = make_rules(tmp_path, {"charges.stt": two_rows()})
    with pytest.raises(RuleNotFound, match="2009-12-31"):
        r.at("charges.stt", date(2009, 12, 31), seg="eq")
    with pytest.raises(RuleNotFound):
        r.at("charges.stt", date(2020, 1, 1), seg="other")
    with pytest.raises(RuleNotFound, match="no rule table"):
        r.at("nope", date(2020, 1, 1))
    with pytest.raises(TypeError):
        r.at("charges.stt", date(2020, 1, 1))


@pytest.mark.parametrize("second_from, why", [("2016-06-02", "gap"), ("2016-05-31", "overlap")])
def test_gap_or_overlap_is_rejected(tmp_path, second_from, why):
    text = table(["seg"], [
        'seg = "eq"\nfrom = 2010-04-01\nto = 2016-05-31\nvalue = "1"',
        f'seg = "eq"\nfrom = {second_from}\nvalue = "2"',
    ])
    with pytest.raises(RuleTableError, match="gap or overlap"):
        make_rules(tmp_path, {"t": text})


def test_each_bad_row_is_named(tmp_path):
    base = 'seg = "eq"\nfrom = 2010-04-01\nvalue = "1"\n'
    cases = {
        "missing source": (base + 'verified_on = 2026-01-01\nconfidence = "primary"\n', "missing `source`"),
        "bad confidence": (base + 'source = "x"\nverified_on = 2026-01-01\nconfidence = "sure"\n', "confidence must be"),
        "assumed without note": (base + 'source = "x"\nverified_on = 2026-01-01\nconfidence = "assumed"\n', "note"),
        "future verified_on": (base + 'source = "x"\nverified_on = 2999-01-01\nconfidence = "primary"\n', "future"),
        "starts late": ('seg = "eq"\nfrom = 2011-01-01\nvalue = "1"\nsource = "x"\nverified_on = 2026-01-01\nconfidence = "primary"\n', "must start on or before"),
    }
    for name, (row, msg) in cases.items():
        text = '[meta]\nkeys = ["seg"]\ncoverage_from = 2010-04-01\n[[row]]\n' + row
        with pytest.raises(RuleTableError, match=msg):
            make_rules(tmp_path / name.replace(" ", "_"), {"t": text})


def test_last_row_must_be_open_ended_unless_declared(tmp_path):
    closed = table(["seg"], ['seg = "eq"\nfrom = 2010-04-01\nto = 2011-03-31\nvalue = "1"'])
    with pytest.raises(RuleTableError, match="open-ended"):
        make_rules(tmp_path / "a", {"t": closed})
    ok = table(["seg"], ['seg = "eq"\nfrom = 2010-04-01\nto = 2011-03-31\nvalue = "1"'],
               extra_meta="open_ended = false")
    make_rules(tmp_path / "b", {"t": ok})


def test_late_keys_may_start_after_coverage(tmp_path):
    text = table(["regime"], [
        'regime = "old"\nfrom = 2010-04-01\nvalue = "1"',
        'regime = "new"\nfrom = 2020-04-01\nvalue = "2"',
    ], extra_meta='late_keys = [{ regime = "new", from = 2020-04-01 }]')
    r = make_rules(tmp_path, {"tax.slabs": text})
    assert r.has("tax.slabs", date(2021, 1, 1), regime="new")
    assert not r.has("tax.slabs", date(2019, 1, 1), regime="new")


def test_rows_carry_confidence_and_payload(tmp_path):
    text = table(["seg"], ['seg = "eq"\nfrom = 2010-04-01\nvalue = "1"\nlist = [ "a", "b" ]'])
    row = make_rules(tmp_path, {"t": text}).at("t", date(2020, 1, 1), seg="eq")
    assert row.ref.confidence == "primary" and row.data["list"] == ["a", "b"]
