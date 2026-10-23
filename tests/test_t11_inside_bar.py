import numpy as np
import pandas as pd

from strategies import t11_inside_bar
from strategies.t11_inside_bar_audit import check_cross_symbol_causality


def _rows_from_trend(symbol: str, n_rows: int, inside_last: bool, flat: bool = False) -> pd.DataFrame:
    """`n_rows` business days of a steady trend (flat if `flat`, otherwise a
    rising trend so the SMA20/50 spread is reliably non-zero), with every
    day's high/low spread wide except the last when `inside_last` is set,
    whose high/low pins strictly inside the day before it's own high/low -
    same construction shape as `strategies/t10_narrow_range_audit.py`'s
    helper, adapted for a two-bar (not trailing-N) comparison."""
    trend = np.full(n_rows, 100.0) if flat else np.linspace(80.0, 140.0, n_rows)
    dates = pd.bdate_range("2015-01-01", periods=n_rows).strftime("%Y-%m-%d")
    rows = []
    prev_close = float(trend[0])
    prev_high = prev_low = None
    for i, (date, close) in enumerate(zip(dates, trend)):
        close = float(close)
        if inside_last and i == n_rows - 1:
            high, low = prev_high - 0.1, prev_low + 0.1
        else:
            high, low = max(prev_close, close) + 2.0, min(prev_close, close) - 2.0
        rows.append(
            {
                "date": date,
                "symbol": symbol,
                "open": prev_close,
                "high": high,
                "low": low,
                "close": close,
                "prevclose": prev_close,
                "volume": 1_000_000.0,
            }
        )
        prev_close, prev_high, prev_low = close, high, low
    return pd.DataFrame(rows)


def test_inside_bar_day_in_uptrend_scores_bullish():
    history = _rows_from_trend("AAA", t11_inside_bar.MIN_ROWS, inside_last=True)
    scores = t11_inside_bar.score(history)
    assert "AAA" in scores
    assert scores["AAA"] > 0


def test_non_inside_day_abstains():
    history = _rows_from_trend("AAA", t11_inside_bar.MIN_ROWS, inside_last=False)
    scores = t11_inside_bar.score(history)
    assert "AAA" not in scores


def test_inside_bar_day_in_downtrend_scores_bearish():
    n = t11_inside_bar.MIN_ROWS
    trend = np.linspace(140.0, 80.0, n)
    dates = pd.bdate_range("2015-01-01", periods=n).strftime("%Y-%m-%d")
    rows = []
    prev_close = float(trend[0])
    prev_high = prev_low = None
    for i, (date, close) in enumerate(zip(dates, trend)):
        close = float(close)
        if i == n - 1:
            high, low = prev_high - 0.1, prev_low + 0.1
        else:
            high, low = max(prev_close, close) + 2.0, min(prev_close, close) - 2.0
        rows.append(
            {
                "date": date,
                "symbol": "AAA",
                "open": prev_close,
                "high": high,
                "low": low,
                "close": close,
                "prevclose": prev_close,
                "volume": 1_000_000.0,
            }
        )
        prev_close, prev_high, prev_low = close, high, low
    history = pd.DataFrame(rows)

    scores = t11_inside_bar.score(history)
    assert "AAA" in scores
    assert scores["AAA"] < 0


def test_inside_bar_day_with_flat_trend_abstains():
    # Inside-bar condition fires, but the trend filter's spread is exactly
    # 0 (fast SMA == slow SMA on a flat series) - undefined direction, so
    # T11 abstains (cards/T11.yml's rules_plain).
    history = _rows_from_trend("AAA", t11_inside_bar.MIN_ROWS, inside_last=True, flat=True)
    scores = t11_inside_bar.score(history)
    assert "AAA" not in scores


def test_exact_equal_high_and_low_still_counts_as_inside():
    # cards/T11.yml's red_flags: equality on either side of the high/low
    # comparison still counts as inside bar (not a strict interior test).
    history = _rows_from_trend("AAA", t11_inside_bar.MIN_ROWS, inside_last=False).copy()
    history = history.reset_index(drop=True)
    yesterday_high = history.loc[len(history) - 2, "high"]
    yesterday_low = history.loc[len(history) - 2, "low"]
    history.loc[len(history) - 1, "high"] = yesterday_high
    history.loc[len(history) - 1, "low"] = yesterday_low

    scores = t11_inside_bar.score(history)
    assert "AAA" in scores


def test_insufficient_history_abstains():
    history = _rows_from_trend("AAA", t11_inside_bar.MIN_ROWS - 1, inside_last=True)
    scores = t11_inside_bar.score(history)
    assert "AAA" not in scores


def test_empty_history_returns_empty_series():
    scores = t11_inside_bar.score(pd.DataFrame())
    assert scores.empty


def test_has_future_prefilter_drops_ineligible_symbols():
    n = t11_inside_bar.MIN_ROWS
    eligible = _rows_from_trend("AAA", n, inside_last=True)
    eligible["has_future"] = True
    ineligible = _rows_from_trend("ZZZ", n, inside_last=True)
    ineligible["has_future"] = False
    history = pd.concat([eligible, ineligible], ignore_index=True)

    scores = t11_inside_bar.score(history)

    assert "AAA" in scores
    assert "ZZZ" not in scores


def test_rules_fired_reports_abstain_with_reason():
    history = _rows_from_trend("AAA", t11_inside_bar.MIN_ROWS, inside_last=False)
    reasoning = t11_inside_bar.rules_fired(history, "AAA")
    assert "abstain" in reasoning


def test_rules_fired_reports_bullish_direction():
    history = _rows_from_trend("AAA", t11_inside_bar.MIN_ROWS, inside_last=True)
    reasoning = t11_inside_bar.rules_fired(history, "AAA")
    assert "bullish" in reasoning


def test_rules_fired_insufficient_history():
    history = _rows_from_trend("AAA", t11_inside_bar.MIN_ROWS - 1, inside_last=True)
    reasoning = t11_inside_bar.rules_fired(history, "AAA")
    assert "insufficient history" in reasoning


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result
