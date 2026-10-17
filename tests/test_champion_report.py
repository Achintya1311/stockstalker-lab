import pandas as pd
import pytest

from engine.champion_report import (
    REQUIRED_COLUMNS,
    SIDE_NAME,
    horizon_results,
    maybe_write_champion_report,
    render,
)
from strategies import champion_v1

N_WARMUP_DAYS = 20  # universe_membership's 20-day turnover window
N_TRADING_DAYS = champion_v1.MIN_ROWS + 30  # enough past MIN_ROWS for several real picks


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
            "turnover": close * 5_000_000.0,  # Rs 25cr floor is 2.5e8; this clears it with room to spare
            "has_future": True,
        })
        prev_close = close
    return rows


def _dataset():
    dates = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2015-01-01", periods=N_TRADING_DAYS)]
    rows = []
    rows += _series("UP", dates, daily_move=0.01)
    rows += _series("DOWN", dates, daily_move=-0.01)
    rows += _series("FLAT", dates, daily_move=0.0)
    return pd.DataFrame(rows)


def test_maybe_write_champion_report_skips_when_columns_missing(tmp_path):
    minimal = pd.DataFrame({"date": ["2015-01-01"], "symbol": ["A"], "close": [1.0]})
    out_path = tmp_path / "champion_v1_train.md"
    assert maybe_write_champion_report(minimal, out_path) is False
    assert not out_path.exists()


def test_maybe_write_champion_report_skips_when_dataset_has_no_train_dates(tmp_path):
    dataset = _dataset()
    dataset["date"] = "2027-01-01"  # past the train split entirely
    out_path = tmp_path / "champion_v1_train.md"
    assert maybe_write_champion_report(dataset, out_path) is False
    assert not out_path.exists()


def test_up_symbol_dominates_bullish_picks_day_horizon():
    dataset = _dataset()
    results = horizon_results(dataset, "day")
    bull = results[1]
    assert bull["n_picks"] > 0
    # UP is in the universe (active future, turnover above floor) and
    # champion_v1 should read its steady uptrend as bullish every day once
    # past MIN_ROWS - DOWN and FLAT should not also land on the bullish side.
    assert bull["accuracy"] > 0.9
    assert bull["edge"] > 0


def test_down_symbol_dominates_bearish_picks_day_horizon():
    dataset = _dataset()
    results = horizon_results(dataset, "day")
    bear = results[-1]
    assert bear["n_picks"] > 0
    assert bear["accuracy"] > 0.9
    assert bear["edge"] > 0


def test_week_horizon_also_produces_picks():
    dataset = _dataset()
    results = horizon_results(dataset, "week")
    assert results[1]["n_picks"] > 0
    assert results[-1]["n_picks"] > 0


def test_render_includes_both_horizons_and_sides():
    dataset = _dataset()
    results = {horizon: horizon_results(dataset, horizon) for horizon in ("day", "week")}
    text = render(results)
    for horizon in ("Day", "Week"):
        assert horizon in text
    for side_name in SIDE_NAME.values():
        assert side_name in text


def test_maybe_write_champion_report_writes_a_real_file(tmp_path):
    dataset = _dataset()
    out_path = tmp_path / "champion_v1_train.md"
    assert maybe_write_champion_report(dataset, out_path) is True
    text = out_path.read_text()
    assert "Champion v1 train results" in text
    assert "Bullish" in text and "Bearish" in text
