# A book of intraday strategies at a 5% worst fall

Picked on 2016-01 to 2021-12 (training), run unchanged on 2022-01 to 2026-05 (test). Common scale 1.21.

| Strategy |
|---|
| theta|strangle2|entry=15|legsl=0.25|tgt=0.5|sl=1.0|days=nonexpiry|vix=(-3.0, 3.0) |
| theta|strangle3|entry=15|legsl=0.25|tgt=None|sl=None|days=nonexpiry|vix=None |
| dir|debit_spread|signal=orb_reversal|tgt=None|sl=None|days=all |
| theta|butterfly4|entry=5|legsl=0.4|tgt=0.5|sl=1.0|days=nonexpiry|vix=(-3.0, 3.0) |
| dir|buy_atm|signal=rsi_momentum|tgt=None|sl=None|days=all |
| theta|strangle2|entry=105|legsl=0.5|tgt=0.5|sl=1.0|days=nonexpiry|vix=(-3.0, 3.0) |
| theta|strangle3|entry=5|legsl=0.5|tgt=None|sl=None|days=nonexpiry|vix=(-3.0, 3.0) |
| theta|straddle|entry=105|legsl=0.5|tgt=0.5|sl=1.0|days=expiry|vix=(-3.0, 3.0) |
| dir|debit_spread|signal=sma20_cross|tgt=None|sl=None|days=all |
| theta|straddle|entry=15|legsl=0.25|tgt=None|sl=None|days=nonexpiry|vix=(-3.0, 3.0) |

| Window | Growth a year after tax | Worst fall |
|---|---|---|
| training | 16.6% | 5.0% |
| test | 16.6% | 4.9% |
