import csv
import hashlib
import json
from datetime import date
from decimal import Decimal

import pytest

from data import nse_web as nw

ETF_ROW = {"CH_SYMBOL": "NIFTYBEES", "CH_SERIES": "EQ", "mTIMESTAMP": "30-Jun-2010", "CH_PREVIOUS_CLS_PRICE": 530.54, "CH_OPENING_PRICE": 527.5,
           "CH_TRADE_HIGH_PRICE": 534.99, "CH_TRADE_LOW_PRICE": 527, "CH_LAST_TRADED_PRICE": 533, "CH_CLOSING_PRICE": 533.87, "VWAP": 530.54,
           "CH_TOT_TRADED_QTY": 53156, "CH_TOT_TRADED_VAL": 28201570.87, "CH_TOTAL_TRADES": None, "CH_TIMESTAMP": "2010-06-29T18:30:00.000Z",
           "COP_DELIV_QTY": 26693, "COP_DELIV_PERC": 50.22}
FO_ROW = {"FH_INSTRUMENT": "FUTIDX", "FH_SYMBOL": "NIFTY", "FH_EXPIRY_DT": "25-Mar-2010", "FH_STRIKE_PRICE": 0, "FH_OPTION_TYPE": "XX", "FH_MARKET_TYPE": "N",
          "FH_OPENING_PRICE": 5214.95, "FH_TRADE_HIGH_PRICE": 5263.9, "FH_TRADE_LOW_PRICE": 5204, "FH_CLOSING_PRICE": 5260.65, "FH_LAST_TRADED_PRICE": 5260.65,
          "FH_PREV_CLS": 5226.7, "FH_SETTLE_PRICE": 5260.4, "FH_TOT_TRADED_QTY": 21269100, "FH_TOT_TRADED_VAL": 1111674.68, "FH_OPEN_INT": 11940200,
          "FH_CHANGE_IN_OI": -4062050, "FH_MARKET_LOT": 50, "FH_TIMESTAMP": "25-Mar-2010", "FH_TIMESTAMP_ORDER": "2010-03-24T18:30:00.000Z",
          "FH_UNDERLYING_VALUE": 5260.4, "CALCULATED_PREMIUM_VAL": 1111674.68}
IDX_ROW = {"EOD_INDEX_NAME": "S&P CNX NIFTY", "EOD_OPEN_INDEX_VAL": 5254.25, "EOD_HIGH_INDEX_VAL": 5320.35, "EOD_CLOSE_INDEX_VAL": 5312.5, "EOD_LOW_INDEX_VAL": 5210,
           "HIT_TURN_OVER": 7083.92, "HIT_TRADED_QTY": 183722824, "EOD_TIMESTAMP": "30-JUN-2010", "HI_TIMESTAMP": "2010-06-29T18:30:00.000Z"}
VIX_ROW = {"EOD_TIMESTAMP": "30-JUN-2010", "EOD_INDEX_NAME": "INDIA VIX", "EOD_OPEN_INDEX_VAL": 23.1, "EOD_HIGH_INDEX_VAL": 24.0, "EOD_LOW_INDEX_VAL": 22.5,
           "EOD_CLOSE_INDEX_VAL": 23.45, "EOD_PREV_CLOSE": 23.0}


def item(kind, rows, **kw):
    base = {"kind": kind, "from": "2010-03-01", "to": "2010-06-30", "url": "u", "status": 200, "n": len(rows), "data": rows}
    return base | kw


def raw_of(*items, meta=None) -> bytes:
    # the same float spelling the site used: dumps writes 527.5 as 527.5 and 5260.4 as 5260.4
    return json.dumps({"meta": meta or {"collected": "2026-10-01T10:00:00.000Z", "script": "data/nse_web_collect.js"}, "items": list(items)}).encode()


def test_etf_rows_come_out_in_the_archive_column_layout_with_blanks_where_the_site_has_nothing():
    got = nw.read_web(raw_of(item("etf", [ETF_ROW], symbol="NIFTYBEES", **{"from": "2010-04-01", "to": "2010-06-30"})))
    assert got["cash"] == [dict(date="2010-06-30", symbol="NIFTYBEES", series="EQ", open="527.5", high="534.99", low="527", close="533.87", last="533",
                                prev_close="530.54", qty="53156", value="28201570.87", trades="", isin="")]
    assert got["fo"] == [] and got["index"] == []


def test_futures_rows_turn_units_into_contracts_and_lakhs_into_rupees_and_keep_the_published_lot():
    got = nw.read_web(raw_of(item("fo", [FO_ROW], symbol="NIFTY", expiry="2010-03-25")))
    assert got["fo"] == [dict(date="2010-03-25", symbol="NIFTY", expiry="2010-03-25", open="5214.95", high="5263.9", low="5204", close="5260.65", settle="5260.4",
                              prev_close="5226.7", contracts="425382", value_rs="111167468000.00", open_int="11940200", chg_oi="-4062050", lot="50", underlying="5260.4")]


def test_index_and_vix_rows_are_named_by_the_request_not_by_the_old_name_in_the_reply():
    got = nw.read_web(raw_of(item("index", [IDX_ROW], index="NIFTY 50"), item("vix", [VIX_ROW])))
    assert got["index"][0] == dict(date="2010-06-30", name="Nifty 50", open="5254.25", high="5320.35", low="5210", close="5312.5", volume="183722824",
                                   turnover_cr="7083.92", pe="", pb="", div_yield="")
    assert (got["index"][1]["name"], got["index"][1]["close"], got["index"][1]["date"]) == ("India VIX", "23.45", "2010-06-30")
    assert got["index"][1]["volume"] == "" and got["index"][1]["turnover_cr"] == ""
    names = [("NIFTY NEXT 50", "Nifty Next 50"), ("NIFTY BANK", "Nifty Bank")]
    for asked, ours in names:
        assert nw.read_web(raw_of(item("index", [IDX_ROW], index=asked)))["index"][0]["name"] == ours


def test_numbers_keep_the_digits_the_site_wrote_no_float_noise():
    row = dict(ETF_ROW, CH_CLOSING_PRICE=0.1, CH_TOT_TRADED_VAL=1e6 + 0.07)
    got = nw.read_web(raw_of(item("etf", [row], symbol="NIFTYBEES", **{"from": "2010-04-01"})))["cash"][0]
    assert got["close"] == "0.1" and got["value"] == "1000000.07"


def test_a_reply_that_does_not_belong_to_its_request_is_refused():
    with pytest.raises(ValueError, match="symbol"):
        nw.read_web(raw_of(item("etf", [dict(ETF_ROW, CH_SYMBOL="GOLDBEES")], symbol="NIFTYBEES", **{"from": "2010-04-01"})))
    with pytest.raises(ValueError, match="outside"):
        nw.read_web(raw_of(item("etf", [dict(ETF_ROW, mTIMESTAMP="30-Jun-2011")], symbol="NIFTYBEES", **{"from": "2010-04-01"})))
    with pytest.raises(ValueError, match="expiry"):
        nw.read_web(raw_of(item("fo", [dict(FO_ROW, FH_EXPIRY_DT="29-Apr-2010")], symbol="NIFTY", expiry="2010-03-25")))
    with pytest.raises(ValueError, match="FUTIDX"):
        nw.read_web(raw_of(item("fo", [dict(FO_ROW, FH_INSTRUMENT="FUTSTK")], symbol="NIFTY", expiry="2010-03-25")))


def test_a_traded_quantity_that_is_not_a_whole_number_of_lots_is_refused():
    with pytest.raises(ValueError, match="lot"):
        nw.read_web(raw_of(item("fo", [dict(FO_ROW, FH_TOT_TRADED_QTY=21269101)], symbol="NIFTY", expiry="2010-03-25")))


def test_a_file_in_another_shape_or_with_an_item_the_reader_does_not_know_is_an_error():
    with pytest.raises(ValueError, match="shape"):
        nw.read_web(b'{"rows": []}')
    with pytest.raises(ValueError, match="kind"):
        nw.read_web(raw_of({"kind": "options", "data": []}))
    with pytest.raises(ValueError, match="CH_CLOSING_PRICE"):
        nw.read_web(raw_of(item("etf", [{k: v for k, v in ETF_ROW.items() if k != "CH_CLOSING_PRICE"}], symbol="NIFTYBEES", **{"from": "2010-04-01"})))


def test_a_part_file_from_a_paused_or_aborted_collection_is_read_and_described_with_what_is_missing():
    meta = {"collected": "x", "status": "paused", "failed": [{"kind": "fo", "key": "NIFTY", "year": 2013, "month": 0}], "missing": []}
    raw = raw_of(item("etf", [ETF_ROW], symbol="NIFTYBEES", **{"from": "2010-04-01"}), meta=meta)
    assert len(nw.read_web(raw)["cash"]) == 1                       # its rows are good; whether the set of files is complete is checked on the rows
    text = nw.describe(raw)
    assert "status paused" in text and "not collected: fo NIFTY 2013-01" in text
    aborted = raw_of(item("etf", [ETF_ROW], symbol="NIFTYBEES", **{"from": "2010-04-01"}), meta=dict(meta, status="aborted", failed=[]))
    assert "status aborted" in nw.describe(aborted)
    finished = raw_of(item("etf", [ETF_ROW], symbol="NIFTYBEES", **{"from": "2010-04-01"}), meta={"collected": "x", "status": "finished", "failed": [], "missing": []})
    assert "status" not in nw.describe(finished)


def test_months_with_no_contract_found_are_reported_by_the_reader_not_hidden():
    meta = {"collected": "x", "status": "finished", "failed": [], "missing": [{"kind": "fo", "symbol": "NIFTY", "year": 2012, "month": 4}]}
    text = nw.describe(raw_of(item("etf", [ETF_ROW], symbol="NIFTYBEES", **{"from": "2010-04-01"}), meta=meta))
    assert "no contract found: NIFTY 2012-04" in text and "cash 1 rows" in text


def test_register_copies_the_file_lists_it_with_its_hash_and_counts_and_verify_finds_a_change(tmp_path):
    src = tmp_path / "downloads" / "nse_web_test.json"
    src.parent.mkdir()
    raw = raw_of(item("etf", [ETF_ROW], symbol="NIFTYBEES", **{"from": "2010-04-01"}), item("fo", [FO_ROW], symbol="NIFTY", expiry="2010-03-25"))
    src.write_bytes(raw)
    root = tmp_path / "data"
    root.mkdir()
    script = tmp_path / "collect.js"
    script.write_text("// the collector")
    row = nw.register(src, root, script, registered=date(2026, 10, 1))
    assert (root / "raw" / "nse_web" / "nse_web_test.json").read_bytes() == raw
    (listed,) = list(csv.DictReader((root / "nse_web_files.csv").open(newline="")))
    assert listed["sha256"] == hashlib.sha256(raw).hexdigest() == row["sha256"] and listed["bytes"] == str(len(raw))
    assert (listed["rows_cash"], listed["rows_fo"], listed["rows_index"]) == ("1", "1", "0")
    assert listed["script_sha256"] == hashlib.sha256(b"// the collector").hexdigest() and listed["collected"] == "2026-10-01T10:00:00.000Z"
    assert nw.verify_files(root) == []
    (root / "raw" / "nse_web" / "nse_web_test.json").write_bytes(raw + b" ")
    assert any("hash" in p for p in nw.verify_files(root))
    nw.register(src, root, script, registered=date(2026, 10, 2))                                       # registering again replaces the row
    assert len(list(csv.DictReader((root / "nse_web_files.csv").open(newline="")))) == 1
    (root / "raw" / "nse_web" / "nse_web_test.json").unlink()
    assert nw.verify_files(root) == [] and any("missing" in p for p in nw.verify_files(root, need_raw=True))


def test_register_refuses_a_file_the_reader_cannot_read_and_lists_nothing(tmp_path):
    src = tmp_path / "bad.json"
    src.write_bytes(b'{"rows": []}')
    root = tmp_path / "data"
    root.mkdir()
    with pytest.raises(ValueError, match="shape"):
        nw.register(src, root, tmp_path / "collect.js")
    assert not (root / "nse_web_files.csv").exists() and not (root / "raw").exists()


def test_rows_outside_the_request_window_of_a_split_window_item_are_judged_by_that_items_own_window():
    # a window that was halved has its own from/to: rows belong to the half they were asked for
    first = item("etf", [ETF_ROW], symbol="NIFTYBEES", **{"from": "2010-04-01", "to": "2010-05-15"})
    with pytest.raises(ValueError, match="outside"):
        nw.read_web(raw_of(first))


def test_a_futures_reply_for_another_symbol_is_refused():
    with pytest.raises(ValueError, match="symbol"):
        nw.read_web(raw_of(item("fo", [dict(FO_ROW, FH_SYMBOL="BANKNIFTY")], symbol="NIFTY", expiry="2010-03-25")))


def test_digits_are_kept_as_written_including_a_trailing_zero():
    text = json.dumps({"meta": {}, "items": [item("etf", [ETF_ROW], symbol="NIFTYBEES", **{"from": "2010-04-01"})]}).replace('"CH_CLOSING_PRICE": 533.87', '"CH_CLOSING_PRICE": 533.50')
    assert nw.read_web(text.encode())["cash"][0]["close"] == "533.50"


NO_TRADES = {k: None for k in ("FH_OPENING_PRICE", "FH_TRADE_HIGH_PRICE", "FH_TRADE_LOW_PRICE", "FH_CLOSING_PRICE", "FH_PREV_CLS", "FH_SETTLE_PRICE", "FH_TOT_TRADED_QTY",
                               "FH_TOT_TRADED_VAL", "FH_OPEN_INT", "FH_CHANGE_IN_OI", "FH_MARKET_LOT", "FH_UNDERLYING_VALUE", "FH_LAST_TRADED_PRICE", "FH_MARKET_TYPE",
                               "CALCULATED_PREMIUM_VAL")}


def test_a_listed_contract_nobody_traded_that_day_has_no_row_and_the_description_counts_them():
    empty = dict(FO_ROW, **NO_TRADES, FH_TIMESTAMP="24-Mar-2010")
    raw = raw_of(item("fo", [FO_ROW, empty], symbol="NIFTY", expiry="2010-03-25"))
    assert [r["date"] for r in nw.read_web(raw)["fo"]] == ["2010-03-25"]
    assert "fo 1 rows" in nw.describe(raw) and "1 futures rows without trades left out" in nw.describe(raw)


def test_a_futures_row_with_only_some_values_missing_is_an_error_and_a_missing_underlying_is_just_blank():
    half = dict(FO_ROW, FH_CLOSING_PRICE=None)
    with pytest.raises(ValueError, match="FH_CLOSING_PRICE"):
        nw.read_web(raw_of(item("fo", [half], symbol="NIFTY", expiry="2010-03-25")))
    no_und = dict(FO_ROW, FH_UNDERLYING_VALUE=None)
    assert nw.read_web(raw_of(item("fo", [no_und], symbol="NIFTY", expiry="2010-03-25")))["fo"][0]["underlying"] == ""


def test_a_reply_that_repeats_an_identical_row_gives_it_once_and_the_description_counts_the_repeats():
    # the site does this on some days (2011-05-06, 2011-08-09, 2011-10-24 for every ETF): the same row twice in one reply
    raw = raw_of(item("etf", [ETF_ROW, ETF_ROW], symbol="NIFTYBEES", **{"from": "2010-04-01"}))
    assert len(nw.read_web(raw)["cash"]) == 1
    assert "1 repeated identical rows dropped" in nw.describe(raw)
    across = raw_of(item("etf", [ETF_ROW], symbol="NIFTYBEES", **{"from": "2010-04-01"}), item("etf", [ETF_ROW], symbol="NIFTYBEES", **{"from": "2010-04-01"}))
    assert len(nw.read_web(across)["cash"]) == 1


def test_the_same_key_with_different_values_is_a_conflict_and_an_error():
    other = dict(ETF_ROW, CH_CLOSING_PRICE=999)
    with pytest.raises(ValueError, match="conflict"):
        nw.read_web(raw_of(item("etf", [ETF_ROW, other], symbol="NIFTYBEES", **{"from": "2010-04-01"})))
    fo2 = dict(FO_ROW, FH_CLOSING_PRICE=1)
    with pytest.raises(ValueError, match="conflict"):
        nw.read_web(raw_of(item("fo", [FO_ROW, fo2], symbol="NIFTY", expiry="2010-03-25")))
