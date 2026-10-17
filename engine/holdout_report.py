"""B7's "then validation" step (`state/queue.md`): the one real Thresholdout
query (`engine.holdout`) over champion v1's validation-split edge, logged as
the one row `ledger/holdout_queries.csv` needs.

Query: champion v1's day-horizon, bullish-side edge over the market line
(SPEC.md section 3) - the first table in `reports/champion_v1_train.md` -
computed on train (unlimited looks, SPEC.md section 4) and compared against
the same statistic on the validation split (2021-01-01 to 2023-12-31, the
true holdout, `config/splits.yml`) through one `engine.holdout.thresholdout_query`
call. Only `train_value` and `released_value` are ever written anywhere -
the true validation-split edge is computed, used once inside that one call,
and discarded; writing it to the ledger would defeat the point of asking
through a noise mechanism at all.

This logs at most once: a second query onward is B8's job (the weekly
budget and repeat-query machinery `state/queue.md` describes), not this
module's. `maybe_log_holdout_query` is idempotent against a ledger that
already carries this query's id, so a push that re-triggers `replay.yml`
without the ledger having been reset can't silently add a second,
un-budgeted query.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from engine.champion_report import REQUIRED_COLUMNS, TRAIN_END, TRAIN_START, horizon_results
from engine.holdout import thresholdout_query

VALIDATION_START, VALIDATION_END = "2021-01-01", "2023-12-31"
QUERY_ID = "champion_v1-day-bullish-edge-v1"
# 3 points of train/holdout disagreement is tolerated as noise, not overfitting
# signal; both Laplace draws use a 1-point scale. Provisional - B8 revisits
# these once the full gate/budget machinery sets them from the gates in
# SPEC.md section 6 rather than a first, standalone query picking round numbers.
THRESHOLD = 0.03
TOLERANCE = 0.01
LEDGER_PATH = Path("ledger/holdout_queries.csv")
LEDGER_FIELDS = [
    "query_id",
    "timestamp",
    "metric",
    "horizon",
    "side",
    "threshold",
    "tolerance",
    "train_value",
    "released_value",
    "budget_spent",
]


def _already_logged(path: Path, query_id: str) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    with open(path, newline="") as f:
        return any(row.get("query_id") == query_id for row in csv.DictReader(f))


def run_champion_v1_validation_query(dataset: pd.DataFrame) -> dict:
    """Compute and answer the one query, without writing anything.

    Split out from `maybe_log_holdout_query` so tests can check the computed
    values directly, without touching the filesystem.
    """
    train_value = horizon_results(dataset, "day", TRAIN_START, TRAIN_END, split="train")[1]["edge"]
    holdout_value = horizon_results(
        dataset, "day", VALIDATION_START, VALIDATION_END, split="validation"
    )[1]["edge"]
    answer = thresholdout_query(train_value, holdout_value, threshold=THRESHOLD, tolerance=TOLERANCE)
    return {
        "query_id": QUERY_ID,
        "timestamp": pd.Timestamp.now(tz="UTC").isoformat(),
        "metric": "edge",
        "horizon": "day",
        "side": "bullish",
        "threshold": THRESHOLD,
        "tolerance": TOLERANCE,
        "train_value": answer.train_value,
        "released_value": answer.released_value,
        "budget_spent": answer.budget_spent,
    }


def maybe_log_holdout_query(dataset: pd.DataFrame, path: Path = LEDGER_PATH) -> bool:
    """Append the one query's row iff `dataset` carries every column the
    query needs, covers both the train and validation splits, and hasn't
    already been logged. Returns whether a row was written."""
    if not REQUIRED_COLUMNS.issubset(dataset.columns):
        return False
    dates = dataset["date"]
    covers_train = ((dates >= TRAIN_START) & (dates <= TRAIN_END)).any()
    covers_validation = ((dates >= VALIDATION_START) & (dates <= VALIDATION_END)).any()
    if not (covers_train and covers_validation):
        return False
    if _already_logged(path, QUERY_ID):
        return False

    row = run_champion_v1_validation_query(dataset)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LEDGER_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)
    return True
