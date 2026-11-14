# m02-leader-pullback-month: train results

`strategies.m02_leader_pullback`, month horizon, train split. `top` = the 5 picks a table would publish each date; `all` = every positive or negative score. Edge and market line in points; definitions in SPEC.md section 3.

## top / bullish

1222 picks on 255 dates (coverage 100.00%). Accuracy 54.50% vs market line 52.88%: edge 2.24 (t 1.50). Directional move after costs -0.49. Positive years 80.00%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2016 | 236 | 59.32% | 3.51 |
| 2017 | 258 | 60.47% | 1.62 |
| 2018 | 259 | 49.81% | 5.77 |
| 2019 | 257 | 49.81% | -0.34 |
| 2020 | 212 | 53.30% | 0.45 |

## top / bearish

No in-universe picks.

## all / bullish

3769 picks on 255 dates (coverage 100.00%). Accuracy 53.44% vs market line 52.88%: edge 3.06 (t 3.17). Directional move after costs -0.63. Positive years 100.00%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2016 | 598 | 58.70% | 4.68 |
| 2017 | 1095 | 59.63% | 2.54 |
| 2018 | 819 | 48.60% | 4.71 |
| 2019 | 782 | 50.38% | 2.87 |
| 2020 | 475 | 45.89% | 0.22 |

## all / bearish

No in-universe picks.

## Month horizon: method

Outcome: the pick date's open (first trading date of the ISO week) to the close of the last trading date of the 4th ISO week, counting the pick week as week 1. A new four-week window starts every week, so windows overlap. A pick whose window ends after its split's end date is dropped. Cost is charged once per four-week hold.

Intervals: month: windows overlap (a new four-week hold starts every week), so dates are not independent. t = mean / standard error of the means of non-overlapping blocks of 8 consecutive pick dates; 95% interval = moving-block bootstrap, block length 8 pick dates, 2000 resamples, seed 0, percentile method. The t above is this block t.

| Selection | Side | Edge | 95% block-bootstrap interval |
|---|---|---|---|
| top | bullish | 2.24 | -0.88 to 5.11 |
| all | bullish | 3.06 | 1.01 to 5.16 |
