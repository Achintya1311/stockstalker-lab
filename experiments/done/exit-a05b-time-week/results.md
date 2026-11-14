# exit-a05b-time-week: train results

`strategies.a05b_max_effect_ranked`, week horizon, train split. `top` = the 5 picks a table would publish each date; `all` = every positive or negative score. Edge and market line in points; definitions in SPEC.md section 3.

## top / bullish

1475 picks on 295 dates (coverage 100.00%). Accuracy 51.39% vs market line 49.16%: edge 2.23 (t 1.86). Directional move after costs -0.50. Positive years 83.33%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2015 | 170 | 52.35% | -0.26 |
| 2016 | 260 | 54.62% | 5.80 |
| 2017 | 260 | 51.15% | 0.20 |
| 2018 | 265 | 48.30% | 3.95 |
| 2019 | 260 | 49.62% | 1.75 |
| 2020 | 260 | 52.69% | 1.05 |

## top / bearish

1475 picks on 295 dates (coverage 100.00%). Accuracy 50.37% vs market line 50.65%: edge -0.28 (t -0.22). Directional move after costs -0.37. Positive years 50.00%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2015 | 170 | 42.94% | -4.34 |
| 2016 | 260 | 49.23% | -1.78 |
| 2017 | 260 | 46.15% | -2.64 |
| 2018 | 265 | 56.23% | 0.71 |
| 2019 | 260 | 53.08% | 1.22 |
| 2020 | 260 | 51.92% | 3.72 |

## all / bullish

20589 picks on 295 dates (coverage 100.00%). Accuracy 48.99% vs market line 49.16%: edge 0.32 (t 1.26). Directional move after costs -0.55. Positive years 33.33%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2015 | 1753 | 52.14% | -0.52 |
| 2016 | 3038 | 50.16% | 1.57 |
| 2017 | 3987 | 50.14% | -0.00 |
| 2018 | 4403 | 44.08% | -0.18 |
| 2019 | 3947 | 47.76% | -0.20 |
| 2020 | 3461 | 52.67% | 0.99 |

## all / bearish

21276 picks on 295 dates (coverage 100.00%). Accuracy 51.44% vs market line 50.65%: edge 0.39 (t 1.57). Directional move after costs -0.18. Positive years 33.33%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2015 | 1811 | 46.82% | -0.80 |
| 2016 | 3195 | 52.58% | 1.46 |
| 2017 | 4070 | 49.14% | -0.04 |
| 2018 | 4588 | 55.65% | -0.11 |
| 2019 | 3931 | 51.92% | -0.05 |
| 2020 | 3681 | 49.50% | 1.49 |

## Exit plan payoff (train-only observation)

Exit plan parameters: time: exit at the close of session 10 (1R = 2 ATR, no stop). Selection: `top`. Entry convention: the pick date's open; R = stop_atr x ATR(14) known before the pick date. Outcomes in R multiples and percent, net of the engine cost model (SPEC.md section 3): bullish = delivery round trip 0.415%, bearish = futures round trip 0.250%, charged once per pick. Baseline: the same exit plan applied to every universe stock on the same dates; the headline is average R above that baseline. Not a gate and not a roster input: SPEC.md has no payoff wording yet (`state/engine-issues.md`).

| Plan | Side | Picks | Right | Avg R | Median R | Profit factor | Avg % | Avg hold | Stop | Target | Time | Worst losing run | Baseline avg R | Avg R above baseline | t | 95% interval |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| exit plan | bullish | 1465 | 48.7% | -0.066 | -0.026 | 0.85 | -0.39% | 10.0 | 0% | 0% | 100% | 22 | -0.082 | 0.016 | 0.44 | -0.049 to 0.092 |

### bullish: by year (exit plan)

| Year | Picks | Right | Avg R | Avg R above baseline |
|---|---|---|---|---|
| 2015 | 170 | 45.3% | -0.205 | -0.076 |
| 2016 | 260 | 49.6% | -0.130 | -0.013 |
| 2017 | 260 | 51.9% | 0.155 | 0.086 |
| 2018 | 265 | 48.7% | -0.046 | 0.137 |
| 2019 | 260 | 41.5% | -0.255 | -0.129 |
| 2020 | 250 | 54.4% | 0.039 | 0.057 |

Dropped (window past the split end or no ATR yet): 10. Intervals: holds overlap across pick dates, so dates are not independent. t = mean / standard error of the means of non-overlapping blocks of 8 consecutive pick dates; 95% interval = moving-block bootstrap, block length 8 pick dates, 2000 resamples, seed 0, percentile method.
