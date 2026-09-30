import csv
import json
from decimal import Decimal

from data import gaps


def test_calendar_gaps_lists_days_only_one_side_has_inside_the_window():
    nse = {"2020-01-01", "2020-01-02", "2020-01-04", "2019-12-31"}
    other = {"2020-01-01", "2020-01-02", "2020-01-03", "2021-01-01"}
    got = gaps.calendar_gaps(nse, other, "2020-01-01", "2020-12-31")
    assert got == {"only_nse": ["2020-01-04"], "only_other": ["2020-01-03"]}


def test_price_diffs_compares_the_days_both_have_as_percent_of_the_other_source():
    got = gaps.price_diffs({"2020-01-01": Decimal("100"), "2020-01-02": Decimal("101"), "2020-01-03": Decimal("5")},
                           {"2020-01-01": Decimal("100"), "2020-01-02": Decimal("100"), "2020-01-04": Decimal("5")})
    assert got == [("2020-01-01", Decimal("100"), Decimal("100"), Decimal("0")), ("2020-01-02", Decimal("101"), Decimal("100"), Decimal("1"))]


def test_summary_counts_the_days_over_the_tolerance_and_names_the_worst():
    diffs = [("2020-01-01", Decimal(100), Decimal(100), Decimal(0)), ("2020-01-02", Decimal(101), Decimal(100), Decimal(1)),
             ("2020-01-03", Decimal(97), Decimal(100), Decimal(-3))]
    s = gaps.summary(diffs, Decimal("0.5"))
    assert s == {"days": 3, "over": 2, "max_abs": Decimal(3), "max_day": "2020-01-03", "worst": [("2020-01-03", Decimal(-3)), ("2020-01-02", Decimal(1))]}
    assert gaps.summary([], Decimal("0.5")) == {"days": 0, "over": 0, "max_abs": Decimal(0), "max_day": None, "worst": []}


def write(path, header, rows):
    with path.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def make_root(tmp_path):
    (tmp_path / "processed").mkdir()
    write(tmp_path / "nse_days.csv", ["kind", "date", "status", "bytes", "sha256", "url", "retrieved"],
          [["cash", "2020-01-01", "ok", 1, "a" * 64, "u", "2026-09-30"], ["cash", "2020-01-02", "ok", 1, "b" * 64, "u", "2026-09-30"],
           ["cash", "2020-01-03", "absent", 0, "", "u", "2026-09-30"], ["cash", "2020-01-04", "denied", 0, "", "u", "2026-09-30"],
           ["fo", "2020-01-01", "ok", 1, "c" * 64, "u", "2026-09-30"], ["fo", "2020-01-02", "absent", 0, "", "u", "2026-09-30"]])
    write(tmp_path / "processed" / "etf_daily_adjusted.csv", ["date", "symbol", "series", "close", "adj_close", "adj_qty"],
          [["2020-01-01", "NIFTYBEES", "EQ", "100", "100", "10"], ["2020-01-02", "NIFTYBEES", "EQ", "101", "101", "10"]])
    write(tmp_path / "processed" / "NIFTYBEES.csv", ["date", "high", "close"], [["2020-01-01", "101", "100"], ["2020-01-02", "102", "100"], ["2020-01-03", "102", "100"]])
    write(tmp_path / "processed" / "amfi_nav_daily.csv", ["date", "code", "nav"], [["2020-01-01", "140084", "100.5"], ["2020-01-02", "140084", "100.0"]])
    (tmp_path / "manifest.json").write_text(json.dumps({"NIFTYBEES.csv": {"excluded": {"2020-01-03": "a glitch"}}}))
    return tmp_path


def test_report_states_the_day_list_the_calendar_check_and_both_price_cross_checks(tmp_path):
    text = gaps.report(make_root(tmp_path), symbol="NIFTYBEES", code="140084", yahoo="NIFTYBEES.csv", start="2020-01-01", end="2020-01-31")
    assert "- cash: ok 2, absent 1, denied 1" in text and "- fo: ok 1, absent 1" in text
    assert "- cash days by year: 2020: 2" in text
    assert "days the NSE cash list has and Yahoo does not: none" in text
    assert "days Yahoo has and the NSE cash list does not: 2020-01-03" in text                      # a real gap, or a day Yahoo wrongly has
    assert "2 days compared, 1 differ by more than 0.5%, largest 1.00% (2020-01-02)" in text       # 101 against 100
    assert "AMFI NAV (scheme 140084): 2 days compared, 0 differ by more than 1%" in text


def test_report_marks_a_day_yahoo_left_out_on_purpose_as_a_known_exclusion(tmp_path):
    root = make_root(tmp_path)
    write(root / "nse_days.csv", ["kind", "date", "status", "bytes", "sha256", "url", "retrieved"],
          [["cash", d, "ok", 1, "a" * 64, "u", "2026-09-30"] for d in ("2020-01-01", "2020-01-02", "2020-01-03")])
    text = gaps.report(root, symbol="NIFTYBEES", code="140084", yahoo="NIFTYBEES.csv", start="2020-01-01", end="2020-01-31")
    assert "days Yahoo has and the NSE cash list does not: none" in text
    write(root / "processed" / "NIFTYBEES.csv", ["date", "high", "close"], [["2020-01-01", "101", "100"], ["2020-01-02", "102", "100"]])
    text = gaps.report(root, symbol="NIFTYBEES", code="140084", yahoo="NIFTYBEES.csv", start="2020-01-01", end="2020-01-31")
    assert "days the NSE cash list has and Yahoo does not: 2020-01-03 (left out of the Yahoo file on purpose: a glitch)" in text


def test_yahoo_is_compared_with_our_split_adjusted_close_and_the_nav_with_the_published_close(tmp_path):
    root = make_root(tmp_path)
    write(root / "processed" / "etf_daily_adjusted.csv", ["date", "symbol", "series", "close", "adj_close", "adj_qty"],
          [["2020-01-01", "NIFTYBEES", "EQ", "1000", "100", "10"], ["2020-01-02", "NIFTYBEES", "EQ", "101", "101", "10"]])
    write(root / "processed" / "amfi_nav_daily.csv", ["date", "code", "nav"], [["2020-01-01", "140084", "1002"], ["2020-01-02", "140084", "101.5"]])
    text = gaps.report(root, symbol="NIFTYBEES", code="140084", yahoo="NIFTYBEES.csv", start="2020-01-01", end="2020-01-31")
    assert "2 days compared, 1 differ by more than 0.5%, largest 1.00% (2020-01-02)" in text          # 100 and 101 against Yahoo's 100 and 100
    assert "AMFI NAV (scheme 140084): 2 days compared, 0 differ by more than 1%" in text              # 1000 against 1002, 101 against 101.5


def test_report_compares_every_listed_etf_with_its_own_nav(tmp_path):
    root = make_root(tmp_path)
    write(root / "processed" / "etf_daily_adjusted.csv", ["date", "symbol", "series", "close", "adj_close", "adj_qty"],
          [["2020-01-01", "NIFTYBEES", "EQ", "100", "100", "10"], ["2020-01-02", "NIFTYBEES", "EQ", "101", "101", "10"],
           ["2020-01-01", "GOLDBEES", "EQ", "50", "50", "10"], ["2020-01-02", "GOLDBEES", "EQ", "52", "52", "10"]])
    write(root / "processed" / "amfi_nav_daily.csv", ["date", "code", "nav"],
          [["2020-01-01", "140084", "100.5"], ["2020-01-02", "140084", "100"], ["2020-01-01", "140088", "50.2"], ["2020-01-02", "140088", "50"]])
    text = gaps.report(root, symbol="NIFTYBEES", code="140084", yahoo="NIFTYBEES.csv", start="2020-01-01", end="2020-01-31",
                       nav_pairs={"NIFTYBEES": "140084", "GOLDBEES": "140088"})
    assert "- NIFTYBEES close against AMFI NAV (scheme 140084): 2 days compared, 0 differ by more than 1%" in text
    assert "- GOLDBEES close against AMFI NAV (scheme 140088): 2 days compared, 1 differ by more than 1%, largest 4.00% (2020-01-02)" in text
