from datetime import date
from decimal import Decimal

import pytest

from calc import api, fyers as F, product as PR
from engine.tax import TaxProfile

PROFILE = TaxProfile("new", Decimal(1500000))


@pytest.fixture(scope="module")
def run():
    return PR.run("Balanced", Decimal(1000000), date(2019, 4, 1), date(2021, 4, 1), PROFILE)


def test_an_etf_trade_becomes_a_fyers_v3_after_market_delivery_order():
    p = F.payload({"asset": "NIFTYBEES", "side": "sell", "units": "37", "date": "2020-03-02"})
    assert p == {"symbol": "NSE:NIFTYBEES-EQ", "qty": 37, "type": 2, "side": -1, "productType": "CNC", "limitPrice": 0, "stopPrice": 0, "validity": "DAY",
                 "disclosedQty": 0, "offlineOrder": True, "orderTag": "preview20200302"}
    assert F.payload({"asset": "GOLDBEES", "side": "buy", "units": "5", "date": "2020-03-02"})["side"] == 1


def test_the_fund_leg_is_not_an_exchange_order():
    assert F.payload({"asset": "LIQUID_FUND", "side": "buy", "units": "1.234", "date": "2020-03-02"}) is None


def test_a_day_preview_lists_the_targets_the_holdings_before_the_orders_with_payloads_and_their_fees(run):
    day = run.booked.trades[0]["date"]
    pv = F.preview(run, date.fromisoformat(day))
    assert pv["fill_day"] == day and pv["decided_on"] == run.dates[run.dates.index(day) - 1]
    assert abs(sum(pv["targets"].values()) - 1) < 1e-9 and set(pv["holdings_before"]) == set(F.ASSETS)
    orders = pv["orders"]
    assert orders and all(o["fees"] == o["trade"]["charges"] for o in orders) and pv["total_fees"] == pytest.approx(sum(float(o["fees"]) for o in orders))
    etf = [o for o in orders if o["trade"]["asset"] != "LIQUID_FUND"]
    assert all(o["payload"]["qty"] == int(o["trade"]["units"]) for o in etf)
    assert all(o["payload"] is None and "fund house" in o["how"] for o in orders if o["trade"]["asset"] == "LIQUID_FUND")
    assert "preview" in pv["label"].lower() and pv["timeline"][0].startswith("After the close")


def test_a_day_with_no_order_says_so_and_the_order_days_are_listed(run):
    days = F.order_days(run)
    assert days and days == sorted(set(t["date"] for t in run.booked.trades))
    quiet = next(d for d in run.dates[1:] if d not in days)
    assert F.preview(run, date.fromisoformat(quiet))["orders"] == []
    with pytest.raises(ValueError, match="not a trading day"):
        F.preview(run, date(2019, 4, 6))


def test_the_api_serves_the_preview_and_refuses_bad_input():
    a = api.preview({"amount": 1000000, "start": "2019-04-01", "end": "2021-04-01", "level": "Balanced", "other_income": 1500000})
    assert a["order_days"] and a["preview"]["fill_day"] == a["order_days"][0]
    b = api.preview({"amount": 1000000, "start": "2019-04-01", "end": "2021-04-01", "level": "Balanced", "date": a["order_days"][3]})
    assert b["preview"]["fill_day"] == a["order_days"][3]
    assert "error" in api.preview({"amount": 1000000, "start": "2012-04-01", "end": "2021-04-01", "level": "Balanced"})
