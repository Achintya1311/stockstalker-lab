import numpy as np
import pandas as pd
import pytest

from strategies import t04_connors_rsi2
from strategies.t04_connors_rsi2_audit import check_cross_symbol_causality


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


def _reference_rsi2(closes: list[float]) -> float:
    """Independent, loop-based Wilder RSI(period=2) on the full series,
    used to cross-check the vectorized implementation under test rather
    than re-deriving the same formula in a different shape."""
    period = 2
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for g, l in zip(gains[period:], losses[period:]):
        avg_gain = avg_gain * (1 - 1.0 / period) + g * (1.0 / period)
        avg_loss = avg_loss * (1 - 1.0 / period) + l * (1.0 / period)

    if avg_gain == 0 and avg_loss == 0:
        return 50.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _reference_sma(closes: list[float], window: int) -> float:
    return sum(closes[-window:]) / window


def _monotonic_closes(n_rows: int, step: float, base: float = 100.0) -> list[float]:
    return [base + step * i for i in range(n_rows)]


def test_all_gains_monotonic_uptrend_abstains():
    # RSI(2) -> exactly 100 (overbought threshold), but close is also above
    # its own SMA200 (the bullish trend reading) - the two legs disagree
    # (bearish RSI extreme inside a bullish trend), so T04 abstains. This
    # is the asymmetric-conjunction behaviour `cards/T04.yml` documents,
    # not a bug.
    closes = _monotonic_closes(220, step=1.0)
    history = _rows_from_closes("AAA", closes)
    scores = t04_connors_rsi2.score(history)
    assert "AAA" not in scores


def test_all_losses_monotonic_downtrend_abstains():
    # Mirror of the above: RSI(2) -> exactly 0 (oversold threshold), but
    # close is below its own SMA200 (bearish trend reading) - disagrees
    # with the bullish RSI extreme, so T04 abstains.
    closes = _monotonic_closes(220, step=-1.0)
    history = _rows_from_closes("AAA", closes)
    scores = t04_connors_rsi2.score(history)
    assert "AAA" not in scores


def test_flat_series_abstains():
    closes = [100.0] * 210
    history = _rows_from_closes("AAA", closes)
    scores = t04_connors_rsi2.score(history)
    # RSI is exactly 50 (neither extreme) and close == SMA (neither strict
    # inequality holds): no agreed setup.
    assert "AAA" not in scores


def test_bullish_setup_uptrend_then_pullback():
    # A long, gentle uptrend (closes well below the eventual level for most
    # of the window) followed by two sharp down days: the pullback pushes
    # RSI(2) toward oversold while the 200-day trailing average, dragged
    # down by the earlier, lower prices, still sits below the latest close
    # - both legs of the conjunction agree bullish.
    rising = list(np.linspace(80.0, 140.0, 215))
    closes = rising + [rising[-1] - 6.0, rising[-1] - 10.0]
    history = _rows_from_closes("AAA", closes)

    scores = t04_connors_rsi2.score(history)

    expected_rsi2 = _reference_rsi2(closes)
    expected_sma = _reference_sma(closes, t04_connors_rsi2.TREND_WINDOW)
    assert closes[-1] > expected_sma
    assert expected_rsi2 < t04_connors_rsi2.OVERSOLD

    assert "AAA" in scores
    expected_score = (t04_connors_rsi2.OVERSOLD - expected_rsi2) / t04_connors_rsi2.OVERSOLD
    assert scores["AAA"] == pytest.approx(expected_score, abs=1e-6)
    assert scores["AAA"] > 0


def test_bearish_setup_downtrend_then_bounce():
    # Mirror of the bullish case: a long downtrend followed by two sharp
    # up days - the bounce pushes RSI(2) toward overbought while the
    # 200-day trailing average, held up by the earlier, higher prices,
    # still sits above the latest close.
    falling = list(np.linspace(140.0, 80.0, 215))
    closes = falling + [falling[-1] + 6.0, falling[-1] + 10.0]
    history = _rows_from_closes("AAA", closes)

    scores = t04_connors_rsi2.score(history)

    expected_rsi2 = _reference_rsi2(closes)
    expected_sma = _reference_sma(closes, t04_connors_rsi2.TREND_WINDOW)
    assert closes[-1] < expected_sma
    assert expected_rsi2 > t04_connors_rsi2.OVERBOUGHT

    assert "AAA" in scores
    expected_score = -(expected_rsi2 - t04_connors_rsi2.OVERBOUGHT) / t04_connors_rsi2.OVERSOLD
    assert scores["AAA"] == pytest.approx(expected_score, abs=1e-6)
    assert scores["AAA"] < 0


def test_insufficient_history_abstains():
    closes = _monotonic_closes(t04_connors_rsi2.MIN_ROWS - 1, step=1.0)
    history = _rows_from_closes("AAA", closes)
    scores = t04_connors_rsi2.score(history)
    assert "AAA" not in scores


def test_empty_history_returns_empty_series():
    scores = t04_connors_rsi2.score(pd.DataFrame())
    assert scores.empty


def test_has_future_prefilter_drops_ineligible_symbols():
    rising = list(np.linspace(80.0, 140.0, 215))
    closes = rising + [rising[-1] - 6.0, rising[-1] - 10.0]
    eligible = _rows_from_closes("AAA", closes)
    eligible["has_future"] = True
    ineligible = _rows_from_closes("ZZZ", closes)
    ineligible["has_future"] = False
    history = pd.concat([eligible, ineligible], ignore_index=True)

    scores = t04_connors_rsi2.score(history)

    assert "AAA" in scores
    assert "ZZZ" not in scores


def test_rules_fired_reports_abstain_with_reason():
    closes = [100.0] * 210
    history = _rows_from_closes("AAA", closes)
    reasoning = t04_connors_rsi2.rules_fired(history, "AAA")
    assert "abstain" in reasoning


def test_rules_fired_reports_bullish_direction():
    rising = list(np.linspace(80.0, 140.0, 215))
    closes = rising + [rising[-1] - 6.0, rising[-1] - 10.0]
    history = _rows_from_closes("AAA", closes)
    reasoning = t04_connors_rsi2.rules_fired(history, "AAA")
    assert "bullish" in reasoning


def test_rules_fired_insufficient_history():
    closes = _monotonic_closes(t04_connors_rsi2.MIN_ROWS - 1, step=1.0)
    history = _rows_from_closes("AAA", closes)
    reasoning = t04_connors_rsi2.rules_fired(history, "AAA")
    assert "insufficient history" in reasoning


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result
