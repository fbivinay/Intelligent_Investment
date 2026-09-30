from datetime import date
from decimal import Decimal as Dc

import pytest

from engine.lots import Inventory
from engine.trace import assert_balanced, const


def inv_with_two_lots():
    inv = Inventory()
    inv.buy("X", date(2020, 1, 1), Dc("10"), const("cost1", "1000"))
    inv.buy("X", date(2021, 1, 1), Dc("10"), const("cost2", "3000"))
    return inv


def test_fifo_takes_oldest_first_and_splits_cost_exactly():
    inv = inv_with_two_lots()
    first = inv.sell("X", Dc("4"))
    assert [(s.acq_date, s.qty, s.cost.value) for s in first] == [(date(2020, 1, 1), Dc("4"), Dc("400"))]
    second = inv.sell("X", Dc("8"))   # 6 left of lot 1, then 2 of lot 2
    assert [(s.acq_date, s.qty) for s in second] == [(date(2020, 1, 1), Dc("6")), (date(2021, 1, 1), Dc("2"))]
    assert [s.cost.value for s in second] == [Dc("600"), Dc("600")]
    assert inv.units("X") == Dc("8")
    for s in first + second:
        assert_balanced(s.cost)


def test_cost_of_sold_plus_kept_equals_original_even_when_not_divisible():
    inv = Inventory()
    inv.buy("X", date(2020, 1, 1), Dc("3"), const("cost", "100"))
    sold = inv.sell("X", Dc("1"))[0].cost.value
    kept = inv.sell("X", Dc("2"))[0].cost.value
    assert sold + kept == Dc("100")


def test_cannot_sell_more_than_held_or_zero():
    inv = inv_with_two_lots()
    with pytest.raises(ValueError, match="only 20"):
        inv.sell("X", Dc("21"))
    with pytest.raises(ValueError):
        inv.sell("X", Dc("0"))
    with pytest.raises(ValueError):
        Inventory().sell("nothing", Dc("1"))


def test_split_multiplies_units_and_keeps_cost_and_dates():
    inv = inv_with_two_lots()
    inv.split("X", Dc("2"))
    s = inv.sell("X", Dc("20"))[0]
    assert (s.acq_date, s.qty, s.cost.value) == (date(2020, 1, 1), Dc("20"), Dc("1000"))


def test_fractional_fund_units_split_cost_without_losing_a_paisa():
    inv = Inventory()
    inv.buy("F", date(2020, 1, 1), Dc("12.345"), const("cost1", "5000.00"))
    inv.buy("F", date(2020, 6, 1), Dc("7.655"), const("cost2", "3500.50"))
    a = inv.sell("F", Dc("0.001"))
    b = inv.sell("F", Dc("19.999"))
    assert sum((s.qty for s in a + b), Dc(0)) == Dc("20") and inv.units("F") == 0
    assert sum((s.cost.value for s in a + b), Dc(0)) == Dc("8500.50")


@pytest.mark.parametrize("instrument, ratio", [("nothing", "2"), ("X", "0"), ("X", "-2")])
def test_a_split_of_something_not_held_or_by_a_bad_ratio_is_refused(instrument, ratio):
    inv = inv_with_two_lots()
    with pytest.raises(ValueError):
        inv.split(instrument, Dc(ratio))
