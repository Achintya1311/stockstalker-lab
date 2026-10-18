import numpy as np
import pandas as pd
import pytest

from strategies import a04_52_week_high
from strategies.a04_52_week_high_audit import check_cross_symbol_causality


def _series_with_range(
    symbol: str,
    n_rows: int,
    low: float,
    high: float,
    last: float,
    base_volume: float = 1_000_000.0,
) -> pd.DataFrame:
    """A series whose trailing `a04_52_week_high.WINDOW_DAYS` window has a
    known expected high, low and final close, so the range score is fully
    determined: every row in the window is `low` except one row set to
    `high` and the final row set to `last` (both inside the window), and
    any rows before the window (if `n_rows > WINDOW_DAYS`) stay at `low`
    too so they can never become the window's own high or low.
    """
    window = a04_52_week_high.WINDOW_DAYS
    assert n_rows >= window
    dates = pd.bdate_range("2015-01-01", periods=n_rows).strftime("%Y-%m-%d")

    closes = np.full(n_rows, low)
    window_start = n_rows - window
    high_idx = window_start + 1 if window > 1 else window_start
    closes[high_idx] = high
    closes[-1] = last

    rows = []
    prev_close = float(closes[0])
    for date, close in zip(dates, closes):
        close = float(close)
        rows.append(
            {
                "date": date,
                "symbol": symbol,
                "open": prev_close,
                "high": max(prev_close, close),
                "low": min(prev_close, close),
                "close": close,
                "prevclose": prev_close,
                "volume": base_volume,
            }
        )
        prev_close = close
    return pd.DataFrame(rows)


def test_close_at_the_window_high_scores_plus_one():
    history = _series_with_range("AAA", a04_52_week_high.MIN_ROWS, low=100.0, high=200.0, last=200.0)
    scores = a04_52_week_high.score(history)
    assert scores["AAA"] == pytest.approx(1.0, rel=1e-9)


def test_close_at_the_window_low_scores_minus_one():
    history = _series_with_range("AAA", a04_52_week_high.MIN_ROWS, low=100.0, high=200.0, last=100.0)
    scores = a04_52_week_high.score(history)
    assert scores["AAA"] == pytest.approx(-1.0, rel=1e-9)


def test_close_at_the_range_midpoint_scores_zero():
    history = _series_with_range("AAA", a04_52_week_high.MIN_ROWS, low=100.0, high=200.0, last=150.0)
    scores = a04_52_week_high.score(history)
    assert scores["AAA"] == pytest.approx(0.0, abs=1e-9)


def test_score_magnitude_matches_the_known_formula():
    # Known expected signal, exactly: close three-quarters of the way from
    # low (100) to high (200) gives nearness 0.75, so score = 2*0.75 - 1 = 0.5.
    history = _series_with_range("AAA", a04_52_week_high.MIN_ROWS, low=100.0, high=200.0, last=175.0)
    scores = a04_52_week_high.score(history)
    assert scores["AAA"] == pytest.approx(0.5, rel=1e-9)


def test_flat_window_scores_exactly_zero():
    history = _series_with_range("AAA", a04_52_week_high.MIN_ROWS, low=100.0, high=100.0, last=100.0)
    scores = a04_52_week_high.score(history)
    assert scores["AAA"] == 0.0


def test_a_move_before_the_window_does_not_change_the_score():
    # Extra rows before the trailing WINDOW_DAYS window stay at `low`
    # (see the fixture docstring), so they can never become the window's
    # own high/low; the score with extra leading history must match the
    # score computed on exactly WINDOW_DAYS rows.
    short = _series_with_range("AAA", a04_52_week_high.MIN_ROWS, low=100.0, high=200.0, last=175.0)
    long = _series_with_range("AAA", a04_52_week_high.MIN_ROWS + 30, low=100.0, high=200.0, last=175.0)
    assert a04_52_week_high.score(short)["AAA"] == pytest.approx(
        a04_52_week_high.score(long)["AAA"], rel=1e-9
    )


def test_too_little_history_abstains():
    history = _series_with_range("AAA", a04_52_week_high.MIN_ROWS, low=100.0, high=200.0, last=175.0)
    history = history.iloc[1:]  # drop one row: now below MIN_ROWS
    scores = a04_52_week_high.score(history)
    assert "AAA" not in scores


def test_empty_history_returns_empty_series():
    scores = a04_52_week_high.score(
        pd.DataFrame(columns=["date", "symbol", "open", "high", "low", "close", "prevclose", "volume"])
    )
    assert scores.empty


def test_score_is_per_symbol_not_coupled_across_the_universe():
    near_low = _series_with_range("AAA", a04_52_week_high.MIN_ROWS, low=100.0, high=200.0, last=100.0)
    near_high = _series_with_range("BBB", a04_52_week_high.MIN_ROWS, low=100.0, high=200.0, last=200.0)
    scores = a04_52_week_high.score(pd.concat([near_low, near_high], ignore_index=True))
    assert scores["AAA"] < 0
    assert scores["BBB"] > 0


def test_rules_fired_reports_the_same_direction_as_score():
    history = _series_with_range("AAA", a04_52_week_high.MIN_ROWS, low=100.0, high=200.0, last=200.0)
    reasoning = a04_52_week_high.rules_fired(history, "AAA")
    assert "bullish" in reasoning
    assert "range score" in reasoning


def test_rules_fired_reports_abstain_on_insufficient_history():
    history = _series_with_range("AAA", a04_52_week_high.MIN_ROWS, low=100.0, high=200.0, last=200.0)
    history = history.iloc[1:]
    reasoning = a04_52_week_high.rules_fired(history, "AAA")
    assert "abstain" in reasoning


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result


def test_score_drops_a_symbol_that_never_had_a_future():
    history = _series_with_range("AAA", a04_52_week_high.MIN_ROWS, low=100.0, high=200.0, last=200.0)
    history["has_future"] = False
    scores = a04_52_week_high.score(history)
    assert "AAA" not in scores


def test_score_keeps_an_eligible_symbol_with_has_future_column_present():
    history = _series_with_range("AAA", a04_52_week_high.MIN_ROWS, low=100.0, high=200.0, last=200.0)
    history["has_future"] = True
    scores = a04_52_week_high.score(history)
    assert scores["AAA"] == pytest.approx(1.0, rel=1e-9)


def test_score_prefilter_does_not_change_an_eligible_symbols_score():
    eligible = _series_with_range("AAA", a04_52_week_high.MIN_ROWS, low=100.0, high=200.0, last=200.0)
    ineligible = _series_with_range("ZZZ", a04_52_week_high.MIN_ROWS, low=100.0, high=200.0, last=100.0)

    with_future_column = pd.concat([eligible, ineligible], ignore_index=True)
    with_future_column["has_future"] = with_future_column["symbol"] == "AAA"

    without_future_column = eligible  # no ineligible symbol, no has_future column at all

    assert a04_52_week_high.score(with_future_column)["AAA"] == a04_52_week_high.score(without_future_column)["AAA"]
