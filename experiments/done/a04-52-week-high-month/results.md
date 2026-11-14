# a04-52-week-high-month: train results

`strategies.a04_52_week_high`, month horizon, train split. `top` = the 5 picks a table would publish each date; `all` = every positive or negative score. Edge and market line in points; definitions in SPEC.md section 3.

## top / bullish

1280 picks on 256 dates (coverage 100.00%). Accuracy 54.84% vs market line 53.02%: edge 1.82 (t 0.89). Directional move after costs -0.37. Positive years 80.00%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2016 | 255 | 52.94% | -2.90 |
| 2017 | 260 | 59.23% | 0.34 |
| 2018 | 265 | 47.92% | 4.11 |
| 2019 | 260 | 52.69% | 2.54 |
| 2020 | 240 | 62.08% | 5.15 |

## top / bearish

1280 picks on 256 dates (coverage 100.00%). Accuracy 47.19% vs market line 46.87%: edge 0.32 (t 0.18). Directional move after costs -1.20. Positive years 60.00%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2016 | 255 | 45.88% | 1.80 |
| 2017 | 260 | 38.08% | -2.86 |
| 2018 | 265 | 52.83% | -3.26 |
| 2019 | 260 | 51.54% | 1.80 |
| 2020 | 240 | 47.50% | 4.55 |

## all / bullish

17920 picks on 256 dates (coverage 100.00%). Accuracy 52.80% vs market line 53.02%: edge 1.45 (t 1.71). Directional move after costs -0.47. Positive years 80.00%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2016 | 3137 | 53.27% | -0.82 |
| 2017 | 5339 | 58.46% | 0.96 |
| 2018 | 3410 | 41.00% | 2.27 |
| 2019 | 3175 | 51.87% | 3.17 |
| 2020 | 2859 | 56.84% | 1.60 |

## all / bearish

19617 picks on 256 dates (coverage 100.00%). Accuracy 48.06% vs market line 46.87%: edge 1.64 (t 2.52). Directional move after costs -0.67. Positive years 100.00%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2016 | 2964 | 42.65% | 0.78 |
| 2017 | 2646 | 41.65% | 1.82 |
| 2018 | 5598 | 54.88% | 1.75 |
| 2019 | 4688 | 51.17% | 2.22 |
| 2020 | 3721 | 42.76% | 1.60 |

## Month horizon: method

Outcome: the pick date's open (first trading date of the ISO week) to the close of the last trading date of the 4th ISO week, counting the pick week as week 1. A new four-week window starts every week, so windows overlap. A pick whose window ends after its split's end date is dropped. Cost is charged once per four-week hold.

Intervals: month: windows overlap (a new four-week hold starts every week), so dates are not independent. t = mean / standard error of the means of non-overlapping blocks of 8 consecutive pick dates; 95% interval = moving-block bootstrap, block length 8 pick dates, 2000 resamples, seed 0, percentile method. The t above is this block t.

| Selection | Side | Edge | 95% block-bootstrap interval |
|---|---|---|---|
| top | bullish | 1.82 | -1.77 to 5.61 |
| top | bearish | 0.32 | -2.96 to 3.88 |
| all | bullish | 1.45 | 0.11 to 3.11 |
| all | bearish | 1.64 | 0.61 to 2.98 |
