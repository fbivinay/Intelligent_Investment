"""Made-up round-number charge rules. They test the engine's logic, never real rates."""
from tests.helpers import table

GST_ALL = '["brokerage", "exchange_txn", "sebi", "ipft", "clearing", "dp", "amc", "account_opening"]'

CHARGES = {
    "fyers.brokerage": table(["product"], [
        'product = "delivery"\nfrom = 2010-04-01\nmode = "zero"',
        'product = "futures"\nfrom = 2010-04-01\nmode = "min_flat_pct"\nflat = "20"\npct = "0.0003"',
    ]),
    "charges.stt": table(["instrument_class", "side"], [
        'instrument_class = "etf_equity"\nside = "buy"\nfrom = 2010-04-01\nvalue = "0"\nround_step = "1"',
        'instrument_class = "etf_equity"\nside = "sell"\nfrom = 2010-04-01\nto = 2015-12-31\nvalue = "0.001"\nround_step = "1"',
        'instrument_class = "etf_equity"\nside = "sell"\nfrom = 2016-01-01\nvalue = "0.0005"\nround_step = "1"',
        'instrument_class = "fut_index"\nside = "buy"\nfrom = 2010-04-01\nvalue = "0"\nround_step = "1"',
        'instrument_class = "fut_index"\nside = "sell"\nfrom = 2010-04-01\nvalue = "0.0002"\nround_step = "1"',
        'instrument_class = "mf_equity"\nside = "buy"\nfrom = 2010-04-01\nvalue = "0"\nround_step = "1"',
        'instrument_class = "mf_equity"\nside = "sell"\nfrom = 2010-04-01\nvalue = "0.00001"\nround_step = "0.01"',
    ]),
    "charges.exchange_txn": table(["exchange", "segment"], [
        'exchange = "NSE"\nsegment = "delivery"\nfrom = 2010-04-01\nvalue = "0.00003"',
        'exchange = "NSE"\nsegment = "futures"\nfrom = 2010-04-01\nvalue = "0.00002"',
    ]),
    "charges.sebi": table([], ['from = 2010-04-01\nvalue = "0.000001"']),
    "charges.ipft": table(["exchange", "segment"], [
        'exchange = "NSE"\nsegment = "delivery"\nfrom = 2010-04-01\nvalue = "0"',
        'exchange = "NSE"\nsegment = "futures"\nfrom = 2010-04-01\nvalue = "0"',
    ]),
    "charges.clearing": table(["segment"], [
        'segment = "delivery"\nfrom = 2010-04-01\nvalue = "0"',
        'segment = "futures"\nfrom = 2010-04-01\nvalue = "0"',
    ]),
    "charges.stamp": table(["segment", "side"], [
        'segment = "delivery"\nside = "buy"\nfrom = 2010-04-01\nvalue = "0.00015"',
        'segment = "delivery"\nside = "sell"\nfrom = 2010-04-01\nvalue = "0"',
        'segment = "futures"\nside = "buy"\nfrom = 2010-04-01\nvalue = "0.00002"',
        'segment = "futures"\nside = "sell"\nfrom = 2010-04-01\nvalue = "0"',
        'segment = "mf"\nside = "buy"\nfrom = 2010-04-01\nvalue = "0.00005"',
        'segment = "mf"\nside = "sell"\nfrom = 2010-04-01\nvalue = "0"',
    ]),
    "charges.gst": table([], [f'from = 2010-04-01\nvalue = "0.18"\napplies_to = {GST_ALL}']),
    # Fyers' own DP fee: Rs 13 per sale until the end of 2020, then Rs 9 per ISIN per day.
    "fyers.dp": table([], [
        'from = 2010-04-01\nto = 2020-12-31\nvalue = "13"\nbasis = "per_sale"',
        'from = 2021-01-01\nvalue = "9"\nbasis = "per_isin_per_day"',
    ]),
    "charges.dp_depository": table([], ['from = 2010-04-01\nvalue = "3.5"']),
    # The AMC group follows the day the account was opened; only the standard group pays.
    "fyers.amc_cohort": table([], [
        'from = 2010-04-01\nto = 2020-03-31\ncohort = "legacy"',
        'from = 2020-04-01\ncohort = "standard"',
    ]),
    "fyers.amc": table(["cohort"], [
        'cohort = "legacy"\nfrom = 2010-04-01\nvalue = "0"',
        'cohort = "standard"\nfrom = 2020-04-01\nvalue = "300"',
    ], extra_meta='late_keys = [{ cohort = "standard", from = 2020-04-01 }]'),
    "fyers.account_opening": table([], [
        'from = 2010-04-01\nto = 2020-03-31\nvalue = "0"',
        'from = 2020-04-01\nvalue = "400"',
    ]),
}
