# Engine self-test (B6, `state/queue.md`)

Train-split window 2018-01-01 to 2018-06-30 - far enough past the dataset's own
first 20 trading days for the 20-day turnover window to have a real
universe throughout, without replaying the whole split. Thresholds per
SPEC.md section 6 (leak alarm) and this item's acceptance (`state/queue.md`).

## Leak check

A strategy that reads the next trading day's already-realised close - not
through `history` (`truncate()` already proves that path withholds it; see
`tests/test_replay.py`), but through its own reference to the full dataset,
the realistic way a strategy module could leak - must trip the leak alarm
(accuracy >= 70.00% or edge >= 15.00 points).

| Picks | Accuracy | Edge (points) | Flagged |
|---|---|---|---|
| 9381 | 100.00% | 56.14 | YES |

Result: **PASS** - the leak alarm catches it.

## Random check

A strategy with no real signal - uniform random direction, independent of
the actual move - run over 5 seeds; its edge on each side
must stay within +-1.50 points of zero.

| Seed | Bull edge | Bear edge | Within tolerance |
|---|---|---|---|
| 0 | -0.17 | -0.21 | YES |
| 1 | -0.21 | -0.26 | YES |
| 2 | -0.26 | -0.21 | YES |
| 3 | 0.01 | -0.02 | YES |
| 4 | 0.16 | 0.14 | YES |

Result: **PASS**
