# b1-trend-cross-trail-week: train results

`strategies.b1_trend_cross`, week horizon, train split. `top` = the 5 picks a table would publish each date; `all` = every positive or negative score. Edge and market line in points; definitions in SPEC.md section 3.

## top / bullish

194 picks on 123 dates (coverage 100.00%). Accuracy 47.42% vs market line 49.56%: edge -2.24 (t -0.59). Directional move after costs -0.05. Positive years 33.33%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2015 | 4 | 25.00% | -44.77 |
| 2016 | 27 | 18.52% | -24.55 |
| 2017 | 50 | 64.00% | 15.14 |
| 2018 | 45 | 44.44% | -0.55 |
| 2019 | 37 | 51.35% | 5.20 |
| 2020 | 31 | 48.39% | -8.30 |

## top / bearish

No in-universe picks.

## all / bullish

198 picks on 123 dates (coverage 100.00%). Accuracy 47.47% vs market line 49.56%: edge -2.24 (t -0.59). Directional move after costs -0.09. Positive years 33.33%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2015 | 4 | 25.00% | -44.77 |
| 2016 | 27 | 18.52% | -24.55 |
| 2017 | 54 | 62.96% | 15.14 |
| 2018 | 45 | 44.44% | -0.55 |
| 2019 | 37 | 51.35% | 5.20 |
| 2020 | 31 | 48.39% | -8.30 |

## all / bearish

No in-universe picks.

## Exit plan payoff (train-only observation)

Exit plan parameters: trail: stop 3 ATR from the best close (1R = 3 ATR), time exit after 20 sessions. Selection: `top`. Entry convention: the pick date's open; R = stop_atr x ATR(14) known before the pick date. Outcomes in R multiples and percent, net of the engine cost model (SPEC.md section 3): bullish = delivery round trip 0.415%, bearish = futures round trip 0.250%, charged once per pick. Baseline: the same exit plan applied to every universe stock on the same dates; the headline is average R above that baseline. Not a gate and not a roster input: SPEC.md has no payoff wording yet (`state/engine-issues.md`).

| Plan | Side | Picks | Right | Avg R | Median R | Profit factor | Avg % | Avg hold | Stop | Target | Time | Worst losing run | Baseline avg R | Avg R above baseline | t | 95% interval |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| exit plan | bullish | 192 | 44.3% | 0.049 | -0.152 | 1.14 | 0.27% | 16.5 | 43% | 0% | 57% | 9 | -0.038 | 0.160 | 2.21 | 0.018 to 0.288 |
| time-only control | bullish | 192 | 47.9% | 0.035 | -0.056 | 1.09 | 0.12% | 20.0 | 0% | 0% | 100% | 8 | -0.051 | 0.153 | 2.21 | 0.011 to 0.299 |

### bullish: by year (exit plan)

| Year | Picks | Right | Avg R | Avg R above baseline |
|---|---|---|---|---|
| 2015 | 4 | 25.0% | -0.414 | -0.046 |
| 2016 | 27 | 22.2% | -0.434 | -0.261 |
| 2017 | 50 | 52.0% | 0.226 | 0.329 |
| 2018 | 45 | 42.2% | -0.022 | 0.228 |
| 2019 | 37 | 43.2% | 0.081 | 0.309 |
| 2020 | 29 | 58.6% | 0.325 | 0.100 |

Dropped (window past the split end or no ATR yet): 2. Intervals: holds overlap across pick dates, so dates are not independent. t = mean / standard error of the means of non-overlapping blocks of 8 consecutive pick dates; 95% interval = moving-block bootstrap, block length 8 pick dates, 2000 resamples, seed 0, percentile method.
