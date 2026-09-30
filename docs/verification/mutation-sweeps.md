# Rule-table mutation sweeps

A check that every number, date and label in `rules/` is pinned by a test. In a throw-away copy of HEAD each field is changed one at a
time (a number, an integer, a date on its own, a boundary between two rows moved a day either way, a flag, a mode, an order, a
treatment, a bucket, a section label, a list item, the grandfathering date), the golden, gate and real-rule tests run, and then the
full suite. A change no test notices is a rule nobody checks.

Run after any change to `rules/` (about 10 minutes with 6 workers; the repository is not touched):

    python docs/verification/mutate_rules.py 6     # numbers, integers, dates, boundaries
    python docs/verification/mutate_rules2.py 6    # flags, modes, orders, labels, list items, test_excludes

Results (2026-09-30):

- Round 1, before the review fixes: 1,436 changes, 62 survived. 60 were the first row of a key starting a day before 2010-04-01
  (the loader now requires the exact start) and 2 were the end of the 1981 cost inflation index series moving a day (two golden cases
  now pin the 2017-03-31 / 2017-04-01 switch).
- Round 2, after all fixes (192 rows: 126 primary, 29 secondary, 37 assumed): 1,266 number, date and boundary changes and 245 flag,
  label and list changes; every one is caught by a test.
