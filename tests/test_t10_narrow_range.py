import numpy as np
import pandas as pd
import pytest

from strategies import t10_narrow_range_core as core
from strategies import t10_nr4_narrow_range, t10_nr7_narrow_range
from strategies.t10_narrow_range_audit import check_cross_symbol_causality


def _rows_from_trend(symbol: str, n_rows: int, narrow_last: bool, flat: bool = False) -> pd.DataFrame:
    """`n_rows` business days of a steady trend (flat if `flat`, otherwise a
    rising trend so the SMA20/50 spread is reliably non-zero), with every
    day's high/low spread wide except the last when `narrow_last` is set,
    whose high/low pins to within 0.01 of its close - the narrowest range
    of any trailing window up to `n_rows` long."""
    trend = np.full(n_rows, 100.0) if flat else np.linspace(80.0, 140.0, n_rows)
    dates = pd.bdate_range("2015-01-01", periods=n_rows).strftime("%Y-%m-%d")
    rows = []
    prev_close = float(trend[0])
    for i, (date, close) in enumerate(zip(dates, trend)):
        close = float(close)
        if narrow_last and i == n_rows - 1:
            high, low = close + 0.01, close - 0.01
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
        prev_close = close
    return pd.DataFrame(rows)


@pytest.mark.parametrize("variant,lookback", [(t10_nr4_narrow_range, 4), (t10_nr7_narrow_range, 7)])
def test_narrow_range_day_in_uptrend_scores_bullish(variant, lookback):
    history = _rows_from_trend("AAA", core.min_rows(lookback), narrow_last=True)
    scores = variant.score(history)
    assert "AAA" in scores
    assert scores["AAA"] > 0


@pytest.mark.parametrize("variant,lookback", [(t10_nr4_narrow_range, 4), (t10_nr7_narrow_range, 7)])
def test_non_narrow_day_abstains(variant, lookback):
    history = _rows_from_trend("AAA", core.min_rows(lookback), narrow_last=False)
    scores = variant.score(history)
    assert "AAA" not in scores


def test_narrow_range_day_in_downtrend_scores_bearish():
    n = core.min_rows(7)
    trend = np.linspace(140.0, 80.0, n)
    dates = pd.bdate_range("2015-01-01", periods=n).strftime("%Y-%m-%d")
    rows = []
    prev_close = float(trend[0])
    for i, (date, close) in enumerate(zip(dates, trend)):
        close = float(close)
        if i == n - 1:
            high, low = close + 0.01, close - 0.01
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
        prev_close = close
    history = pd.DataFrame(rows)

    scores = t10_nr7_narrow_range.score(history)
    assert "AAA" in scores
    assert scores["AAA"] < 0


def test_narrow_range_day_with_flat_trend_abstains():
    # Narrow-range condition fires, but the trend filter's spread is
    # exactly 0 (fast SMA == slow SMA on a flat series) - undefined
    # direction, so T10 abstains (cards/T10.yml's rules_plain).
    history = _rows_from_trend("AAA", core.min_rows(7), narrow_last=True, flat=True)
    scores = t10_nr7_narrow_range.score(history)
    assert "AAA" not in scores


def test_nr4_fires_on_a_day_nr7_would_also_flag():
    # Every NR7 day is also an NR4 day over its own trailing 4 sessions
    # (cards/T10.yml's red_flags): both variants should fire on the same
    # deliberately-narrow final day.
    history = _rows_from_trend("AAA", core.min_rows(7), narrow_last=True)
    # Build an NR4-sized slice directly rather than relying on t10_nr7's
    # longer history, since min_rows differs between the two variants.
    history_nr4 = _rows_from_trend("AAA", core.min_rows(4), narrow_last=True)
    nr4_scores = t10_nr4_narrow_range.score(history_nr4)
    nr7_scores = t10_nr7_narrow_range.score(history)
    assert "AAA" in nr4_scores
    assert "AAA" in nr7_scores
    assert np.sign(nr4_scores["AAA"]) == np.sign(nr7_scores["AAA"])


@pytest.mark.parametrize("variant,lookback", [(t10_nr4_narrow_range, 4), (t10_nr7_narrow_range, 7)])
def test_insufficient_history_abstains(variant, lookback):
    history = _rows_from_trend("AAA", core.min_rows(lookback) - 1, narrow_last=True)
    scores = variant.score(history)
    assert "AAA" not in scores


@pytest.mark.parametrize("variant", [t10_nr4_narrow_range, t10_nr7_narrow_range])
def test_empty_history_returns_empty_series(variant):
    scores = variant.score(pd.DataFrame())
    assert scores.empty


def test_has_future_prefilter_drops_ineligible_symbols():
    n = core.min_rows(7)
    eligible = _rows_from_trend("AAA", n, narrow_last=True)
    eligible["has_future"] = True
    ineligible = _rows_from_trend("ZZZ", n, narrow_last=True)
    ineligible["has_future"] = False
    history = pd.concat([eligible, ineligible], ignore_index=True)

    scores = t10_nr7_narrow_range.score(history)

    assert "AAA" in scores
    assert "ZZZ" not in scores


def test_rules_fired_reports_abstain_with_reason():
    history = _rows_from_trend("AAA", core.min_rows(7), narrow_last=False)
    reasoning = t10_nr7_narrow_range.rules_fired(history, "AAA")
    assert "abstain" in reasoning


def test_rules_fired_reports_bullish_direction():
    history = _rows_from_trend("AAA", core.min_rows(7), narrow_last=True)
    reasoning = t10_nr7_narrow_range.rules_fired(history, "AAA")
    assert "bullish" in reasoning


def test_rules_fired_insufficient_history():
    history = _rows_from_trend("AAA", core.min_rows(7) - 1, narrow_last=True)
    reasoning = t10_nr7_narrow_range.rules_fired(history, "AAA")
    assert "insufficient history" in reasoning


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result
