# m01-momentum-12-1-month: train results

`strategies.m01_momentum_12_1`, month horizon, train split. `top` = the 5 picks a table would publish each date; `all` = every positive or negative score. Edge and market line in points; definitions in SPEC.md section 3.

## top / bullish

1255 picks on 251 dates (coverage 100.00%). Accuracy 56.02% vs market line 53.56%: edge 2.46 (t 1.30). Directional move after costs 0.03. Positive years 60.00%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2016 | 230 | 55.65% | -3.44 |
| 2017 | 260 | 60.77% | 1.88 |
| 2018 | 265 | 49.81% | 5.99 |
| 2019 | 260 | 57.69% | 7.54 |
| 2020 | 240 | 56.25% | -0.68 |

## top / bearish

1255 picks on 251 dates (coverage 100.00%). Accuracy 48.76% vs market line 46.32%: edge 2.44 (t 1.10). Directional move after costs -0.80. Positive years 80.00%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2016 | 230 | 43.91% | 3.10 |
| 2017 | 260 | 34.23% | -6.71 |
| 2018 | 265 | 59.62% | 3.53 |
| 2019 | 260 | 58.46% | 8.72 |
| 2020 | 240 | 46.67% | 3.72 |

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
| top | bullish | 2.46 | -1.32 to 6.39 |
| top | bearish | 2.44 | -1.51 to 6.04 |
| all | bullish | 1.87 | 0.88 to 3.06 |
| all | bearish | 1.89 | 0.85 to 3.15 |
