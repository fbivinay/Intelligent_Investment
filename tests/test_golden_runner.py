from datetime import date

import pytest

from tests.golden_runner import (all_boundaries, check_boundary_tags, load_cases, missing_coverage,
                                 run_case, same)
from tests.golden_skeleton import changes, skeleton
from tests.helpers import make_rules, table


@pytest.fixture
def rules(tmp_path):
    text = table(["seg"], [
        'seg = "eq"\nfrom = 2010-04-01\nto = 2016-05-31\nvalue = "0.001"',
        'seg = "eq"\nfrom = 2016-06-01\nvalue = "0.0005"\nlist = [ "a", "b" ]',
    ])
    return make_rules(tmp_path, {"charges.stt": text})


def write(tmp_path, body):
    (tmp_path / "golden").mkdir(exist_ok=True)
    (tmp_path / "golden" / "a.toml").write_text(body, encoding="utf-8")
    return load_cases(tmp_path / "golden")


CASE = '''
[[case]]
id = "stt-before"
kind = "rule_value"
source = "S1 test"
table = "charges.stt"
on = 2016-05-31
key = { seg = "eq" }
boundary = ["charges.stt[seg=eq]@2016-06-01:before"]
[case.expect]
value = "0.001"
'''


def test_rule_value_case_passes_and_reports_the_row_used(rules, tmp_path):
    (c,) = write(tmp_path, CASE)
    check_boundary_tags(c, run_case(rules, c))


def test_wrong_typed_value_fails(rules, tmp_path):
    (c,) = write(tmp_path, CASE.replace('value = "0.001"', 'value = "0.002"'))
    with pytest.raises(AssertionError, match="source says '0.002'"):
        run_case(rules, c)


def test_several_fields_and_non_numbers_are_compared(rules, tmp_path):
    body = CASE.replace("2016-05-31", "2016-06-01").replace('value = "0.001"', 'value = "0.00050"\nlist = [ "a", "b" ]')
    (c,) = write(tmp_path, body.replace('boundary = ["charges.stt[seg=eq]@2016-06-01:before"]\n', ""))
    run_case(rules, c)
    assert same("0.15", "0.150") and same(["a"], ["a"]) and not same(["a"], ["b"]) and same(True, True)


def test_a_case_on_the_wrong_side_fails_its_boundary_tag(rules, tmp_path):
    body = CASE.replace("on = 2016-05-31", "on = 2016-06-01").replace('value = "0.001"', 'value = "0.0005"')
    (c,) = write(tmp_path, body)
    with pytest.raises(AssertionError, match="did not use that row"):
        check_boundary_tags(c, run_case(rules, c))


def test_coverage_lists_every_missing_side_of_every_change(rules, tmp_path):
    assert list(all_boundaries(rules)) == [("charges.stt[seg=eq]", date(2016, 6, 1))]
    (c,) = write(tmp_path, CASE)
    assert missing_coverage(rules, [c]) == ["charges.stt[seg=eq]@2016-06-01:after"]


def test_cases_need_id_kind_source_and_unique_ids(tmp_path):
    with pytest.raises(ValueError, match="missing `source`"):
        write(tmp_path, '[[case]]\nid = "a"\nkind = "rule_value"\n')
    (tmp_path / "golden" / "a.toml").write_text(CASE + CASE, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_cases(tmp_path / "golden")


def test_skeleton_prints_a_tagged_case_on_each_side_of_a_change(rules):
    text = skeleton(rules, "charges.stt", ["value"])
    assert "on = 2016-05-31" in text and "on = 2016-06-01" in text
    assert 'boundary = ["charges.stt[seg=eq]@2016-06-01:before"]' in text
    assert 'value = ""' in text and text.count("[[case]]") == 2


def test_changes_lists_each_date_with_the_rules_that_change(rules):
    assert changes(rules, ("charges.",)) == ["2016-06-01: charges.stt[seg=eq]"]
    assert changes(rules, ("tax.",)) == []
