import numpy as np
import pandas as pd
import pytest

from strategies import t14_cci
from strategies.t14_cci_audit import check_cross_symbol_causality


def _rows_from_hlc(
    symbol: str,
    highs: list[float],
    lows: list[float],
    closes: list[float],
    base_volume: float = 1_000_000.0,
) -> pd.DataFrame:
    dates = pd.bdate_range("2015-01-01", periods=len(closes)).strftime("%Y-%m-%d")
    rows = []
    prev_close = float(closes[0])
    for date, high, low, close in zip(dates, highs, lows, closes):
        close = float(close)
        rows.append(
            {
                "date": date,
                "symbol": symbol,
                "open": prev_close,
                "high": float(high),
                "low": float(low),
                "close": close,
                "prevclose": prev_close,
                "volume": base_volume,
            }
        )
        prev_close = close
    return pd.DataFrame(rows)


def _reference_cci(highs: list[float], lows: list[float], closes: list[float]) -> tuple[float, float]:
    """Independent, loop-based CCI(20) on the full series (Lambert's own
    definition: mean *absolute* deviation of TP from the current bar's
    SMA_TP, not the standard deviation), used to cross-check the
    vectorized implementation under test rather than re-deriving the same
    formula in a different shape. Returns (cci_latest, cci_prev)."""
    tp = [(h + l + c) / 3.0 for h, l, c in zip(highs, lows, closes)]
    n = len(tp)
    out = [float("nan")] * n
    for i in range(t14_cci.PERIOD - 1, n):
        window = np.array(tp[i - t14_cci.PERIOD + 1 : i + 1])
        sma = window.mean()
        mad = np.mean(np.abs(window - sma))
        out[i] = float("nan") if mad == 0 else (tp[i] - sma) / (t14_cci.SCALE * mad)
    return out[-1], out[-2]


def _flat_baseline(n_flat: int, level: float = 100.0, half_spread: float = 0.2) -> tuple[list, list, list]:
    highs = [level + half_spread] * n_flat
    lows = [level - half_spread] * n_flat
    closes = [level] * n_flat
    return highs, lows, closes


def test_bullish_cross_after_sharp_drop_then_recovery():
    # A flat baseline keeps SMA_TP/MeanDev stable; a sharp one-bar drop
    # pushes CCI deep below -100 (prior bar), then a partial recovery
    # pulls it back above -100 on the latest bar - a fresh cross up.
    n_flat = t14_cci.MIN_ROWS - 2
    highs, lows, closes = _flat_baseline(n_flat)
    highs += [100.0, 97.0]
    lows += [69.0, 95.0]
    closes += [70.0, 96.0]
    history = _rows_from_hlc("AAA", highs, lows, closes)

    cci_latest, cci_prev = _reference_cci(highs, lows, closes)
    assert cci_prev <= -100.0
    assert cci_latest > -100.0

    scores = t14_cci.score(history)
    assert "AAA" in scores
    expected_score = (cci_latest - t14_cci.LOWER_THRESHOLD) / 100.0
    assert scores["AAA"] == pytest.approx(expected_score, abs=1e-6)
    assert scores["AAA"] > 0


def test_bearish_cross_after_sharp_rally_then_pullback():
    # Mirror of the above: a sharp one-bar rally pushes CCI deep above
    # +100 (prior bar), then a partial pullback brings it back below +100
    # on the latest bar - a fresh cross down.
    n_flat = t14_cci.MIN_ROWS - 2
    highs, lows, closes = _flat_baseline(n_flat)
    highs += [131.0, 107.0]
    lows += [129.0, 105.0]
    closes += [130.0, 106.0]
    history = _rows_from_hlc("AAA", highs, lows, closes)

    cci_latest, cci_prev = _reference_cci(highs, lows, closes)
    assert cci_prev >= 100.0
    assert cci_latest < 100.0

    scores = t14_cci.score(history)
    assert "AAA" in scores
    expected_score = (cci_latest - t14_cci.UPPER_THRESHOLD) / 100.0
    assert scores["AAA"] == pytest.approx(expected_score, abs=1e-6)
    assert scores["AAA"] < 0


def test_already_crossed_abstains():
    # Both the prior and the latest bar sit deep below -100 - no fresh
    # cross, even though CCI is clearly in oversold territory on the
    # latest bar too (the literal "crossing" reading, not a continuous
    # "is below" state).
    n_flat = t14_cci.MIN_ROWS - 2
    highs, lows, closes = _flat_baseline(n_flat)
    highs += [70.5, 70.5]
    lows += [69.5, 69.5]
    closes += [70.0, 70.0]
    history = _rows_from_hlc("AAA", highs, lows, closes)

    cci_latest, cci_prev = _reference_cci(highs, lows, closes)
    assert cci_prev <= -100.0
    assert cci_latest <= -100.0

    scores = t14_cci.score(history)
    assert "AAA" not in scores


def test_flat_series_abstains():
    # A perfectly flat series collapses MeanDev to exactly 0: CCI is
    # undefined throughout, so this abstains rather than dividing by zero.
    highs, lows, closes = _flat_baseline(t14_cci.MIN_ROWS)
    history = _rows_from_hlc("AAA", highs, lows, closes)
    scores = t14_cci.score(history)
    assert "AAA" not in scores


def test_insufficient_history_abstains():
    highs, lows, closes = _flat_baseline(t14_cci.MIN_ROWS - 1)
    history = _rows_from_hlc("AAA", highs, lows, closes)
    scores = t14_cci.score(history)
    assert "AAA" not in scores


def test_empty_history_returns_empty_series():
    scores = t14_cci.score(pd.DataFrame())
    assert scores.empty


def test_has_future_prefilter_drops_ineligible_symbols():
    n_flat = t14_cci.MIN_ROWS - 2
    highs, lows, closes = _flat_baseline(n_flat)
    highs += [100.0, 97.0]
    lows += [69.0, 95.0]
    closes += [70.0, 96.0]
    eligible = _rows_from_hlc("AAA", highs, lows, closes)
    eligible["has_future"] = True
    ineligible = _rows_from_hlc("ZZZ", highs, lows, closes)
    ineligible["has_future"] = False
    history = pd.concat([eligible, ineligible], ignore_index=True)

    scores = t14_cci.score(history)

    assert "AAA" in scores
    assert "ZZZ" not in scores


def test_rules_fired_reports_abstain_with_reason():
    highs, lows, closes = _flat_baseline(t14_cci.MIN_ROWS)
    history = _rows_from_hlc("AAA", highs, lows, closes)
    reasoning = t14_cci.rules_fired(history, "AAA")
    assert "abstain" in reasoning


def test_rules_fired_reports_bullish_direction():
    n_flat = t14_cci.MIN_ROWS - 2
    highs, lows, closes = _flat_baseline(n_flat)
    highs += [100.0, 97.0]
    lows += [69.0, 95.0]
    closes += [70.0, 96.0]
    history = _rows_from_hlc("AAA", highs, lows, closes)
    reasoning = t14_cci.rules_fired(history, "AAA")
    assert "bullish" in reasoning


def test_rules_fired_insufficient_history():
    highs, lows, closes = _flat_baseline(t14_cci.MIN_ROWS - 1)
    history = _rows_from_hlc("AAA", highs, lows, closes)
    reasoning = t14_cci.rules_fired(history, "AAA")
    assert "insufficient history" in reasoning


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result
