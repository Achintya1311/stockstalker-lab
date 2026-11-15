# b2-m01-relative-week: train results

`strategies.m01_momentum_12_1`, week horizon, train split. `top` = the 5 picks a table would publish each date; `all` = every positive or negative score. Edge and market line in points; definitions in SPEC.md section 3.

Opt-in scoring (train-only observation, not SPEC section 3 as written): yardstick relative, top_n 5. Under the relative yardstick: a bullish pick is right when its move is strictly above the median move of all in-universe stocks on that pick date (bearish: strictly below); market line = exact share of in-universe stocks strictly beating that median in the side's direction (ties count as misses, so it is at or just under 50%); costs cancel in this comparison (same side, same cost); directional move after costs is the usual absolute one.

## top / bullish

1275 picks on 255 dates (coverage 100.00%). Accuracy 50.35% vs market line 49.83%: edge 0.53 (t 0.34). Directional move after costs -0.57. Positive years 60.00%. Move above the universe median (costs cancel) -0.06.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2016 | 230 | 44.35% | -5.47 |
| 2017 | 260 | 51.15% | 1.32 |
| 2018 | 265 | 52.08% | 2.22 |
| 2019 | 260 | 53.85% | 4.00 |
| 2020 | 260 | 49.62% | -0.16 |

## top / bearish

1275 picks on 255 dates (coverage 100.00%). Accuracy 51.84% vs market line 49.83%: edge 2.02 (t 1.32). Directional move after costs -0.26. Positive years 80.00%. Move above the universe median (costs cancel) -0.11.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2016 | 230 | 50.00% | 0.18 |
| 2017 | 260 | 48.46% | -1.38 |
| 2018 | 265 | 50.57% | 0.71 |
| 2019 | 260 | 58.08% | 8.23 |
| 2020 | 260 | 51.92% | 2.15 |

## all / bullish

19789 picks on 255 dates (coverage 100.00%). Accuracy 51.04% vs market line 49.83%: edge 1.15 (t 2.50). Directional move after costs -0.43. Positive years 80.00%. Move above the universe median (costs cancel) 0.13.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2016 | 3026 | 49.80% | -0.03 |
| 2017 | 4295 | 50.76% | 0.95 |
| 2018 | 4871 | 51.37% | 1.50 |
| 2019 | 4061 | 51.96% | 2.05 |
| 2020 | 3536 | 50.93% | 1.14 |

## all / bearish

17638 picks on 255 dates (coverage 100.00%). Accuracy 51.16% vs market line 49.83%: edge 1.28 (t 2.55). Directional move after costs -0.17. Positive years 80.00%. Move above the universe median (costs cancel) -0.06.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2016 | 2500 | 49.80% | -0.04 |
| 2017 | 3655 | 50.70% | 0.93 |
| 2018 | 4129 | 51.59% | 1.76 |
| 2019 | 3795 | 52.15% | 2.32 |
| 2020 | 3559 | 51.03% | 1.27 |
