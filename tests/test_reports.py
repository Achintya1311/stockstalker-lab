import pandas as pd
import pytest

from engine.reports import maybe_write_market_line_report, yearly_market_line


def _dataset_one_year_one_up_one_down():
    # 25 trading days (enough for the 20-day turnover window) of two symbols,
    # both liquid and with an active future throughout; on the last day A is
    # up and B is down.
    dates = [f"2015-01-{d:02d}" for d in range(1, 26)]
    rows = []
    for i, d in enumerate(dates):
        move_a = 0.01 if i == len(dates) - 1 else 0.0
        move_b = -0.01 if i == len(dates) - 1 else 0.0
        rows.append({"date": d, "symbol": "A", "open": 100.0, "close": 100.0 * (1 + move_a),
                      "has_future": True, "turnover": 1e9})
        rows.append({"date": d, "symbol": "B", "open": 100.0, "close": 100.0 * (1 + move_b),
                      "has_future": True, "turnover": 1e9})
    return pd.DataFrame(rows)


def test_yearly_market_line_hand_computed_last_day_only_observation_that_moves():
    dataset = _dataset_one_year_one_up_one_down()
    table = yearly_market_line(dataset, "day")
    # Flat days contribute neither an up nor a down; only the final day moves.
    row = table[table["year"] == 2015].iloc[0]
    # The rolling 20-day turnover window only fills from the 20th trading date
    # on, so only the last 6 of the 25 dates (x2 symbols = 12 rows) are in
    # the universe at all; of those, only the final date's 2 rows move.
    assert row["n_obs"] == 12
    assert row["share_up"] == pytest.approx(1 / 12)
    assert row["share_down"] == pytest.approx(1 / 12)


def test_maybe_write_market_line_report_skips_when_columns_missing(tmp_path):
    minimal = pd.DataFrame({"date": ["2015-01-01"], "symbol": ["A"], "close": [1.0]})
    out_path = tmp_path / "market_line_train.md"
    wrote = maybe_write_market_line_report(minimal, out_path)
    assert wrote is False
    assert not out_path.exists()


def test_maybe_write_market_line_report_writes_when_columns_present(tmp_path):
    dataset = _dataset_one_year_one_up_one_down()
    out_path = tmp_path / "nested" / "market_line_train.md"
    wrote = maybe_write_market_line_report(dataset, out_path)
    assert wrote is True
    text = out_path.read_text()
    assert "# Market line, train split" in text
    assert "## Day" in text and "## Week" in text
