import csv
from datetime import date
from decimal import Decimal

import pytest

from data import adjust as adj


def row(d, sym, close, qty="1000", series="EQ", open_=None, high=None, low=None):
    return {"date": d, "symbol": sym, "series": series, "open": open_ or close, "high": high or close, "low": low or close, "close": close, "last": close,
            "prev_close": close, "qty": qty, "value": "1", "trades": "1", "isin": "X"}


SPLIT = [{"symbol": "NIFTYBEES", "ex_date": date(2019, 12, 19), "factor": Decimal(10), "evidence": "close 1292.54 to 130.2 (ratio 9.93); NAV 1292.5 to 130.8"}]


def test_a_split_changes_every_price_before_the_ex_date_and_none_from_it_on():
    rows = [row("2019-12-17", "NIFTYBEES", "1290.00", qty="100"), row("2019-12-18", "NIFTYBEES", "1292.54", qty="200"),
            row("2019-12-19", "NIFTYBEES", "130.20", qty="3000"), row("2019-12-20", "NIFTYBEES", "131.00", qty="4000")]
    out = adj.adjust(rows, SPLIT)
    assert [(r["date"], r["adj_close"], r["adj_qty"], r["adj_factor"]) for r in out] == [
        ("2019-12-17", "129", "1000", "10"), ("2019-12-18", "129.254", "2000", "10"), ("2019-12-19", "130.20", "3000", "1"), ("2019-12-20", "131.00", "4000", "1")]
    assert out[1]["close"] == "1292.54" and out[1]["qty"] == "200"                        # the published columns are untouched


def test_open_high_low_are_adjusted_like_the_close_and_other_symbols_are_left_alone():
    rows = [row("2019-12-18", "NIFTYBEES", "1292.54", open_="1300.0", high="1310.0", low="1280.0"), row("2019-12-18", "GOLDBEES", "35.5")]
    a, b = adj.adjust(rows, SPLIT)
    assert (a["adj_open"], a["adj_high"], a["adj_low"]) == ("130", "131", "128") and (b["adj_close"], b["adj_factor"]) == ("35.5", "1")


def test_two_splits_multiply_for_days_before_both():
    actions = SPLIT + [{"symbol": "NIFTYBEES", "ex_date": date(2022, 1, 3), "factor": Decimal(2), "evidence": "x"}]
    rows = [row("2019-12-18", "NIFTYBEES", "1000"), row("2020-06-01", "NIFTYBEES", "100"), row("2022-01-03", "NIFTYBEES", "50")]
    assert [r["adj_factor"] for r in adj.adjust(rows, actions)] == ["20", "2", "1"]


def test_actions_are_read_with_their_evidence_and_bad_ones_are_refused(tmp_path):
    p = tmp_path / "a.csv"
    p.write_text("symbol,ex_date,kind,factor,evidence\nNIFTYBEES,2019-12-19,split,10,\"ratio 9.93; NAV agrees\"\n", newline="")
    (a,) = adj.load_actions(p)
    assert a == {"symbol": "NIFTYBEES", "ex_date": date(2019, 12, 19), "factor": Decimal(10), "nav_ex_date": None, "evidence": "ratio 9.93; NAV agrees"}
    for bad, why in [("NIFTYBEES,2019-12-19,split,0,x", "factor"), ("NIFTYBEES,2019-12-19,split,-2,x", "factor"), ("NIFTYBEES,2019-12-19,merger,10,x", "kind"),
                     ("NIFTYBEES,2019-12-19,split,10,", "evidence"),
                     ("NIFTYBEES,2019-12-19,split,10,x\nNIFTYBEES,2019-12-19,split,2,y", "twice")]:
        p.write_text("symbol,ex_date,kind,factor,evidence\n" + bad + "\n", newline="")
        with pytest.raises(ValueError, match=why):
            adj.load_actions(p)


def test_candidates_are_day_to_day_close_ratios_outside_the_band_per_symbol():
    rows = [row("2019-12-18", "NIFTYBEES", "1292.54"), row("2019-12-19", "NIFTYBEES", "130.20"), row("2019-12-20", "NIFTYBEES", "131.00"),
            row("2019-12-18", "GOLDBEES", "35.5"), row("2019-12-19", "GOLDBEES", "36.0")]
    (c,) = adj.candidates(rows)
    assert (c["symbol"], c["date"], c["prev_date"], c["ratio"]) == ("NIFTYBEES", "2019-12-19", "2019-12-18", Decimal("1292.54") / Decimal("130.20"))


def test_a_series_that_changes_between_days_is_not_compared_across_series():
    rows = [row("2019-12-18", "X", "100", series="EQ"), row("2019-12-19", "X", "10", series="BE")]
    assert adj.candidates(rows) == []


def test_unexplained_lists_the_gaps_no_action_covers():
    rows = [row("2019-12-18", "NIFTYBEES", "1292.54"), row("2019-12-19", "NIFTYBEES", "130.20"), row("2020-03-02", "NIFTYBEES", "130.0"),
            row("2020-03-03", "NIFTYBEES", "60.0")]
    assert [(c["symbol"], c["date"]) for c in adj.unexplained(rows, SPLIT)] == [("NIFTYBEES", "2020-03-03")]
    assert adj.unexplained(rows[:2], SPLIT) == []


def test_an_action_whose_ex_date_shows_no_gap_is_reported_as_unconfirmed():
    rows = [row("2019-12-18", "NIFTYBEES", "130.0"), row("2019-12-19", "NIFTYBEES", "130.2")]
    assert [a["symbol"] for a in adj.unconfirmed(rows, SPLIT)] == ["NIFTYBEES"]
    rows = [row("2019-12-18", "NIFTYBEES", "1292.54"), row("2019-12-19", "NIFTYBEES", "130.20")]
    assert adj.unconfirmed(rows, SPLIT) == []


def test_build_writes_the_adjusted_csv_from_the_processed_one_and_repeats_byte_for_byte(tmp_path):
    (tmp_path / "processed").mkdir()
    fields = ["date", "symbol", "series", "open", "high", "low", "close", "last", "prev_close", "qty", "value", "trades", "isin"]
    with (tmp_path / "processed" / "nse_etf_daily.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fields, lineterminator="\n")
        w.writeheader()
        w.writerows([row("2019-12-18", "NIFTYBEES", "1292.54"), row("2019-12-19", "NIFTYBEES", "130.20")])
    (tmp_path / "corporate_actions.csv").write_text("symbol,ex_date,kind,factor,evidence\nNIFTYBEES,2019-12-19,split,10,\"ratio 9.93\"\n", newline="")
    assert adj.build(tmp_path) == 2
    first = (tmp_path / "processed" / "etf_daily_adjusted.csv").read_bytes()
    assert adj.build(tmp_path) == 2 and (tmp_path / "processed" / "etf_daily_adjusted.csv").read_bytes() == first and b"\r" not in first
    rows = list(csv.DictReader((tmp_path / "processed" / "etf_daily_adjusted.csv").open(newline="")))
    assert rows[0]["adj_close"] == "129.254" and rows[1]["adj_close"] == "130.20"


def test_build_refuses_when_a_gap_is_left_unexplained(tmp_path):
    (tmp_path / "processed").mkdir()
    fields = ["date", "symbol", "series", "open", "high", "low", "close", "last", "prev_close", "qty", "value", "trades", "isin"]
    with (tmp_path / "processed" / "nse_etf_daily.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fields, lineterminator="\n")
        w.writeheader()
        w.writerows([row("2019-12-18", "NIFTYBEES", "1292.54"), row("2019-12-19", "NIFTYBEES", "130.20")])
    (tmp_path / "corporate_actions.csv").write_text("symbol,ex_date,kind,factor,evidence\n", newline="")
    with pytest.raises(ValueError, match="NIFTYBEES 2019-12-19"):
        adj.build(tmp_path)


def test_an_action_whose_factor_does_not_match_the_gap_is_unconfirmed():
    rows = [row("2019-12-18", "NIFTYBEES", "1292.54"), row("2019-12-19", "NIFTYBEES", "130.20")]
    two = [{"symbol": "NIFTYBEES", "ex_date": date(2019, 12, 19), "factor": Decimal(2), "evidence": "typo"}]
    assert [a["factor"] for a in adj.unconfirmed(rows, two)] == [Decimal(2)]


def test_a_jump_up_is_a_candidate_too_for_example_a_consolidation():
    rows = [row("2021-01-04", "X", "10"), row("2021-01-05", "X", "100")]
    (c,) = adj.candidates(rows)
    assert (c["date"], c["ratio"]) == ("2021-01-05", Decimal("0.1"))


def test_build_refuses_an_action_that_shows_no_gap_in_the_prices(tmp_path):
    (tmp_path / "processed").mkdir()
    fields = ["date", "symbol", "series", "open", "high", "low", "close", "last", "prev_close", "qty", "value", "trades", "isin"]
    with (tmp_path / "processed" / "nse_etf_daily.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fields, lineterminator="\n")
        w.writeheader()
        w.writerows([row("2019-12-18", "NIFTYBEES", "130.0"), row("2019-12-19", "NIFTYBEES", "130.2")])
    (tmp_path / "corporate_actions.csv").write_text("symbol,ex_date,kind,factor,evidence\nNIFTYBEES,2019-12-19,split,10,\"typo\"\n", newline="")
    with pytest.raises(ValueError, match="shows no matching gap"):
        adj.build(tmp_path)


def test_the_date_the_nav_series_switches_scale_is_optional_and_read_when_given(tmp_path):
    p = tmp_path / "a.csv"
    p.write_text("symbol,ex_date,kind,factor,nav_ex_date,evidence\nNIFTYBEES,2019-12-19,split,10,2019-12-23,\"x\"\nGOLDBEES,2019-12-19,split,100,,\"y\"\n", newline="")
    gold, nifty = adj.load_actions(p)
    assert (gold["symbol"], gold["nav_ex_date"]) == ("GOLDBEES", None) and nifty["nav_ex_date"] == date(2019, 12, 23)
