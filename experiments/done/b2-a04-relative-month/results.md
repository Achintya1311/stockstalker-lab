# b2-a04-relative-month: train results

`strategies.a04_52_week_high`, month horizon, train split. `top` = the 5 picks a table would publish each date; `all` = every positive or negative score. Edge and market line in points; definitions in SPEC.md section 3.

Opt-in scoring (train-only observation, not SPEC section 3 as written): yardstick relative, top_n 5. Under the relative yardstick: a bullish pick is right when its move is strictly above the median move of all in-universe stocks on that pick date (bearish: strictly below); market line = exact share of in-universe stocks strictly beating that median in the side's direction (ties count as misses, so it is at or just under 50%); costs cancel in this comparison (same side, same cost); directional move after costs is the usual absolute one.

## top / bullish

1280 picks on 256 dates (coverage 100.00%). Accuracy 51.41% vs market line 49.82%: edge 1.58 (t 0.63). Directional move after costs -0.37. Positive years 60.00%. Move above the universe median (costs cancel) -0.18.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2016 | 255 | 45.49% | -4.31 |
| 2017 | 260 | 47.69% | -2.14 |
| 2018 | 265 | 55.85% | 6.01 |
| 2019 | 260 | 54.23% | 4.39 |
| 2020 | 240 | 53.75% | 3.95 |

## top / bearish

1280 picks on 256 dates (coverage 100.00%). Accuracy 49.61% vs market line 49.82%: edge -0.22 (t -0.10). Directional move after costs -1.20. Positive years 40.00%. Move above the universe median (costs cancel) -0.72.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2016 | 255 | 53.73% | 3.92 |
| 2017 | 260 | 45.00% | -4.83 |
| 2018 | 265 | 49.81% | -0.03 |
| 2019 | 260 | 50.00% | 0.16 |
| 2020 | 240 | 49.58% | -0.22 |

## all / bullish

17920 picks on 256 dates (coverage 100.00%). Accuracy 51.46% vs market line 49.82%: edge 1.15 (t 0.92). Directional move after costs -0.47. Positive years 60.00%. Move above the universe median (costs cancel) 0.16.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2016 | 3137 | 48.84% | -2.13 |
| 2017 | 5339 | 50.27% | 0.39 |
| 2018 | 3410 | 54.87% | 4.25 |
| 2019 | 3175 | 53.92% | 3.58 |
| 2020 | 2859 | 49.77% | -0.59 |

## all / bearish

19617 picks on 256 dates (coverage 100.00%). Accuracy 51.20% vs market line 49.82%: edge 1.12 (t 1.12). Directional move after costs -0.67. Positive years 60.00%. Move above the universe median (costs cancel) -0.07.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2016 | 2964 | 48.62% | -1.04 |
| 2017 | 2646 | 50.19% | 0.86 |
| 2018 | 5598 | 52.79% | 3.08 |
| 2019 | 4688 | 52.56% | 2.73 |
| 2020 | 3721 | 49.85% | -0.20 |

## Month horizon: method

Outcome: the pick date's open (first trading date of the ISO week) to the close of the last trading date of the 4th ISO week, counting the pick week as week 1. A new four-week window starts every week, so windows overlap. A pick whose window ends after its split's end date is dropped. Cost is charged once per four-week hold.

Intervals: month: windows overlap (a new four-week hold starts every week), so dates are not independent. t = mean / standard error of the means of non-overlapping blocks of 8 consecutive pick dates; 95% interval = moving-block bootstrap, block length 8 pick dates, 2000 resamples, seed 0, percentile method. The t above is this block t.

| Selection | Side | Edge | 95% block-bootstrap interval |
|---|---|---|---|
| top | bullish | 1.58 | -3.11 to 5.74 |
| top | bearish | -0.22 | -3.73 to 4.06 |
| all | bullish | 1.15 | -0.68 to 3.41 |
| all | bearish | 1.12 | -0.26 to 3.05 |
