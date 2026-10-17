import csv

import pytest

from gates.trials import FIELDS, cumulative_trial_count, record_trial


def _row(**overrides) -> dict:
    base = {
        "trial_id": "champion_v1@1-day-bullish-train-001",
        "timestamp": "2026-10-17T12:00:00+00:00",
        "strategy_id": "champion_v1",
        "version": 1,
        "horizon": "day",
        "side": "bullish",
        "split": "train",
        "edge": 0.06,
        "t_stat": 3.2,
        "all_gates_passed": False,
        "notes": "first trial",
    }
    base.update(overrides)
    return base


def test_cumulative_trial_count_is_zero_before_any_trial(tmp_path):
    path = tmp_path / "trials.csv"
    assert cumulative_trial_count(path) == 0


def test_record_trial_requires_every_field(tmp_path):
    path = tmp_path / "trials.csv"
    incomplete = _row()
    del incomplete["edge"]
    with pytest.raises(ValueError):
        record_trial(incomplete, path)
    assert not path.exists()


def test_record_trial_appends_and_never_overwrites(tmp_path):
    path = tmp_path / "trials.csv"
    record_trial(_row(trial_id="t1"), path)
    record_trial(_row(trial_id="t2"), path)
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    assert [r["trial_id"] for r in rows] == ["t1", "t2"]
    assert set(rows[0]) == set(FIELDS)


def test_cumulative_trial_count_matches_row_count(tmp_path):
    path = tmp_path / "trials.csv"
    for i in range(3):
        record_trial(_row(trial_id=f"t{i}"), path)
    assert cumulative_trial_count(path) == 3
