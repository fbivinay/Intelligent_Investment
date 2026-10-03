from datetime import date
from decimal import Decimal

from engine.lots import Inventory
from engine.trace import const


def test_selling_everything_survives_rounding_dust():
    # The total of the lots rounds up at 28 digits, so taking them one by one leaves dust that is in no lot (Max level, Rs 25 lakh, crashed here).
    inv = Inventory()
    inv.buy("X", date(2020, 1, 1), Decimal(1000000), const("c", Decimal(1)))
    inv.buy("X", date(2020, 1, 2), Decimal("0.5555555555555555555555555555"), const("c", Decimal(1)))
    out = inv.sell("X", inv.units("X"))
    assert len(out) == 2 and inv.units("X") == 0
