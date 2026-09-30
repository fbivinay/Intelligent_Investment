import io
import zipfile

from data import nse_read as nr

CASH_OLD_HEAD = "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,TIMESTAMP,TOTALTRADES,ISIN,"
CASH_NEW_HEAD = ("TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,XpryDt,FininstrmActlXpryDt,StrkPric,OptnTp,FinInstrmNm,"
                 "OpnPric,HghPric,LwPric,ClsPric,LastPric,PrvsClsgPric,UndrlygPric,SttlmPric,OpnIntrst,ChngInOpnIntrst,TtlTradgVol,TtlTrfVal,"
                 "TtlNbOfTxsExctd,SsnId,NewBrdLotQty,Rmks,Rsvd1,Rsvd2,Rsvd3,Rsvd4")
FO_OLD_HEAD = "INSTRUMENT,SYMBOL,EXPIRY_DT,STRIKE_PR,OPTION_TYP,OPEN,HIGH,LOW,CLOSE,SETTLE_PR,CONTRACTS,VAL_INLAKH,OPEN_INT,CHG_IN_OI,TIMESTAMP,"
IDX_HEAD = "Index Name,Index Date,Open Index Value,High Index Value,Low Index Value,Closing Index Value,Points Change,Change(%),Volume,Turnover (Rs. Cr.),P/E,P/B,Div Yield"


def zipped(lines: list[str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("file.csv", "\n".join(lines) + "\n")
    return buf.getvalue()


def test_cash_old_layout_gives_the_etf_rows_exactly_as_published_and_nothing_else():
    raw = zipped([CASH_OLD_HEAD,
                  "20MICRONS,EQ,28.5,29,28.4,28.5,28.55,28.55,37348,1073029.7,01-JUN-2016,119,INE144J01027,",
                  "NIFTYBEES,EQ,827,831.75,826,828.85,829.05,826.68,32150,26661845.83,01-JUN-2016,1158,INF732E01011,"])
    assert nr.read_cash(raw, {"NIFTYBEES"}) == [dict(date="2016-06-01", symbol="NIFTYBEES", series="EQ", open="827", high="831.75", low="826",
                                                   close="828.85", last="829.05", prev_close="826.68", qty="32150", value="26661845.83",
                                                   trades="1158", isin="INF732E01011")]


def test_cash_old_layout_keeps_the_unadjusted_previous_close_on_a_split_day():
    raw = zipped([CASH_OLD_HEAD, "NIFTYBEES,EQ,129.2,130.33,129.05,130.2,130.26,1292.54,271593,35256962.4,19-DEC-2019,3336,INF732E01011,"])
    (row,) = nr.read_cash(raw, {"NIFTYBEES"})
    assert (row["date"], row["close"], row["prev_close"]) == ("2019-12-19", "130.2", "1292.54")      # ten times: the split, not hidden


def test_cash_new_layout_maps_to_the_same_fields():
    raw = zipped([CASH_NEW_HEAD,
                  "2025-08-01,2025-08-01,CM,NSE,STK,19078,IN0020200104,SGBJUN28,GB,,,,,2.5%GOLDBONDS2028SR-III,9863.00,10099.99,9860.00,9939.00,9939.00,9900.00,,9929.50,,,420,4175051.35,41,F1,1,,,,,",
                  "2025-08-01,2025-08-01,CM,NSE,STK,10576,INF204KB14I2,NIFTYBEES,EQ,,,,,NIP IND ETF NIFTY BEES,280.99,280.99,277.03,277.35,277.46,279.26,,277.36,,,4744556,1319936913.14,66609,F1,1,,,,,"])
    assert nr.read_cash(raw, {"NIFTYBEES"}) == [dict(date="2025-08-01", symbol="NIFTYBEES", series="EQ", open="280.99", high="280.99", low="277.03",
                                                   close="277.35", last="277.46", prev_close="279.26", qty="4744556", value="1319936913.14",
                                                   trades="66609", isin="INF204KB14I2")]


def test_futures_old_layout_keeps_index_futures_only_and_turns_lakhs_into_rupees():
    raw = zipped([FO_OLD_HEAD,
                  "FUTIDX,BANKNIFTY,30-Jun-2016,0,XX,17631.1,17644,17381.1,17419.7,17419.7,100762,528975.29,1656030,-49920,01-JUN-2016,",
                  "FUTIDX,NIFTY,30-Jun-2016,0,XX,8200,8224.9,8178.3,8194.55,8194.55,125472,771709.04,21499350,-130800,01-JUN-2016,",
                  "OPTIDX,NIFTY,30-Jun-2016,8200,CE,150,160,140,155,155,1000,1000.5,500,10,01-JUN-2016,",
                  "FUTSTK,RELIANCE,30-Jun-2016,0,XX,1000,1010,990,1005,1005,50,50.25,500,10,01-JUN-2016,"])
    rows = nr.read_fo(raw, {"NIFTY"})
    assert rows == [dict(date="2016-06-01", symbol="NIFTY", expiry="2016-06-30", open="8200", high="8224.9", low="8178.3", close="8194.55",
                         settle="8194.55", prev_close="", contracts="125472", value_rs="77170904000.00", open_int="21499350",
                         chg_oi="-130800", lot="", underlying="")]


def test_futures_new_layout_has_lot_size_and_underlying_and_ignores_options():
    raw = zipped([CASH_NEW_HEAD,
                  "2025-08-01,2025-08-01,FO,NSE,IDF,52168,,NIFTY,,2025-10-28,2025-10-28,,,NIFTY25OCTFUT,25017.40,25104.10,24862.70,24892.40,24878.00,25139.50,24565.35,24892.40,61125,61125,1658,3107391712.50,1303,F1,75,,,,,",
                  "2025-08-01,2025-08-01,FO,NSE,IDO,52170,,NIFTY,,2025-10-28,2025-10-28,25000.00,CE,NIFTY25OCT25000CE,700.00,720.00,680.00,690.00,690.00,700.00,24565.35,690.00,1000,10,50,1000000.00,20,F1,75,,,,,",
                  "2025-08-01,2025-08-01,FO,NSE,STF,52180,,RELIANCE,,2025-08-28,2025-08-28,,,RELIANCE25AUGFUT,1400.00,1410.00,1390.00,1405.00,1405.00,1400.00,1402.00,1405.00,5000,100,50,3000000.00,20,F1,500,,,,,"])
    assert nr.read_fo(raw, {"NIFTY"}) == [dict(date="2025-08-01", symbol="NIFTY", expiry="2025-10-28", open="25017.40", high="25104.10", low="24862.70",
                                              close="24892.40", settle="24892.40", prev_close="25139.50", contracts="1658", value_rs="3107391712.50",
                                              open_int="61125", chg_oi="61125", lot="75", underlying="24565.35")]


def test_index_rows_blank_out_dashes_and_use_iso_dates():
    raw = "\n".join([IDX_HEAD,
                     "Nifty 50,31-01-2018,11018.8,11058.5,10979.3,11027.7,-21.95,-.2,253462573,14459.69,27.5,3.73,1.03",
                     "India VIX,31-01-2018,12.1,12.5,11.9,12.3,0.1,0.8,-,-,-,-,-",
                     "Nifty Auto,31-01-2018,1,2,0.5,1.5,0,0,1,1,1,1,1"]).encode()
    rows = nr.read_index(raw, {"Nifty 50", "India VIX"})
    assert rows[0] == dict(date="2018-01-31", name="Nifty 50", open="11018.8", high="11058.5", low="10979.3", close="11027.7", volume="253462573",
                           turnover_cr="14459.69", pe="27.5", pb="3.73", div_yield="1.03")
    assert rows[1]["name"] == "India VIX" and (rows[1]["volume"], rows[1]["pe"], rows[1]["div_yield"]) == ("", "", "") and len(rows) == 2


def test_index_names_that_nse_changed_are_read_under_one_name():
    raw = "\n".join([IDX_HEAD, "S&P CNX Nifty,03-01-2014,6000,6010,5990,6005,5,0.1,1,1,18.5,2.6,1.4"]).encode()
    assert nr.read_index(raw, {"Nifty 50"})[0]["name"] == "Nifty 50"


def test_a_file_in_a_layout_nobody_taught_the_reader_is_an_error_not_an_empty_result():
    import pytest
    with pytest.raises(ValueError, match="layout"):
        nr.read_cash(zipped(["A,B,C", "1,2,3"]), {"NIFTYBEES"})
    with pytest.raises(ValueError, match="layout"):
        nr.read_index(b"A,B\n1,2\n", {"Nifty 50"})


def test_index_names_match_whatever_the_capitalisation_and_come_out_as_we_spell_them():
    raw = "\n".join([IDX_HEAD, "NIFTY Midcap 100,03-01-2018,1,2,0.5,1.5,0,0,1,1,1,1,1", "Nifty Midcap 150,03-01-2018,1,2,0.5,1.5,0,0,1,1,1,1,1"]).encode()
    rows = nr.read_index(raw, {"Nifty Midcap 100"})
    assert [r["name"] for r in rows] == ["Nifty Midcap 100"]


def test_a_two_digit_year_in_the_old_cash_file_is_read_as_20xx():
    raw = zipped([CASH_OLD_HEAD, "NIFTYBEES,EQ,114.5,115,114,114.86,114.9,114.4,100,100,13-Jul-20,5,INF732E01011,"])
    assert nr.read_cash(raw, {"NIFTYBEES"})[0]["date"] == "2020-07-13"


def test_futures_dates_with_a_two_digit_year_are_read_the_same_way():
    raw = zipped([FO_OLD_HEAD, "FUTIDX,NIFTY,30-Jul-20,0,XX,10000,10100,9900,10050,10050,1000,1000,500,10,13-Jul-20,"])
    (row,) = nr.read_fo(raw, {"NIFTY"})
    assert (row["date"], row["expiry"]) == ("2020-07-13", "2020-07-30")


def test_futures_prefilter_keeps_working_when_the_file_has_no_index_futures_at_all():
    raw = zipped([FO_OLD_HEAD, "OPTIDX,NIFTY,30-Jun-2016,8200,CE,150,160,140,155,155,1000,1000.5,500,10,01-JUN-2016,"])
    assert nr.read_fo(raw, {"NIFTY"}) == []


def test_an_index_file_that_writes_the_date_month_first_is_read_as_the_day_it_was_asked_for():
    raw = "\n".join([IDX_HEAD, "Nifty 50,04-06-2023,1,2,0.5,1.5,0,0,1,1,1,1,1"]).encode()          # 2023-04-06 written as MM-DD-YYYY
    assert nr.read_index(raw, {"Nifty 50"}, day="2023-04-06")[0]["date"] == "2023-04-06"
    assert nr.read_index(raw, {"Nifty 50"})[0]["date"] == "2023-06-04"                               # without a day to hold it to, it is read as written
    assert nr.read_index(raw, {"Nifty 50"}, day="2023-01-01")[0]["date"] == "2023-06-04"             # a date that fits neither way is not touched


def test_the_midcap_100_index_is_read_under_one_name_across_its_renaming_in_2018():
    raw = "\n".join([IDX_HEAD, "Nifty Free Float Midcap 100,05-07-2016,1,2,0.5,14122.85,0,0,1,1,32.83,1,1", "Nifty Full Midcap 100,05-07-2016,1,2,0.5,4352.82,0,0,1,1,41.12,1,1"]).encode()
    rows = nr.read_index(raw, {"Nifty Midcap 100"})
    assert [(r["name"], r["close"]) for r in rows] == [("Nifty Midcap 100", "14122.85")]            # the Full Midcap 100 is a different index


def test_index_names_before_the_november_2015_renaming_are_read_under_todays_names():
    # 2015-11-06 is the last day of the CNX names; every one of these renamings kept the index (closes are continuous across it)
    raw = "\n".join([IDX_HEAD,
                     "CNX Nifty,06-11-2015,7960,7970,7930,7954.3,1,0.1,1,1,22.1,3.1,1.4",
                     "CNX Nifty Junior,06-11-2015,19500,19600,19400,19561.75,1,0.1,1,1,25.1,3.4,1.2",
                     "CNX Bank,06-11-2015,17000,17100,16900,17086.5,1,0.1,1,1,16.1,2.1,1.0",
                     "CNX Midcap,06-11-2015,13000,13100,12900,12995.7,1,0.1,1,1,21.1,2.6,1.1",
                     "CNX Nifty Shariah,06-11-2015,1,2,0.5,1.5,0,0,1,1,1,1,1"]).encode()
    rows = nr.read_index(raw, {"Nifty 50", "Nifty Next 50", "Nifty Bank", "Nifty Midcap 100"})
    assert {r["name"]: r["close"] for r in rows} == {"Nifty 50": "7954.3", "Nifty Next 50": "19561.75", "Nifty Bank": "17086.5", "Nifty Midcap 100": "12995.7"}
