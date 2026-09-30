import csv
import json
from datetime import date

import pytest

from data import amfi_nav as an

HISTORY = {"meta": {"fund_house": "Nippon India Mutual Fund", "scheme_code": 140084, "scheme_name": "Nippon India ETF Nifty 50 BeES - Direct Plan",
                    "isin_growth": "INF204KB14I2"},
           "data": [{"date": "15-01-2020", "nav": "130.78930"}, {"date": "18-12-2019", "nav": "1292.54000"}]}
REPORT = "\n".join([
    "Scheme Code;NAV Name;Plan;Option;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Net Asset Value;Date", "",
    "Open Ended Schemes ( Growth )", "", "", "Sahara Mutual Fund",
    "120373;SAHARA BANKING & FINANCIAL SERVICES FUND- GROWTH - Direct;;;INF515L01AJ6;;83.5348;15-Jan-2020",
    "140084;Nippon India ETF Nifty 50 BeES;Direct Plan;;INF204KB14I2;;130.7893;15-Jan-2020",
    "101525;HDFC Nifty 50 Index Fund - Growth Plan;Regular Plan;Growth Option;INF179K01KZ8;;N.A.;15-Jan-2020", ""])


def raw_of(history=HISTORY) -> bytes:
    return json.dumps(history).encode()


def opener_for(bodies: dict):
    """An opener that answers each address with the body given for it, and records what was asked."""
    asked = []

    def opener(url):
        asked.append(url)
        for key, body in bodies.items():
            if key in url:
                return 200, body
        return 404, b""
    opener.asked = asked
    return opener


def test_history_rows_come_out_with_iso_dates_and_the_nav_as_published_text():
    meta, rows = an.parse_history(raw_of())
    assert meta == {"code": "140084", "name": "Nippon India ETF Nifty 50 BeES - Direct Plan", "isin": "INF204KB14I2"}
    assert rows == [("2019-12-18", "1292.54000"), ("2020-01-15", "130.78930")]          # oldest first; the split is not smoothed


def test_a_history_in_another_shape_is_an_error_not_an_empty_result():
    with pytest.raises(ValueError, match="shape"):
        an.parse_history(b'{"status": "ERROR"}')
    with pytest.raises(ValueError, match="shape"):
        an.parse_history(b'{"meta": {"scheme_code": 1}, "data": [{"nav": "1"}]}')


def test_report_lines_are_read_by_code_and_date_and_not_available_is_left_out():
    got = an.parse_report(REPORT)
    assert got == {("120373", "2020-01-15"): "83.5348", ("140084", "2020-01-15"): "130.7893"}


def test_a_report_with_a_different_header_is_refused():
    with pytest.raises(ValueError, match="header"):
        an.parse_report("Scheme Code;Name;NAV\n1;a;2\n")


def test_sync_stores_the_raw_history_and_lists_it_with_its_hash(tmp_path):
    opener = opener_for({"/mf/140084": raw_of()})
    an.sync({"140084": "Nifty BeES, Nippon direct"}, tmp_path, opener, retrieved=date(2026, 9, 30))
    (row,) = list(csv.DictReader((tmp_path / "amfi_schemes.csv").open(newline="")))
    assert (row["code"], row["label"], row["rows"], row["first"], row["last"]) == ("140084", "Nifty BeES, Nippon direct", "2", "2019-12-18", "2020-01-15")
    assert (tmp_path / "raw" / "amfi" / "140084.json").read_bytes() == raw_of()
    assert len(row["sha256"]) == 64 and row["retrieved"] == "2026-09-30" and row["url"] == "https://api.mfapi.in/mf/140084"


def test_sync_stops_when_a_scheme_cannot_be_fetched_and_lists_nothing_for_it(tmp_path):
    with pytest.raises(RuntimeError, match="140084"):
        an.sync({"140084": "x"}, tmp_path, opener_for({}), sleep=lambda s: None, retrieved=date(2026, 9, 30))
    assert not (tmp_path / "amfi_schemes.csv").exists() or "140084" not in (tmp_path / "amfi_schemes.csv").read_text()


def test_sync_twice_replaces_the_list_row_and_does_not_duplicate_it(tmp_path):
    for _ in range(2):
        an.sync({"140084": "x"}, tmp_path, opener_for({"/mf/140084": raw_of()}), retrieved=date(2026, 9, 30))
    assert len(list(csv.DictReader((tmp_path / "amfi_schemes.csv").open(newline="")))) == 1


def test_build_writes_one_sorted_csv_of_every_scheme_and_repeats_byte_for_byte(tmp_path):
    other = {"meta": {"scheme_code": 101525, "scheme_name": "HDFC Nifty 50 Index Fund - Regular", "isin_growth": "INF179K01KZ8"},
             "data": [{"date": "15-01-2020", "nav": "112.72300"}]}
    an.sync({"140084": "a", "101525": "b"}, tmp_path, opener_for({"/mf/140084": raw_of(), "/mf/101525": raw_of(other)}), retrieved=date(2026, 9, 30))
    assert an.build(tmp_path) == 3
    first = (tmp_path / "processed" / "amfi_nav_daily.csv").read_bytes()
    rows = list(csv.DictReader((tmp_path / "processed" / "amfi_nav_daily.csv").open(newline="")))
    assert [(r["date"], r["code"], r["nav"]) for r in rows] == [("2019-12-18", "140084", "1292.54000"), ("2020-01-15", "101525", "112.72300"),
                                                                ("2020-01-15", "140084", "130.78930")]
    an.build(tmp_path)
    assert (tmp_path / "processed" / "amfi_nav_daily.csv").read_bytes() == first and b"\r" not in first


def test_build_refuses_a_raw_history_that_no_longer_matches_its_hash(tmp_path):
    an.sync({"140084": "a"}, tmp_path, opener_for({"/mf/140084": raw_of()}), retrieved=date(2026, 9, 30))
    (tmp_path / "raw" / "amfi" / "140084.json").write_bytes(b"{}")
    with pytest.raises(ValueError, match="hash"):
        an.build(tmp_path)


def test_check_compares_our_navs_with_the_amfi_report_on_the_given_days(tmp_path):
    an.sync({"140084": "a"}, tmp_path, opener_for({"/mf/140084": raw_of()}), retrieved=date(2026, 9, 30))
    opener = opener_for({"frmdt=15-Jan-2020": REPORT.encode()})
    result = an.check(tmp_path, [date(2020, 1, 15)], opener)
    assert result == {"compared": 1, "differ": [], "missing_in_report": [], "missing_in_ours": []} and "frmdt=15-Jan-2020&todt=15-Jan-2020" in opener.asked[0]


def test_check_names_a_nav_that_differs_and_a_scheme_the_report_lacks(tmp_path):
    changed = {"meta": HISTORY["meta"], "data": [{"date": "15-01-2020", "nav": "131.00000"}, {"date": "16-01-2020", "nav": "5.0"}]}
    an.sync({"140084": "a"}, tmp_path, opener_for({"/mf/140084": raw_of(changed)}), retrieved=date(2026, 9, 30))
    opener = opener_for({"frmdt=15-Jan-2020": REPORT.encode(), "frmdt=16-Jan-2020": b"Scheme Code;NAV Name;Plan;Option;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Net Asset Value;Date\n"})
    result = an.check(tmp_path, [date(2020, 1, 15), date(2020, 1, 16)], opener)
    assert result["differ"] == [("140084", "2020-01-15", "131.00000", "130.7893")] and result["missing_in_report"] == [("140084", "2020-01-16")]
    assert result["compared"] == 1


def test_check_names_a_day_the_report_has_for_our_scheme_and_we_do_not(tmp_path):
    thin = {"meta": HISTORY["meta"], "data": [{"date": "16-01-2020", "nav": "5.0"}]}
    an.sync({"140084": "a"}, tmp_path, opener_for({"/mf/140084": raw_of(thin)}), retrieved=date(2026, 9, 30))
    result = an.check(tmp_path, [date(2020, 1, 15)], opener_for({"frmdt=15-Jan-2020": REPORT.encode()}))
    assert result == {"compared": 0, "differ": [], "missing_in_report": [], "missing_in_ours": [("140084", "2020-01-15")]}


def test_a_nav_that_is_not_a_positive_number_is_an_error_naming_the_day():
    bad = {"meta": HISTORY["meta"], "data": [{"date": "15-01-2020", "nav": "0.00000"}]}
    with pytest.raises(ValueError, match="2020-01-15"):
        an.parse_history(raw_of(bad))
