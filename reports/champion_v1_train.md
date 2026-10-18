# Champion v1 train results (B7, `state/queue.md`)

`strategies/champion_v1.py` - the current StockStalker blended score (trend 0.4 / momentum 0.35 / volume 0.25) - run through the real replay engine on the train split (2015-01-01 to 2020-12-31), day and week, split into bullish (score > 0) and bearish (score < 0) picks. Definitions per SPEC.md section 3; gates per SPEC.md section 6 are checked on test, not here - this is the train-split baseline before any validation look.

## Day

### Day - Bullish

Whole split: 107821 picks, accuracy 44.47%, edge -0.10 points, directional move after costs -0.54 points.

| Year | Picks | Accuracy | Edge (points) |
|---|---|---|---|
| 2015 | 8872 | 43.05% | -0.40 |
| 2016 | 16092 | 45.52% | -0.56 |
| 2017 | 24546 | 43.92% | 0.16 |
| 2018 | 18615 | 44.46% | 0.12 |
| 2019 | 18837 | 43.88% | 0.28 |
| 2020 | 20859 | 45.48% | -0.25 |

### Day - Bearish

Whole split: 95503 picks, accuracy 54.00%, edge 0.15 points, directional move after costs -0.12 points.

| Year | Picks | Accuracy | Edge (points) |
|---|---|---|---|
| 2015 | 12099 | 54.18% | 0.03 |
| 2016 | 13637 | 53.90% | -0.33 |
| 2017 | 14090 | 54.47% | 0.18 |
| 2018 | 23300 | 53.87% | 0.50 |
| 2019 | 18465 | 53.32% | -0.09 |
| 2020 | 13912 | 54.61% | 0.59 |

## Week

### Week - Bullish

Whole split: 22760 picks, accuracy 48.82%, edge 0.12 points, directional move after costs -0.53 points.

| Year | Picks | Accuracy | Edge (points) |
|---|---|---|---|
| 2015 | 1876 | 48.99% | -0.35 |
| 2016 | 3420 | 49.27% | -1.45 |
| 2017 | 5072 | 50.02% | 0.36 |
| 2018 | 4091 | 45.03% | 1.11 |
| 2019 | 4046 | 46.39% | -0.25 |
| 2020 | 4255 | 52.90% | 1.18 |

### Week - Bearish

Whole split: 20123 picks, accuracy 51.58%, edge 0.74 points, directional move after costs -0.12 points.

| Year | Picks | Accuracy | Edge (points) |
|---|---|---|---|
| 2015 | 2571 | 48.93% | 1.25 |
| 2016 | 2831 | 51.96% | 0.71 |
| 2017 | 2994 | 48.66% | 0.97 |
| 2018 | 4939 | 56.37% | 2.08 |
| 2019 | 3869 | 50.40% | -0.73 |
| 2020 | 2919 | 49.98% | 0.23 |
