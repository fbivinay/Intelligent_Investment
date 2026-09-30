import pytest

from tests.golden_runner import check_boundary_tags, load_cases, run_case
from tests.helpers import make_rules
from tests.synth_charges import CHARGES

CHARGES_CASE = '''
[[case]]
id = "etf-sell-after-stt-cut"
kind = "charges"
source = "test"
work = "turnover 100 x 1000 = 100000; STT 0.0005 x 100000 = 50"
boundary = ["charges.stt[instrument_class=etf_equity,side=sell]@2016-01-01:after"]
[case.input]
on = 2016-01-01
instrument_class = "etf_equity"
side = "sell"
qty = "100"
price = "1000"
[case.expect]
stt = "50"
'''


def load(tmp_path, body):
    (tmp_path / "golden").mkdir(parents=True, exist_ok=True)
    (tmp_path / "golden" / "a.toml").write_text(body, encoding="utf-8")
    return load_cases(tmp_path / "golden")


def test_charges_case_runs_and_its_boundary_tag_checks(tmp_path):
    rules = make_rules(tmp_path / "r", CHARGES)
    (c,) = load(tmp_path, CHARGES_CASE)
    check_boundary_tags(c, run_case(rules, c))


def test_a_wrong_hand_calculation_fails(tmp_path):
    rules = make_rules(tmp_path / "r", CHARGES)
    (c,) = load(tmp_path, CHARGES_CASE.replace('stt = "50"', 'stt = "51"'))
    with pytest.raises(AssertionError, match="hand-worked 51"):
        run_case(rules, c)


DP_AMC_CASE = '''
[[case]]
id = "dp-2020"
kind = "dp"
source = "test"
[case.input]
on = 2020-01-01
[case.expect]
total = "19.47"
basis = "per_sale"

[[case]]
id = "amc-standard"
kind = "amc"
source = "test"
[case.input]
on = 2021-03-31
opened = 2020-06-01
[case.expect]
total = "354"

[[case]]
id = "opening-2020"
kind = "account_opening"
source = "test"
[case.input]
opened = 2020-06-01
[case.expect]
total = "472"
'''


def test_dp_amc_and_account_opening_cases_run(tmp_path):
    rules = make_rules(tmp_path / "r", CHARGES)
    for c in load(tmp_path, DP_AMC_CASE):
        run_case(rules, c)


COHORT_CASE = '''
[[case]]
id = "amc-opened-the-day-before"
kind = "amc"
source = "test"
boundary = ["fyers.amc_cohort[]@2020-04-01:before"]
[case.input]
on = 2021-03-31
opened = 2020-03-31
[case.expect]
total = "0"
'''


def test_a_cohort_boundary_tag_checks_against_the_opening_date(tmp_path):
    rules = make_rules(tmp_path / "r", CHARGES)
    (c,) = load(tmp_path, COHORT_CASE)
    check_boundary_tags(c, run_case(rules, c))
    wrong = COHORT_CASE.replace("opened = 2020-03-31", "opened = 2020-04-01")
    (d,) = load(tmp_path / "again", wrong.replace('total = "0"', 'total = "354"'))
    with pytest.raises(AssertionError, match="did not use that row"):
        check_boundary_tags(d, run_case(rules, d))


def test_a_wrong_dp_basis_fails(tmp_path):
    rules = make_rules(tmp_path / "r", CHARGES)
    (c,) = load(tmp_path, DP_AMC_CASE.replace('basis = "per_sale"', 'basis = "per_isin_per_day"').split("[[case]]\nid = \"amc-standard\"")[0])
    with pytest.raises(AssertionError, match="basis"):
        run_case(rules, c)
