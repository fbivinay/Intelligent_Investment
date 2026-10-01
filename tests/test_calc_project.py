from decimal import Decimal

import numpy as np
import pytest

from calc import project as PJ
from engine.tax import TaxProfile

PROFILE = TaxProfile("new", Decimal(1500000))


def test_a_history_with_one_constant_return_grows_every_path_the_same():
    paths = PJ.bootstrap(np.full(500, 0.001), days=252, paths=200, seed=1)
    assert paths.shape == (200, 2) and np.allclose(paths[:, -1], 1.001 ** 252) and np.allclose(paths[:, 0], 1.0)


def test_the_bootstrap_is_reproducible_and_samples_the_history():
    rng = np.random.default_rng(3)
    r = rng.normal(0.0004, 0.01, 2000)
    a, b = PJ.bootstrap(r, 504, 300, seed=7), PJ.bootstrap(r, 504, 300, seed=7)
    assert np.array_equal(a, b) and not np.array_equal(a, PJ.bootstrap(r, 504, 300, seed=8))
    growth = np.log(a[:, -1]).mean() / 504
    assert growth == pytest.approx(np.log1p(r).mean(), abs=0.0004)
    assert PJ.bootstrap(r, 504, 300, seed=7, checkpoints=4).shape == (300, 5)


def test_the_tax_curve_is_the_engines_tax_of_one_sale_at_each_grid_point_and_zero_on_a_loss():
    curve = PJ.tax_curve(Decimal(1000000), {"etf_equity": 1.0}, years=5, profile=PROFILE)
    m = np.array([0.8, 1.0, 1.5])
    tax = curve(m)
    assert tax[0] == 0 and tax[1] == 0 and tax[2] == pytest.approx((500000 - 125000) * 0.125 * 1.04, abs=5.0)          # interpolated between grid points
    mixed = PJ.tax_curve(Decimal(1000000), {"etf_equity": 0.5, "mf_debt": 0.5}, years=5, profile=PROFILE)
    assert mixed(np.array([1.5]))[0] > curve(np.array([1.5]))[0] * 0.5                           # the fund half is taxed at the slab


def test_a_projection_orders_its_percentiles_and_never_taxes_more_than_the_gain():
    rng = np.random.default_rng(4)
    p = PJ.project(rng.normal(0.0005, 0.01, 3000), Decimal(1000000), {"etf_equity": 1.0}, years=5, profile=PROFILE, seed=2)
    assert p["p10"] <= p["p50"] <= p["p90"] and p["after_tax"]["p10"] <= p["after_tax"]["p50"] <= p["after_tax"]["p90"]
    assert p["after_tax"]["p50"] <= p["p50"] and 0 <= p["chance_of_loss"] <= 1 and len(p["fan"]) == 6 and p["fan"][0]["p50"] == pytest.approx(1000000)
    assert p["years"] == 5 and p["paths"] == PJ.PATHS and "ESTIMATE" in p["label"]


def test_a_flat_history_projects_no_gain_no_tax_and_no_chance_of_loss():
    p = PJ.project(np.zeros(1000), Decimal(500000), {"mf_debt": 1.0}, years=3, profile=PROFILE, seed=1)
    assert p["p10"] == p["p90"] == pytest.approx(500000) and p["after_tax"]["p50"] == pytest.approx(500000) and p["chance_of_loss"] == 0


def test_the_horizon_is_limited():
    with pytest.raises(ValueError, match="1 to 20"):
        PJ.project(np.zeros(100), Decimal(1000), {"etf_equity": 1.0}, years=25, profile=PROFILE)
