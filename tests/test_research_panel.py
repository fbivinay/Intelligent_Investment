import csv
from datetime import date, timedelta

import numpy as np
import pytest

from research import panel as pn

ETF_COLS = ["date", "symbol", "series", "adj_open", "adj_high", "adj_low", "adj_close", "value", "adj_qty"]
NAV_COLS = ["date", "code", "adj_nav"]
IDX_COLS = ["date", "name", "close", "pe", "pb", "div_yield"]


def write(path, cols, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f, lineterminator=chr(10))
        w.writerow(cols)
        w.writerows(rows)


def days(start, n):
    d, out = start, []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def make_root(tmp_path, n=6, start=date(2012, 12, 26), skip=None, etf_price=lambda sym, i: 100 + i):
    """A tiny data folder: the four ETFs on n trading days, a regular and a direct liquid fund, Nifty 50 and India VIX."""
    ds = days(start, n)
    etf = []
    for sym in pn.ASSETS:
        for i, d in enumerate(ds):
            if skip == (sym, d):
                continue
            p = etf_price(sym, i)
            etf.append([d.isoformat(), sym, "EQ", p, p + 1, p - 1, p + 0.5, 1_000_000 + i, round((1_000_000 + i) / (p + 0.25))])
    write(tmp_path / "processed" / "etf_daily_adjusted.csv", ETF_COLS, etf)
    nav = []
    c = start - timedelta(days=3)
    v_reg, v_dir = 100.0, 50.0
    while c <= start + timedelta(days=12):
        nav.append([c.isoformat(), pn.LIQUID_REGULAR, round(v_reg, 6)])
        if c >= date(2013, 1, 1):
            nav.append([c.isoformat(), pn.LIQUID_DIRECT, round(v_dir, 6)])
        v_reg *= 1.001
        v_dir *= 1.002
        c += timedelta(days=1)
    write(tmp_path / "processed" / "amfi_nav_adjusted.csv", NAV_COLS, nav)
    idx = []
    for i, d in enumerate(ds):
        idx.append([d.isoformat(), "Nifty 50", 5000 + i, "20.5" if i > 2 else "", "3.1" if i > 2 else "", ""])
        idx.append([d.isoformat(), "India VIX", 15 + i * 0.1, "", "", ""])
    write(tmp_path / "processed" / "nse_index_daily.csv", IDX_COLS, idx)
    return tmp_path, ds


def test_panel_holds_the_trading_days_every_etf_has_and_arrays_line_up(tmp_path):
    root, ds = make_root(tmp_path)
    p = pn.load_panel(root, end="2030-01-01")
    assert [str(x) for x in p.dates] == [d.isoformat() for d in ds]
    assert p.assets == pn.ASSETS and p.open.shape == (6, 4) and p.close.shape == (6, 4) and p.value.shape == (6, 4) and p.vwap.shape == (6, 4)
    assert p.close[0, 0] == 100.5 and p.open[1, 2] == 101 and p.high[0, 1] == 101 and p.low[0, 3] == 99
    assert p.cash.shape == (6,) and p.nifty.shape == (6,) and p.vix.shape == (6,)
    assert p.nifty[2] == 5002 and np.isnan(p.pe[0]) and p.pe[3] == 20.5 and p.vix[1] == pytest.approx(15.1)


def test_end_cuts_every_array(tmp_path):
    root, ds = make_root(tmp_path)
    p = pn.load_panel(root, end=ds[2].isoformat())
    assert len(p.dates) == 3 and p.open.shape[0] == 3 and p.cash.shape[0] == 3 and p.nifty.shape[0] == 3 and p.pe.shape[0] == 3


def test_a_day_an_etf_lacks_while_the_others_have_it_is_refused_and_named(tmp_path):
    ds = days(date(2012, 12, 26), 6)
    root, _ = make_root(tmp_path, skip=("GOLDBEES", ds[3]))
    with pytest.raises(ValueError, match="GOLDBEES.*" + ds[3].isoformat()):
        pn.load_panel(root, end="2030-01-01")


def test_cash_takes_the_regular_plan_to_the_splice_and_the_direct_plan_after_on_daily_returns(tmp_path):
    root, ds = make_root(tmp_path)        # trading days 2012-12-26 .. 2013-01-02; regular grows 0.1% a calendar day, direct 0.2%; splice on 2013-01-01
    p = pn.load_panel(root, end="2030-01-01")
    assert p.cash[0] == pytest.approx(1.0)
    by = {str(d): c for d, c in zip(p.dates, p.cash)}
    assert by["2012-12-31"] / by["2012-12-26"] == pytest.approx(1.001 ** 5, rel=1e-6)              # five calendar days on the regular plan
    assert by["2013-01-01"] / by["2012-12-31"] == pytest.approx(1.001, rel=1e-6)                   # the splice day itself is still the regular plan
    assert by["2013-01-02"] / by["2013-01-01"] == pytest.approx(1.002, rel=1e-6)                   # the first day after it is the direct plan


def test_the_cash_series_is_continuous_across_a_unit_change_already_adjusted_in_the_nav_file(tmp_path):
    root, ds = make_root(tmp_path)
    p = pn.load_panel(root, end="2030-01-01")
    r = np.diff(p.cash) / p.cash[:-1]
    assert np.all(r > 0) and np.all(r < 0.01)       # no day is a jump


def test_cash_is_never_negative_or_missing_and_starts_at_one(tmp_path):
    root, _ = make_root(tmp_path)
    p = pn.load_panel(root, end="2030-01-01")
    assert np.all(np.isfinite(p.cash)) and np.all(p.cash > 0) and p.cash[0] == 1.0


def test_default_end_is_the_design_end_so_the_frozen_years_are_never_loaded():
    assert pn.DESIGN_END == "2023-09-30"
    import inspect
    assert inspect.signature(pn.load_panel).parameters["end"].default == pn.DESIGN_END


def test_a_nifty_or_vix_day_missing_is_nan_not_an_error(tmp_path):
    root, ds = make_root(tmp_path)
    rows = [r for r in csv.DictReader((root / "processed" / "nse_index_daily.csv").open(newline="")) if not (r["name"] == "India VIX" and r["date"] == ds[2].isoformat())]
    write(root / "processed" / "nse_index_daily.csv", IDX_COLS, [[r[c] for c in IDX_COLS] for r in rows])
    p = pn.load_panel(root, end="2030-01-01")
    assert np.isnan(p.vix[2]) and np.isfinite(p.vix[1])


def test_a_weekend_session_only_some_etfs_traded_is_left_out_and_recorded_not_an_error(tmp_path):
    # Gold ETFs traded on the Sundays of Akshaya Tritiya (2010-05-16) and Dhanteras (2012-11-11): the others were closed
    root, ds = make_root(tmp_path)
    rows = list(csv.DictReader((root / "processed" / "etf_daily_adjusted.csv").open(newline="")))
    rows.append({"date": "2012-12-30", "symbol": "GOLDBEES", "series": "EQ", "adj_open": "200", "adj_high": "201", "adj_low": "199", "adj_close": "200.5", "value": "5", "adj_qty": "1"})
    write(root / "processed" / "etf_daily_adjusted.csv", ETF_COLS, [[r[c] for c in ETF_COLS] for r in rows])
    p = pn.load_panel(root, end="2030-01-01")
    assert len(p.dates) == 6 and p.special_days == ("2012-12-30",)
    assert "2012-12-30" not in [str(d) for d in p.dates]


def test_vwap_is_traded_value_over_traded_quantity_on_the_adjusted_unit_size(tmp_path):
    root, ds = make_root(tmp_path)
    p = pn.load_panel(root, end="2030-01-01")
    assert p.vwap[0, 0] == pytest.approx(1_000_000 / round(1_000_000 / 100.25), rel=1e-9)
    assert np.all(p.vwap >= p.low * 0.99) and np.all(p.vwap <= p.high * 1.01)


def test_a_vwap_outside_the_days_range_means_the_quantity_is_on_another_unit_size_and_is_refused(tmp_path):
    root, ds = make_root(tmp_path)
    rows = list(csv.DictReader((root / "processed" / "etf_daily_adjusted.csv").open(newline="")))
    rows[3]["adj_qty"] = str(int(rows[3]["adj_qty"]) * 10)                          # e.g. a split applied to the price but not to the quantity
    write(root / "processed" / "etf_daily_adjusted.csv", ETF_COLS, [[r[c] for c in ETF_COLS] for r in rows])
    with pytest.raises(ValueError, match="VWAP"):
        pn.load_panel(root, end="2030-01-01")


def test_only_the_eq_series_is_read_and_a_row_after_the_end_is_ignored_in_every_file(tmp_path):
    root, ds = make_root(tmp_path)
    rows = list(csv.DictReader((root / "processed" / "etf_daily_adjusted.csv").open(newline="")))
    rows.append(dict(rows[0], series="BE", adj_close="999"))                        # another series of the same day: not read
    write(root / "processed" / "etf_daily_adjusted.csv", ETF_COLS, [[r[c] for c in ETF_COLS] for r in rows])
    idx = list(csv.DictReader((root / "processed" / "nse_index_daily.csv").open(newline="")))
    idx.append({"date": "2031-01-01", "name": "Nifty 50", "close": "1", "pe": "", "pb": "", "div_yield": ""})       # after the end: not read
    write(root / "processed" / "nse_index_daily.csv", IDX_COLS, [[r[c] for c in IDX_COLS] for r in idx])
    p = pn.load_panel(root, end="2030-01-01")
    assert p.close[0, 0] == 100.5 and len(p.dates) == 6 and len(p.nifty) == 6


def test_a_vwap_above_the_days_high_is_refused_too(tmp_path):
    root, ds = make_root(tmp_path)
    rows = list(csv.DictReader((root / "processed" / "etf_daily_adjusted.csv").open(newline="")))
    rows[3]["adj_qty"] = str(max(1, int(rows[3]["adj_qty"]) // 10))                 # the quantity ten times too small: VWAP ten times too high
    write(root / "processed" / "etf_daily_adjusted.csv", ETF_COLS, [[r[c] for c in ETF_COLS] for r in rows])
    with pytest.raises(ValueError, match="VWAP"):
        pn.load_panel(root, end="2030-01-01")
