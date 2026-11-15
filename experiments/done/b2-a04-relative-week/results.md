# b2-a04-relative-week: train results

`strategies.a04_52_week_high`, week horizon, train split. `top` = the 5 picks a table would publish each date; `all` = every positive or negative score. Edge and market line in points; definitions in SPEC.md section 3.

Opt-in scoring (train-only observation, not SPEC section 3 as written): yardstick relative, top_n 5. Under the relative yardstick: a bullish pick is right when its move is strictly above the median move of all in-universe stocks on that pick date (bearish: strictly below); market line = exact share of in-universe stocks strictly beating that median in the side's direction (ties count as misses, so it is at or just under 50%); costs cancel in this comparison (same side, same cost); directional move after costs is the usual absolute one.

## top / bullish

1300 picks on 260 dates (coverage 100.00%). Accuracy 51.62% vs market line 49.82%: edge 1.79 (t 1.10). Directional move after costs -0.55. Positive years 80.00%. Move above the universe median (costs cancel) 0.01.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2016 | 255 | 45.10% | -4.70 |
| 2017 | 260 | 51.54% | 1.70 |
| 2018 | 265 | 53.96% | 4.11 |
| 2019 | 260 | 53.08% | 3.23 |
| 2020 | 260 | 54.23% | 4.45 |

## top / bearish

1300 picks on 260 dates (coverage 100.00%). Accuracy 48.62% vs market line 49.82%: edge -1.21 (t -0.77). Directional move after costs -0.34. Positive years 40.00%. Move above the universe median (costs cancel) -0.25.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2016 | 255 | 50.20% | 0.39 |
| 2017 | 260 | 46.54% | -3.30 |
| 2018 | 265 | 46.79% | -3.06 |
| 2019 | 260 | 49.62% | -0.23 |
| 2020 | 260 | 50.00% | 0.22 |

## all / bullish

18416 picks on 260 dates (coverage 100.00%). Accuracy 51.10% vs market line 49.82%: edge 0.99 (t 1.54). Directional move after costs -0.55. Positive years 80.00%. Move above the universe median (costs cancel) 0.12.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2016 | 3141 | 48.74% | -1.60 |
| 2017 | 5347 | 50.72% | 0.85 |
| 2018 | 3410 | 52.99% | 2.58 |
| 2019 | 3175 | 52.60% | 2.36 |
| 2020 | 3343 | 50.55% | 0.71 |

## all / bearish

19700 picks on 260 dates (coverage 100.00%). Accuracy 50.94% vs market line 49.82%: edge 1.00 (t 2.02). Directional move after costs -0.19. Positive years 80.00%. Move above the universe median (costs cancel) -0.06.

| Year | Picks | Accuracy | Edge |
|---|---|---|---|
| 2016 | 2964 | 48.45% | -1.28 |
| 2017 | 2647 | 51.61% | 1.86 |
| 2018 | 5604 | 51.68% | 1.83 |
| 2019 | 4700 | 51.70% | 1.89 |
| 2020 | 3785 | 50.41% | 0.65 |
