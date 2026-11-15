# b2-m02-relative-month: train results

`strategies.m02_leader_pullback`, month horizon, train split. `top` = the 5 picks a table would publish each date; `all` = every positive or negative score. Edge and market line in points; definitions in SPEC.md section 3.

Opt-in scoring (train-only observation, not SPEC section 3 as written): yardstick relative, top_n 5. Under the relative yardstick: a bullish pick is right when its move is strictly above the median move of all in-universe stocks on that pick date (bearish: strictly below); market line = exact share of in-universe stocks strictly beating that median in the side's direction (ties count as misses, so it is at or just under 50%); costs cancel in this comparison (same side, same cost); directional move after costs is the usual absolute one.

## top / bullish

1222 picks on 255 dates (coverage 100.00%). Accuracy 50.49% vs market line 49.82%: edge 1.42 (t 0.97). Directional move after costs -0.49. Positive years 60.00%. Move above the universe median (costs cancel) -0.14.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2016 | 236 | 48.73% | 1.31 |
| 2017 | 258 | 48.45% | -1.24 |
| 2018 | 259 | 56.76% | 7.20 |
| 2019 | 257 | 49.42% | -0.42 |
| 2020 | 212 | 48.58% | 0.02 |

## top / bearish

No in-universe picks.

## all / bullish

3769 picks on 255 dates (coverage 100.00%). Accuracy 52.67% vs market line 49.82%: edge 3.44 (t 3.58). Directional move after costs -0.63. Positive years 100.00%. Move above the universe median (costs cancel) 0.35.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2016 | 598 | 51.67% | 3.23 |
| 2017 | 1095 | 51.05% | 2.71 |
| 2018 | 819 | 56.65% | 6.69 |
| 2019 | 782 | 51.41% | 2.64 |
| 2020 | 475 | 52.84% | 1.68 |

## all / bearish

No in-universe picks.

## Month horizon: method

Outcome: the pick date's open (first trading date of the ISO week) to the close of the last trading date of the 4th ISO week, counting the pick week as week 1. A new four-week window starts every week, so windows overlap. A pick whose window ends after its split's end date is dropped. Cost is charged once per four-week hold.

Intervals: month: windows overlap (a new four-week hold starts every week), so dates are not independent. t = mean / standard error of the means of non-overlapping blocks of 8 consecutive pick dates; 95% interval = moving-block bootstrap, block length 8 pick dates, 2000 resamples, seed 0, percentile method. The t above is this block t.

| Selection | Side | Edge | 95% block-bootstrap interval |
|---|---|---|---|
| top | bullish | 1.42 | -2.08 to 4.31 |
| all | bullish | 3.44 | 1.03 to 5.59 |
