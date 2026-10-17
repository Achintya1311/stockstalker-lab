import csv

import pandas as pd
import pytest

from gates.budgets import (
    TEST_LOOK_FIELDS,
    can_spend_holdout_query,
    can_take_test_look,
    holdout_budget_remaining,
    holdout_queries_this_week,
    record_test_look,
)
# Aliased: these two names start with "test_", so importing them under their
# real names gets them collected by pytest as test functions in their own
# right (called with no args during collection, which just silently exercises
# the real ledger path and warns - see PytestReturnNotNoneWarning).
from gates.budgets import test_look_budget_remaining as look_budget_remaining
from gates.budgets import test_looks_this_week as looks_this_week

SPLITS = {
    "validation": {"start": "2021-01-01", "end": "2023-12-31", "max_queries_per_week": 2},
    "test": {"start": "2024-01-01", "end": "2026-07-31", "max_looks_per_week": 1},
}

# A Thursday, so "same ISO week" has both earlier-in-week and later-in-week neighbours.
NOW = pd.Timestamp("2026-10-15T12:00:00Z")


def _write_ledger(path, timestamps):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp"])
        writer.writeheader()
        for ts in timestamps:
            writer.writerow({"timestamp": ts})


def test_holdout_queries_this_week_counts_only_the_current_iso_week(tmp_path):
    path = tmp_path / "holdout_queries.csv"
    _write_ledger(
        path,
        [
            "2026-10-12T00:00:00Z",  # Monday of the same ISO week as NOW
            "2026-10-16T00:00:00Z",  # Friday, same week
            "2026-10-11T23:59:00Z",  # Sunday, previous ISO week
            "2026-10-19T00:00:00Z",  # Monday, next ISO week
        ],
    )
    assert holdout_queries_this_week(NOW, path) == 2


def test_holdout_queries_this_week_is_zero_for_a_missing_ledger(tmp_path):
    path = tmp_path / "does_not_exist.csv"
    assert holdout_queries_this_week(NOW, path) == 0


def test_holdout_budget_remaining_and_can_spend(tmp_path):
    path = tmp_path / "holdout_queries.csv"
    _write_ledger(path, ["2026-10-12T00:00:00Z", "2026-10-13T00:00:00Z"])  # 2 this week, cap is 2
    assert holdout_budget_remaining(NOW, SPLITS, path) == 0
    assert can_spend_holdout_query(NOW, SPLITS, path) is False

    _write_ledger(path, ["2026-10-12T00:00:00Z"])  # 1 this week, cap is 2
    assert holdout_budget_remaining(NOW, SPLITS, path) == 1
    assert can_spend_holdout_query(NOW, SPLITS, path) is True


def test_holdout_budget_remaining_never_goes_negative(tmp_path):
    path = tmp_path / "holdout_queries.csv"
    _write_ledger(path, ["2026-10-12T00:00:00Z"] * 5)  # over the cap of 2
    assert holdout_budget_remaining(NOW, SPLITS, path) == 0


def test_test_look_budget_tracks_its_own_cap_and_ledger(tmp_path):
    path = tmp_path / "test_looks.csv"
    assert looks_this_week(NOW, path) == 0
    assert can_take_test_look(NOW, SPLITS, path) is True  # cap is 1, nothing spent yet

    row = {k: "x" for k in TEST_LOOK_FIELDS}
    row["timestamp"] = "2026-10-13T00:00:00Z"
    record_test_look(row, path)

    assert looks_this_week(NOW, path) == 1
    assert look_budget_remaining(NOW, SPLITS, path) == 0
    assert can_take_test_look(NOW, SPLITS, path) is False


def test_record_test_look_requires_every_field(tmp_path):
    path = tmp_path / "test_looks.csv"
    incomplete = {k: "x" for k in TEST_LOOK_FIELDS if k != "metric"}
    with pytest.raises(ValueError):
        record_test_look(incomplete, path)
    assert not path.exists()


def test_record_test_look_appends_header_once(tmp_path):
    path = tmp_path / "test_looks.csv"
    row = {k: "x" for k in TEST_LOOK_FIELDS}
    record_test_look({**row, "timestamp": "2026-10-13T00:00:00Z"}, path)
    record_test_look({**row, "timestamp": "2026-10-14T00:00:00Z"}, path)
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert set(rows[0]) == set(TEST_LOOK_FIELDS)
