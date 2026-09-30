import csv
from decimal import Decimal

from data import lots


def fut(d, sym, contracts, close, value, lot="", expiry="2016-06-30"):
    return {"date": d, "symbol": sym, "expiry": expiry, "close": close, "settle": close, "contracts": contracts, "value_rs": value, "lot": lot}


def test_the_lot_is_traded_value_over_contracts_over_price_when_enough_contracts_traded():
    assert lots.implied_lot(fut("2016-06-01", "NIFTY", "125472", "8194.55", "77170904000.00")) == Decimal("77170904000.00") / Decimal("125472") / Decimal("8194.55")
    assert lots.daily_lots([fut("2016-06-01", "NIFTY", "10000", "8000", str(10000 * 8000 * Decimal("72.9")))]) == {("NIFTY", "2016-06-01"): 75}   # value uses traded prices, not the close
    assert lots.implied_lot(fut("2016-06-01", "NIFTY", "999", "8194.55", "1")) is None                # too few contracts: value over contracts is noise
    assert lots.implied_lot(fut("2016-06-01", "NIFTY", "0", "8194.55", "0")) is None


def test_a_day_takes_the_lot_most_contracts_agree_on_and_skips_a_day_with_no_agreement():
    good = [fut("2016-06-01", "NIFTY", "10000", "8000", str(10000 * 75 * 8000), expiry=e) for e in ("2016-06-30", "2016-07-28")]
    odd = [fut("2016-06-01", "NIFTY", "10000", "8000", str(10000 * 60 * 8000), expiry="2016-08-25")]     # a far contract traded at odd prices
    assert lots.daily_lots(good + odd) == {("NIFTY", "2016-06-01"): 75}
    split = [fut("2016-06-02", "NIFTY", "10000", "8000", str(10000 * 75 * 8000), expiry="2016-06-30"),
             fut("2016-06-02", "NIFTY", "10000", "8000", str(10000 * 50 * 8000), expiry="2016-07-28")]
    assert lots.daily_lots(split) == {}


def test_history_merges_days_with_the_same_lot_and_starts_a_new_run_when_it_changes():
    daily = {("NIFTY", "2016-06-01"): 75, ("NIFTY", "2016-06-02"): 75, ("NIFTY", "2016-06-03"): 50, ("BANKNIFTY", "2016-06-01"): 40}
    assert lots.history(daily) == [("BANKNIFTY", "2016-06-01", "2016-06-01", 40), ("NIFTY", "2016-06-01", "2016-06-02", 75), ("NIFTY", "2016-06-03", "2016-06-03", 50)]


def test_the_inference_is_checked_against_the_lot_the_exchange_publishes_from_2024():
    rows = [fut("2025-01-01", "NIFTY", "10000", "24000", str(10000 * 75 * 24000), lot="75"),
            fut("2025-01-02", "NIFTY", "10000", "24000", str(10000 * 25 * 24000), lot="75")]
    assert lots.check_published(rows) == {"compared": 2, "differ": [("NIFTY", "2025-01-02", 25, 75)]}


def test_build_writes_the_history_and_refuses_to_run_without_the_futures_file(tmp_path):
    import pytest
    with pytest.raises(FileNotFoundError):
        lots.build(tmp_path)
    (tmp_path / "processed").mkdir()
    with (tmp_path / "processed" / "nse_index_futures_daily.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, ["date", "symbol", "expiry", "close", "settle", "contracts", "value_rs", "lot"], lineterminator="\n")
        w.writeheader()
        w.writerow(fut("2016-06-01", "NIFTY", "10000", "8000", str(10000 * 75 * 8000)))
    assert lots.build(tmp_path) == {"runs": 1, "days": 1, "differ": 0}
    (row,) = list(csv.DictReader((tmp_path / "lot_sizes.csv").open(newline="")))
    assert (row["symbol"], row["first_seen"], row["last_seen"], row["lot"]) == ("NIFTY", "2016-06-01", "2016-06-01", "75")


def test_exactly_the_minimum_number_of_contracts_is_enough():
    assert lots.implied_lot(fut("2016-06-01", "NIFTY", "1000", "8000", str(1000 * 75 * 8000))) == Decimal(75)


def test_a_day_is_decided_by_contracts_traded_not_by_the_number_of_contracts_listed():
    big = [fut("2016-06-01", "NIFTY", "20000", "8000", str(20000 * 75 * 8000), expiry="2016-06-30")]
    small = [fut("2016-06-01", "NIFTY", "1500", "8000", str(1500 * 60 * 8000), expiry=e) for e in ("2016-07-28", "2016-08-25")]
    assert lots.daily_lots(big + small) == {("NIFTY", "2016-06-01"): 75}


def test_two_symbols_with_the_same_lot_are_two_runs():
    assert lots.history({("BANKNIFTY", "2016-06-01"): 50, ("NIFTY", "2016-06-01"): 50}) == [("BANKNIFTY", "2016-06-01", "2016-06-01", 50),
                                                                                          ("NIFTY", "2016-06-01", "2016-06-01", 50)]
