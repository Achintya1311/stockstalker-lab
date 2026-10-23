import numpy as np
import pandas as pd
import pytest

from strategies import t07_bollinger_squeeze_breakout as t07
from strategies.t07_bollinger_squeeze_breakout_audit import check_cross_symbol_causality


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


def _reference_pctb_and_squeeze(closes: list[float]) -> tuple[float, bool]:
    """Independent numpy computation (explicit per-window loops, not
    pandas' rolling machinery) used to cross-check the module under test
    rather than re-deriving the same formula in the same shape - same
    convention `strategies/t04_connors_rsi2.py` and
    `strategies/t05_macd_crossover.py`'s own tests use for a harder-to-
    hand-derive signal."""
    arr = np.asarray(closes, dtype=float)
    widths = []
    for end in range(t07.WINDOW, len(arr) + 1):
        window = arr[end - t07.WINDOW : end]
        middle = window.mean()
        sigma = window.std(ddof=0)
        band_width = t07.SIGMA_MULT * sigma
        widths.append(float("nan") if middle == 0 else (2 * band_width) / middle)
    latest_width = widths[-1]
    lookback_widths = widths[-t07.WIDTH_LOOKBACK :]
    squeeze = latest_width <= min(lookback_widths)

    window = arr[-t07.WINDOW :]
    middle = window.mean()
    sigma = window.std(ddof=0)
    band_width = t07.SIGMA_MULT * sigma
    if band_width == 0:
        return float("nan"), squeeze
    upper, lower = middle + band_width, middle - band_width
    pctb = (arr[-1] - lower) / (upper - lower)
    return pctb, squeeze


def _narrowing_oscillation(n_rows: int, wide_amp: float = 3.0, narrow_amp: float = 0.3, narrow_tail: int = 19) -> list[float]:
    """`n_rows` closes oscillating at `wide_amp` around 100, narrowing to
    `narrow_amp` for the trailing `narrow_tail` rows - a genuine squeeze
    (band width strictly decreasing into the latest few bars, not a
    constant-amplitude series where every window trivially ties for the
    126-session low)."""
    closes = []
    for i in range(n_rows):
        amp = narrow_amp if i >= n_rows - narrow_tail else wide_amp
        closes.append(100.0 + (amp if i % 2 == 0 else -amp))
    return closes


def _widening_oscillation(n_rows: int, narrow_amp: float = 0.3, wide_amp: float = 3.0, wide_tail: int = 19) -> list[float]:
    """The mirror image of `_narrowing_oscillation`: narrow for most of
    history, then wide for the trailing `wide_tail` rows - today's width
    is not a new low, used to prove the squeeze gate actually suppresses
    a would-be breakout rather than %B outside the bands firing on its
    own."""
    closes = []
    for i in range(n_rows):
        amp = wide_amp if i >= n_rows - wide_tail else narrow_amp
        closes.append(100.0 + (amp if i % 2 == 0 else -amp))
    return closes


def test_squeeze_then_break_above_upper_band_is_bullish():
    closes = _narrowing_oscillation(t07.MIN_ROWS - 1) + [101.5]
    history = _rows_from_closes("AAA", closes)

    pctb, squeeze = _reference_pctb_and_squeeze(closes)
    assert squeeze
    assert pctb > 1

    scores = t07.score(history)
    assert "AAA" in scores
    assert scores["AAA"] == pytest.approx(pctb - 1, abs=1e-9)
    assert scores["AAA"] > 0


def test_squeeze_then_break_below_lower_band_is_bearish():
    closes = _narrowing_oscillation(t07.MIN_ROWS - 1) + [98.5]
    history = _rows_from_closes("AAA", closes)

    pctb, squeeze = _reference_pctb_and_squeeze(closes)
    assert squeeze
    assert pctb < 0

    scores = t07.score(history)
    assert "AAA" in scores
    assert scores["AAA"] == pytest.approx(pctb, abs=1e-9)
    assert scores["AAA"] < 0


def test_squeeze_without_a_break_abstains():
    closes = _narrowing_oscillation(t07.MIN_ROWS)
    history = _rows_from_closes("AAA", closes)

    pctb, squeeze = _reference_pctb_and_squeeze(closes)
    assert squeeze
    assert 0 <= pctb <= 1

    scores = t07.score(history)
    assert "AAA" not in scores


def test_break_without_a_squeeze_abstains():
    # Today's band is wide (not a 126-session low), even though the
    # close itself sits well outside it - proves the squeeze gate, not
    # just the band break, decides the outcome.
    closes = _widening_oscillation(t07.MIN_ROWS - 1) + [110.0]
    history = _rows_from_closes("AAA", closes)

    pctb, squeeze = _reference_pctb_and_squeeze(closes)
    assert not squeeze
    assert pctb > 1

    scores = t07.score(history)
    assert "AAA" not in scores


def test_flat_series_abstains():
    # Zero standard deviation collapses the bands to a single price -
    # %B is undefined, not infinitely outside the bands, even though a
    # flat series trivially "squeezes" to a zero width.
    closes = [100.0] * t07.MIN_ROWS
    history = _rows_from_closes("AAA", closes)
    scores = t07.score(history)
    assert "AAA" not in scores


def test_insufficient_history_abstains():
    closes = _narrowing_oscillation(t07.MIN_ROWS - 1)
    history = _rows_from_closes("AAA", closes)
    scores = t07.score(history)
    assert "AAA" not in scores


def test_empty_history_returns_empty_series():
    scores = t07.score(pd.DataFrame())
    assert scores.empty


def test_has_future_prefilter_drops_ineligible_symbols():
    closes = _narrowing_oscillation(t07.MIN_ROWS - 1) + [101.5]
    eligible = _rows_from_closes("AAA", closes)
    eligible["has_future"] = True
    ineligible = _rows_from_closes("ZZZ", closes)
    ineligible["has_future"] = False
    history = pd.concat([eligible, ineligible], ignore_index=True)

    scores = t07.score(history)

    assert "AAA" in scores
    assert "ZZZ" not in scores


def test_rules_fired_reports_no_squeeze_abstain():
    closes = _widening_oscillation(t07.MIN_ROWS - 1) + [110.0]
    history = _rows_from_closes("AAA", closes)
    reasoning = t07.rules_fired(history, "AAA")
    assert "not at its 126-session low" in reasoning


def test_rules_fired_reports_squeeze_without_break_abstain():
    closes = _narrowing_oscillation(t07.MIN_ROWS)
    history = _rows_from_closes("AAA", closes)
    reasoning = t07.rules_fired(history, "AAA")
    assert "squeeze held" in reasoning
    assert "inside the bands" in reasoning


def test_rules_fired_reports_flat_bands_abstain():
    closes = [100.0] * t07.MIN_ROWS
    history = _rows_from_closes("AAA", closes)
    reasoning = t07.rules_fired(history, "AAA")
    assert "flat bands" in reasoning


def test_rules_fired_reports_bullish_direction():
    closes = _narrowing_oscillation(t07.MIN_ROWS - 1) + [101.5]
    history = _rows_from_closes("AAA", closes)
    reasoning = t07.rules_fired(history, "AAA")
    assert "bullish" in reasoning


def test_rules_fired_reports_bearish_direction():
    closes = _narrowing_oscillation(t07.MIN_ROWS - 1) + [98.5]
    history = _rows_from_closes("AAA", closes)
    reasoning = t07.rules_fired(history, "AAA")
    assert "bearish" in reasoning


def test_rules_fired_insufficient_history():
    closes = _narrowing_oscillation(t07.MIN_ROWS - 1)
    history = _rows_from_closes("AAA", closes)
    reasoning = t07.rules_fired(history, "AAA")
    assert "insufficient history" in reasoning


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result
