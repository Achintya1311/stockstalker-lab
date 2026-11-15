# b3-m01-top15-month: train results

`strategies.m01_momentum_12_1`, month horizon, train split. `top` = the 15 picks a table would publish each date; `all` = every positive or negative score. Edge and market line in points; definitions in SPEC.md section 3.

Opt-in scoring (train-only observation, not SPEC section 3 as written): yardstick absolute, top_n 15.

## top / bullish

3765 picks on 251 dates (coverage 100.00%). Accuracy 54.69% vs market line 53.56%: edge 1.13 (t 0.91). Directional move after costs -0.04. Positive years 40.00%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2016 | 690 | 58.99% | -0.11 |
| 2017 | 780 | 57.95% | -0.94 |
| 2018 | 795 | 46.16% | 2.35 |
| 2019 | 780 | 54.74% | 4.59 |
| 2020 | 720 | 56.39% | -0.54 |

## top / bearish

3765 picks on 251 dates (coverage 100.00%). Accuracy 49.35% vs market line 46.32%: edge 3.03 (t 2.66). Directional move after costs -0.58. Positive years 80.00%.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2016 | 690 | 44.64% | 3.82 |
| 2017 | 780 | 38.85% | -2.10 |
| 2018 | 795 | 56.98% | 0.89 |
| 2019 | 780 | 58.59% | 8.85 |
| 2020 | 720 | 46.81% | 3.86 |

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
| top | bullish | 1.13 | -1.35 to 3.65 |
| top | bearish | 3.03 | 0.72 to 5.53 |
| all | bullish | 1.87 | 0.88 to 3.06 |
| all | bearish | 1.89 | 0.85 to 3.15 |
