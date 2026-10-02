# A book of intraday strategies at a 5% worst fall

Picked on 2016-01 to 2021-12 (training), run unchanged on 2022-01 to 2026-05 (test). Common scale 1.01.

| Strategy |
|---|
| theta|strangle2|entry=15|legsl=0.25|tgt=0.5|sl=1.0|days=nonexpiry|vix=(-3.0, 3.0) |
| theta|strangle3|entry=15|legsl=0.25|tgt=None|sl=None|days=nonexpiry|vix=None |
| dir|debit_spread|signal=orb_reversal|tgt=None|sl=None|days=all |

| Window | Growth a year after tax | Worst fall |
|---|---|---|
| training | 15.1% | 5.0% |
| test | 11.4% | 3.7% |
