# b3-m01-top20-month: train results

`strategies.m01_momentum_12_1`, month horizon, train split. `top` = the 20 picks a table would publish each date; `all` = every positive or negative score. Edge and market line in points; definitions in SPEC.md section 3.

Opt-in scoring (train-only observation, not SPEC section 3 as written): yardstick absolute, top_n 20.

## top / bullish

5020 picks on 251 dates (coverage 100.00%). Accuracy 55.18% vs market line 53.56%: edge 1.62 (t 1.57). Directional move after costs -0.00. Positive years 40.00%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2016 | 920 | 58.80% | -0.29 |
| 2017 | 1040 | 58.46% | -0.43 |
| 2018 | 1060 | 47.74% | 3.92 |
| 2019 | 1040 | 54.81% | 4.66 |
| 2020 | 960 | 56.77% | -0.16 |

## top / bearish

5020 picks on 251 dates (coverage 100.00%). Accuracy 49.20% vs market line 46.32%: edge 2.88 (t 2.51). Directional move after costs -0.52. Positive years 80.00%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2016 | 920 | 45.22% | 4.40 |
| 2017 | 1040 | 39.23% | -1.71 |
| 2018 | 1060 | 56.89% | 0.80 |
| 2019 | 1040 | 57.12% | 7.38 |
| 2020 | 960 | 46.77% | 3.82 |

## all / bullish

19498 picks on 251 dates (coverage 100.00%). Accuracy 54.49% vs market line 53.56%: edge 1.87 (t 3.40). Directional move after costs -0.03. Positive years 100.00%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2016 | 3022 | 60.19% | 2.03 |
| 2017 | 4287 | 59.65% | 1.39 |
| 2018 | 4871 | 44.98% | 1.27 |
| 2019 | 4059 | 53.02% | 3.17 |
| 2020 | 3259 | 58.48% | 1.48 |

## all / bearish

17352 picks on 251 dates (coverage 100.00%). Accuracy 49.16% vs market line 46.32%: edge 1.89 (t 3.16). Directional move after costs -0.45. Positive years 100.00%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2016 | 2500 | 44.04% | 2.22 |
| 2017 | 3654 | 42.91% | 1.24 |
| 2018 | 4123 | 58.04% | 1.16 |
| 2019 | 3785 | 53.16% | 3.38 |
| 2020 | 3290 | 44.29% | 1.49 |

## Month horizon: method

Outcome: the pick date's open (first trading date of the ISO week) to the close of the last trading date of the 4th ISO week, counting the pick week as week 1. A new four-week window starts every week, so windows overlap. A pick whose window ends after its split's end date is dropped. Cost is charged once per four-week hold.

Intervals: month: windows overlap (a new four-week hold starts every week), so dates are not independent. t = mean / standard error of the means of non-overlapping blocks of 8 consecutive pick dates; 95% interval = moving-block bootstrap, block length 8 pick dates, 2000 resamples, seed 0, percentile method. The t above is this block t.

| Selection | Side | Edge | 95% block-bootstrap interval |
|---|---|---|---|
| top | bullish | 1.62 | -0.35 to 3.86 |
| top | bearish | 2.88 | 0.65 to 5.16 |
| all | bullish | 1.87 | 0.88 to 3.06 |
| all | bearish | 1.89 | 0.85 to 3.15 |
