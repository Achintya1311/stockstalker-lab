import json
import sys

import pandas as pd
import pytest
import yaml

from engine.run_queue import main, pick_dates_for_horizon, run_experiment
from engine.replay import SplitViolation

SPLITS = {"train": {"start": "2015-01-01", "end": "2020-12-31"}}


def test_pick_dates_for_horizon_day_keeps_every_trading_date():
    dates = ["2015-01-01", "2015-01-02", "2015-01-05", "2015-01-06"]  # Thu, Fri, Mon, Tue
    out = pick_dates_for_horizon(dates, "2015-01-01", "2015-01-06", "day")
    assert out == dates


def test_pick_dates_for_horizon_week_keeps_only_the_first_trading_day_of_each_iso_week():
    # 2015-01-01/02 fall in ISO week 1; 05/06/07 fall in ISO week 2.
    dates = ["2015-01-01", "2015-01-02", "2015-01-05", "2015-01-06", "2015-01-07"]
    out = pick_dates_for_horizon(dates, "2015-01-01", "2015-01-07", "week")
    assert out == ["2015-01-01", "2015-01-05"]


def test_pick_dates_for_horizon_rejects_unknown_horizon():
    with pytest.raises(ValueError):
        pick_dates_for_horizon(["2015-01-01"], "2015-01-01", "2015-01-01", "month")


def _write_strategy_module(tmp_path, monkeypatch, always_bullish=True):
    monkeypatch.syspath_prepend(str(tmp_path))
    code = (
        "import pandas as pd\n\n"
        "def score(history):\n"
        "    symbols = history['symbol'].unique()\n"
        f"    value = 1.0 if {always_bullish} else float('nan')\n"
        "    return pd.Series([value] * len(symbols), index=symbols)\n"
    )
    (tmp_path / "dummy_strategy.py").write_text(code)


def _dataset():
    dates = ["2015-01-01", "2015-01-02", "2015-01-05", "2015-01-06"]
    rows = []
    for d in dates:
        for sym in ("AAA", "BBB"):
            rows.append({"date": d, "symbol": sym, "close": 100.0})
    return pd.DataFrame(rows)


def test_run_experiment_produces_hashed_picks_only_for_authorised_dates(tmp_path, monkeypatch):
    _write_strategy_module(tmp_path, monkeypatch)
    import dummy_strategy  # noqa: F401  (import error would fail the test clearly)

    exp = {
        "strategy": "dummy_strategy",
        "split": "train",
        "horizon": "day",
        "dates": {"start": "2015-01-01", "end": "2015-01-06"},
    }
    picks, pick_hash = run_experiment(_dataset(), exp, SPLITS)
    # The first dataset date has no prior history to truncate to, so the
    # strategy sees an empty history and makes no pick that day.
    assert sorted(picks["date"].unique()) == ["2015-01-02", "2015-01-05", "2015-01-06"]
    assert len(pick_hash) == 64


def test_run_experiment_raises_when_split_does_not_authorise_the_range(tmp_path, monkeypatch):
    _write_strategy_module(tmp_path, monkeypatch)
    exp = {
        "strategy": "dummy_strategy",
        "split": "train",
        "horizon": "day",
        "dates": {"start": "2015-01-01", "end": "2021-01-01"},  # 2021 is outside train
    }
    dataset = pd.concat([_dataset(), pd.DataFrame([{"date": "2021-01-01", "symbol": "AAA", "close": 1.0}])])
    with pytest.raises(SplitViolation):
        run_experiment(dataset, exp, SPLITS)


def test_main_processes_the_queue_and_moves_the_experiment_to_done(tmp_path, monkeypatch):
    _write_strategy_module(tmp_path, monkeypatch)

    data_path = tmp_path / "dataset.parquet"
    _dataset().to_parquet(data_path, index=False)

    pending_dir = tmp_path / "pending"
    done_dir = tmp_path / "done"
    pending_dir.mkdir()
    exp = {
        "id": "demo-experiment",
        "strategy": "dummy_strategy",
        "split": "train",
        "horizon": "day",
        "dates": {"start": "2015-01-01", "end": "2015-01-06"},
    }
    (pending_dir / "demo.yml").write_text(yaml.dump(exp))

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "engine.run_queue.load_splits",
        lambda *a, **k: SPLITS,
    )
    argv = [
        "run_queue.py", "--data", str(data_path),
        "--pending", str(pending_dir), "--done", str(done_dir),
    ]
    monkeypatch.setattr(sys, "argv", argv)

    main()

    assert not (pending_dir / "demo.yml").exists()  # consumed from the queue
    out_dir = done_dir / "demo-experiment"
    manifest = json.loads((out_dir / "manifest.json").read_text())
    assert manifest["id"] == "demo-experiment"
    assert manifest["n_picks"] > 0
    assert len(manifest["pick_log_sha256"]) == 64
    picks = pd.read_parquet(out_dir / "picks.parquet")
    assert set(picks.columns) == {"date", "symbol", "score"}


def test_main_with_an_empty_queue_does_nothing(tmp_path, capsys):
    main_args = ["--data", str(tmp_path / "nope.parquet"), "--pending", str(tmp_path / "pending"), "--done", str(tmp_path / "done")]
    import engine.run_queue as rq
    import sys as _sys
    old_argv = _sys.argv
    try:
        _sys.argv = ["run_queue.py", *main_args]
        rq.main()
    finally:
        _sys.argv = old_argv
    assert "no experiments queued" in capsys.readouterr().out
