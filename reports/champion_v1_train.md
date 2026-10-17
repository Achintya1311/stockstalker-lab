# Champion v1 train results (B7, `state/queue.md`)

`strategies/champion_v1.py` - the current StockStalker blended score (trend 0.4 / momentum 0.35 / volume 0.25) - run through the real replay engine on the train split (2015-01-01 to 2020-12-31), day and week, split into bullish (score > 0) and bearish (score < 0) picks. Definitions per SPEC.md section 3; gates per SPEC.md section 6 are checked on test, not here - this is the train-split baseline before any validation look.

## Day

### Day - Bullish

Whole split: 107754 picks, accuracy 44.56%, edge -0.11 points, directional move after costs -0.54 points.

| Year | Picks | Accuracy | Edge (points) |
|---|---|---|---|
| 2015 | 8800 | 43.02% | -0.51 |
| 2016 | 16056 | 45.66% | -0.53 |
| 2017 | 24552 | 43.92% | 0.18 |
| 2018 | 18615 | 44.46% | 0.12 |
| 2019 | 18707 | 43.97% | 0.25 |
| 2020 | 21024 | 45.70% | -0.25 |

### Day - Bearish

Whole split: 95004 picks, accuracy 53.95%, edge 0.19 points, directional move after costs -0.12 points.

| Year | Picks | Accuracy | Edge (points) |
|---|---|---|---|
| 2015 | 12060 | 54.10% | -0.03 |
| 2016 | 13584 | 53.89% | -0.28 |
| 2017 | 14099 | 54.49% | 0.20 |
| 2018 | 23300 | 53.87% | 0.50 |
| 2019 | 18483 | 53.30% | -0.11 |
| 2020 | 13478 | 54.38% | 0.82 |

## Week

### Week - Bullish

Whole split: 22799 picks, accuracy 48.80%, edge 0.07 points, directional move after costs -0.53 points.

| Year | Picks | Accuracy | Edge (points) |
|---|---|---|---|
| 2015 | 1814 | 49.17% | -0.59 |
| 2016 | 3437 | 49.14% | -1.27 |
| 2017 | 5068 | 50.00% | 0.34 |
| 2018 | 4091 | 45.03% | 1.11 |
| 2019 | 4048 | 46.37% | -0.23 |
| 2020 | 4341 | 52.82% | 0.91 |

### Week - Bearish

Whole split: 19987 picks, accuracy 51.54%, edge 0.75 points, directional move after costs -0.13 points.

| Year | Picks | Accuracy | Edge (points) |
|---|---|---|---|
| 2015 | 2521 | 48.55% | 1.17 |
| 2016 | 2825 | 52.14% | 0.82 |
| 2017 | 2998 | 48.63% | 0.96 |
| 2018 | 4939 | 56.37% | 2.08 |
| 2019 | 3870 | 50.52% | -0.76 |
| 2020 | 2834 | 49.65% | 0.28 |
