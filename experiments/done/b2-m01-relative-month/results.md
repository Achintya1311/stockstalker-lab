# b2-m01-relative-month: train results

`strategies.m01_momentum_12_1`, month horizon, train split. `top` = the 5 picks a table would publish each date; `all` = every positive or negative score. Edge and market line in points; definitions in SPEC.md section 3.

Opt-in scoring (train-only observation, not SPEC section 3 as written): yardstick relative, top_n 5. Under the relative yardstick: a bullish pick is right when its move is strictly above the median move of all in-universe stocks on that pick date (bearish: strictly below); market line = exact share of in-universe stocks strictly beating that median in the side's direction (ties count as misses, so it is at or just under 50%); costs cancel in this comparison (same side, same cost); directional move after costs is the usual absolute one.

## top / bullish

1255 picks on 251 dates (coverage 100.00%). Accuracy 50.76% vs market line 49.83%: edge 0.93 (t 0.48). Directional move after costs 0.03. Positive years 60.00%. Move above the universe median (costs cancel) 0.09.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2016 | 230 | 43.48% | -6.34 |
| 2017 | 260 | 52.31% | 2.48 |
| 2018 | 265 | 53.21% | 3.36 |
| 2019 | 260 | 54.62% | 4.77 |
| 2020 | 240 | 49.17% | -0.64 |

## top / bearish

1255 picks on 251 dates (coverage 100.00%). Accuracy 52.67% vs market line 49.83%: edge 2.84 (t 1.23). Directional move after costs -0.80. Positive years 80.00%. Move above the universe median (costs cancel) -0.19.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2016 | 230 | 53.04% | 3.22 |
| 2017 | 260 | 41.54% | -8.29 |
| 2018 | 265 | 55.85% | 6.01 |
| 2019 | 260 | 61.92% | 12.08 |
| 2020 | 240 | 50.83% | 1.03 |

## all / bullish

19498 picks on 251 dates (coverage 100.00%). Accuracy 51.36% vs market line 49.83%: edge 1.33 (t 1.83). Directional move after costs -0.03. Positive years 60.00%. Move above the universe median (costs cancel) 0.20.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2016 | 3022 | 49.37% | -0.55 |
| 2017 | 4287 | 51.20% | 1.40 |
| 2018 | 4871 | 52.10% | 2.24 |
| 2019 | 4059 | 53.71% | 3.64 |
| 2020 | 3259 | 49.37% | -0.46 |

## all / bearish

17352 picks on 251 dates (coverage 100.00%). Accuracy 51.39% vs market line 49.83%: edge 1.35 (t 1.72). Directional move after costs -0.45. Positive years 60.00%. Move above the universe median (costs cancel) -0.02.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2016 | 2500 | 49.08% | -0.86 |
| 2017 | 3654 | 51.07% | 1.22 |
| 2018 | 4123 | 52.32% | 2.39 |
| 2019 | 3785 | 53.98% | 3.97 |
| 2020 | 3290 | 49.39% | -0.37 |

## Month horizon: method

Outcome: the pick date's open (first trading date of the ISO week) to the close of the last trading date of the 4th ISO week, counting the pick week as week 1. A new four-week window starts every week, so windows overlap. A pick whose window ends after its split's end date is dropped. Cost is charged once per four-week hold.

Intervals: month: windows overlap (a new four-week hold starts every week), so dates are not independent. t = mean / standard error of the means of non-overlapping blocks of 8 consecutive pick dates; 95% interval = moving-block bootstrap, block length 8 pick dates, 2000 resamples, seed 0, percentile method. The t above is this block t.

| Selection | Side | Edge | 95% block-bootstrap interval |
|---|---|---|---|
| top | bullish | 0.93 | -3.14 to 5.30 |
| top | bearish | 2.84 | -1.45 to 7.78 |
| all | bullish | 1.33 | 0.05 to 3.30 |
| all | bearish | 1.35 | 0.03 to 3.45 |
