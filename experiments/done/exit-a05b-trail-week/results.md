# exit-a05b-trail-week: train results

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

Exit plan parameters: trail: stop 3 ATR from the best close (1R = 3 ATR), time exit after 20 sessions. Selection: `top`. Entry convention: the pick date's open; R = stop_atr x ATR(14) known before the pick date. Outcomes in R multiples and percent, net of the engine cost model (SPEC.md section 3): bullish = delivery round trip 0.415%, bearish = futures round trip 0.250%, charged once per pick. Baseline: the same exit plan applied to every universe stock on the same dates; the headline is average R above that baseline. Not a gate and not a roster input: SPEC.md has no payoff wording yet (`state/engine-issues.md`).

| Plan | Side | Picks | Right | Avg R | Median R | Profit factor | Avg % | Avg hold | Stop | Target | Time | Worst losing run | Baseline avg R | Avg R above baseline | t | 95% interval |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| exit plan | bullish | 1455 | 45.6% | -0.008 | -0.099 | 0.98 | 0.06% | 16.4 | 40% | 0% | 60% | 26 | -0.040 | 0.032 | 0.98 | -0.016 to 0.093 |
| time-only control | bullish | 1455 | 50.2% | -0.027 | 0.005 | 0.94 | -0.09% | 20.0 | 0% | 0% | 100% | 27 | -0.050 | 0.022 | 0.55 | -0.046 to 0.104 |

### bullish: by year (exit plan)

| Year | Picks | Right | Avg R | Avg R above baseline |
|---|---|---|---|---|
| 2015 | 170 | 34.7% | -0.260 | -0.077 |
| 2016 | 260 | 46.5% | 0.016 | 0.059 |
| 2017 | 260 | 53.5% | 0.164 | 0.060 |
| 2018 | 265 | 42.6% | -0.085 | 0.099 |
| 2019 | 260 | 40.0% | -0.129 | -0.037 |
| 2020 | 240 | 52.9% | 0.176 | 0.051 |

Dropped (window past the split end or no ATR yet): 20. Intervals: holds overlap across pick dates, so dates are not independent. t = mean / standard error of the means of non-overlapping blocks of 8 consecutive pick dates; 95% interval = moving-block bootstrap, block length 8 pick dates, 2000 resamples, seed 0, percentile method.
