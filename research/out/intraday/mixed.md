# Low level with Nifty and Bank Nifty strategies

| Index | Strategy |
|---|---|
| NIFTY | theta|strangle2|entry=15|legsl=0.25|tgt=0.5|sl=1.0|days=nonexpiry|vix=(-3.0, 3.0) |
| BANKNIFTY | theta|strangle2|entry=15|legsl=0.4|tgt=0.5|sl=1.0|days=nonexpiry|vix=(-3.0, 3.0) |
| NIFTY | theta|strangle3|entry=15|legsl=0.25|tgt=None|sl=None|days=nonexpiry|vix=None |
| BANKNIFTY | longvol|long_strangle2|signal=orb|tgt=0.3|sl=0.3|days=expiry |
| BANKNIFTY | theta|strangle3|entry=105|legsl=0.5|tgt=None|sl=None|days=nonexpiry|vix=(-3.0, 3.0) |
| NIFTY | dir|debit_spread|signal=orb_reversal|tgt=None|sl=None|days=all |
| NIFTY | theta|butterfly4|entry=5|legsl=0.4|tgt=0.5|sl=1.0|days=nonexpiry|vix=(-3.0, 3.0) |
| NIFTY | dir|buy_atm|signal=rsi_momentum|tgt=None|sl=None|days=all |

## Rs 50 lakh

Test: before tax and charges 19.8%; before tax 18.2%, market fall 0.6%. Training before tax 20.0%.

| Regime | Other income | After tax a year | Worst fall (tax paid included) |
|---|---|---|---|
| new | Rs 0 lakh | 16.8% | 1.2% |
| new | Rs 12 lakh | 12.7% | 2.7% |
| new | Rs 25 lakh | 12.3% | 2.8% |
| new | Rs 60 lakh | 11.8% | 3.1% |
| new | Rs 150 lakh | 11.3% | 3.3% |
| old | Rs 0 lakh | 15.5% | 1.7% |
| old | Rs 12 lakh | 12.3% | 2.8% |
| old | Rs 25 lakh | 12.3% | 2.8% |
| old | Rs 60 lakh | 11.8% | 3.1% |
| old | Rs 150 lakh | 11.3% | 3.3% |

## Rs 10 lakh

Test: before tax and charges 10.8%; before tax 10.4%, market fall 0.3%. Training before tax 9.7%.

| Regime | Other income | After tax a year | Worst fall (tax paid included) |
|---|---|---|---|
| new | Rs 0 lakh | 10.4% | 0.3% |
| new | Rs 12 lakh | 6.9% | 2.4% |
| new | Rs 25 lakh | 7.1% | 1.9% |
| new | Rs 60 lakh | 6.8% | 2.1% |
| new | Rs 150 lakh | 6.6% | 2.2% |
| old | Rs 0 lakh | 10.4% | 0.3% |
| old | Rs 12 lakh | 7.1% | 1.9% |
| old | Rs 25 lakh | 7.1% | 1.9% |
| old | Rs 60 lakh | 6.8% | 2.1% |
| old | Rs 150 lakh | 6.6% | 2.2% |

