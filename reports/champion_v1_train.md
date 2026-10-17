# Champion v1 train results (B7, `state/queue.md`)

`strategies/champion_v1.py` - the current StockStalker blended score (trend 0.4 / momentum 0.35 / volume 0.25) - run through the real replay engine on the train split (2015-01-01 to 2020-12-31), day and week, split into bullish (score > 0) and bearish (score < 0) picks. Definitions per SPEC.md section 3; gates per SPEC.md section 6 are checked on test, not here - this is the train-split baseline before any validation look.

## Day

### Day - Bullish

Whole split: 107735 picks, accuracy 44.55%, edge -0.11 points, directional move after costs -0.54 points.

| Year | Picks | Accuracy | Edge (points) |
|---|---|---|---|
| 2015 | 8797 | 43.01% | -0.52 |
| 2016 | 16053 | 45.65% | -0.54 |
| 2017 | 24540 | 43.92% | 0.18 |
| 2018 | 18615 | 44.46% | 0.12 |
| 2019 | 18707 | 43.97% | 0.25 |
| 2020 | 21023 | 45.70% | -0.26 |

### Day - Bearish

Whole split: 94993 picks, accuracy 53.95%, edge 0.19 points, directional move after costs -0.12 points.

| Year | Picks | Accuracy | Edge (points) |
|---|---|---|---|
| 2015 | 12059 | 54.10% | -0.03 |
| 2016 | 13582 | 53.89% | -0.28 |
| 2017 | 14096 | 54.48% | 0.20 |
| 2018 | 23300 | 53.87% | 0.50 |
| 2019 | 18483 | 53.30% | -0.11 |
| 2020 | 13473 | 54.37% | 0.82 |

## Week

### Week - Bullish

Whole split: 22798 picks, accuracy 48.80%, edge 0.07 points, directional move after costs -0.53 points.

| Year | Picks | Accuracy | Edge (points) |
|---|---|---|---|
| 2015 | 1813 | 49.15% | -0.63 |
| 2016 | 3437 | 49.14% | -1.27 |
| 2017 | 5068 | 50.00% | 0.34 |
| 2018 | 4091 | 45.03% | 1.11 |
| 2019 | 4048 | 46.37% | -0.23 |
| 2020 | 4341 | 52.82% | 0.91 |

### Week - Bearish

Whole split: 19985 picks, accuracy 51.54%, edge 0.75 points, directional move after costs -0.13 points.

| Year | Picks | Accuracy | Edge (points) |
|---|---|---|---|
| 2015 | 2520 | 48.53% | 1.15 |
| 2016 | 2825 | 52.14% | 0.82 |
| 2017 | 2998 | 48.63% | 0.96 |
| 2018 | 4939 | 56.37% | 2.08 |
| 2019 | 3870 | 50.52% | -0.76 |
| 2020 | 2833 | 49.66% | 0.29 |
