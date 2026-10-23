import numpy as np
import pandas as pd
import pytest

from strategies import t05_macd_crossover
from strategies.t05_macd_crossover_audit import check_cross_symbol_causality


def _rows_from_closes(symbol: str, closes: list[float], base_volume: float = 1_000_000.0) -> pd.DataFrame:
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


def _reference_macd_signal(closes: list[float]) -> tuple[float, float, float, float]:
    """Independent, loop-based plain EMA (alpha = 2/(span+1), seeded by the
    first observation - pandas' own `ewm(span=N, adjust=False)` formula)
    on the full series, used to cross-check the vectorized implementation
    under test rather than re-deriving the same formula in a different
    shape. Returns (macd_latest, macd_prev, signal_latest, signal_prev).
    """

    def _ema(values: list[float], span: int) -> list[float]:
        alpha = 2.0 / (span + 1)
        out = [values[0]]
        for x in values[1:]:
            out.append(alpha * x + (1 - alpha) * out[-1])
        return out

    ema_fast = _ema(closes, t05_macd_crossover.FAST)
    ema_slow = _ema(closes, t05_macd_crossover.SLOW)
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal_line = _ema(macd_line, t05_macd_crossover.SIGNAL)
    return macd_line[-1], macd_line[-2], signal_line[-1], signal_line[-2]


def _monotonic_closes(n_rows: int, step: float, base: float = 100.0) -> list[float]:
    return [base + step * i for i in range(n_rows)]


def test_steady_uptrend_already_crossed_abstains():
    # A long, steady uptrend settles into MACD sitting persistently above
    # its own signal line (`cards/T05.yml`'s own derivation) - no fresh
    # cross on the latest bar even though MACD is clearly bullish, so this
    # card abstains (the literal "crossing" reading, not a continuous
    # "is above" state the way `strategies/t01_sma_crossover.py` reads).
    closes = list(np.linspace(80.0, 140.0, 80))
    history = _rows_from_closes("AAA", closes)
    scores = t05_macd_crossover.score(history)
    assert "AAA" not in scores


def test_flat_series_abstains():
    closes = [100.0] * 60
    history = _rows_from_closes("AAA", closes)
    scores = t05_macd_crossover.score(history)
    # MACD and signal are both pinned at exactly 0 throughout a flat
    # series: no strict inequality ever holds, so no fresh cross.
    assert "AAA" not in scores


def test_bullish_cross_after_decline_then_sharp_rally():
    # A long decline lets MACD settle persistently below (and converge
    # toward) its own signal line; a sharp two-day rally pulls the fast
    # EMA up quickly while the signal line (lagging further) is still
    # anchored near the prior, lower level - MACD crosses above signal on
    # the latest bar.
    closes = list(np.linspace(140.0, 80.0, 60)) + [78.0, 88.0]
    history = _rows_from_closes("AAA", closes)

    macd_latest, macd_prev, signal_latest, signal_prev = _reference_macd_signal(closes)
    assert macd_prev <= signal_prev
    assert macd_latest > signal_latest

    scores = t05_macd_crossover.score(history)
    assert "AAA" in scores
    expected_score = (macd_latest - signal_latest) / abs(closes[-1])
    assert scores["AAA"] == pytest.approx(expected_score, abs=1e-6)
    assert scores["AAA"] > 0


def test_bearish_cross_after_rally_then_sharp_decline():
    # Mirror of the above: a long rally settles MACD above its signal
    # line; a sharp two-day decline pulls the fast EMA down quickly while
    # the signal line is still anchored near the prior, higher level -
    # MACD crosses below signal on the latest bar.
    closes = list(np.linspace(80.0, 140.0, 60)) + [142.0, 132.0]
    history = _rows_from_closes("AAA", closes)

    macd_latest, macd_prev, signal_latest, signal_prev = _reference_macd_signal(closes)
    assert macd_prev >= signal_prev
    assert macd_latest < signal_latest

    scores = t05_macd_crossover.score(history)
    assert "AAA" in scores
    expected_score = (macd_latest - signal_latest) / abs(closes[-1])
    assert scores["AAA"] == pytest.approx(expected_score, abs=1e-6)
    assert scores["AAA"] < 0


def test_insufficient_history_abstains():
    closes = _monotonic_closes(t05_macd_crossover.MIN_ROWS - 1, step=1.0)
    history = _rows_from_closes("AAA", closes)
    scores = t05_macd_crossover.score(history)
    assert "AAA" not in scores


def test_empty_history_returns_empty_series():
    scores = t05_macd_crossover.score(pd.DataFrame())
    assert scores.empty


def test_has_future_prefilter_drops_ineligible_symbols():
    closes = list(np.linspace(140.0, 80.0, 60)) + [78.0, 88.0]
    eligible = _rows_from_closes("AAA", closes)
    eligible["has_future"] = True
    ineligible = _rows_from_closes("ZZZ", closes)
    ineligible["has_future"] = False
    history = pd.concat([eligible, ineligible], ignore_index=True)

    scores = t05_macd_crossover.score(history)

    assert "AAA" in scores
    assert "ZZZ" not in scores


def test_rules_fired_reports_abstain_with_reason():
    closes = [100.0] * 60
    history = _rows_from_closes("AAA", closes)
    reasoning = t05_macd_crossover.rules_fired(history, "AAA")
    assert "abstain" in reasoning


def test_rules_fired_reports_bullish_direction():
    closes = list(np.linspace(140.0, 80.0, 60)) + [78.0, 88.0]
    history = _rows_from_closes("AAA", closes)
    reasoning = t05_macd_crossover.rules_fired(history, "AAA")
    assert "bullish" in reasoning


def test_rules_fired_insufficient_history():
    closes = _monotonic_closes(t05_macd_crossover.MIN_ROWS - 1, step=1.0)
    history = _rows_from_closes("AAA", closes)
    reasoning = t05_macd_crossover.rules_fired(history, "AAA")
    assert "insufficient history" in reasoning


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result
