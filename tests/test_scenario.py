from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal as Dc

import pytest

from engine.scenario import Bar, buy_and_hold
from engine.tax import TaxProfile
from engine.trace import assert_balanced
from tests.helpers import make_rules, table
from tests.synth_charges import CHARGES
from tests.synth_tax import TAX

# An account that pays the yearly AMC and an opening fee whatever day it was opened, so both show up in the story.
PAYING = {
    "fyers.amc_cohort": table([], ['from = 2010-04-01\ncohort = "standard"']),
    "fyers.amc": table(["cohort"], ['cohort = "standard"\nfrom = 2010-04-01\nvalue = "300"']),
    "fyers.account_opening": table([], ['from = 2010-04-01\nvalue = "400"']),
}


@pytest.fixture
def rules(tmp_path):
    return make_rules(tmp_path, {**CHARGES, **TAX, **PAYING})


def bars():
    """Daily bars 2015-04-01 .. 2019-06-03, price 100 until 2018-01-31 (high 150), 300 after."""
    out, d = [], date(2015, 4, 1)
    while d <= date(2019, 6, 3):
        if d.weekday() < 5:
            price = Dc("100") if d < date(2018, 2, 1) else Dc("300")
            out.append(Bar(d, Dc("150") if d == date(2018, 1, 31) else price, price))
        d += timedelta(days=1)
    return out


def rnd(x, step):
    return (x / step).quantize(Dc(1), rounding=ROUND_HALF_UP) * step


def hand_calc(amount, dividend_per_unit=Dc(0), amc_years=5, opening_fee=True):
    """The same story worked by hand with the made-up rates typed in, sharing no code with the engine."""
    units = int(amount // 100)
    while True:  # whole units such that price + buy charges fit in the amount
        t = Dc(units) * 100
        stamp, exch, sebi = rnd(t * Dc("0.00015"), Dc("0.01")), rnd(t * Dc("0.00003"), Dc("0.01")), rnd(t * Dc("0.000001"), Dc("0.01"))
        gst = rnd((exch + sebi) * Dc("0.18"), Dc("0.01"))
        buy_total = stamp + exch + sebi + gst
        if t + buy_total <= amount:
            break
        units -= 1
    t_sell = Dc(units) * 300
    stt = rnd(t_sell * Dc("0.0005"), Dc(1))
    exch_s, sebi_s = rnd(t_sell * Dc("0.00003"), Dc("0.01")), rnd(t_sell * Dc("0.000001"), Dc("0.01"))
    gst_s = rnd((exch_s + sebi_s) * Dc("0.18"), Dc("0.01"))
    dp = rnd((Dc(13) + Dc("3.5")) * Dc("0.18"), Dc("0.01")) + Dc("16.5")
    sell_total = stt + exch_s + sebi_s + gst_s + dp
    amc = amc_years * Dc("354")                           # FY2015 .. FY2019, 300 + 18% each
    opening = Dc("472") if opening_fee else Dc(0)         # 400 + 18%, once, on the day the account is opened
    cost = t + stamp + exch + sebi + gst
    fmv = Dc(units) * 150                                 # highest price on 31 Jan 2018
    cost_used = max(cost, min(fmv, t_sell))
    gain = t_sell - (exch_s + sebi_s + gst_s + dp) - cost_used
    taxable = max(Dc(0), gain - 100000)                   # 1 lakh exemption
    extra = rnd(Dc(117000) + taxable * Dc("0.10") * Dc("1.04"), Dc(10)) - Dc(117000)
    net = amount + (t_sell - t) + Dc(units) * dividend_per_unit - (buy_total + sell_total + amc + opening) - extra
    return units, net, extra


def run(rules, amount, **kw):
    return buy_and_hold(rules, instrument="ETF", instrument_class="etf_equity", bars=bars(),
                        dividends=kw.pop("dividends", {}), amount=Dc(amount), start=date(2015, 4, 1),
                        end=date(2019, 6, 3), profile=TaxProfile("old", Dc("1000000")), **kw)


def test_matches_a_hand_calculation_to_the_paisa(rules):
    r = run(rules, "1000000")
    units, net, extra = hand_calc(Dc("1000000"))
    assert r.units == units
    assert r.waterfall["tax"].value == extra > 0
    assert r.net.value == net
    assert_balanced(r.net)


def test_the_opening_fee_and_the_yearly_amc_are_charges_of_this_investment(rules):
    r = run(rules, "1000000")
    assert r.waterfall["account_opening"].value == Dc("472.00")
    assert r.waterfall["amc"].value == Dc("1770.00")         # five financial years, FY2015-16 to FY2019-20
    assert r.waterfall["charges"].value == (r.waterfall["buy_charges"].value + r.waterfall["sale_charges"].value
                                            + r.waterfall["amc"].value + r.waterfall["account_opening"].value)


def test_an_account_opened_in_2015_is_in_the_legacy_group_and_pays_neither_fee(tmp_path):
    rules = make_rules(tmp_path, {**CHARGES, **TAX})       # the made-up legacy group: opened before 2020-04-01
    r = run(rules, "1000000")
    _, net, _ = hand_calc(Dc("1000000"), amc_years=0, opening_fee=False)
    assert r.net.value == net and r.waterfall["amc"].value == 0 and r.waterfall["account_opening"].value == 0


def test_dividends_add_to_gross_and_are_traced(rules):
    r = run(rules, "1000000", dividends={date(2016, 6, 1): Dc("2"), date(2015, 4, 1): Dc("9")})
    _, net, _ = hand_calc(Dc("1000000"), Dc(2))
    assert r.net.value == net                       # the 2015-04-01 ex-date is the buy day: not entitled
    assert r.waterfall["gross_profit"].value == (Dc(300) - 100) * r.units + 2 * r.units


def test_still_holding_pays_no_sale_charges_or_capital_gains_tax(rules):
    r = run(rules, "1000000", sell_at_end=False)
    assert r.waterfall["sale_charges"].value == 0 and r.waterfall["tax"].value == 0
    assert not r.sold
    assert r.waterfall["account_opening"].value == Dc("472.00")   # the account was opened either way


def test_amount_too_small_or_period_empty_is_an_error(rules):
    with pytest.raises(ValueError, match="too small"):
        run(rules, "50")
    with pytest.raises(ValueError, match="no usable price history"):
        buy_and_hold(rules, instrument="ETF", instrument_class="etf_equity", bars=bars(), dividends={},
                     amount=Dc("1000"), start=date(2030, 1, 1), end=date(2031, 1, 1),
                     profile=TaxProfile("old", Dc("0")))


@pytest.mark.parametrize("amount", ["0", "-1000"])
def test_a_zero_or_negative_amount_is_refused(rules, amount):
    with pytest.raises(ValueError, match="positive"):
        run(rules, amount)
