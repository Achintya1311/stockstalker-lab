# b1-trend-cross-trail-day: train results

`strategies.b1_trend_cross`, day horizon, train split. `top` = the 5 picks a table would publish each date; `all` = every positive or negative score. Edge and market line in points; definitions in SPEC.md section 3.

## top / bullish

887 picks on 550 dates (coverage 100.00%). Accuracy 43.97% vs market line 44.53%: edge -0.57 (t -0.32). Directional move after costs -0.52. Positive years 50.00%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2015 | 20 | 40.00% | -13.48 |
| 2016 | 110 | 45.45% | 2.45 |
| 2017 | 235 | 40.00% | -5.88 |
| 2018 | 202 | 42.57% | -1.13 |
| 2019 | 180 | 45.56% | 4.83 |
| 2020 | 140 | 50.00% | 0.38 |

## top / bearish

No in-universe picks.

## all / bullish

908 picks on 550 dates (coverage 100.00%). Accuracy 43.50% vs market line 44.53%: edge -0.64 (t -0.36). Directional move after costs -0.55. Positive years 50.00%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2015 | 20 | 40.00% | -13.48 |
| 2016 | 110 | 45.45% | 2.45 |
| 2017 | 245 | 39.18% | -6.13 |
| 2018 | 206 | 42.23% | -1.15 |
| 2019 | 183 | 45.36% | 4.81 |
| 2020 | 144 | 49.31% | 0.36 |

## all / bearish

No in-universe picks.

## Exit plan payoff (train-only observation)

Exit plan parameters: trail: stop 3 ATR from the best close (1R = 3 ATR), time exit after 20 sessions. Selection: `top`. Entry convention: the pick date's open; R = stop_atr x ATR(14) known before the pick date. Outcomes in R multiples and percent, net of the engine cost model (SPEC.md section 3): bullish = delivery round trip 0.415%, bearish = futures round trip 0.250%, charged once per pick. Baseline: the same exit plan applied to every universe stock on the same dates; the headline is average R above that baseline. Not a gate and not a roster input: SPEC.md has no payoff wording yet (`state/engine-issues.md`).

| Plan | Side | Picks | Right | Avg R | Median R | Profit factor | Avg % | Avg hold | Stop | Target | Time | Worst losing run | Baseline avg R | Avg R above baseline | t | 95% interval |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| exit plan | bullish | 878 | 45.2% | -0.007 | -0.139 | 0.98 | -0.13% | 16.3 | 43% | 0% | 57% | 16 | -0.041 | 0.035 | 1.14 | -0.034 to 0.107 |
| time-only control | bullish | 878 | 49.9% | -0.007 | -0.008 | 0.98 | -0.07% | 20.0 | 0% | 0% | 100% | 16 | -0.049 | 0.029 | 0.89 | -0.045 to 0.105 |

### bullish: by year (exit plan)

| Year | Picks | Right | Avg R | Avg R above baseline |
|---|---|---|---|---|
| 2015 | 20 | 40.0% | -0.109 | 0.167 |
| 2016 | 110 | 40.9% | -0.185 | -0.111 |
| 2017 | 235 | 47.7% | 0.053 | 0.055 |
| 2018 | 202 | 41.1% | -0.162 | 0.100 |
| 2019 | 180 | 40.6% | -0.091 | 0.045 |
| 2020 | 131 | 58.0% | 0.405 | 0.011 |

Dropped (window past the split end or no ATR yet): 9. Intervals: holds overlap across pick dates, so dates are not independent. t = mean / standard error of the means of non-overlapping blocks of 20 consecutive pick dates; 95% interval = moving-block bootstrap, block length 20 pick dates, 2000 resamples, seed 0, percentile method.
