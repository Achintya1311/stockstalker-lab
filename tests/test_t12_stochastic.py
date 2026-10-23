import numpy as np
import pandas as pd
import pytest

from strategies import t12_stochastic
from strategies.t12_stochastic_audit import check_cross_symbol_causality


def _rows_from_closes(symbol: str, closes: list[float], base_volume: float = 1_000_000.0) -> pd.DataFrame:
    """Each day's high/low is just max/min(prevclose, close) - no extra
    intraday spread - so adjusted high/low/close stay exactly derivable
    from the close sequence alone, the simplest fixture that still
    exercises this card's rolling high/low window (unlike T05's
    close-only cards, this one needs real high/low, not just close)."""
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


def _reference_smoothed_k(closes: list[float]) -> tuple[float, float]:
    """Independent, loop-based rolling-window/SMA computation on the full
    series, used to cross-check the vectorized implementation under test
    rather than re-deriving the same formula in a different shape.
    Returns (k_prev, k_latest)."""
    n = len(closes)
    highs = [max(closes[i - 1] if i > 0 else closes[0], closes[i]) for i in range(n)]
    lows = [min(closes[i - 1] if i > 0 else closes[0], closes[i]) for i in range(n)]

    raw_k: list[float] = []
    for i in range(n):
        if i < t12_stochastic.K_PERIOD - 1:
            raw_k.append(float("nan"))
            continue
        window = range(i - t12_stochastic.K_PERIOD + 1, i + 1)
        hh = max(highs[j] for j in window)
        ll = min(lows[j] for j in window)
        if hh == ll:
            raw_k.append(float("nan"))
        else:
            raw_k.append((closes[i] - ll) / (hh - ll) * 100.0)

    def _sma_at(values: list[float], end: int, window: int) -> float:
        span = values[end - window + 1 : end + 1]
        if any(pd.isna(v) for v in span):
            return float("nan")
        return sum(span) / window

    k_series = [_sma_at(raw_k, i, t12_stochastic.K_SMOOTH) for i in range(n)]
    return k_series[-2], k_series[-1]


def _monotonic_closes(n_rows: int, step: float, base: float = 100.0) -> list[float]:
    return [base + step * i for i in range(n_rows)]


def test_steady_uptrend_already_crossed_abstains():
    # A long, steady uptrend settles %K pinned at (or near) 100 - already
    # past the 80 threshold for many bars, no fresh cross down through it
    # on the latest bar, the same "already crossed, no fresh cross"
    # reading `cards/T05.yml`'s MACD crossing documents.
    closes = list(np.linspace(60.0, 140.0, 80))
    history = _rows_from_closes("AAA", closes)
    scores = t12_stochastic.score(history)
    assert "AAA" not in scores


def test_persistent_decline_already_crossed_abstains():
    # Mirror of the above: a long, steady decline settles %K pinned at (or
    # near) 0 - already past the 20 threshold for many bars, no fresh
    # cross up through it on the latest bar.
    closes = list(np.linspace(140.0, 60.0, 80))
    history = _rows_from_closes("AAA", closes)
    scores = t12_stochastic.score(history)
    assert "AAA" not in scores


def test_flat_series_abstains():
    closes = [100.0] * 60
    history = _rows_from_closes("AAA", closes)
    scores = t12_stochastic.score(history)
    # High == low in every rolling window throughout a flat series: raw
    # %K's denominator is exactly 0 every bar, so %K is NaN throughout -
    # never a real cross.
    assert "AAA" not in scores


def test_bullish_cross_after_decline_then_sharp_rally():
    # A long decline pins %K near 0 (well below 20); a sharp rally on the
    # final bar pulls price (and the rolling-window extremes) up enough to
    # push smoothed %K back up through 20.
    closes = list(np.linspace(140.0, 80.0, 60)) + [78.0, 130.0]
    history = _rows_from_closes("AAA", closes)

    k_prev, k_latest = _reference_smoothed_k(closes)
    assert k_prev < 20
    assert k_latest >= 20

    scores = t12_stochastic.score(history)
    assert "AAA" in scores
    expected_score = (20.0 - k_prev) / 20.0
    assert scores["AAA"] == pytest.approx(expected_score, abs=1e-6)
    assert scores["AAA"] > 0


def test_bearish_cross_after_rally_then_sharp_decline():
    # Mirror of the above: a long rally pins %K near 100 (well above 80);
    # a sharp decline on the final bar pulls smoothed %K back down through
    # 80.
    closes = list(np.linspace(80.0, 140.0, 60)) + [142.0, 100.0]
    history = _rows_from_closes("AAA", closes)

    k_prev, k_latest = _reference_smoothed_k(closes)
    assert k_prev > 80
    assert k_latest <= 80

    scores = t12_stochastic.score(history)
    assert "AAA" in scores
    expected_score = -(k_prev - 80.0) / 20.0
    assert scores["AAA"] == pytest.approx(expected_score, abs=1e-6)
    assert scores["AAA"] < 0


def test_insufficient_history_abstains():
    closes = _monotonic_closes(t12_stochastic.MIN_ROWS - 1, step=1.0)
    history = _rows_from_closes("AAA", closes)
    scores = t12_stochastic.score(history)
    assert "AAA" not in scores


def test_empty_history_returns_empty_series():
    scores = t12_stochastic.score(pd.DataFrame())
    assert scores.empty


def test_has_future_prefilter_drops_ineligible_symbols():
    closes = list(np.linspace(140.0, 80.0, 60)) + [78.0, 130.0]
    eligible = _rows_from_closes("AAA", closes)
    eligible["has_future"] = True
    ineligible = _rows_from_closes("ZZZ", closes)
    ineligible["has_future"] = False
    history = pd.concat([eligible, ineligible], ignore_index=True)

    scores = t12_stochastic.score(history)

    assert "AAA" in scores
    assert "ZZZ" not in scores


def test_rules_fired_reports_abstain_with_reason():
    closes = [100.0] * 60
    history = _rows_from_closes("AAA", closes)
    reasoning = t12_stochastic.rules_fired(history, "AAA")
    assert "abstain" in reasoning


def test_rules_fired_reports_bullish_direction():
    closes = list(np.linspace(140.0, 80.0, 60)) + [78.0, 130.0]
    history = _rows_from_closes("AAA", closes)
    reasoning = t12_stochastic.rules_fired(history, "AAA")
    assert "bullish" in reasoning


def test_rules_fired_insufficient_history():
    closes = _monotonic_closes(t12_stochastic.MIN_ROWS - 1, step=1.0)
    history = _rows_from_closes("AAA", closes)
    reasoning = t12_stochastic.rules_fired(history, "AAA")
    assert "insufficient history" in reasoning


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result
