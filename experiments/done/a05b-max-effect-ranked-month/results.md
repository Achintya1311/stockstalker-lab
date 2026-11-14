# a05b-max-effect-ranked-month: train results

`strategies.a05b_max_effect_ranked`, month horizon, train split. `top` = the 5 picks a table would publish each date; `all` = every positive or negative score. Edge and market line in points; definitions in SPEC.md section 3.

## top / bullish

1455 picks on 291 dates (coverage 100.00%). Accuracy 52.85% vs market line 52.00%: edge 0.85 (t 0.53). Directional move after costs -0.16. Positive years 50.00%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2015 | 170 | 42.94% | -2.48 |
| 2016 | 260 | 52.69% | -2.35 |
| 2017 | 260 | 64.23% | 5.34 |
| 2018 | 265 | 47.55% | 3.73 |
| 2019 | 260 | 49.62% | -0.54 |
| 2020 | 240 | 57.08% | 0.15 |

## top / bearish

1455 picks on 291 dates (coverage 100.00%). Accuracy 50.45% vs market line 47.90%: edge 2.55 (t 1.63). Directional move after costs 0.19. Positive years 66.67%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2015 | 170 | 51.18% | -3.40 |
| 2016 | 260 | 54.23% | 9.35 |
| 2017 | 260 | 38.46% | -2.48 |
| 2018 | 265 | 61.13% | 5.04 |
| 2019 | 260 | 52.69% | 2.95 |
| 2020 | 240 | 44.58% | 1.63 |

## all / bullish

20276 picks on 291 dates (coverage 100.00%). Accuracy 51.21% vs market line 52.00%: edge -0.26 (t -1.02). Directional move after costs -0.47. Positive years 33.33%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2015 | 1753 | 45.18% | -0.37 |
| 2016 | 3034 | 54.78% | 0.32 |
| 2017 | 3979 | 57.33% | -0.63 |
| 2018 | 4403 | 43.02% | -0.38 |
| 2019 | 3942 | 49.21% | -0.80 |
| 2020 | 3165 | 57.35% | 0.31 |

## all / bearish

21006 picks on 291 dates (coverage 100.00%). Accuracy 48.06% vs market line 47.90%: edge -0.18 (t -0.67). Directional move after costs -0.33. Positive years 33.33%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2015 | 1811 | 54.67% | -0.56 |
| 2016 | 3195 | 45.67% | 0.39 |
| 2017 | 4069 | 40.87% | -0.51 |
| 2018 | 4582 | 56.13% | -0.33 |
| 2019 | 3924 | 49.24% | -0.69 |
| 2020 | 3425 | 43.21% | 0.53 |

## Month horizon: method

Outcome: the pick date's open (first trading date of the ISO week) to the close of the last trading date of the 4th ISO week, counting the pick week as week 1. A new four-week window starts every week, so windows overlap. A pick whose window ends after its split's end date is dropped. Cost is charged once per four-week hold.

Intervals: month: windows overlap (a new four-week hold starts every week), so dates are not independent. t = mean / standard error of the means of non-overlapping blocks of 8 consecutive pick dates; 95% interval = moving-block bootstrap, block length 8 pick dates, 2000 resamples, seed 0, percentile method. The t above is this block t.

| Selection | Side | Edge | 95% block-bootstrap interval |
|---|---|---|---|
| top | bullish | 0.85 | -1.66 to 4.22 |
| top | bearish | 2.55 | -0.56 to 5.08 |
| all | bullish | -0.26 | -0.89 to 0.32 |
| all | bearish | -0.18 | -0.85 to 0.46 |
