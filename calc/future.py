"""Invest today: what one payment now, or the same payment every month, could be worth after a number of years if an option earns again what it
earned, after every charge and tax, over the years the calculator has. An ESTIMATE from history, never a forecast or a promise.

The value is linear in the payment, so the website multiplies the payment by a factor worked out here: (1 + r)^years for one payment, and for a
payment at the start of every month, each payment grown for the months it is invested at the monthly rate equal to r a year.
"""
from __future__ import annotations

LABEL = "ESTIMATE: each option's past yearly return after charges and tax, assumed to repeat; not a forecast or a promise"
HORIZONS = range(1, 31)


def lump(rate: float, years: float) -> float:
    """What 1 rupee paid today is worth after `years` at `rate` a year."""
    return (1.0 + rate) ** years


def monthly(rate: float, years: int) -> float:
    """What 1 rupee paid at the start of every month for `years` is worth at the end, each payment growing at `rate` a year for the months it stays."""
    n = 12 * years
    g = (1.0 + rate) ** (1.0 / 12.0)
    if abs(g - 1.0) < 1e-15:
        return float(n)
    return g * (g ** n - 1.0) / (g - 1.0)


def factors(rates: dict[str, float]) -> dict[str, dict[str, list[float]]]:
    """For each option, the one-payment and monthly factors for 1 to 30 years."""
    return {k: {"lump": [round(lump(r, y), 10) for y in HORIZONS], "sip": [round(monthly(r, y), 8) for y in HORIZONS]} for k, r in rates.items()}


if __name__ == "__main__":
    assert abs(lump(0.10, 2) - 1.21) < 1e-12
    assert abs(monthly(0.0, 3) - 36) < 1e-12
    g = 1.10 ** (1 / 12)
    assert abs(monthly(0.10, 1) - sum(g ** (12 - m) for m in range(12))) < 1e-9          # 12 payments, the first grows 12 months, the last 1
    print("future checks done")
