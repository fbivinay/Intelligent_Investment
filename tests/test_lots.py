import csv
from decimal import Decimal

import pytest

from data import lots


def fut(d, sym, contracts, close, value, lot="", expiry="2016-06-30"):
    return {"date": d, "symbol": sym, "expiry": expiry, "close": close, "settle": close, "contracts": contracts, "value_rs": value, "lot": lot}


def day(d, lot, expiry="2016-06-30", sym="NIFTY", contracts=10000, price=8000):
    """One trading day of a contract whose traded value says it has this lot."""
    return fut(d, sym, str(contracts), str(price), str(contracts * lot * price), expiry=expiry)


def test_the_lot_is_traded_value_over_contracts_over_price_when_enough_contracts_traded():
    assert lots.implied_lot(fut("2016-06-01", "NIFTY", "125472", "8194.55", "77170904000.00")) == Decimal("77170904000.00") / Decimal("125472") / Decimal("8194.55")
    assert lots.implied_lot(fut("2016-06-01", "NIFTY", "999", "8194.55", "1")) is None                # too few contracts: value over contracts is noise
    assert lots.implied_lot(fut("2016-06-01", "NIFTY", "0", "8194.55", "0")) is None


def test_exactly_the_minimum_number_of_contracts_is_enough():
    assert lots.implied_lot(fut("2016-06-01", "NIFTY", "1000", "8000", str(1000 * 75 * 8000))) == Decimal(75)


def test_a_contract_has_one_lot_all_its_days_vote_on_and_a_wild_day_is_outvoted():
    rows = [day("2016-06-01", 75), day("2016-06-02", 75), day("2016-06-03", 75), day("2016-06-06", 60)]
    assert lots.contract_lots(rows) == {("NIFTY", "2016-06-30"): (75, Decimal(3) / Decimal(4))}


def test_value_uses_traded_prices_not_the_close_so_the_working_out_is_rounded_to_a_multiple_of_5():
    rows = [fut("2016-06-01", "NIFTY", "10000", "8000", str(10000 * 8000 * Decimal("72.9")))]
    assert lots.contract_lots(rows) == {("NIFTY", "2016-06-30"): (75, Decimal(1))}


def test_two_contracts_traded_on_the_same_day_can_have_different_lots():
    rows = [day("2025-01-02", 25, expiry="2025-01-30"), day("2025-01-02", 75, expiry="2025-02-27")]
    got = lots.contract_lots(rows)
    assert got[("NIFTY", "2025-01-30")][0] == 25 and got[("NIFTY", "2025-02-27")][0] == 75


def test_votes_are_weighted_by_contracts_traded_and_no_majority_gives_no_lot():
    big = day("2016-06-01", 75, contracts=20000)
    small = [day("2016-06-02", 60, contracts=1500), day("2016-06-03", 60, contracts=1500)]
    assert lots.contract_lots([big] + small)[("NIFTY", "2016-06-30")][0] == 75
    split = [day("2016-06-01", 75), day("2016-06-02", 50)]
    assert lots.contract_lots(split) == {}
    assert lots.contract_lots([day("2016-06-01", 75, contracts=999)]) == {}                          # nothing traded enough to say


def test_history_merges_consecutive_expiries_with_the_same_lot_by_symbol():
    got = {("NIFTY", "2016-06-30"): (75, 1), ("NIFTY", "2016-07-28"): (75, 1), ("NIFTY", "2021-07-29"): (50, 1), ("BANKNIFTY", "2016-06-30"): (50, 1)}
    assert lots.history(got) == [("BANKNIFTY", "2016-06-30", "2016-06-30", 50), ("NIFTY", "2016-06-30", "2016-07-28", 75), ("NIFTY", "2021-07-29", "2021-07-29", 50)]


def test_the_working_out_is_checked_against_the_lot_the_exchange_publishes_from_2024():
    rows = [fut("2025-01-01", "NIFTY", "10000", "24000", str(10000 * 75 * 24000), lot="75", expiry="2025-02-27"),
            fut("2025-01-02", "NIFTY", "10000", "24000", str(10000 * 75 * 24000), lot="75", expiry="2025-02-27"),
            fut("2025-01-01", "NIFTY", "10000", "24000", str(10000 * 25 * 24000), lot="75", expiry="2025-03-27")]
    assert lots.check_published(rows) == {"compared": 2, "differ": [("NIFTY", "2025-03-27", 25, 75)]}


def test_build_writes_one_row_per_contract_and_says_how_many_disagree_with_the_published_lot(tmp_path):
    with pytest.raises(FileNotFoundError):
        lots.build(tmp_path)
    (tmp_path / "processed").mkdir()
    with (tmp_path / "processed" / "nse_index_futures_daily.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, ["date", "symbol", "expiry", "close", "settle", "contracts", "value_rs", "lot"], lineterminator="\n")
        w.writeheader()
        w.writerows([day("2016-06-01", 75), day("2016-06-02", 75), day("2016-06-01", 75, expiry="2016-07-28"), day("2016-06-01", 40, sym="BANKNIFTY")])
    assert lots.build(tmp_path) == {"contracts": 3, "runs": 2, "differ": 0}
    rows = list(csv.DictReader((tmp_path / "lot_sizes.csv").open(newline="")))
    assert [(r["symbol"], r["expiry"], r["lot"], r["agree"]) for r in rows] == [("BANKNIFTY", "2016-06-30", "40", "1.00"), ("NIFTY", "2016-06-30", "75", "1.00"),
                                                                                  ("NIFTY", "2016-07-28", "75", "1.00")]


def test_two_symbols_with_the_same_lot_are_two_runs():
    got = {("BANKNIFTY", "2016-06-30"): (50, 1), ("NIFTY", "2016-06-30"): (50, 1)}
    assert lots.history(got) == [("BANKNIFTY", "2016-06-30", "2016-06-30", 50), ("NIFTY", "2016-06-30", "2016-06-30", 50)]
