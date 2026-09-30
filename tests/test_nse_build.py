import csv
import io
import zipfile
from datetime import date

from data import nse_archive as na
from data import nse_build as nb

CASH_HEAD = "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,TIMESTAMP,TOTALTRADES,ISIN,"
FO_HEAD = "INSTRUMENT,SYMBOL,EXPIRY_DT,STRIKE_PR,OPTION_TYP,OPEN,HIGH,LOW,CLOSE,SETTLE_PR,CONTRACTS,VAL_INLAKH,OPEN_INT,CHG_IN_OI,TIMESTAMP,"
IDX_HEAD = "Index Name,Index Date,Open Index Value,High Index Value,Low Index Value,Closing Index Value,Points Change,Change(%),Volume,Turnover (Rs. Cr.),P/E,P/B,Div Yield"


def zipped(lines):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("f.csv", "\n".join(lines) + "\n")
    return buf.getvalue()


def put(root, kind, d, raw):
    """Write a raw file and list it, the way the downloader does."""
    p = na.raw_path(root, kind, d)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(raw)
    import hashlib
    na.append_days([dict(kind=kind, date=d.isoformat(), status="ok", bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), url="u", retrieved="2026-09-30")], root)


def make_root(tmp_path):
    d1, d2 = date(2016, 6, 1), date(2016, 6, 2)
    put(tmp_path, "cash", d1, zipped([CASH_HEAD, "NIFTYBEES,EQ,827,831.75,826,828.85,829.05,826.68,32150,26661845.83,01-JUN-2016,1158,INF732E01011,",
                                     "GOLDBEES,EQ,2500,2510,2490,2505,2505,2495,1000,2500000,01-JUN-2016,50,INF204KB16I7,"]))
    put(tmp_path, "cash", d2, zipped([CASH_HEAD, "NIFTYBEES,EQ,829,835,828,834.5,834,828.85,40000,33000000,02-JUN-2016,1200,INF732E01011,"]))
    put(tmp_path, "fo", d1, zipped([FO_HEAD, "FUTIDX,NIFTY,30-Jun-2016,0,XX,8200,8224.9,8178.3,8194.55,8194.55,125472,771709.04,21499350,-130800,01-JUN-2016,"]))
    put(tmp_path, "index", d1, ("\n".join([IDX_HEAD, "Nifty 50,01-06-2016,8200,8224.9,8178.3,8194.55,1,0.1,1,1,21.5,3.1,1.3"]) + "\n").encode())
    # an absent day and a holiday: nothing to read
    na.append_days([dict(kind="cash", date="2016-06-03", status="absent", bytes=0, sha256="", url="u", retrieved="2026-09-30")], tmp_path)
    return tmp_path


def read(path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def test_build_writes_one_sorted_csv_per_kind_from_the_raw_files_that_are_listed(tmp_path):
    root = make_root(tmp_path)
    counts = nb.build(root, etfs={"NIFTYBEES", "GOLDBEES"}, futures={"NIFTY"}, indices={"Nifty 50"})
    assert counts == {"cash": 3, "fo": 1, "index": 1, "index_month_first": 0, "cash_web": 0, "fo_web": 0, "index_web": 0}
    etf = read(root / "processed" / "nse_etf_daily.csv")
    assert [(r["date"], r["symbol"], r["close"]) for r in etf] == [("2016-06-01", "GOLDBEES", "2505"), ("2016-06-01", "NIFTYBEES", "828.85"),
                                                                    ("2016-06-02", "NIFTYBEES", "834.5")]
    assert read(root / "processed" / "nse_index_futures_daily.csv")[0]["expiry"] == "2016-06-30"
    assert read(root / "processed" / "nse_index_daily.csv")[0]["pe"] == "21.5"


def test_build_is_repeatable_byte_for_byte_and_writes_lf_line_ends(tmp_path):
    root = make_root(tmp_path)
    nb.build(root, {"NIFTYBEES"}, {"NIFTY"}, {"Nifty 50"})
    first = {p.name: p.read_bytes() for p in (root / "processed").iterdir()}
    nb.build(root, {"NIFTYBEES"}, {"NIFTY"}, {"Nifty 50"})
    assert {p.name: p.read_bytes() for p in (root / "processed").iterdir()} == first
    assert all(b"\r" not in v for v in first.values())


def test_build_refuses_a_raw_file_whose_hash_is_not_the_listed_one(tmp_path):
    import pytest
    root = make_root(tmp_path)
    na.raw_path(root, "cash", date(2016, 6, 1)).write_bytes(b"changed")
    with pytest.raises(ValueError, match="hash"):
        nb.build(root, {"NIFTYBEES"}, {"NIFTY"}, {"Nifty 50"})


def test_build_names_a_listed_day_whose_raw_file_is_missing_instead_of_skipping_it(tmp_path):
    import pytest
    root = make_root(tmp_path)
    na.raw_path(root, "fo", date(2016, 6, 1)).unlink()
    with pytest.raises(ValueError, match="missing"):
        nb.build(root, {"NIFTYBEES"}, {"NIFTY"}, {"Nifty 50"})


def test_build_names_every_file_whose_rows_or_layout_disagree_in_one_error(tmp_path):
    import pytest
    d1, d2, d3 = date(2016, 6, 1), date(2016, 6, 2), date(2016, 6, 3)
    put(tmp_path, "cash", d1, zipped([CASH_HEAD, "NIFTYBEES,EQ,827,831.75,826,828.85,829.05,826.68,32150,26661845.83,05-JUN-2016,1158,INF732E01011,"]))   # dated wrongly
    put(tmp_path, "cash", d2, zipped(["A,B,C", "1,2,3"]))                                                                                              # unknown layout
    put(tmp_path, "cash", d3, zipped([CASH_HEAD, "NIFTYBEES,EQ,827,831.75,826,828.85,829.05,826.68,32150,26661845.83,03-JUN-2016,1158,INF732E01011,"]))  # fine
    with pytest.raises(ValueError) as e:
        nb.build(tmp_path, {"NIFTYBEES"}, {"NIFTY"}, {"Nifty 50"})
    msg = str(e.value)
    assert "2 files" in msg and "cash 2016-06-01: a row is dated 2016-06-05" in msg and "cash 2016-06-02" in msg and "layout" in msg
    assert not (tmp_path / "processed" / "nse_etf_daily.csv").exists()                     # nothing is written from a build that found problems


def test_build_reads_an_index_file_written_month_first_as_its_day_and_counts_it(tmp_path):
    put(tmp_path, "index", date(2023, 4, 6), ("\n".join([IDX_HEAD, "Nifty 50,04-06-2023,8200,8224.9,8178.3,8194.55,1,0.1,1,1,21.5,3.1,1.3"]) + "\n").encode())
    put(tmp_path, "index", date(2023, 4, 12), ("\n".join([IDX_HEAD, "Nifty 50,12-04-2023,8200,8224.9,8178.3,8194.55,1,0.1,1,1,21.5,3.1,1.3"]) + "\n").encode())
    counts = nb.build(tmp_path, {"NIFTYBEES"}, {"NIFTY"}, {"Nifty 50"})
    assert counts["index"] == 2 and counts["index_month_first"] == 1
    assert [r["date"] for r in read(tmp_path / "processed" / "nse_index_daily.csv")] == ["2023-04-06", "2023-04-12"]


def test_build_refuses_two_rows_for_one_key(tmp_path):
    import pytest
    put(tmp_path, "index", date(2016, 7, 7), ("\n".join([IDX_HEAD, "Nifty Free Float Midcap 100,07-07-2016,1,2,0.5,14122.85,0,0,1,1,32.83,1,1",
                                                        "NIFTY Midcap 100,07-07-2016,1,2,0.5,14095.35,0,0,1,1,32.77,1,1"]) + "\n").encode())
    with pytest.raises(ValueError, match="twice"):
        nb.build(tmp_path, {"NIFTYBEES"}, {"NIFTY"}, {"Nifty Midcap 100"})
    assert not (tmp_path / "processed" / "nse_index_daily.csv").exists()


def web_file(tmp_path, *items, name="nse_web_test.json"):
    import json
    from data import nse_web as nw
    src = tmp_path / name
    src.write_text(json.dumps({"meta": {"collected": "2026-10-01T10:00:00.000Z", "status": "finished", "failed": [], "missing": []}, "items": list(items)}))
    return nw.register(src, tmp_path, tmp_path / "no_script.js", registered=date(2026, 10, 1))


WEB_ETF = {"CH_SYMBOL": "NIFTYBEES", "CH_SERIES": "EQ", "mTIMESTAMP": "30-Jun-2010", "CH_PREVIOUS_CLS_PRICE": 530.54, "CH_OPENING_PRICE": 527.5, "CH_TRADE_HIGH_PRICE": 534.99,
           "CH_TRADE_LOW_PRICE": 527, "CH_LAST_TRADED_PRICE": 533, "CH_CLOSING_PRICE": 533.87, "CH_TOT_TRADED_QTY": 53156, "CH_TOT_TRADED_VAL": 28201570.87, "CH_TOTAL_TRADES": None}
WEB_INDEX = {"EOD_INDEX_NAME": "S&P CNX NIFTY", "EOD_OPEN_INDEX_VAL": 5254.25, "EOD_HIGH_INDEX_VAL": 5320.35, "EOD_CLOSE_INDEX_VAL": 5312.5, "EOD_LOW_INDEX_VAL": 5210,
             "HIT_TURN_OVER": 7083.92, "HIT_TRADED_QTY": 183722824, "EOD_TIMESTAMP": "30-JUN-2010"}
WEB_FO = {"FH_INSTRUMENT": "FUTIDX", "FH_SYMBOL": "NIFTY", "FH_EXPIRY_DT": "29-Jul-2010", "FH_OPENING_PRICE": 5214.95, "FH_TRADE_HIGH_PRICE": 5263.9, "FH_TRADE_LOW_PRICE": 5204,
          "FH_CLOSING_PRICE": 5260.65, "FH_PREV_CLS": 5226.7, "FH_SETTLE_PRICE": 5260.4, "FH_TOT_TRADED_QTY": 21269100, "FH_TOT_TRADED_VAL": 1111674.68, "FH_OPEN_INT": 11940200,
          "FH_CHANGE_IN_OI": -4062050, "FH_MARKET_LOT": 50, "FH_TIMESTAMP": "30-Jun-2010", "FH_UNDERLYING_VALUE": 5260.4}


def web_items():
    return [{"kind": "etf", "symbol": "NIFTYBEES", "from": "2010-04-01", "to": "2010-06-30", "data": [WEB_ETF]},
            {"kind": "index", "index": "NIFTY 50", "from": "2010-04-01", "to": "2010-06-30", "data": [WEB_INDEX]},
            {"kind": "fo", "symbol": "NIFTY", "expiry": "2010-07-29", "from": "2010-04-01", "to": "2010-06-30", "data": [WEB_FO]}]


def test_build_adds_the_website_file_for_the_years_before_the_archive_and_marks_where_each_row_came_from(tmp_path):
    root = make_root(tmp_path)
    web_file(root, *web_items())
    counts = nb.build(root, etfs={"NIFTYBEES", "GOLDBEES"}, futures={"NIFTY"}, indices={"Nifty 50"})
    assert counts == {"cash": 4, "fo": 2, "index": 2, "index_month_first": 0, "cash_web": 1, "fo_web": 1, "index_web": 1}
    etf = read(root / "processed" / "nse_etf_daily.csv")
    assert [(r["date"], r["symbol"], r["source"]) for r in etf] == [("2010-06-30", "NIFTYBEES", "web"), ("2016-06-01", "GOLDBEES", "archive"),
                                                                     ("2016-06-01", "NIFTYBEES", "archive"), ("2016-06-02", "NIFTYBEES", "archive")]
    assert etf[0]["close"] == "533.87" and etf[0]["isin"] == "" and etf[0]["trades"] == ""
    assert [(r["date"], r["source"]) for r in read(root / "processed" / "nse_index_daily.csv")] == [("2010-06-30", "web"), ("2016-06-01", "archive")]
    fo = read(root / "processed" / "nse_index_futures_daily.csv")
    assert [(r["date"], r["expiry"], r["source"], r["lot"]) for r in fo] == [("2010-06-30", "2010-07-29", "web", "50"), ("2016-06-01", "2016-06-30", "archive", "")]


def test_where_the_archive_and_the_website_both_have_a_row_the_archive_row_is_kept_and_the_overlap_is_not_counted_as_added(tmp_path):
    root = make_root(tmp_path)
    same_day = dict(WEB_ETF, mTIMESTAMP="01-Jun-2016", CH_SYMBOL="NIFTYBEES", CH_CLOSING_PRICE=999)
    web_file(root, {"kind": "etf", "symbol": "NIFTYBEES", "from": "2016-06-01", "to": "2016-06-01", "data": [same_day]})
    counts = nb.build(root, etfs={"NIFTYBEES", "GOLDBEES"}, futures={"NIFTY"}, indices={"Nifty 50"})
    assert counts["cash"] == 3 and counts["cash_web"] == 0
    rows = [r for r in read(root / "processed" / "nse_etf_daily.csv") if r["date"] == "2016-06-01" and r["symbol"] == "NIFTYBEES"]
    assert [(r["close"], r["source"]) for r in rows] == [("828.85", "archive")]


def test_build_refuses_a_website_file_whose_hash_no_longer_matches(tmp_path):
    import pytest
    root = make_root(tmp_path)
    web_file(root, *web_items())
    (root / "raw" / "nse_web" / "nse_web_test.json").write_bytes(b"{}")
    with pytest.raises(ValueError, match="hash"):
        nb.build(root, {"NIFTYBEES"}, {"NIFTY"}, {"Nifty 50"})


def test_website_rows_for_an_instrument_outside_the_build_universe_are_left_out(tmp_path):
    root = make_root(tmp_path)
    web_file(root, *web_items())
    counts = nb.build(root, etfs={"GOLDBEES"}, futures={"BANKNIFTY"}, indices={"Nifty Bank"})
    assert (counts["cash_web"], counts["fo_web"], counts["index_web"]) == (0, 0, 0)
