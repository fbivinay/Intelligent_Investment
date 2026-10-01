import json
from decimal import Decimal

import pytest

from calc import api


@pytest.fixture(scope="module")
def answer():
    return api.calculate({"amount": 500000, "start": "2016-04-01", "end": "2024-03-28", "level": "Balanced", "regime": "new", "other_income": 1500000,
                          "compare": ["NIFTYBEES", "GOLDBEES", "LIQUID_FUND", "NIFTY50_INDEX_FUND"], "horizon": 3})


def test_the_answer_is_plain_json_with_the_product_first_and_the_chosen_alternatives():
    a = api.calculate({"amount": 200000, "start": "2018-06-01", "end": "2019-06-03", "level": "Conservative", "compare": ["GOLDBEES"], "horizon": 1})
    assert json.loads(json.dumps(a)) == a
    assert [r["id"] for r in a["results"]] == ["PRODUCT_Conservative", "GOLDBEES"]


def test_every_money_figure_has_a_trace_that_exists_and_whose_value_matches(answer):
    for r in answer["results"]:
        for key in ("net", "gross_end", "charges", "tax", "held_net"):
            fig = r[key]
            t = answer["traces"][fig["trace"]]
            assert Decimal(t["value"]) == Decimal(fig["exact"]) and abs(float(fig["exact"]) - fig["value"]) < 0.01
        for line in r["charges_by_kind"] + r["tax_by_fy"]:
            assert line["trace"] in answer["traces"]


def test_the_traces_carry_their_rules_sources_and_the_flags_of_weak_rules(answer):
    t = answer["traces"][answer["results"][0]["tax"]["trace"]]
    found = []

    def walk(n):
        found.extend(n.get("rules", []))
        for c in n.get("inputs", []):
            walk(c)
    walk(t)
    assert found and all({"id", "source", "verified_on", "confidence"} <= set(r) for r in found)
    assert "flags" in t


def test_long_lists_in_a_trace_are_cut_with_a_line_saying_how_many_more(answer):
    big = [t for t in answer["traces"].values() if any(c.get("op") == "more" for c in t.get("inputs", []))]
    assert big
    more = [c for c in big[0]["inputs"] if c["op"] == "more"][0]
    assert "more" in more["label"] and len(big[0]["inputs"]) == api.MAX_CHILDREN + 1


def test_the_stamps_the_csv_the_series_and_the_projections_are_there(answer):
    assert answer["stamps"]["data_as_of"] == "2026-09-30" and answer["stamps"]["rules_verified_on"] == "2026-09-30" and "frozen-design-v1" in answer["stamps"]["signal"]
    assert answer["csv"]["trades"].startswith("date,asset,class,side") and answer["csv"]["tax_lines"].startswith("financial_year,")
    s = answer["series"]["PRODUCT_Balanced"]
    assert s["dates"][0] == "2016-04-01" and len(s["dates"]) == len(s["values"]) and len(s["dates"]) < 600              # thinned for the chart
    p = answer["projections"]["NIFTYBEES"]
    assert p["years"] == 3 and p["p10"] <= p["p50"] <= p["p90"] and "ESTIMATE" in p["label"]


def test_the_end_convention_picks_the_headline_ending():
    hold = api.calculate({"amount": 200000, "start": "2018-06-01", "end": "2019-06-03", "level": "Conservative", "compare": [], "end_convention": "hold", "horizon": 1})
    sell = api.calculate({"amount": 200000, "start": "2018-06-01", "end": "2019-06-03", "level": "Conservative", "compare": [], "end_convention": "sell", "horizon": 1})
    assert hold["results"][0]["headline"] == "held" and sell["results"][0]["headline"] == "sold"
    assert hold["results"][0]["held_net"]["exact"] == sell["results"][0]["held_net"]["exact"]


@pytest.mark.parametrize("params,needle", [
    ({"amount": 100000, "start": "2016-04-01", "end": "2015-04-01"}, "after the start"),
    ({"amount": -5, "start": "2016-04-01", "end": "2017-04-01"}, "amount"),
    ({"amount": 100000, "start": "2009-04-01", "end": "2017-04-01"}, "2010-04-01"),
    ({"amount": 100000, "start": "2016-04-01", "end": "2030-04-01"}, "2026-09-30"),
    ({"amount": 100000, "start": "2016-04-01", "end": "2017-04-01", "level": "Wild"}, "level"),
    ({"amount": 100000, "start": "2016-04-01", "end": "2017-04-01", "regime": "flat"}, "regime"),
    ({"amount": 100000, "start": "2016-04-01", "end": "2017-04-01", "horizon": 40}, "horizon"),
    ({"amount": 100000, "start": "not a date", "end": "2017-04-01"}, "date"),
    ({"amount": 100000, "start": "2016-04-01", "end": "2017-04-01", "compare": ["SENSEX"]}, "unknown option"),
])
def test_bad_inputs_are_refused_with_a_message_and_nothing_else(params, needle):
    a = api.calculate(params)
    assert a["error"] and needle in a["error"] and "results" not in a


def test_a_product_start_before_2013_04_and_a_fund_that_did_not_exist_yet_are_messages_beside_the_other_results():
    a = api.calculate({"amount": 300000, "start": "2010-04-05", "end": "2014-04-01", "level": "Aggressive", "compare": ["NIFTYBEES", "NEXT50_INDEX_FUND"], "horizon": 1})
    ids = {m["id"]: m["text"] for m in a["messages"]}
    assert "2013-04-01" in ids["PRODUCT_Aggressive"] and "2010-06-29" in ids["NEXT50_INDEX_FUND"]
    assert [r["id"] for r in a["results"]] == ["NIFTYBEES"]
