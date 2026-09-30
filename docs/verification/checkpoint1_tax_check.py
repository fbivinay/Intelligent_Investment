"""Hand check of the sale-year tax in checkpoint 1, worked with plain Decimal arithmetic and no engine tax code.

The engine's own figures are printed beside it. Run from the repo root:
    python docs/verification/checkpoint1_tax_check.py
"""
import sys
from datetime import date
from decimal import ROUND_HALF_UP, Decimal as D
from pathlib import Path

sys.path.insert(0, ".")
from data.fetch_yahoo import load_bars, load_dividends  # noqa: E402
from engine.charges import Order, dp_charge, order_charges  # noqa: E402
from engine.rules import Rules  # noqa: E402
from engine.scenario import buy_and_hold  # noqa: E402
from engine.tax import TaxProfile  # noqa: E402

rules = Rules.load(Path("rules"))
bars = load_bars(Path("data/processed/NIFTYBEES.csv"))
divs = load_dividends(Path("data/processed/NIFTYBEES_dividends.csv"))
START, END, AMOUNT, INCOME = date(2014, 1, 1), date(2026, 9, 28), D("100000"), D("1500000")

r = buy_and_hold(rules, instrument="NIFTYBEES", instrument_class="etf_equity", bars=bars, dividends=divs, amount=AMOUNT,
                 start=START, end=END, profile=TaxProfile("new", INCOME))
buy = next(b for b in bars if b.on >= START)
sell = [b for b in bars if b.on <= END][-1]
ref = [b for b in bars if b.on <= date(2018, 1, 31)][-1]
q = D(r.units)


def rupees(x):
    return f"{x:,.2f}"


# cost of acquisition: the price paid plus the buy charges that a gain may deduct (everything except STT)
bc = order_charges(rules, Order(buy.on, "etf_equity", "buy", q, buy.close))
cost = q * buy.close + sum(v.value for k, v in bc.lines.items() if k != "stt")
# value of the units on 31 Jan 2018: the highest price quoted that day (section 55(2)(ac)), which floors the cost
fmv = q * ref.high
sale_value = q * sell.close
sc = order_charges(rules, Order(sell.on, "etf_equity", "sell", q, sell.close))
sale_costs = sum(v.value for k, v in sc.lines.items() if k != "stt") + dp_charge(rules, sell.on).value
floor = max(cost, min(fmv, sale_value))
gain = sale_value - sale_costs - floor
exemption = D("125000")
taxable = max(gain - exemption, D(0))
ltcg_tax = taxable * D("0.125")

# tax year 2026-27, new regime: slabs 4 lakh nil, 5% to 8, 10% to 12, 15% to 16, 20% to 20, 25% to 24, 30% above
slabs = [(D("400000"), D("0")), (D("800000"), D("0.05")), (D("1200000"), D("0.10")), (D("1600000"), D("0.15")),
         (D("2000000"), D("0.20")), (D("2400000"), D("0.25")), (None, D("0.30"))]


def slab_tax(income):
    tax, lower = D(0), D(0)
    for upto, rate in slabs:
        top = income if upto is None else min(income, upto)
        tax += max(top - lower, D(0)) * rate
        lower = upto if upto is not None else lower
    return tax


def tenth(x):
    return (x / 10).quantize(D(1), rounding=ROUND_HALF_UP) * 10


without = tenth(slab_tax(INCOME) * D("1.04"))
with_ = tenth((slab_tax(INCOME) + ltcg_tax) * D("1.04"))  # income 15 lakh + gain is well under the Rs 50 lakh surcharge line
print(f"bought {q} units on {buy.on} at {buy.close}; sold on {sell.on} at {sell.close}")
print(f"cost of acquisition (price + buy charges without STT)   {rupees(cost)}")
print(f"value on 31 Jan 2018 (highest price {ref.high} on {ref.on})   {rupees(fmv)}")
print(f"sale value                                              {rupees(sale_value)}")
print(f"sale costs without STT (incl. DP fee)                   {rupees(sale_costs)}")
print(f"cost used: higher of cost and lower of value and sale   {rupees(floor)}")
print(f"long-term gain                                          {rupees(gain)}")
print(f"after the Rs 1,25,000 exemption                          {rupees(taxable)}")
print(f"tax at 12.5%                                            {rupees(ltcg_tax)}")
print(f"slab tax on Rs 15 lakh, new regime                      {rupees(slab_tax(INCOME))}")
print(f"tax with the sale x 1.04 cess, to Rs 10                 {rupees(with_)}")
print(f"tax without the sale x 1.04 cess, to Rs 10              {rupees(without)}")
print(f"tax caused by the sale (by hand)                        {rupees(with_ - without)}")
print(f"tax caused by the sale (engine)                         {rupees(r.waterfall['tax'].value)}")
