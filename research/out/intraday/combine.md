# A book of intraday strategies at a 5% worst fall

Picked on 2016-01 to 2021-12 (training), run unchanged on 2022-01 to 2026-05 (test). Common scale 1.04.

| Strategy |
|---|
| theta|strangle3|entry=105|legsl=None|tgt=None|sl=None|days=all|vix=None |
| theta|strangle2|entry=15|legsl=0.25|tgt=0.5|sl=1.0|days=nonexpiry|vix=(-3.0, 3.0) |
| theta|strangle3|entry=15|legsl=0.25|tgt=None|sl=None|days=nonexpiry|vix=None |

| Window | Growth a year after tax | Worst fall |
|---|---|---|
| training | 16.9% | 5.0% |
| test | 21.9% | 7.3% |
