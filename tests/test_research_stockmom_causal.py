"""The Max level's stock picks use no future data (picks made on the data cut after a day equal the full run's picks up to that day) and are shares,
never exchange-traded fund units.

Needs data/processed/stocks_eq.parquet (python -m research.stocks_build; not in git); skipped without it.
"""
from pathlib import Path

import pandas as pd
import pytest

from research import maxmodel as X, stockmom as M

PARQUET = Path(__file__).resolve().parents[1] / "data" / "processed" / "stocks_eq.parquet"
pytestmark = pytest.mark.skipif(not PARQUET.exists(), reason="stocks_eq.parquet is not on this machine")


@pytest.fixture(scope="module")
def data():
    return M.wide()


def test_the_max_picks_on_data_cut_after_a_day_are_the_full_runs_picks_up_to_that_day(data):
    f, idx, traded = data
    full = M.picks(idx, f["value"], traded, 30, 500, trend=X.TREND)
    for cut in ("2018-12-31", "2020-04-30", "2024-07-01"):                 # a quarter's end, a market-switch month, a quarter's first day
        c = pd.Timestamp(cut)
        part = M.picks(idx.loc[:c], f["value"].loc[:c], traded.loc[:c], 30, 500, trend=X.TREND)
        assert part == {d: v for d, v in full.items() if d <= c}, cut


def test_the_max_picks_are_shares_never_fund_units(data):
    f, idx, traded = data
    picked = {s for v in M.picks(idx, f["value"], traded, 30, 500, trend=X.TREND).values() for s in v}
    assert len(picked) > 100 and not picked & M.funds()
    assert {"NIFTYBEES", "GOLDBEES", "LIQUIDBEES"} <= M.funds()            # the fund units are known, and the market switch still reads the Nifty ETF
