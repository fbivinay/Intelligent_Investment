# Notes written after the frozen run (2026-10-01)

Nothing in `report.md`, `record.json`, the selection logs or the signal files was changed after the run. These notes only read them.

## Pre-registered hypotheses

| Level | Primary: product beats S0 after selling all, drawdown within the cap | E1 beats S0 (secondary) | S6 beats E1 (secondary) |
|---|---|---|---|
| Conservative (10%) | No: the product held S0 every year (equal, +0.00) | not tested at this level | No: 10.0% against 10.9% |
| Balanced (20%) | Yes: +2.87 points a year (6.8% against 3.9%), drawdown 13.1% | Yes: 10.0% against 3.9% | No: 9.9% against 10.0% |
| Aggressive (30%) | Yes: +7.22 points a year (10.9% against 3.7%), drawdown 13.2% | Yes: 10.9% against 3.7% | No: 9.7% against 10.9% |

The deep model (S6) again earned less than its own equal-weight starting point, as in the design period: its out-of-sample moves away from equal weight lost money.

## Why the fund-heavy accounts lose about 3 points a year when everything is sold

The research tax profile (new regime, other income Rs 12 lakh, fixed in the spec before any result) sits exactly on the Rs 12 lakh rebate threshold of section 87A that
applies from FY 2025-26. A gain taxed at slab rates (the liquid fund, bought after 2023-03-31) takes total income above the threshold, so the whole rebate is lost:

| Other income | Extra tax on a Rs 2,25,000 liquid-fund gain sold on 2026-09-30 (engine) |
|---|---|
| Rs 10 lakh | Rs 26,000 (11.6%) |
| Rs 12 lakh | Rs 97,500 (43.3%) |
| Rs 15 lakh | Rs 41,600 (18.5%) |
| Rs 25 lakh | Rs 70,200 (31.2%) |

So the "after selling all" figures of the liquid fund held (4.0%), of plain holding at Conservative (4.0%) and, partly, of the other accounts that hold the fund are as
bad as they can be for this one profile. It is the law as the rule tables encode it, not a fault, and every account in a row faces the same profile; but a user at
another income level gets different numbers, which is why the site will replay the signal with the user's own tax profile.

## Context

One path: Gold BeES rose about 36% a year after tax over these three years, Junior BeES about 17%, Nifty BeES about 6.5%. Strategies that held gold (E1 a fifth,
E3 momentum rotation most of the time) gained from it. E3 (momentum rotation) was the weakest family in the design period and the strongest here; that is the kind of
reversal three years can show, and why the frozen years were never used to choose anything.
