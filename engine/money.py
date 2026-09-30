"""Exact money maths. Floats are refused; rounding is always an explicit step."""
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal

ZERO = Decimal(0)


def D(x) -> Decimal:
    if isinstance(x, float):
        raise TypeError(f"float {x!r} refused: pass a str, int or Decimal")
    return x if isinstance(x, Decimal) else Decimal(x)


def round_step(x: Decimal, step: Decimal, floor: bool = False) -> Decimal:
    """Round x to a multiple of step: 0.01 paise, 1 rupee, 10 statutory tax rounding."""
    mode = ROUND_FLOOR if floor else ROUND_HALF_UP
    return (x / step).quantize(Decimal(1), rounding=mode) * step
