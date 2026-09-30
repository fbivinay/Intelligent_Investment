"""FIFO lots. Cost is a trace node, so a sale's cost basis can be explained."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from engine.trace import Node, const, div, mul, sub


@dataclass(frozen=True)
class Lot:
    acq_date: date
    qty: Decimal
    cost: Node  # total cost of acquisition of `qty` units, buy-side deductible charges included


@dataclass(frozen=True)
class Slice:
    acq_date: date
    qty: Decimal
    cost: Node


class Inventory:
    def __init__(self):
        self._lots: dict[str, list[Lot]] = {}

    def units(self, instrument: str) -> Decimal:
        return sum((lot.qty for lot in self._lots.get(instrument, [])), Decimal(0))

    def buy(self, instrument: str, acq_date: date, qty: Decimal, cost: Node) -> None:
        if qty <= 0:
            raise ValueError("qty must be positive")
        self._lots.setdefault(instrument, []).append(Lot(acq_date, qty, cost))

    def sell(self, instrument: str, qty: Decimal) -> list[Slice]:
        """Take `qty` units oldest-first. Raises rather than going short."""
        if qty <= 0:
            raise ValueError("qty must be positive")
        held = self.units(instrument)
        if qty > held:
            raise ValueError(f"cannot sell {qty} {instrument}: only {held} held")
        lots, out, need = self._lots[instrument], [], qty
        while need > 0:
            lot = lots[0]
            if lot.qty <= need:
                out.append(Slice(lot.acq_date, lot.qty, lot.cost))
                need -= lot.qty
                lots.pop(0)
                continue
            share = div("Share of lot sold", const("Units sold", need), const("Units in lot", lot.qty))
            sold = mul(f"Cost of {need} units from the {lot.acq_date} lot", lot.cost, share)
            lots[0] = Lot(lot.acq_date, lot.qty - need, sub("Cost of units kept", lot.cost, sold))
            out.append(Slice(lot.acq_date, need, sold))
            need = Decimal(0)
        return out

    def split(self, instrument: str, ratio: Decimal) -> None:
        """A split: `ratio` new units per old unit; total cost and dates unchanged. Bonus units are new lots at zero cost via `buy`."""
        if ratio <= 0:
            raise ValueError("split ratio must be positive")
        if self.units(instrument) <= 0:
            raise ValueError(f"cannot split {instrument}: none held")
        self._lots[instrument] = [Lot(lot.acq_date, lot.qty * ratio, lot.cost) for lot in self._lots[instrument]]
