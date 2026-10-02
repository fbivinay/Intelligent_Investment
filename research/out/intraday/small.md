# Small-account books, whole lots

## low: Rs 100,000, worst fall limit 5%

No book trades on half the training days within 4%: the account cannot hold its lots at that risk.

## medium: Rs 300,000, worst fall limit 12%

| Strategy | Size |
|---|---|
| NIFTY:theta|strangle2|entry=15|legsl=0.25|tgt=None|sl=None|days=nonexpiry|vix=(-3.0, 3.0) | 0.5 |
| BANKNIFTY:theta|strangle2|entry=5|legsl=0.25|tgt=None|sl=None|days=dte2|vix=(-3.0, 3.0) | 0.2 |
| NIFTY:theta|strangle2|entry=105|legsl=None|tgt=None|sl=None|days=all|vix=(-3.0, 3.0) | 0.1 |
| NIFTY:theta|strangle2|entry=105|legsl=None|tgt=None|sl=None|days=expiry|vix=None | 0.1 |
| NIFTY:theta|strangle2|entry=105|legsl=None|tgt=0.5|sl=1.0|days=expiry|vix=None | 0.1 |

| Window | Growth a year after tax | Worst fall |
|---|---|---|
| training 2016-2021 | 35.7% | 9.5% |
| test 2022-2026 | 10.0% | 6.5% |
| whole period (one account) | 44.1% | 15.9% |
