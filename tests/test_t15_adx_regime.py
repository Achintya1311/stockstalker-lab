import numpy as np
import pandas as pd
import pytest

from strategies import t15_adx_regime
from strategies.t15_adx_regime_audit import check_cross_symbol_causality


def _rows_from_closes(symbol: str, closes: list[float], base_volume: float = 1_000_000.0) -> pd.DataFrame:
    """Close-only fixture (high/low derived from open/close), same helper
    shape every earlier `strategies/t0*` test module uses - fine for the
    history-length/prefilter checks below, which don't depend on ADX's
    own intraday range at all."""
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


def _rows_from_ohlc(symbol: str, highs, lows, closes) -> pd.DataFrame:
    """Explicit high/low fixture - ADX needs real intraday range that
    differs from a close-derived high/low, unlike every earlier
    `strategies/t0*` card's close-only indicators."""
    n = len(closes)
    dates = pd.bdate_range("2015-01-01", periods=n).strftime("%Y-%m-%d")
    rows = []
    prev_close = float(closes[0])
    for date, h, l, c in zip(dates, highs, lows, closes):
        c = float(c)
        rows.append(
            {
                "date": date,
                "symbol": symbol,
                "open": prev_close,
                "high": float(h),
                "low": float(l),
                "close": c,
                "prevclose": prev_close,
                "volume": 1_000_000.0,
            }
        )
        prev_close = c
    return pd.DataFrame(rows)


def _make_ohlc(n: int, drift: float, noise_scale: float, range_scale: float, seed: int):
    """Synthetic OHLC series with real intraday range, used to search for
    (and then pin down) fixtures that land ADX(14) reliably in each of
    T15's three regime bands - the same construction
    `strategies/t15_adx_regime_audit.py::_synthetic_symbol` uses, exposed
    here so a test can also append a sharp tail move on top of it."""
    rng = np.random.default_rng(seed)
    steps = rng.normal(drift, noise_scale, n)
    closes = np.clip(100.0 + np.cumsum(steps), 1.0, None)
    ranges = np.clip(rng.normal(range_scale, range_scale * 0.2, n), 0.05, None)
    prev_close = float(closes[0])
    highs, lows = [], []
    for close, rng_width in zip(closes, ranges):
        close = float(close)
        highs.append(max(prev_close, close) + rng_width / 2)
        lows.append(min(prev_close, close) - rng_width / 2)
        prev_close = close
    return np.array(highs), np.array(lows), closes


def _reference_adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> float:
    """Independent, loop-based Wilder ADX on the full series, used to
    cross-check the vectorized implementation under test (and to confirm
    each fixture below actually lands in the regime band its test name
    claims) rather than re-deriving the same formula in a different
    shape, same convention `strategies/t04_connors_rsi2_audit.py`'s
    `_reference_rsi2` test helper uses."""
    n = len(close)
    tr = np.empty(n)
    tr[0] = high[0] - low[0]
    dm_plus = np.zeros(n)
    dm_minus = np.zeros(n)
    for i in range(1, n):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
        up, down = high[i] - high[i - 1], low[i - 1] - low[i]
        if up > down and up > 0:
            dm_plus[i] = up
        if down > up and down > 0:
            dm_minus[i] = down

    def wilder(arr):
        out = [None] * n
        if n > period:
            val = float(np.mean(arr[1 : period + 1]))
            out[period] = val
            for i in range(period + 1, n):
                val = val * (1 - 1 / period) + arr[i] * (1 / period)
                out[i] = val
        return out

    smoothed_tr, smoothed_dm_plus, smoothed_dm_minus = wilder(tr), wilder(dm_plus), wilder(dm_minus)
    dx = [None] * n
    for i in range(n):
        if smoothed_tr[i] is not None and smoothed_tr[i] > 0:
            di_plus = 100 * smoothed_dm_plus[i] / smoothed_tr[i]
            di_minus = 100 * smoothed_dm_minus[i] / smoothed_tr[i]
            total = di_plus + di_minus
            dx[i] = 100 * abs(di_plus - di_minus) / total if total > 0 else 0.0
        elif smoothed_tr[i] == 0:
            dx[i] = 0.0

    dx_valid = [v for v in dx[period:] if v is not None]
    if len(dx_valid) < period:
        return float("nan")
    val = float(np.mean(dx_valid[:period]))
    for v in dx_valid[period:]:
        val = val * (1 - 1 / period) + v * (1 / period)
    return val


def _reference_rsi14(closes: list[float]) -> float:
    """Independent, loop-based Wilder RSI(14), same shape as
    `strategies/t04_connors_rsi2_audit.py`'s `_reference_rsi2` but with
    period 14 (T03/T15's period) instead of 2 (T04's)."""
    period = 14
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for g, loss in zip(gains[period:], losses[period:]):
        avg_gain = avg_gain * (1 - 1 / period) + g * (1 / period)
        avg_loss = avg_loss * (1 - 1 / period) + loss * (1 / period)
    if avg_gain == 0 and avg_loss == 0:
        return 50.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


# Fixtures below were found by scanning drift values against
# `_reference_adx` (see the card's rules_plain) until each landed
# reliably in the band its test name claims, then pinned to fixed
# parameters - deterministic given the seed, not re-searched per run.


def test_trend_regime_bullish_matches_t01_spread():
    high, low, close = _make_ohlc(220, drift=0.3, noise_scale=1.0, range_scale=1.0, seed=1)
    reference_adx = _reference_adx(high, low, close)
    assert reference_adx > t15_adx_regime.TREND_THRESHOLD

    history = _rows_from_ohlc("AAA", high, low, close)
    scores = t15_adx_regime.score(history)

    fast_sma = float(pd.Series(close).tail(t15_adx_regime.FAST).mean())
    slow_sma = float(pd.Series(close).tail(t15_adx_regime.SLOW).mean())
    expected = (fast_sma - slow_sma) / abs(slow_sma)

    assert "AAA" in scores
    assert scores["AAA"] == pytest.approx(expected, abs=1e-9)
    assert scores["AAA"] > 0


def test_trend_regime_bearish_matches_t01_spread():
    high, low, close = _make_ohlc(220, drift=-0.3, noise_scale=1.0, range_scale=1.0, seed=1)
    reference_adx = _reference_adx(high, low, close)
    assert reference_adx > t15_adx_regime.TREND_THRESHOLD

    history = _rows_from_ohlc("AAA", high, low, close)
    scores = t15_adx_regime.score(history)

    fast_sma = float(pd.Series(close).tail(t15_adx_regime.FAST).mean())
    slow_sma = float(pd.Series(close).tail(t15_adx_regime.SLOW).mean())
    expected = (fast_sma - slow_sma) / abs(slow_sma)

    assert "AAA" in scores
    assert scores["AAA"] == pytest.approx(expected, abs=1e-9)
    assert scores["AAA"] < 0


def _choppy_then_sharp_move(direction: float):
    """218 choppy (near-zero-drift) bars, then two sharp `direction`-signed
    days - the choppy base keeps ADX low (oscillating moves cancel out in
    Wilder's directional-movement sum), while the sharp tail move pushes
    RSI(14) to its own extreme, the same "long base, then a sharp
    countermove" construction `strategies/t04_connors_rsi2_audit.py`'s
    test fixtures use, here built from a sideways base instead of a
    trending one so ADX itself (not just the trend filter) reads low."""
    high, low, close = _make_ohlc(218, drift=0.0, noise_scale=1.0, range_scale=1.0, seed=2)
    tail_closes = [close[-1] + direction * 8.0, close[-1] + direction * 18.0]
    prev_close = close[-1]
    tail_high, tail_low = [], []
    for tail_close in tail_closes:
        tail_high.append(max(prev_close, tail_close) + 0.3)
        tail_low.append(min(prev_close, tail_close) - 0.3)
        prev_close = tail_close
    full_close = np.concatenate([close, tail_closes])
    full_high = np.concatenate([high, tail_high])
    full_low = np.concatenate([low, tail_low])
    return full_high, full_low, full_close


def test_mean_reversion_regime_bullish_matches_t03_rsi():
    high, low, close = _choppy_then_sharp_move(direction=-1.0)
    reference_adx = _reference_adx(high, low, close)
    reference_rsi = _reference_rsi14(list(close))
    assert reference_adx < t15_adx_regime.MEAN_REVERSION_THRESHOLD
    assert reference_rsi < t15_adx_regime.RSI_OVERSOLD

    history = _rows_from_ohlc("BBB", high, low, close)
    scores = t15_adx_regime.score(history)

    expected = (t15_adx_regime.RSI_OVERSOLD - reference_rsi) / t15_adx_regime.RSI_OVERSOLD
    assert "BBB" in scores
    assert scores["BBB"] == pytest.approx(expected, abs=1e-6)
    assert scores["BBB"] > 0


def test_mean_reversion_regime_bearish_matches_t03_rsi():
    high, low, close = _choppy_then_sharp_move(direction=1.0)
    reference_adx = _reference_adx(high, low, close)
    reference_rsi = _reference_rsi14(list(close))
    assert reference_adx < t15_adx_regime.MEAN_REVERSION_THRESHOLD
    assert reference_rsi > t15_adx_regime.RSI_OVERBOUGHT

    history = _rows_from_ohlc("CCC", high, low, close)
    scores = t15_adx_regime.score(history)

    expected = -(reference_rsi - t15_adx_regime.RSI_OVERBOUGHT) / t15_adx_regime.RSI_OVERSOLD
    assert "CCC" in scores
    assert scores["CCC"] == pytest.approx(expected, abs=1e-6)
    assert scores["CCC"] < 0


def test_mean_reversion_regime_inside_thresholds_abstains():
    # Same choppy base as the mean-reversion fixtures above, but with no
    # sharp tail move at all: ADX stays low (mean-reversion regime
    # chosen), but RSI never reaches either threshold, so T03's own gate
    # - unchanged by T15 - doesn't fire.
    high, low, close = _make_ohlc(220, drift=0.0, noise_scale=1.0, range_scale=1.0, seed=2)
    reference_adx = _reference_adx(high, low, close)
    reference_rsi = _reference_rsi14(list(close))
    assert reference_adx < t15_adx_regime.MEAN_REVERSION_THRESHOLD
    assert t15_adx_regime.RSI_OVERSOLD < reference_rsi < t15_adx_regime.RSI_OVERBOUGHT

    history = _rows_from_ohlc("DDD", high, low, close)
    scores = t15_adx_regime.score(history)
    assert "DDD" not in scores


def test_no_mans_land_abstains():
    high, low, close = _make_ohlc(220, drift=0.10, noise_scale=1.0, range_scale=1.0, seed=2)
    reference_adx = _reference_adx(high, low, close)
    assert t15_adx_regime.MEAN_REVERSION_THRESHOLD <= reference_adx <= t15_adx_regime.TREND_THRESHOLD

    history = _rows_from_ohlc("EEE", high, low, close)
    scores = t15_adx_regime.score(history)
    assert "EEE" not in scores


def test_vectorized_adx_matches_independent_reference():
    # Cross-check `t15_adx_regime._adx_latest` itself (not just the final
    # score) against the independent loop-based reference, on the same
    # trend fixture `test_trend_regime_bullish_matches_t01_spread` uses.
    high, low, close = _make_ohlc(220, drift=0.3, noise_scale=1.0, range_scale=1.0, seed=1)
    reference_adx = _reference_adx(high, low, close)
    module_adx = t15_adx_regime._adx_latest(high, low, close, t15_adx_regime.PERIOD)
    assert module_adx == pytest.approx(reference_adx, abs=1e-6)


def test_insufficient_history_abstains():
    closes = [100.0 + i * 0.1 for i in range(t15_adx_regime.MIN_ROWS - 1)]
    history = _rows_from_closes("AAA", closes)
    scores = t15_adx_regime.score(history)
    assert "AAA" not in scores


def test_empty_history_returns_empty_series():
    scores = t15_adx_regime.score(pd.DataFrame())
    assert scores.empty


def test_has_future_prefilter_drops_ineligible_symbols():
    high, low, close = _make_ohlc(220, drift=0.3, noise_scale=1.0, range_scale=1.0, seed=1)
    eligible = _rows_from_ohlc("AAA", high, low, close)
    eligible["has_future"] = True
    ineligible = _rows_from_ohlc("ZZZ", high, low, close)
    ineligible["has_future"] = False
    history = pd.concat([eligible, ineligible], ignore_index=True)

    scores = t15_adx_regime.score(history)

    assert "AAA" in scores
    assert "ZZZ" not in scores


def test_rules_fired_reports_insufficient_history():
    closes = [100.0 + i * 0.1 for i in range(t15_adx_regime.MIN_ROWS - 1)]
    history = _rows_from_closes("AAA", closes)
    reasoning = t15_adx_regime.rules_fired(history, "AAA")
    assert "insufficient history" in reasoning


def test_rules_fired_reports_trend_regime_bullish():
    high, low, close = _make_ohlc(220, drift=0.3, noise_scale=1.0, range_scale=1.0, seed=1)
    history = _rows_from_ohlc("AAA", high, low, close)
    reasoning = t15_adx_regime.rules_fired(history, "AAA")
    assert "trend regime" in reasoning
    assert "bullish" in reasoning


def test_rules_fired_reports_mean_reversion_regime_bullish():
    high, low, close = _choppy_then_sharp_move(direction=-1.0)
    history = _rows_from_ohlc("BBB", high, low, close)
    reasoning = t15_adx_regime.rules_fired(history, "BBB")
    assert "mean-reversion regime" in reasoning
    assert "bullish" in reasoning


def test_rules_fired_reports_no_mans_land_abstain():
    high, low, close = _make_ohlc(220, drift=0.10, noise_scale=1.0, range_scale=1.0, seed=2)
    history = _rows_from_ohlc("EEE", high, low, close)
    reasoning = t15_adx_regime.rules_fired(history, "EEE")
    assert "no man's land" in reasoning
    assert "abstain" in reasoning


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result
