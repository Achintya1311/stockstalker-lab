import pandas as pd
import pytest

from strategies import t13_williams_r
from strategies.t13_williams_r_audit import check_cross_symbol_causality


def _constant_steps(symbol: str, n_rows: int, step: float, base: float = 100.0, base_volume: float = 1_000_000.0) -> pd.DataFrame:
    """`n_rows` rows, each close exactly `step` away from the previous one -
    a known expected signal: for a monotonic run, the rolling 14-day high
    and low both resolve to specific, hand-derivable rows (the oldest row
    in the window on the declining side, the latest row on the rising
    side), giving an exact closed-form %R at the boundary (-100 or 0)
    rather than an approximation - same reasoning
    `tests/test_t03_rsi_thresholds.py::_constant_steps` uses for RSI's own
    boundary (0 or 100)."""
    dates = pd.bdate_range("2015-01-01", periods=n_rows).strftime("%Y-%m-%d")
    closes = [base + step * i for i in range(n_rows)]

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


def _flat_series(symbol: str, n_rows: int, base: float = 100.0, base_volume: float = 1_000_000.0) -> pd.DataFrame:
    return _constant_steps(symbol, n_rows, step=0.0, base=base, base_volume=base_volume)


def _reference_williams_r_latest(closes: list[float]) -> float:
    """Independent, loop-based rolling-window computation on the full
    series (same no-extra-spread high/low convention `_constant_steps`
    uses: `high[i] = max(close[i-1], close[i])`, `low[i] = min(close[i-1],
    close[i])`, with `close[-1]` standing in for day 0's own prevclose),
    used to cross-check the vectorized implementation under test for a
    series that isn't a clean monotonic run - same approach
    `tests/test_t12_stochastic.py::_reference_smoothed_k` uses."""
    n = len(closes)
    highs = [max(closes[i - 1] if i > 0 else closes[0], closes[i]) for i in range(n)]
    lows = [min(closes[i - 1] if i > 0 else closes[0], closes[i]) for i in range(n)]

    window = range(n - t13_williams_r.PERIOD, n)
    hh = max(highs[j] for j in window)
    ll = min(lows[j] for j in window)
    return -100.0 * (hh - closes[-1]) / (hh - ll)


def test_a_steady_decline_scores_fully_bullish_at_the_minus_100_floor():
    # Monotonic decline: the rolling-window high resolves to the oldest
    # row in the window (the largest prior close) and the rolling low to
    # the latest row itself, so %R = -100 exactly (deep oversold) -
    # score = (-80 - (-100)) / 20 = 1.0, the most bullish this card can
    # report. Unlike T12's crossing cards, this fires on every bar past
    # the threshold, including a long-persisted extreme - no "already
    # crossed, no fresh cross" abstain case here.
    history = _constant_steps("AAA", t13_williams_r.MIN_ROWS, step=-1.0)
    scores = t13_williams_r.score(history)
    assert "AAA" in scores
    assert scores["AAA"] == pytest.approx(1.0, rel=1e-9)


def test_a_steady_rally_scores_fully_bearish_at_the_zero_ceiling():
    # Mirror of the above: monotonic rise pins the rolling-window high at
    # the latest close and the rolling low at the oldest row, so %R = 0
    # exactly (deep overbought) - score = -(0 - (-20)) / 20 = -1.0.
    history = _constant_steps("AAA", t13_williams_r.MIN_ROWS, step=1.0)
    scores = t13_williams_r.score(history)
    assert "AAA" in scores
    assert scores["AAA"] == pytest.approx(-1.0, rel=1e-9)


def test_flat_series_abstains_on_zero_denominator():
    # High == low in every rolling window throughout a flat series: %R's
    # denominator is exactly 0 every bar, so %R is NaN - never a real
    # reading, the same zero-denominator abstain case
    # `tests/test_t12_stochastic.py::test_flat_series_abstains` documents
    # for raw %K.
    history = _flat_series("AAA", t13_williams_r.MIN_ROWS)
    scores = t13_williams_r.score(history)
    assert "AAA" not in scores


def test_genuinely_mid_range_abstains():
    # A decline followed by a partial bounce lands the latest close
    # somewhere inside the trailing window's high/low range, not pinned
    # at either edge - %R should sit strictly inside -80 to -20 and the
    # symbol abstains. Confirmed via the independent reference
    # computation rather than a hand-guessed fixture, the same style
    # T12's test file uses for its non-boundary cases.
    closes = [113.0 - i for i in range(14)] + [106.0]
    history = _rows_from_closes("AAA", closes)

    r_latest = _reference_williams_r_latest(closes)
    assert t13_williams_r.OVERSOLD < r_latest < t13_williams_r.OVERBOUGHT

    scores = t13_williams_r.score(history)
    assert "AAA" not in scores


def _rows_from_closes(symbol: str, closes: list[float], base_volume: float = 1_000_000.0) -> pd.DataFrame:
    """Same no-extra-spread row convention as `_constant_steps`, but from
    an arbitrary close sequence rather than a fixed step."""
    dates = pd.bdate_range("2015-01-01", periods=len(closes)).strftime("%Y-%m-%d")
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


def test_too_little_history_abstains():
    history = _constant_steps("AAA", t13_williams_r.MIN_ROWS, step=-1.0)
    history = history.iloc[:-1]  # one row short of MIN_ROWS
    scores = t13_williams_r.score(history)
    assert "AAA" not in scores


def test_empty_history_returns_empty_series():
    scores = t13_williams_r.score(
        pd.DataFrame(columns=["date", "symbol", "open", "high", "low", "close", "prevclose", "volume"])
    )
    assert scores.empty


def test_score_is_per_symbol_not_coupled_across_the_universe():
    declining = _constant_steps("AAA", t13_williams_r.MIN_ROWS, step=-1.0)
    rising = _constant_steps("BBB", t13_williams_r.MIN_ROWS, step=1.0)
    scores = t13_williams_r.score(pd.concat([declining, rising], ignore_index=True))
    assert scores["AAA"] > 0
    assert scores["BBB"] < 0


def test_has_future_prefilter_drops_ineligible_symbols():
    eligible = _constant_steps("AAA", t13_williams_r.MIN_ROWS, step=-1.0)
    eligible["has_future"] = True
    ineligible = _constant_steps("ZZZ", t13_williams_r.MIN_ROWS, step=-1.0)
    ineligible["has_future"] = False
    history = pd.concat([eligible, ineligible], ignore_index=True)

    scores = t13_williams_r.score(history)

    assert "AAA" in scores
    assert "ZZZ" not in scores


def test_rules_fired_reports_bullish_direction():
    history = _constant_steps("AAA", t13_williams_r.MIN_ROWS, step=-1.0)
    reasoning = t13_williams_r.rules_fired(history, "AAA")
    assert "bullish" in reasoning
    assert "%R" in reasoning


def test_rules_fired_reports_abstain_with_reason():
    history = _flat_series("AAA", t13_williams_r.MIN_ROWS)
    reasoning = t13_williams_r.rules_fired(history, "AAA")
    assert "abstain" in reasoning


def test_rules_fired_insufficient_history():
    history = _constant_steps("AAA", t13_williams_r.MIN_ROWS, step=-1.0).iloc[:-1]
    reasoning = t13_williams_r.rules_fired(history, "AAA")
    assert "insufficient history" in reasoning


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result
