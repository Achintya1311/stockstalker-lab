# a01-weekly-reversal-month: train results

`strategies.a01_weekly_reversal`, month horizon, train split. `top` = the 5 picks a table would publish each date; `all` = every positive or negative score. Edge and market line in points; definitions in SPEC.md section 3.

## top / bullish

1525 picks on 305 dates (coverage 100.00%). Accuracy 47.87% vs market line 51.47%: edge -3.60 (t -2.68). Directional move after costs -0.66. Positive years 0.00%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2015 | 240 | 37.08% | -6.91 |
| 2016 | 260 | 52.31% | -2.73 |
| 2017 | 260 | 50.00% | -8.89 |
| 2018 | 265 | 43.77% | -0.04 |
| 2019 | 260 | 48.85% | -1.31 |
| 2020 | 240 | 55.00% | -1.93 |

## top / bearish

1518 picks on 305 dates (coverage 100.00%). Accuracy 51.98% vs market line 48.43%: edge 3.77 (t 2.94). Directional move after costs 0.26. Positive years 100.00%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2015 | 240 | 56.25% | 0.27 |
| 2016 | 260 | 49.23% | 4.35 |
| 2017 | 260 | 42.31% | 1.37 |
| 2018 | 265 | 60.00% | 3.91 |
| 2019 | 260 | 56.92% | 7.19 |
| 2020 | 233 | 46.78% | 5.38 |

## all / bullish

21037 picks on 305 dates (coverage 100.00%). Accuracy 51.79% vs market line 51.47%: edge 0.11 (t 0.22). Directional move after costs -0.34. Positive years 66.67%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2015 | 2610 | 48.05% | 0.18 |
| 2016 | 3005 | 55.81% | -0.56 |
| 2017 | 3625 | 58.40% | -1.40 |
| 2018 | 4638 | 44.59% | 0.28 |
| 2019 | 3971 | 49.99% | 1.14 |
| 2020 | 3188 | 56.27% | 1.10 |

## all / bearish

21900 picks on 305 dates (coverage 100.00%). Accuracy 49.34% vs market line 48.43%: edge 0.53 (t 1.25). Directional move after costs -0.08. Positive years 83.33%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2015 | 2536 | 60.37% | 0.93 |
| 2016 | 3234 | 46.78% | 1.94 |
| 2017 | 4417 | 41.86% | -0.51 |
| 2018 | 4360 | 57.66% | 0.11 |
| 2019 | 3923 | 49.83% | 0.29 |
| 2020 | 3430 | 42.10% | 0.46 |

## Month horizon: method

Outcome: the pick date's open (first trading date of the ISO week) to the close of the last trading date of the 4th ISO week, counting the pick week as week 1. A new four-week window starts every week, so windows overlap. A pick whose window ends after its split's end date is dropped. Cost is charged once per four-week hold.

Intervals: month: windows overlap (a new four-week hold starts every week), so dates are not independent. t = mean / standard error of the means of non-overlapping blocks of 8 consecutive pick dates; 95% interval = moving-block bootstrap, block length 8 pick dates, 2000 resamples, seed 0, percentile method. The t above is this block t.

| Selection | Side | Edge | 95% block-bootstrap interval |
|---|---|---|---|
| top | bullish | -3.60 | -6.43 to -1.12 |
| top | bearish | 3.77 | 1.27 to 6.06 |
| all | bullish | 0.11 | -0.64 to 0.81 |
| all | bearish | 0.53 | -0.28 to 1.40 |
