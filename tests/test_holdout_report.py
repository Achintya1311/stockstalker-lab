import csv

import pandas as pd

from engine.holdout_report import (
    LEDGER_FIELDS,
    QUERY_ID,
    maybe_log_holdout_query,
    run_champion_v1_validation_query,
)
from strategies import champion_v1

N_WARMUP_DAYS = 20  # universe_membership's 20-day turnover window


def _series(symbol: str, dates: list[str], daily_move: float) -> list[dict]:
    rows = []
    prev_close = 100.0
    for d in dates:
        close = prev_close * (1.0 + daily_move)
        rows.append({
            "date": d, "symbol": symbol, "open": prev_close,
            "high": max(prev_close, close), "low": min(prev_close, close),
            "close": close, "prevclose": prev_close,
            "volume": 1_000_000.0 * (1.0 + daily_move),
            "turnover": close * 5_000_000.0,
            "has_future": True,
        })
        prev_close = close
    return rows


def _dataset_covering_train_and_validation():
    # Enough history past champion_v1.MIN_ROWS before 2021, and continuous
    # through the whole validation split (2021-01-01 to 2023-12-31).
    dates = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2015-01-01", "2023-12-31")]
    rows = []
    rows += _series("UP", dates, daily_move=0.01)
    rows += _series("DOWN", dates, daily_move=-0.01)
    return pd.DataFrame(rows)


def test_maybe_log_holdout_query_skips_when_columns_missing(tmp_path):
    minimal = pd.DataFrame({"date": ["2015-01-01"], "symbol": ["A"], "close": [1.0]})
    path = tmp_path / "holdout_queries.csv"
    assert maybe_log_holdout_query(minimal, path) is False
    assert not path.exists()


def test_maybe_log_holdout_query_skips_when_dataset_misses_validation_dates(tmp_path):
    dataset = _dataset_covering_train_and_validation()
    train_only = dataset[dataset["date"] <= "2020-12-31"]
    path = tmp_path / "holdout_queries.csv"
    assert maybe_log_holdout_query(train_only, path) is False
    assert not path.exists()


def test_run_champion_v1_validation_query_never_exposes_the_raw_holdout_value():
    dataset = _dataset_covering_train_and_validation()
    row = run_champion_v1_validation_query(dataset)
    assert set(row) == set(LEDGER_FIELDS)
    assert isinstance(row["train_value"], float)
    assert isinstance(row["released_value"], float)
    assert isinstance(row["budget_spent"], bool)
    assert row["query_id"] == QUERY_ID


def test_maybe_log_holdout_query_writes_one_row(tmp_path):
    dataset = _dataset_covering_train_and_validation()
    path = tmp_path / "holdout_queries.csv"
    assert maybe_log_holdout_query(dataset, path) is True
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["query_id"] == QUERY_ID


def test_maybe_log_holdout_query_is_idempotent(tmp_path):
    dataset = _dataset_covering_train_and_validation()
    path = tmp_path / "holdout_queries.csv"
    assert maybe_log_holdout_query(dataset, path) is True
    assert maybe_log_holdout_query(dataset, path) is False
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
