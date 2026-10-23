import numpy as np
import pandas as pd
import pytest

from strategies import t09_supertrend as t09
from strategies.t09_supertrend_audit import check_cross_symbol_causality


def _trend_rows(symbol: str, n_rows: int, drift: float, noise: float, seed: int, spread: float = 0.3) -> pd.DataFrame:
    """`n_rows` business days with a steady per-day `drift` plus small
    `noise`, wide enough high/low `spread` to make ATR non-degenerate but
    small relative to the cumulative drift, so a clean trend dominates
    the whole warmup - same "degenerate, hand-reasoned" construction
    style T04/T05 use for their monotonic fixtures, extended with a
    high/low band Supertrend needs."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2015-01-01", periods=n_rows).strftime("%Y-%m-%d")
    steps = drift + rng.normal(0.0, noise, n_rows)
    closes = np.clip(100.0 + np.cumsum(steps), 1.0, None)

    rows = []
    prev_close = float(closes[0])
    for date, close in zip(dates, closes):
        close = float(close)
        rows.append(
            {
                "date": date,
                "symbol": symbol,
                "open": prev_close,
                "high": max(prev_close, close) + spread,
                "low": min(prev_close, close) - spread,
                "close": close,
                "prevclose": prev_close,
                "volume": 1_000_000.0,
            }
        )
        prev_close = close
    return pd.DataFrame(rows)


def test_clean_uptrend_is_bullish():
    # Steady +1.0/day drift, spread (0.3) and noise (0.05) both tiny
    # relative to the trend: the lower band should ratchet up with price
    # and close should stay above it throughout, so by MIN_ROWS the line
    # is bullish regardless of the arbitrary seed side.
    history = _trend_rows("AAA", t09.MIN_ROWS, drift=1.0, noise=0.05, seed=1)

    scores = t09.score(history)

    assert "AAA" in scores
    assert scores["AAA"] > 0


def test_clean_downtrend_is_bearish():
    history = _trend_rows("AAA", t09.MIN_ROWS, drift=-1.0, noise=0.05, seed=1)

    scores = t09.score(history)

    assert "AAA" in scores
    assert scores["AAA"] < 0


def test_insufficient_history_abstains():
    history = _trend_rows("AAA", t09.MIN_ROWS - 1, drift=1.0, noise=0.05, seed=1)

    scores = t09.score(history)

    assert "AAA" not in scores


def test_empty_history_returns_empty_series():
    scores = t09.score(pd.DataFrame(columns=["date", "symbol", "open", "high", "low", "close", "prevclose", "volume"]))

    assert scores.empty


def test_has_future_prefilter_drops_ineligible_symbols():
    history = _trend_rows("AAA", t09.MIN_ROWS, drift=1.0, noise=0.05, seed=1)
    history["has_future"] = False

    scores = t09.score(history)

    assert scores.empty


def test_multiple_symbols_scored_independently():
    up = _trend_rows("UP", t09.MIN_ROWS, drift=1.0, noise=0.05, seed=1)
    down = _trend_rows("DOWN", t09.MIN_ROWS, drift=-1.0, noise=0.05, seed=2)
    history = pd.concat([up, down], ignore_index=True)

    scores = t09.score(history)

    assert scores["UP"] > 0
    assert scores["DOWN"] < 0


def test_supertrend_line_sign_matches_returned_score():
    # The line's own construction guarantees close sits at or below it on
    # a bearish bar and at or above it on a bullish one (cards/T09.yml's
    # rules_plain); confirm that invariant holds directly against
    # `_supertrend_line`'s own output, not just the wrapped score.
    history = _trend_rows("AAA", t09.MIN_ROWS, drift=1.0, noise=0.05, seed=1)
    row = history.sort_values("date").tail(t09.MIN_ROWS)

    line = t09._supertrend_line(
        row["high"].to_numpy(), row["low"].to_numpy(), row["close"].to_numpy(), t09.ATR_PERIOD, t09.MULTIPLIER
    )
    assert not np.isnan(line[-1])
    assert row["close"].to_numpy()[-1] >= line[-1]


def test_rules_fired_reports_direction():
    history = _trend_rows("AAA", t09.MIN_ROWS, drift=1.0, noise=0.05, seed=1)

    message = t09.rules_fired(history, "AAA")

    assert "bullish" in message
    assert "T09 Supertrend" in message


def test_rules_fired_abstains_message_on_insufficient_history():
    history = _trend_rows("AAA", t09.MIN_ROWS - 1, drift=1.0, noise=0.05, seed=1)

    message = t09.rules_fired(history, "AAA")

    assert "insufficient history" in message


def test_wilder_smooth_matches_known_seed():
    # Same shape of direct check T03/T04 run on their own Wilder helper:
    # the first valid output is exactly the plain mean of the `period`
    # values after index 0 (index 0 itself is never read by the seed).
    values = pd.Series([0.0, 2.0, 4.0, 6.0, 8.0])
    smoothed = t09._wilder_smooth(values, period=4)

    assert smoothed.iloc[:4].isna().all()
    assert smoothed.iloc[4] == pytest.approx((2.0 + 4.0 + 6.0 + 8.0) / 4)


def test_true_range_uses_high_low_and_gaps():
    high = np.array([10.0, 20.0, 8.0])
    low = np.array([5.0, 9.0, 1.0])
    close = np.array([7.0, 10.0, 8.0])

    tr = t09._true_range(high, low, close)

    # Row 1: high-low=11, |high-prevclose|=|20-7|=13, |low-prevclose|=|9-7|=2 -> max 13
    assert tr[1] == pytest.approx(13.0)
    # Row 2: high-low=7, |high-prevclose|=|8-10|=2, |low-prevclose|=|1-10|=9 -> max 9
    assert tr[2] == pytest.approx(9.0)


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result
