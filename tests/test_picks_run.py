import json
from pathlib import Path

import pandas as pd
from strategies import champion_v1
from tests._picks_dataset import make_dataset

from picks.run import run
from picks.source import LIVE_SOURCE_PATH

N_ROWS = champion_v1.MIN_ROWS + 15


def _dates_ending(end: str) -> list[str]:
    return list(pd.bdate_range(end=end, periods=N_ROWS).strftime("%Y-%m-%d"))


def _write_parquet(tmp_path, dataset: pd.DataFrame) -> Path:
    path = tmp_path / "dataset.parquet"
    dataset.to_parquet(path, index=False)
    return path


def _no_source(tmp_path):
    # A missing source in a temp dir (and no draft beside it), so dry runs here test the
    # champion v1 fallback whatever the real config/ holds.
    return tmp_path / "no-config" / "live_source.json"


def test_run_writes_day_picks_for_the_next_session_across_a_real_holiday(tmp_path):
    # Monday 2026-10-19 -> Dussehra on Tuesday 2026-10-20 (config/nse_holidays.txt)
    # -> the real next trading session is Wednesday 2026-10-21.
    dates = _dates_ending("2026-10-19")
    dataset = make_dataset({"UP": 0.01, "DOWN": -0.01}, dates)
    data_path = _write_parquet(tmp_path, dataset)
    out_dir = tmp_path / "out"

    run(data_path, out_dir, mode="dry", source_path=_no_source(tmp_path))

    picks_path = out_dir / "day" / "2026-10-21.json"
    assert picks_path.exists()
    data = json.loads(picks_path.read_text())
    assert data["asof"] == "2026-10-19"
    assert data["label"] == "provisional"  # no config/live_source.json -> dry fallback
    assert [p["symbol"] for p in data["tables"]["bullish"]] == ["UP"]
    assert [p["symbol"] for p in data["tables"]["bearish"]] == ["DOWN"]
    assert "hit" not in data["tables"]["bullish"][0]  # outcome not known yet
    assert not (out_dir / "week").exists()  # 2026-10-21 is still the same ISO week as 2026-10-19


def test_run_also_writes_week_picks_on_the_weeks_last_trading_day(tmp_path):
    # Friday 2026-10-16 -> Monday 2026-10-19 starts a new ISO week.
    dates = _dates_ending("2026-10-16")
    dataset = make_dataset({"UP": 0.01, "DOWN": -0.01}, dates)
    data_path = _write_parquet(tmp_path, dataset)
    out_dir = tmp_path / "out"

    run(data_path, out_dir, mode="dry", source_path=_no_source(tmp_path))

    assert (out_dir / "day" / "2026-10-19.json").exists()
    week_path = out_dir / "week" / "2026-10-19.json"
    assert week_path.exists()
    week_data = json.loads(week_path.read_text())
    assert week_data["horizon"] == "week"


def test_run_is_idempotent_and_never_overwrites_an_existing_picks_file(tmp_path):
    dates = _dates_ending("2026-10-19")
    dataset = make_dataset({"UP": 0.01, "DOWN": -0.01}, dates)
    data_path = _write_parquet(tmp_path, dataset)
    out_dir = tmp_path / "out"

    run(data_path, out_dir, mode="dry", source_path=_no_source(tmp_path))
    picks_path = out_dir / "day" / "2026-10-21.json"
    first_content = picks_path.read_text()

    run(data_path, out_dir, mode="dry", source_path=_no_source(tmp_path))  # same dataset, same asof/session
    assert picks_path.read_text() == first_content


def test_run_scores_an_earlier_days_picks_once_its_outcome_lands_in_the_dataset(tmp_path):
    dates = _dates_ending("2026-10-19")
    dataset = make_dataset({"UP": 0.01, "DOWN": -0.01}, dates)
    data_path = _write_parquet(tmp_path, dataset)
    out_dir = tmp_path / "out"

    run(data_path, out_dir, mode="dry", source_path=_no_source(tmp_path))  # writes day/2026-10-21.json, unscored

    # A later dry run, after the dataset has grown to include 2026-10-21's
    # own close (what a real `dataset.yml` update after that session would do).
    next_day = make_dataset({"UP": 0.01, "DOWN": -0.01}, dates + ["2026-10-21"])
    data_path_2 = _write_parquet(tmp_path, next_day)
    run(data_path_2, out_dir, mode="dry", source_path=_no_source(tmp_path))

    scored = json.loads((out_dir / "day" / "2026-10-21.json").read_text())
    assert scored["tables"]["bullish"][0]["hit"] is True  # UP kept rising
    assert "move_pct" in scored["tables"]["bullish"][0]

    # And a new next-session pick was written for the day after that.
    assert (out_dir / "day" / "2026-10-22.json").exists()


def test_run_live_mode_does_nothing_when_live_source_is_missing(tmp_path):
    # Relies on the real repo not yet carrying config/live_source.json
    # (SPEC.md section 10: committed by Fri 30 Oct, not yet). Confirmed by
    # the default LIVE_SOURCE_PATH itself, so this test stays honest if
    # that file is ever added for real.
    assert not LIVE_SOURCE_PATH.exists()

    dates = _dates_ending("2026-10-19")
    dataset = make_dataset({"UP": 0.01}, dates)
    data_path = _write_parquet(tmp_path, dataset)
    out_dir = tmp_path / "out"

    run(data_path, out_dir, mode="live")

    assert not out_dir.exists()


def test_run_live_mode_runs_the_one_time_exam_backfill_when_a_source_is_given(tmp_path):
    dates = list(pd.bdate_range("2026-05-01", periods=90).strftime("%Y-%m-%d"))
    dataset = make_dataset({"UP": 0.01, "DOWN": -0.01}, dates)
    data_path = _write_parquet(tmp_path, dataset)
    out_dir = tmp_path / "out"

    source_path = tmp_path / "live_source.json"
    source_path.write_text(
        json.dumps(
            {
                "chosen_on": "2026-08-31",
                "tables": {
                    k: {"strategy": "champion_v1@v1", "label": "provisional", "why": "x"}
                    for k in ("day_bullish", "day_bearish", "week_bullish", "week_bearish")
                },
            }
        )
    )

    run(data_path, out_dir, mode="live", source_path=source_path)

    exam_day_files = list((out_dir / "exam" / "day").glob("*.json"))
    assert exam_day_files
    assert all("hit" in p for f in exam_day_files for picks in json.loads(f.read_text())["tables"].values() for p in picks)

    # Second live run: exam/ already exists, so it must not be touched again.
    first_mtime = exam_day_files[0].stat().st_mtime_ns
    run(data_path, out_dir, mode="live", source_path=source_path)
    assert exam_day_files[0].stat().st_mtime_ns == first_mtime


def test_run_writes_a_summary_json(tmp_path):
    dates = _dates_ending("2026-10-19")
    dataset = make_dataset({"UP": 0.01, "DOWN": -0.01}, dates)
    data_path = _write_parquet(tmp_path, dataset)
    out_dir = tmp_path / "out"

    run(data_path, out_dir, mode="dry", source_path=_no_source(tmp_path))

    summary = json.loads((out_dir / "summary.json").read_text())
    assert "live" in summary and "exam" in summary
    assert summary["live"]["day_bullish"]["n_picks"] == 1


def test_run_with_no_dataset_does_nothing(tmp_path):
    out_dir = tmp_path / "out"
    run(tmp_path / "missing.parquet", out_dir, mode="dry", source_path=_no_source(tmp_path))
    assert not out_dir.exists()
