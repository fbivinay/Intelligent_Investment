import json
from datetime import date
from decimal import Decimal as Dc

import pytest

from data.fetch_yahoo import load_bars, load_dividends, parse, save


def payload(splits=None, divs=None):
    r = {"meta": {"gmtoffset": 19800},
         "timestamp": [1515024900, 1517357100, 1517443500],   # 03:45 UTC = 09:15 IST: 2018-01-04, 2018-01-31, 2018-02-01
         "indicators": {"quote": [{"high": [111.1234567, 113.8499984741211, None], "close": [110.9, 113.5439987, None]}]}}
    ev = {}
    if splits:
        ev["splits"] = splits
    if divs:
        ev["dividends"] = divs
    if ev:
        r["events"] = ev
    return json.dumps({"chart": {"result": [r]}}).encode()


def test_parse_uses_local_dates_two_decimals_and_skips_gaps():
    bars, divs = parse(payload())
    assert bars == [(date(2018, 1, 4), Dc("111.12"), Dc("110.90")), (date(2018, 1, 31), Dc("113.85"), Dc("113.54"))]
    assert divs == {}


def test_parse_reads_dividends_and_refuses_splits():
    _, divs = parse(payload(divs={"a": {"date": 1517357100, "amount": 0.35}}))
    assert divs == {date(2018, 1, 31): Dc("0.3500")}
    with pytest.raises(ValueError, match="split"):
        parse(payload(splits={"a": {"date": 1}}))


def test_save_writes_csv_manifest_and_round_trips(tmp_path):
    out = save("NIFTYBEES.NS", payload(), date(2026, 9, 29), root=tmp_path)
    assert out.name == "NIFTYBEES.csv"
    m = json.loads((tmp_path / "manifest.json").read_text())["NIFTYBEES.csv"]
    assert m["rows"] == 2 and m["first"] == "2018-01-04" and len(m["raw_sha256"]) == 64 and m["dividend_events"] == 0
    bars = load_bars(out)
    assert bars[1].high == Dc("113.85") and bars[1].on == date(2018, 1, 31)
    assert load_dividends(tmp_path / "processed" / "NIFTYBEES_dividends.csv") == {}


def test_every_file_save_writes_has_lf_line_ends(tmp_path):
    save("NIFTYBEES.NS", payload(), date(2026, 9, 29), root=tmp_path)
    for path in (tmp_path / "manifest.json", *(tmp_path / "processed").iterdir()):
        assert b"\r" not in path.read_bytes(), path.name


def test_an_empty_or_error_reply_is_refused_not_saved(tmp_path):
    with pytest.raises(ValueError, match="no price rows"):
        save("X.NS", json.dumps({"chart": {"result": [{"meta": {"gmtoffset": 0}, "timestamp": [], "indicators": {"quote": [{"high": [], "close": []}]}}]}}).encode(),
             date(2026, 9, 29), root=tmp_path)
    with pytest.raises(ValueError, match="Yahoo returned no data"):
        parse(json.dumps({"chart": {"result": None, "error": {"code": "Not Found"}}}).encode())
    assert not (tmp_path / "processed").exists()


def test_save_can_leave_out_known_bad_bars_and_says_why(tmp_path):
    corrections = {"exclude": {"2018-01-31": "closing print far from its neighbours"}}
    out = save("NIFTYBEES.NS", payload(), date(2026, 9, 29), root=tmp_path, corrections=corrections)
    m = json.loads((tmp_path / "manifest.json").read_text())["NIFTYBEES.csv"]
    assert m["rows"] == 1 and m["excluded"] == {"2018-01-31": "closing print far from its neighbours"}
    assert [b.on for b in load_bars(out)] == [date(2018, 1, 4)]


def test_an_exclusion_that_matches_no_bar_is_an_error(tmp_path):
    with pytest.raises(ValueError, match="matches no bar"):
        save("NIFTYBEES.NS", payload(), date(2026, 9, 29), root=tmp_path, corrections={"exclude": {"2001-01-01": "x"}})


def test_save_adds_hand_checked_dividends_with_their_source(tmp_path):
    corrections = {"dividends": {"2018-01-10": {"per_unit": "1.0000", "source": "Trendlyne"}}}
    save("NIFTYBEES.NS", payload(divs={"a": {"date": 1517357100, "amount": 0.35}}), date(2026, 9, 29), root=tmp_path,
         corrections=corrections)
    m = json.loads((tmp_path / "manifest.json").read_text())["NIFTYBEES.csv"]
    assert m["dividend_events"] == 2 and m["manual_dividends"] == {"2018-01-10": "Trendlyne"}
    assert load_dividends(tmp_path / "processed" / "NIFTYBEES_dividends.csv") == {
        date(2018, 1, 10): Dc("1.0000"), date(2018, 1, 31): Dc("0.3500")}


def test_a_manual_dividend_on_a_date_the_source_already_has_is_refused(tmp_path):
    corrections = {"dividends": {"2018-01-31": {"per_unit": "1.0000", "source": "Trendlyne"}}}
    with pytest.raises(ValueError, match="already"):
        save("NIFTYBEES.NS", payload(divs={"a": {"date": 1517357100, "amount": 0.35}}), date(2026, 9, 29), root=tmp_path,
             corrections=corrections)


def test_verify_finds_a_changed_data_file_and_passes_a_clean_one(tmp_path):
    from data.fetch_yahoo import verify
    save("NIFTYBEES.NS", payload(), date(2026, 9, 29), root=tmp_path)
    assert verify(tmp_path) == []
    csv_path = tmp_path / "processed" / "NIFTYBEES.csv"
    csv_path.write_text(csv_path.read_text().replace("111.12", "111.13"))
    problems = verify(tmp_path)
    assert len(problems) == 1 and "NIFTYBEES.csv" in problems[0] and "hash" in problems[0]


def test_the_frozen_repository_data_matches_its_manifest():
    from data.fetch_yahoo import verify
    assert verify() == []


def test_verify_also_checks_the_dividends_file(tmp_path):
    from data.fetch_yahoo import verify
    save("NIFTYBEES.NS", payload(divs={"a": {"date": 1517357100, "amount": 0.35}}), date(2026, 9, 29), root=tmp_path)
    m = json.loads((tmp_path / "manifest.json").read_text())["NIFTYBEES.csv"]
    assert m["dividends_csv"] == "NIFTYBEES_dividends.csv" and len(m["dividends_csv_sha256"]) == 64
    assert verify(tmp_path) == []
    div = tmp_path / "processed" / "NIFTYBEES_dividends.csv"
    div.write_text(div.read_text().replace("0.3500", "9.0000"))
    problems = verify(tmp_path)
    assert len(problems) == 1 and "NIFTYBEES_dividends.csv" in problems[0] and "hash" in problems[0]


def test_verify_finds_a_dividends_file_that_is_missing_or_a_manifest_without_its_hash(tmp_path):
    from data.fetch_yahoo import verify
    save("NIFTYBEES.NS", payload(), date(2026, 9, 29), root=tmp_path)
    (tmp_path / "processed" / "NIFTYBEES_dividends.csv").unlink()
    assert any("NIFTYBEES_dividends.csv" in p and "missing" in p for p in verify(tmp_path))
    save("NIFTYBEES.NS", payload(), date(2026, 9, 29), root=tmp_path)
    m = json.loads((tmp_path / "manifest.json").read_text())
    del m["NIFTYBEES.csv"]["dividends_csv_sha256"]
    (tmp_path / "manifest.json").write_text(json.dumps(m))
    assert any("no hash" in p for p in verify(tmp_path))


def test_the_manifest_records_what_the_prices_are_adjusted_for(tmp_path):
    save("NIFTYBEES.NS", payload(), date(2026, 9, 29), root=tmp_path,
         corrections={"adjusted": {"2019-12-19": "1-for-10 unit split, earlier prices adjusted without a split event"}})
    m = json.loads((tmp_path / "manifest.json").read_text())["NIFTYBEES.csv"]
    assert m["adjusted"] == {"2019-12-19": "1-for-10 unit split, earlier prices adjusted without a split event"}
    save("NIFTYBEES.NS", payload(), date(2026, 9, 29), root=tmp_path)
    assert json.loads((tmp_path / "manifest.json").read_text())["NIFTYBEES.csv"]["adjusted"] == {}
