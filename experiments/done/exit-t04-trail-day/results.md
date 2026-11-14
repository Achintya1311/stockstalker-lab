# exit-t04-trail-day: train results

`strategies.t04_connors_rsi2`, day horizon, train split. `top` = the 5 picks a table would publish each date; `all` = every positive or negative score. Edge and market line in points; definitions in SPEC.md section 3.

## top / bullish

3952 picks on 1087 dates (coverage 85.12%). Accuracy 48.61% vs market line 45.17%: edge 3.37 (t 3.69). Directional move after costs -0.41. Positive years 100.00%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2015 | 117 | 47.86% | 8.18 |
| 2016 | 727 | 49.38% | 2.57 |
| 2017 | 845 | 48.76% | 4.17 |
| 2018 | 765 | 48.63% | 4.16 |
| 2019 | 816 | 49.88% | 3.35 |
| 2020 | 682 | 46.19% | 1.60 |

## top / bearish

4264 picks on 1123 dates (coverage 87.94%). Accuracy 57.55% vs market line 54.82%: edge 2.32 (t 2.65). Directional move after costs -0.01. Positive years 83.33%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2015 | 175 | 60.00% | 2.13 |
| 2016 | 654 | 56.88% | 5.06 |
| 2017 | 918 | 58.71% | 2.66 |
| 2018 | 904 | 57.74% | 1.96 |
| 2019 | 881 | 58.00% | 2.62 |
| 2020 | 732 | 55.33% | -0.81 |

## all / bullish

8352 picks on 1087 dates (coverage 85.12%). Accuracy 49.93% vs market line 45.17%: edge 3.33 (t 3.85). Directional move after costs -0.41. Positive years 100.00%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2015 | 164 | 51.83% | 8.95 |
| 2016 | 1478 | 50.47% | 1.91 |
| 2017 | 2332 | 48.07% | 4.22 |
| 2018 | 1582 | 51.01% | 4.41 |
| 2019 | 1467 | 49.83% | 3.05 |
| 2020 | 1329 | 51.17% | 1.86 |

## all / bearish

9380 picks on 1123 dates (coverage 87.94%). Accuracy 56.82% vs market line 54.82%: edge 2.29 (t 2.84). Directional move after costs -0.05. Positive years 83.33%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2015 | 293 | 63.14% | 3.14 |
| 2016 | 1257 | 55.37% | 5.99 |
| 2017 | 1432 | 57.47% | 1.56 |
| 2018 | 2283 | 57.34% | 2.40 |
| 2019 | 2054 | 56.62% | 2.58 |
| 2020 | 2061 | 55.99% | -1.31 |

## Exit plan payoff (train-only observation)

Exit plan parameters: trail: stop 3 ATR from the best close (1R = 3 ATR), time exit after 20 sessions. Selection: `top`. Entry convention: the pick date's open; R = stop_atr x ATR(14) known before the pick date. Outcomes in R multiples and percent, net of the engine cost model (SPEC.md section 3): bullish = delivery round trip 0.415%, bearish = futures round trip 0.250%, charged once per pick. Baseline: the same exit plan applied to every universe stock on the same dates; the headline is average R above that baseline. Not a gate and not a roster input: SPEC.md has no payoff wording yet (`state/engine-issues.md`).

| Plan | Side | Picks | Right | Avg R | Median R | Profit factor | Avg % | Avg hold | Stop | Target | Time | Worst losing run | Baseline avg R | Avg R above baseline | t | 95% interval |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| exit plan | bullish | 3897 | 45.0% | -0.041 | -0.113 | 0.90 | -0.37% | 16.0 | 44% | 0% | 56% | 81 | -0.038 | -0.002 | -0.09 | -0.061 to 0.056 |
| time-only control | bullish | 3897 | 50.3% | -0.072 | 0.008 | 0.84 | -0.61% | 20.0 | 0% | 0% | 100% | 49 | -0.054 | -0.015 | -0.45 | -0.079 to 0.049 |

### bullish: by year (exit plan)

| Year | Picks | Right | Avg R | Avg R above baseline |
|---|---|---|---|---|
| 2015 | 117 | 47.9% | -0.110 | 0.067 |
| 2016 | 727 | 49.4% | -0.025 | -0.032 |
| 2017 | 845 | 44.0% | -0.028 | -0.089 |
| 2018 | 765 | 36.1% | -0.188 | 0.038 |
| 2019 | 816 | 46.8% | -0.006 | 0.072 |
| 2020 | 627 | 49.3% | 0.068 | -0.016 |

Dropped (window past the split end or no ATR yet): 55. Intervals: holds overlap across pick dates, so dates are not independent. t = mean / standard error of the means of non-overlapping blocks of 20 consecutive pick dates; 95% interval = moving-block bootstrap, block length 20 pick dates, 2000 resamples, seed 0, percentile method.
