from datetime import date

from engine.tax import CGEvent
from engine.trace import const


def ev(acq, sale, cost, proceeds, cls="etf_equity", sale_costs="0", fmv=None, label="X"):
    """A capital-gains sale built from ISO dates and plain numbers."""
    return CGEvent(label, date.fromisoformat(sale), cls, date.fromisoformat(acq),
                   const("Proceeds", proceeds), const("Sale costs", sale_costs), const("Cost", cost),
                   const("Value on 31 Jan 2018", fmv) if fmv else None)
