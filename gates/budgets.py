"""Weekly budgets for validation Thresholdout queries and test looks (B8,
`state/queue.md`: "budgets in the ledger (`ledger/holdout_queries.csv`,
`ledger/test_looks.csv`)").

SPEC.md section 4 fixes both caps in `config/splits.yml`:
"Validation ... at most 60 queries a week" (`max_queries_per_week`) and
"Test ... at most 2 looks a week, every look logged in
`ledger/test_looks.csv`" (`max_looks_per_week`). `engine.holdout_report`
already logs B7's one validation query directly into
`ledger/holdout_queries.csv` without a budget check (its own docstring:
"the weekly budget and repeat-query machinery is B8's job"); this module is
that reusable budget, for the `evaluate` lane (SPEC.md section 9) to
consult before spending a query or a look, and for `ledger/test_looks.csv`,
which nothing has written to yet.

"A week" is the ISO calendar week (Monday-Sunday) the timestamp falls in,
not a rolling 7-day window - the same week definition `engine.scoring.week_moves`
already uses for week-horizon picks, and the one SPEC.md section 7 implies
("Roster changes happen on Sundays only" - a week-shaped cadence).
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from engine.replay import load_splits

HOLDOUT_LEDGER = Path("ledger/holdout_queries.csv")
TEST_LOOKS_LEDGER = Path("ledger/test_looks.csv")

TEST_LOOK_FIELDS = [
    "look_id",
    "timestamp",
    "strategy_id",
    "version",
    "horizon",
    "side",
    "metric",
    "value",
    "notes",
]


def _iso_week(ts: pd.Timestamp) -> tuple[int, int]:
    iso = ts.isocalendar()
    return int(iso.year), int(iso.week)


def _count_in_same_iso_week(path: Path, now: pd.Timestamp) -> int:
    if not path.exists() or path.stat().st_size == 0:
        return 0
    df = pd.read_csv(path)
    if df.empty or "timestamp" not in df.columns:
        return 0
    week = _iso_week(now)
    timestamps = pd.to_datetime(df["timestamp"], utc=True)
    return int(sum(1 for ts in timestamps if _iso_week(ts) == week))


def _now(now: pd.Timestamp | None) -> pd.Timestamp:
    return now if now is not None else pd.Timestamp.now(tz="UTC")


def holdout_queries_this_week(now: pd.Timestamp | None = None, path: Path = HOLDOUT_LEDGER) -> int:
    return _count_in_same_iso_week(path, _now(now))


def holdout_budget_remaining(
    now: pd.Timestamp | None = None, splits: dict | None = None, path: Path = HOLDOUT_LEDGER
) -> int:
    splits = splits if splits is not None else load_splits()
    cap = int(splits["validation"]["max_queries_per_week"])
    return max(0, cap - holdout_queries_this_week(now, path))


def can_spend_holdout_query(
    now: pd.Timestamp | None = None, splits: dict | None = None, path: Path = HOLDOUT_LEDGER
) -> bool:
    return holdout_budget_remaining(now, splits, path) > 0


def test_looks_this_week(now: pd.Timestamp | None = None, path: Path = TEST_LOOKS_LEDGER) -> int:
    return _count_in_same_iso_week(path, _now(now))


def test_look_budget_remaining(
    now: pd.Timestamp | None = None, splits: dict | None = None, path: Path = TEST_LOOKS_LEDGER
) -> int:
    splits = splits if splits is not None else load_splits()
    cap = int(splits["test"]["max_looks_per_week"])
    return max(0, cap - test_looks_this_week(now, path))


def can_take_test_look(
    now: pd.Timestamp | None = None, splits: dict | None = None, path: Path = TEST_LOOKS_LEDGER
) -> bool:
    return test_look_budget_remaining(now, splits, path) > 0


def record_test_look(row: dict, path: Path = TEST_LOOKS_LEDGER) -> None:
    """Append one test-look row. Callers must call `can_take_test_look` first
    and only look at test-split data at all if it returns True - this
    function only logs the look, it does not gate it."""
    missing = set(TEST_LOOK_FIELDS) - set(row)
    if missing:
        raise ValueError(f"test-look row missing required field(s): {sorted(missing)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TEST_LOOK_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow({k: row[k] for k in TEST_LOOK_FIELDS})
