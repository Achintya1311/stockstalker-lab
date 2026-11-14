# exit-a01-fixed-week: train results

`strategies.a01_weekly_reversal`, week horizon, train split. `top` = the 5 picks a table would publish each date; `all` = every positive or negative score. Edge and market line in points; definitions in SPEC.md section 3.

## top / bullish

1545 picks on 309 dates (coverage 100.00%). Accuracy 48.87% vs market line 48.89%: edge -0.03 (t -0.02). Directional move after costs -0.51. Positive years 50.00%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2015 | 240 | 50.83% | 0.95 |
| 2016 | 260 | 48.08% | -0.74 |
| 2017 | 260 | 48.46% | -2.50 |
| 2018 | 265 | 42.64% | -1.71 |
| 2019 | 260 | 48.85% | 0.98 |
| 2020 | 260 | 54.62% | 2.98 |

## top / bearish

1538 picks on 309 dates (coverage 100.00%). Accuracy 53.19% vs market line 50.91%: edge 2.48 (t 1.83). Directional move after costs 0.02. Positive years 83.33%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2015 | 240 | 52.08% | 2.15 |
| 2016 | 260 | 56.92% | 5.91 |
| 2017 | 260 | 51.15% | 2.36 |
| 2018 | 265 | 53.96% | -1.55 |
| 2019 | 260 | 53.85% | 1.99 |
| 2020 | 253 | 50.99% | 4.10 |

## all / bullish

21257 picks on 309 dates (coverage 100.00%). Accuracy 49.83% vs market line 48.89%: edge 0.59 (t 1.59). Directional move after costs -0.43. Positive years 66.67%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2015 | 2614 | 49.31% | 0.18 |
| 2016 | 3006 | 52.40% | 0.81 |
| 2017 | 3629 | 53.07% | 1.63 |
| 2018 | 4641 | 45.85% | -0.37 |
| 2019 | 3979 | 46.47% | -0.60 |
| 2020 | 3388 | 53.90% | 1.87 |

## all / bearish

22273 picks on 309 dates (coverage 100.00%). Accuracy 52.56% vs market line 50.91%: edge 1.29 (t 3.34). Directional move after costs -0.02. Positive years 83.33%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2015 | 2539 | 49.74% | 1.97 |
| 2016 | 3236 | 54.64% | 2.33 |
| 2017 | 4422 | 51.63% | 1.32 |
| 2018 | 4363 | 57.53% | 0.62 |
| 2019 | 3927 | 50.47% | -1.08 |
| 2020 | 3786 | 50.21% | 2.62 |

## Exit plan payoff (train-only observation)

Exit plan parameters: fixed: stop 2 ATR (= 1R), target 2R, time exit after 10 sessions. Selection: `top`. Entry convention: the pick date's open; R = stop_atr x ATR(14) known before the pick date. Outcomes in R multiples and percent, net of the engine cost model (SPEC.md section 3): bullish = delivery round trip 0.415%, bearish = futures round trip 0.250%, charged once per pick. Baseline: the same exit plan applied to every universe stock on the same dates; the headline is average R above that baseline. Not a gate and not a roster input: SPEC.md has no payoff wording yet (`state/engine-issues.md`).

| Plan | Side | Picks | Right | Avg R | Median R | Profit factor | Avg % | Avg hold | Stop | Target | Time | Worst losing run | Baseline avg R | Avg R above baseline | t | 95% interval |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| exit plan | bearish | 1528 | 47.3% | -0.004 | -0.080 | 0.99 | 0.00% | 8.2 | 30% | 7% | 63% | 16 | -0.018 | 0.019 | 0.53 | -0.044 to 0.076 |
| time-only control | bearish | 1528 | 50.6% | 0.019 | 0.012 | 1.05 | 0.03% | 10.0 | 0% | 0% | 100% | 16 | -0.018 | 0.050 | 1.38 | -0.020 to 0.110 |

### bearish: by year (exit plan)

| Year | Picks | Right | Avg R | Avg R above baseline |
|---|---|---|---|---|
| 2015 | 240 | 44.2% | -0.084 | -0.123 |
| 2016 | 260 | 48.5% | 0.044 | 0.065 |
| 2017 | 260 | 43.1% | -0.061 | 0.094 |
| 2018 | 265 | 51.3% | 0.086 | 0.010 |
| 2019 | 260 | 51.9% | 0.047 | 0.026 |
| 2020 | 243 | 44.0% | -0.069 | 0.035 |

Dropped (window past the split end or no ATR yet): 10. Intervals: holds overlap across pick dates, so dates are not independent. t = mean / standard error of the means of non-overlapping blocks of 8 consecutive pick dates; 95% interval = moving-block bootstrap, block length 8 pick dates, 2000 resamples, seed 0, percentile method.
