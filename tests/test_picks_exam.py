import json

from strategies import champion_v1
from tests._picks_dataset import make_dataset, trading_dates

from picks.exam import EXAM_START, run_exam_backfill

SOURCE = {
    "tables": {
        "day_bullish": {"strategy": "champion_v1@v1", "label": "provisional", "why": "x"},
        "day_bearish": {"strategy": "champion_v1@v1", "label": "provisional", "why": "x"},
        "week_bullish": {"strategy": "champion_v1@v1", "label": "provisional", "why": "x"},
        "week_bearish": {"strategy": "champion_v1@v1", "label": "provisional", "why": "x"},
    }
}


def _dataset():
    # 2026-05-01 .. 2026-09-03: 66 rows (well over MIN_ROWS) before the exam
    # split opens on 2026-08-01, then on into it.
    dates = trading_dates(90, start="2026-05-01")
    assert dates[0] < EXAM_START < dates[-1]
    return make_dataset({"UP": 0.01, "DOWN": -0.01}, dates), dates


def test_run_exam_backfill_only_writes_dates_inside_the_exam_split(tmp_path):
    dataset, dates = _dataset()
    out_dir = tmp_path / "exam"
    n_written = run_exam_backfill(dataset, SOURCE, out_dir, "2026-09-03T12:00:00Z")
    assert n_written > 0

    day_files = sorted((out_dir / "day").glob("*.json"))
    assert day_files
    for f in day_files:
        assert f.stem >= EXAM_START

    week_files = sorted((out_dir / "week").glob("*.json"))
    assert week_files
    for f in week_files:
        assert f.stem >= EXAM_START


def test_run_exam_backfill_picks_are_already_scored(tmp_path):
    dataset, dates = _dataset()
    out_dir = tmp_path / "exam"
    run_exam_backfill(dataset, SOURCE, out_dir, "2026-09-03T12:00:00Z")

    day_files = sorted((out_dir / "day").glob("*.json"))
    data = json.loads(day_files[0].read_text())
    assert data["tables"]["bullish"], "UP should be picked bullish on at least one exam day"
    for pick in data["tables"]["bullish"]:
        assert "hit" in pick and "move_pct" in pick


def test_run_exam_backfill_follows_the_configured_strategy_direction(tmp_path):
    dataset, dates = _dataset()
    out_dir = tmp_path / "exam"
    run_exam_backfill(dataset, SOURCE, out_dir, "2026-09-03T12:00:00Z")

    day_files = sorted((out_dir / "day").glob("*.json"))
    any_bullish_up = any(
        any(p["symbol"] == "UP" for p in json.loads(f.read_text())["tables"]["bullish"]) for f in day_files
    )
    any_bearish_down = any(
        any(p["symbol"] == "DOWN" for p in json.loads(f.read_text())["tables"]["bearish"]) for f in day_files
    )
    assert any_bullish_up
    assert any_bearish_down
