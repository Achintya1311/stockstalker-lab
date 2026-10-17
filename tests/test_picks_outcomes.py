import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from picks.outcomes import (
    day_session_available,
    first_commit_time,
    is_late,
    mark_late,
    score_picks_file,
    week_session_available,
)

IST = ZoneInfo("Asia/Kolkata")


def _day_dataset():
    return pd.DataFrame(
        [
            {"date": "2026-10-19", "symbol": "AAA", "open": 100.0, "close": 110.0},
            {"date": "2026-10-19", "symbol": "BBB", "open": 100.0, "close": 90.0},
        ]
    )


def test_day_session_available_true_once_the_date_is_in_the_dataset():
    assert day_session_available(_day_dataset(), "2026-10-19") is True
    assert day_session_available(_day_dataset(), "2026-10-20") is False


def _week_dataset():
    rows = []
    for d, o, c in [
        ("2026-10-19", 100.0, 101.0),
        ("2026-10-20", 101.0, 102.0),
        ("2026-10-21", 102.0, 103.0),
        ("2026-10-22", 103.0, 104.0),
        ("2026-10-23", 104.0, 108.0),  # Friday close
    ]:
        rows.append({"date": d, "symbol": "AAA", "open": o, "close": c})
    return pd.DataFrame(rows)


def test_week_session_available_false_while_the_week_is_still_in_progress():
    dataset = _week_dataset()
    in_progress = dataset[dataset["date"] <= "2026-10-21"]  # only through Wednesday
    assert week_session_available(in_progress, "2026-10-19") is False


def test_week_session_available_true_once_a_later_iso_week_is_in_the_data():
    dataset = pd.concat([_week_dataset(), pd.DataFrame([{"date": "2026-10-26", "symbol": "AAA", "open": 1.0, "close": 1.0}])])
    assert week_session_available(dataset, "2026-10-19") is True


def test_score_picks_file_day_arithmetic_matches_a_hand_computed_example():
    data = {
        "horizon": "day",
        "session": "2026-10-19",
        "tables": {
            "bullish": [{"symbol": "AAA", "strategy": "x", "reasoning": "r"}],
            "bearish": [{"symbol": "BBB", "strategy": "x", "reasoning": "r"}],
        },
    }
    changed = score_picks_file(data, _day_dataset())
    assert changed is True

    bullish = data["tables"]["bullish"][0]
    assert bullish["open"] == 100.0 and bullish["close"] == 110.0
    assert bullish["move_pct"] == pytest.approx(10.0)
    assert bullish["move_rs"] == pytest.approx(10.0)
    assert bullish["hit"] is True  # rose, picked bullish

    bearish = data["tables"]["bearish"][0]
    assert bearish["move_pct"] == pytest.approx(-10.0)
    assert bearish["hit"] is True  # fell, picked bearish


def test_score_picks_file_flat_move_is_always_a_miss():
    data = {
        "horizon": "day",
        "session": "2026-10-19",
        "tables": {"bullish": [{"symbol": "FLAT", "strategy": "x", "reasoning": "r"}]},
    }
    flat = pd.DataFrame([{"date": "2026-10-19", "symbol": "FLAT", "open": 100.0, "close": 100.0}])
    score_picks_file(data, flat)
    assert data["tables"]["bullish"][0]["hit"] is False


def test_score_picks_file_week_arithmetic_uses_mondays_open_and_fridays_close():
    data = {
        "horizon": "week",
        "session": "2026-10-19",
        "tables": {"bullish": [{"symbol": "AAA", "strategy": "x", "reasoning": "r"}]},
    }
    # A later ISO week's row must already be in the dataset, or the week
    # isn't provably complete yet (see week_session_available's own tests).
    dataset = pd.concat(
        [_week_dataset(), pd.DataFrame([{"date": "2026-10-26", "symbol": "AAA", "open": 1.0, "close": 1.0}])]
    )
    changed = score_picks_file(data, dataset)
    assert changed is True
    pick = data["tables"]["bullish"][0]
    assert pick["open"] == 100.0 and pick["close"] == 108.0
    assert pick["move_pct"] == pytest.approx(8.0)
    assert pick["hit"] is True


def test_score_picks_file_no_op_when_outcome_not_yet_available():
    data = {
        "horizon": "day",
        "session": "2026-10-20",
        "tables": {"bullish": [{"symbol": "AAA", "strategy": "x", "reasoning": "r"}]},
    }
    assert score_picks_file(data, _day_dataset()) is False
    assert "hit" not in data["tables"]["bullish"][0]


def test_score_picks_file_is_idempotent_once_already_scored():
    data = {
        "horizon": "day",
        "session": "2026-10-19",
        "tables": {"bullish": [{"symbol": "AAA", "strategy": "x", "reasoning": "r"}]},
    }
    score_picks_file(data, _day_dataset())
    data["tables"]["bullish"][0]["hit"] = "untouched-sentinel"  # prove a second pass leaves it alone
    changed_again = score_picks_file(data, _day_dataset())
    assert changed_again is False
    assert data["tables"]["bullish"][0]["hit"] == "untouched-sentinel"


def _init_repo_with_committed_file(tmp_path: Path, commit_iso: str) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True)
    picks_file = repo / "day" / "2026-10-19.json"
    picks_file.parent.mkdir()
    picks_file.write_text("{}")
    import os

    env = {**os.environ, "GIT_AUTHOR_DATE": commit_iso, "GIT_COMMITTER_DATE": commit_iso}
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "add"], cwd=repo, check=True, env=env)
    return picks_file


def test_first_commit_time_reads_the_commit_that_added_the_file(tmp_path):
    picks_file = _init_repo_with_committed_file(tmp_path, "2026-10-19T08:00:00+05:30")
    commit_time = first_commit_time(picks_file, repo_root=tmp_path / "repo")
    assert commit_time.astimezone(IST).isoformat() == "2026-10-19T08:00:00+05:30"


def test_first_commit_time_none_for_an_uncommitted_file(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    uncommitted = repo / "day" / "2026-10-19.json"
    uncommitted.parent.mkdir()
    uncommitted.write_text("{}")
    assert first_commit_time(uncommitted, repo_root=repo) is None


def test_mark_late_sets_true_for_a_commit_after_the_cutoff(tmp_path):
    picks_file = _init_repo_with_committed_file(tmp_path, "2026-10-19T09:30:00+05:30")
    data = {"session": "2026-10-19", "tables": {"bullish": [{"symbol": "AAA"}]}}
    changed = mark_late(data, picks_file, repo_root=tmp_path / "repo")
    assert changed is True
    assert data["tables"]["bullish"][0]["late"] is True


def test_mark_late_sets_false_for_a_commit_before_the_cutoff(tmp_path):
    picks_file = _init_repo_with_committed_file(tmp_path, "2026-10-19T08:00:00+05:30")
    data = {"session": "2026-10-19", "tables": {"bullish": [{"symbol": "AAA"}]}}
    mark_late(data, picks_file, repo_root=tmp_path / "repo")
    assert data["tables"]["bullish"][0]["late"] is False


def test_is_late_false_right_at_the_cutoff_and_true_just_after():
    before = datetime.fromisoformat("2026-10-19T09:14:59+05:30")
    at_cutoff = datetime.fromisoformat("2026-10-19T09:15:00+05:30")
    after = datetime.fromisoformat("2026-10-19T09:15:01+05:30")
    assert is_late(before, "2026-10-19") is False
    assert is_late(at_cutoff, "2026-10-19") is False
    assert is_late(after, "2026-10-19") is True


def test_mark_late_is_a_no_op_when_commit_time_is_unknown(tmp_path):
    data = {"session": "2026-10-19", "tables": {"bullish": [{"symbol": "AAA"}]}}
    never_committed = tmp_path / "day" / "2026-10-19.json"
    assert mark_late(data, never_committed) is False
    assert "late" not in data["tables"]["bullish"][0]
