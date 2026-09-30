import pytest

from tests.golden_runner import check_boundary_tags, load_cases, run_case
from tests.helpers import make_rules
from tests.synth_tax import TAX

TAX_CASE = '''
[[case]]
id = "stcg-2019"
kind = "tax_fy"
source = "test"
work = "10,000 x 15% = 1,500; x 1.04 cess = 1,560"
[case.input]
fy = 2019
regime = "old"
other_income = "1000000"
[[case.input.events]]
sale_date = 2019-12-01
acq_date = 2019-06-01
asset_class = "etf_equity"
proceeds = "20000"
cost = "10000"
[case.expect]
extra = "1560"
special_tax = "1500"
'''


def load(tmp_path, body):
    (tmp_path / "golden").mkdir(parents=True, exist_ok=True)
    (tmp_path / "golden" / "a.toml").write_text(body, encoding="utf-8")
    return load_cases(tmp_path / "golden")


def test_tax_fy_case_runs(tmp_path):
    rules = make_rules(tmp_path / "r", TAX)
    (c,) = load(tmp_path, TAX_CASE)
    run_case(rules, c)


def test_a_wrong_hand_calculation_fails(tmp_path):
    rules = make_rules(tmp_path / "r", TAX)
    (c,) = load(tmp_path, TAX_CASE.replace('extra = "1560"', 'extra = "1561"'))
    with pytest.raises(AssertionError, match="hand-worked 1561"):
        run_case(rules, c)


CARRY_CASE = '''
[[case]]
id = "loss-carried-in"
kind = "tax_fy"
source = "test"
work = "gain 100,000 less loss 40,000 = 60,000 x 15% = 9,000; x 1.04 = 9,360"
[case.input]
fy = 2019
regime = "old"
other_income = "1000000"
carry_st = [{ origin = 2018, amount = "40000" }]
[[case.input.events]]
sale_date = 2019-09-01
acq_date = 2019-05-01
asset_class = "etf_equity"
proceeds = "200000"
cost = "100000"
[case.expect]
extra = "9360"
'''


def test_a_case_can_bring_losses_forward_and_dividends_and_interest_in(tmp_path):
    rules = make_rules(tmp_path / "r", TAX)
    (c,) = load(tmp_path, CARRY_CASE)
    run_case(rules, c)
    div = CARRY_CASE.replace('carry_st = [{ origin = 2018, amount = "40000" }]', 'dividends = "100000"\ninterest = "10000"')
    div = div.replace('extra = "9360"', 'total_income = "1110000"')
    (d,) = load(tmp_path / "again", div)
    run_case(rules, d)
