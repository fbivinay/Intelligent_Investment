from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

from engine.charges import Order, dp_charge, order_charges
from engine.rules import Rules
from research import replay as RP, sim
from research.panel import ASSETS, Panel

RULES = Rules.load(Path(__file__).resolve().parents[1] / "rules")


def weekdays(start, n):
    d, out = start, []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def world(n=600, start=date(2018, 4, 2), seed=3):
    days = weekdays(start, n)
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.012, (n, 4)), axis=0))
    nan = np.full(n, np.nan)
    return days, Panel(dates=np.array(days, dtype="datetime64[D]"), assets=list(ASSETS), open=close, high=close * 1.01, low=close * 0.99, close=close, value=np.full((n, 4), 3e8),
                       vwap=close * 1.001, cash=1.0002 ** np.arange(n), nifty=close[:, 0], vix=nan, pe=nan, pb=nan)


def weights(n, seed=4):
    rng = np.random.default_rng(seed)
    w = rng.dirichlet(np.ones(5), n // 40 + 1).repeat(40, axis=0)[:n]
    return w


def test_the_order_log_lists_every_order_with_its_day_side_units_fill_price_and_charges_and_adds_up_to_the_daily_totals():
    days, p = world()
    r = sim.simulate(p, weights(600), RULES, sim.SimConfig(harvest=True))
    log = r.order_log
    assert log.shape == (r.orders, 6) and r.orders > 20
    t = log[:, 0].astype(int)
    assert np.allclose(np.bincount(t, weights=log[:, 5], minlength=600), r.charges) and np.allclose(np.bincount(t, weights=log[:, 3] * log[:, 4], minlength=600), r.traded)
    assert set(np.unique(log[:, 2])) == {0.0, 1.0} and (log[:, 3] > 0).all() and (np.mod(log[log[:, 1] < 4, 3], 1) == 0).all()      # ETFs in whole units


def test_the_exact_charges_are_the_engines_own_for_each_order_plus_the_depository_charge_on_an_etf_sale():
    days, p = world()
    r = sim.simulate(p, weights(600), RULES, sim.SimConfig())
    exact = RP.exact_charges(RULES, days, r.order_log)
    for k in (0, 5, len(exact) - 1):
        t, a, side, u, price = int(r.order_log[k, 0]), int(r.order_log[k, 1]), int(r.order_log[k, 2]), r.order_log[k, 3], r.order_log[k, 4]
        cls = sim.ASSET_CLASS[a]
        want = order_charges(RULES, Order(days[t], cls, "sell" if side else "buy", Decimal(repr(float(u))), Decimal(repr(float(price))))).total.value
        want = float(want) + (float(dp_charge(RULES, days[t]).value) if side and cls != "mf_debt" else 0.0)
        assert exact[k] == pytest.approx(want, abs=1e-9)


def test_the_check_reports_the_gap_between_the_simulators_charges_and_the_engines_and_it_is_small():
    days, p = world()
    r = sim.simulate(p, weights(600), RULES, sim.SimConfig(harvest=True))
    c = RP.check(r, RULES, days)
    exact = RP.exact_charges(RULES, days, r.order_log)
    assert c["orders"] == r.orders and c["sim_charges"] == pytest.approx(r.order_log[:, 5].sum()) and c["exact_charges"] == pytest.approx(exact.sum())
    assert c["max_order_gap"] == pytest.approx(np.abs(r.order_log[:, 5] - exact).max())
    assert c["max_order_gap"] <= max(1.0, 0.005 * exact.max()) and abs(c["total_gap"]) / r.equity[-1] < 1e-4
    assert c["wealth_gap_share"] == pytest.approx(c["total_gap"] / r.equity[-1])


def test_an_empty_order_log_has_no_gap():
    days, p = world(n=50)
    r = sim.simulate(p, np.tile([0, 0, 0, 0, 1.0], (50, 1)), RULES, sim.SimConfig())
    c = RP.check(r, RULES, days)
    assert c["orders"] == r.orders and c["total_gap"] == pytest.approx(0.0, abs=1e-6)
