# exit-e2a-fixed-day: train results

`strategies.e2a_a02_crowded`, day horizon, train split. `top` = the 5 picks a table would publish each date; `all` = every positive or negative score. Edge and market line in points; definitions in SPEC.md section 3.

## top / bullish

2149 picks on 808 dates (coverage 68.53%). Accuracy 44.25% vs market line 44.20%: edge -1.58 (t -1.25). Directional move after costs -0.74. Positive years 33.33%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2015 | 288 | 48.96% | 7.85 |
| 2016 | 321 | 41.74% | -1.49 |
| 2017 | 377 | 41.11% | -6.85 |
| 2018 | 464 | 46.34% | 1.69 |
| 2019 | 457 | 43.54% | -3.55 |
| 2020 | 242 | 44.21% | -6.93 |

## top / bearish

2767 picks on 936 dates (coverage 79.39%). Accuracy 61.44% vs market line 55.08%: edge 7.46 (t 6.92). Directional move after costs 0.13. Positive years 100.00%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2015 | 321 | 59.19% | 4.17 |
| 2016 | 422 | 63.74% | 8.09 |
| 2017 | 626 | 62.62% | 6.77 |
| 2018 | 478 | 59.00% | 5.49 |
| 2019 | 392 | 61.73% | 9.26 |
| 2020 | 528 | 61.55% | 10.46 |

## all / bullish

3421 picks on 808 dates (coverage 68.53%). Accuracy 45.72% vs market line 44.20%: edge -1.38 (t -1.11). Directional move after costs -0.63. Positive years 33.33%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2015 | 392 | 48.21% | 8.32 |
| 2016 | 525 | 41.14% | -0.31 |
| 2017 | 485 | 42.06% | -6.94 |
| 2018 | 801 | 50.31% | 2.07 |
| 2019 | 731 | 44.73% | -3.78 |
| 2020 | 487 | 46.20% | -7.49 |

## all / bearish

3819 picks on 936 dates (coverage 79.39%). Accuracy 60.38% vs market line 55.08%: edge 7.14 (t 6.74). Directional move after costs 0.10. Positive years 100.00%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2015 | 379 | 58.84% | 4.03 |
| 2016 | 572 | 61.71% | 7.16 |
| 2017 | 907 | 61.74% | 6.58 |
| 2018 | 681 | 58.59% | 6.05 |
| 2019 | 528 | 62.12% | 9.64 |
| 2020 | 752 | 58.91% | 8.94 |

## Exit plan payoff (train-only observation)

Exit plan parameters: fixed: stop 2 ATR (= 1R), target 2R, time exit after 10 sessions. Selection: `top`. Entry convention: the pick date's open; R = stop_atr x ATR(14) known before the pick date. Outcomes in R multiples and percent, net of the engine cost model (SPEC.md section 3): bullish = delivery round trip 0.415%, bearish = futures round trip 0.250%, charged once per pick. Baseline: the same exit plan applied to every universe stock on the same dates; the headline is average R above that baseline. Not a gate and not a roster input: SPEC.md has no payoff wording yet (`state/engine-issues.md`).

| Plan | Side | Picks | Right | Avg R | Median R | Profit factor | Avg % | Avg hold | Stop | Target | Time | Worst losing run | Baseline avg R | Avg R above baseline | t | 95% interval |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| exit plan | bearish | 2751 | 48.1% | 0.061 | -0.048 | 1.15 | 0.36% | 8.1 | 30% | 9% | 61% | 19 | -0.011 | 0.094 | 3.34 | 0.037 to 0.150 |
| time-only control | bearish | 2751 | 50.9% | 0.049 | 0.017 | 1.11 | 0.23% | 10.0 | 0% | 0% | 100% | 17 | -0.013 | 0.064 | 2.01 | 0.005 to 0.133 |

### bearish: by year (exit plan)

| Year | Picks | Right | Avg R | Avg R above baseline |
|---|---|---|---|---|
| 2015 | 321 | 50.5% | 0.197 | 0.033 |
| 2016 | 422 | 56.2% | 0.200 | 0.229 |
| 2017 | 626 | 44.1% | -0.028 | 0.082 |
| 2018 | 478 | 49.6% | 0.076 | 0.034 |
| 2019 | 392 | 50.5% | 0.096 | 0.083 |
| 2020 | 512 | 41.4% | -0.074 | 0.093 |

Dropped (window past the split end or no ATR yet): 16. Intervals: holds overlap across pick dates, so dates are not independent. t = mean / standard error of the means of non-overlapping blocks of 10 consecutive pick dates; 95% interval = moving-block bootstrap, block length 10 pick dates, 2000 resamples, seed 0, percentile method.
