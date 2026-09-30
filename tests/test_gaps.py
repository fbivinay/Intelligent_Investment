import csv
import json
from datetime import date
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
    assert s == {"days": 3, "over": 2, "median_abs": Decimal(1), "max_abs": Decimal(3), "max_day": "2020-01-03", "worst": [("2020-01-03", Decimal(-3)), ("2020-01-02", Decimal(1))]}
    assert gaps.summary([], Decimal("0.5")) == {"days": 0, "over": 0, "median_abs": Decimal(0), "max_abs": Decimal(0), "max_day": None, "worst": []}


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
    assert "2 days compared, 1 differ by more than 0.5%, median 0.50%, largest 1.00% (2020-01-02)" in text       # 101 against 100
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
    (root / "corporate_actions.csv").write_text("symbol,ex_date,kind,factor,nav_ex_date,evidence\nNIFTYBEES,2020-01-02,split,10,2020-01-02,\"x\"\n", newline="")
    text = gaps.report(root, symbol="NIFTYBEES", code="140084", yahoo="NIFTYBEES.csv", start="2020-01-01", end="2020-01-31")
    assert "2 days compared, 1 differ by more than 0.5%, median 0.50%, largest 1.00% (2020-01-02)" in text          # 100 and 101 against Yahoo's 100 and 100
    assert "AMFI NAV (scheme 140084): 2 days compared, 0 differ by more than 1%" in text              # 1002 on the old scale is 100.2 against 100, 101.5 against 101


def test_report_compares_every_listed_etf_with_its_own_nav(tmp_path):
    root = make_root(tmp_path)
    write(root / "processed" / "etf_daily_adjusted.csv", ["date", "symbol", "series", "close", "adj_close", "adj_qty"],
          [["2020-01-01", "NIFTYBEES", "EQ", "100", "100", "10"], ["2020-01-02", "NIFTYBEES", "EQ", "101", "101", "10"],
           ["2020-01-01", "GOLDBEES", "EQ", "50", "50", "10"], ["2020-01-02", "GOLDBEES", "EQ", "52", "52", "10"]])
    write(root / "processed" / "amfi_nav_daily.csv", ["date", "code", "nav"],
          [["2020-01-01", "140084", "100.5"], ["2020-01-02", "140084", "100"], ["2020-01-01", "140088", "50.2"], ["2020-01-02", "140088", "50"]])
    text = gaps.report(root, symbol="NIFTYBEES", code="140084", yahoo="NIFTYBEES.csv", start="2020-01-01", end="2020-01-31",
                       nav_pairs={"NIFTYBEES": "140084", "GOLDBEES": "140088"})
    assert "- NIFTYBEES split-adjusted close against AMFI NAV (scheme 140084): 2 days compared, 0 differ by more than 1%" in text
    assert "- GOLDBEES split-adjusted close against AMFI NAV (scheme 140088): 2 days compared, 1 differ by more than 1%, median 2.20%, largest 4.00% (2020-01-02)" in text


def test_a_nav_that_switches_scale_days_after_the_price_is_compared_on_one_scale(tmp_path):
    root = make_root(tmp_path)
    write(root / "processed" / "etf_daily_adjusted.csv", ["date", "symbol", "series", "close", "adj_close", "adj_qty"],
          [["2020-01-01", "NIFTYBEES", "EQ", "1000", "100", "10"], ["2020-01-02", "NIFTYBEES", "EQ", "101", "101", "10"], ["2020-01-03", "NIFTYBEES", "EQ", "102", "102", "10"]])
    write(root / "processed" / "amfi_nav_daily.csv", ["date", "code", "nav"], [["2020-01-01", "140084", "1002"], ["2020-01-02", "140084", "1010"], ["2020-01-03", "140084", "102.1"]])
    (root / "corporate_actions.csv").write_text("symbol,ex_date,kind,factor,nav_ex_date,evidence\nNIFTYBEES,2020-01-02,split,10,2020-01-03,\"NAV switches a day later\"\n", newline="")
    text = gaps.report(root, symbol="NIFTYBEES", code="140084", yahoo="NIFTYBEES.csv", start="2020-01-01", end="2020-01-31")
    assert "AMFI NAV (scheme 140084): 3 days compared, 0 differ by more than 1%" in text


def test_without_a_nav_switch_date_the_nav_is_taken_to_switch_with_the_price(tmp_path):
    root = make_root(tmp_path)
    write(root / "processed" / "etf_daily_adjusted.csv", ["date", "symbol", "series", "close", "adj_close", "adj_qty"],
          [["2020-01-01", "NIFTYBEES", "EQ", "1000", "100", "10"], ["2020-01-02", "NIFTYBEES", "EQ", "101", "101", "10"]])
    write(root / "processed" / "amfi_nav_daily.csv", ["date", "code", "nav"], [["2020-01-01", "140084", "1002"], ["2020-01-02", "140084", "101.2"]])
    (root / "corporate_actions.csv").write_text("symbol,ex_date,kind,factor,evidence\nNIFTYBEES,2020-01-02,split,10,\"x\"\n", newline="")
    text = gaps.report(root, symbol="NIFTYBEES", code="140084", yahoo="NIFTYBEES.csv", start="2020-01-01", end="2020-01-31")
    assert "AMFI NAV (scheme 140084): 2 days compared, 0 differ by more than 1%" in text


def test_two_splits_multiply_when_the_nav_is_put_on_the_latest_unit_size(tmp_path):
    root = make_root(tmp_path)
    write(root / "processed" / "etf_daily_adjusted.csv", ["date", "symbol", "series", "close", "adj_close", "adj_qty"],
          [["2020-01-01", "NIFTYBEES", "EQ", "2000", "100", "10"], ["2020-01-03", "NIFTYBEES", "EQ", "201", "100.5", "10"], ["2020-01-05", "NIFTYBEES", "EQ", "101", "101", "10"]])
    write(root / "processed" / "amfi_nav_daily.csv", ["date", "code", "nav"], [["2020-01-01", "140084", "2010"], ["2020-01-03", "140084", "201"], ["2020-01-05", "140084", "100.9"]])
    (root / "corporate_actions.csv").write_text("symbol,ex_date,kind,factor,nav_ex_date,evidence\nNIFTYBEES,2020-01-03,split,10,,\"a\"\nNIFTYBEES,2020-01-05,split,2,,\"b\"\n", newline="")
    text = gaps.report(root, symbol="NIFTYBEES", code="140084", yahoo="NIFTYBEES.csv", start="2020-01-01", end="2020-01-31")
    assert "AMFI NAV (scheme 140084): 3 days compared, 0 differ by more than 1%" in text


def test_nav_against_its_index_shows_a_payout_as_a_one_day_step_down_and_kept_dividends_as_drift():
    index = {"2020-01-01": Decimal(1000), "2020-01-02": Decimal(1010), "2020-01-03": Decimal(1020), "2020-01-06": Decimal(1030)}
    nav = {"2020-01-01": Decimal(100), "2020-01-02": Decimal(101), "2020-01-03": Decimal(100), "2020-01-06": Decimal(103)}      # 2 paid out on the 3rd
    got = gaps.nav_vs_index(nav, index, Decimal("0.25"))
    assert got["days"] == 4 and (got["first"], got["last"]) == ("2020-01-01", "2020-01-06")
    (step,) = got["steps"]
    assert step[:2] == ("2020-01-02", "2020-01-03") and f"{step[2]:.2f}" == "-1.96"
    steady = gaps.nav_vs_index({d: v / 10 for d, v in index.items()}, index, Decimal("0.25"))
    assert steady["steps"] == [] and abs(steady["drift"]) < Decimal("0.0001")


def test_a_step_across_a_long_gap_is_not_called_a_one_day_payout():
    index = {"2020-01-01": Decimal(1000), "2020-02-01": Decimal(1000)}
    nav = {"2020-01-01": Decimal(100), "2020-02-01": Decimal(90)}
    assert gaps.nav_vs_index(nav, index, Decimal("0.25"))["steps"] == []


def test_report_asks_whether_each_equity_etf_pays_dividends_out(tmp_path):
    root = make_root(tmp_path)
    write(root / "processed" / "nse_index_daily.csv", ["date", "name", "close"],
          [["2020-01-01", "Nifty 50", "1000"], ["2020-01-02", "Nifty 50", "1010"], ["2020-01-03", "Nifty 50", "1020"]])
    write(root / "processed" / "amfi_nav_daily.csv", ["date", "code", "nav"], [["2020-01-01", "140084", "100"], ["2020-01-02", "140084", "101"], ["2020-01-03", "140084", "100"]])
    text = gaps.report(root, symbol="NIFTYBEES", code="140084", yahoo="NIFTYBEES.csv", start="2020-01-01", end="2020-01-31", index_pairs={"NIFTYBEES": "Nifty 50"})
    assert "## Do the equity ETFs pay dividends out?" in text
    assert "- NIFTYBEES NAV against Nifty 50 (scheme 140084): 3 days" in text and "1 one-day step down over 0.25%" in text and "2020-01-03 -1.96%" in text


def test_a_small_wobble_of_the_ratio_below_the_threshold_is_not_a_payout():
    index = {"2020-01-01": Decimal(1000), "2020-01-02": Decimal(1000)}
    nav = {"2020-01-01": Decimal(100), "2020-01-02": Decimal("99.9")}                     # -0.1%: tracking noise, not a dividend
    assert gaps.nav_vs_index(nav, index, Decimal("0.25"))["steps"] == []


def test_the_dividend_check_puts_a_split_nav_on_one_unit_size_first(tmp_path):
    root = make_root(tmp_path)
    write(root / "processed" / "nse_index_daily.csv", ["date", "name", "close"],
          [["2020-01-01", "Nifty 50", "1000"], ["2020-01-02", "Nifty 50", "1000"], ["2020-01-03", "Nifty 50", "1000"]])
    write(root / "processed" / "amfi_nav_daily.csv", ["date", "code", "nav"], [["2020-01-01", "140084", "1000"], ["2020-01-02", "140084", "1000"], ["2020-01-03", "140084", "100"]])
    (root / "corporate_actions.csv").write_text("symbol,ex_date,kind,factor,nav_ex_date,evidence\nNIFTYBEES,2020-01-02,split,10,2020-01-03,\"x\"\n", newline="")
    text = gaps.report(root, symbol="NIFTYBEES", code="140084", yahoo="NIFTYBEES.csv", start="2020-01-01", end="2020-01-31", index_pairs={"NIFTYBEES": "Nifty 50"})
    assert "3 days, ratio drift" in text and "0 one-day step down" in text



def test_compare_sources_counts_the_rows_both_have_and_names_the_worst_difference():
    web = [{"date": "2016-01-04", "symbol": "X", "close": "100", "qty": "10"}, {"date": "2016-01-05", "symbol": "X", "close": "103", "qty": "10"},
           {"date": "2010-01-05", "symbol": "X", "close": "1", "qty": "1"}]
    arc = [{"date": "2016-01-04", "symbol": "X", "close": "100.00", "qty": "10"}, {"date": "2016-01-05", "symbol": "X", "close": "100", "qty": "10"}]
    got = gaps.compare_sources(web, arc, ("date", "symbol"), ["close", "qty"])
    assert got["both"] == 2
    assert got["fields"]["close"] == {"compared": 2, "differ": 1, "worst_pct": Decimal(3), "worst_key": ("2016-01-05", "X")}
    assert got["fields"]["qty"] == {"compared": 2, "differ": 0, "worst_pct": Decimal(0), "worst_key": None}


def test_compare_sources_leaves_out_values_either_source_does_not_have():
    web = [{"date": "d", "symbol": "X", "prev_close": "5"}]
    arc = [{"date": "d", "symbol": "X", "prev_close": ""}]
    assert gaps.compare_sources(web, arc, ("date", "symbol"), ["prev_close"])["fields"]["prev_close"]["compared"] == 0


def test_report_sets_the_website_file_against_the_archive_on_the_days_both_have(tmp_path):
    import json
    from data import nse_web as nw
    root = make_root(tmp_path)
    cols = ["date", "symbol", "series", "open", "high", "low", "close", "last", "prev_close", "qty", "value", "trades", "isin", "source"]
    write(root / "processed" / "nse_etf_daily.csv", cols, [["2016-06-01", "NIFTYBEES", "EQ", "827", "831.75", "826", "828.85", "829.05", "826.68", "32150", "26661845.83", "1158", "I", "archive"]])
    web_row = {"CH_SYMBOL": "NIFTYBEES", "CH_SERIES": "EQ", "mTIMESTAMP": "01-Jun-2016", "CH_PREVIOUS_CLS_PRICE": 826.68, "CH_OPENING_PRICE": 827, "CH_TRADE_HIGH_PRICE": 831.75,
               "CH_TRADE_LOW_PRICE": 826, "CH_LAST_TRADED_PRICE": 829.05, "CH_CLOSING_PRICE": 999, "CH_TOT_TRADED_QTY": 32150, "CH_TOT_TRADED_VAL": 26661845.83, "CH_TOTAL_TRADES": 1158}
    src = tmp_path / "web.json"
    src.write_text(json.dumps({"meta": {"collected": "x", "status": "finished", "failed": [], "missing": []},
                               "items": [{"kind": "etf", "symbol": "NIFTYBEES", "from": "2016-06-01", "to": "2016-06-01", "data": [web_row]}]}))
    nw.register(src, root, tmp_path / "none.js", registered=date(2026, 10, 1))
    text = gaps.report(root, symbol="NIFTYBEES", code="140084", yahoo="NIFTYBEES.csv", start="2016-06-01", end="2016-06-30")
    assert "## Website file against the archive files" in text
    assert "- cash: 1 rows in both; differ: close 1 of 1 (largest 20.53%, 2016-06-01 NIFTYBEES EQ)" in text
