import numpy as np
import pandas as pd
import pytest

from strategies import t06_bollinger_pctb
from strategies.t06_bollinger_pctb_audit import check_cross_symbol_causality


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


def _reference_pctb(closes: list[float]) -> float:
    """Independent numpy computation (plain `mean`/`std(ddof=0)` over the
    trailing window, not pandas' rolling machinery) used to cross-check
    the module under test rather than re-deriving the same formula in the
    same shape."""
    window = np.array(closes[-t06_bollinger_pctb.WINDOW :])
    middle = window.mean()
    sigma = window.std(ddof=0)
    band_width = t06_bollinger_pctb.SIGMA_MULT * sigma
    upper, lower = middle + band_width, middle - band_width
    return (closes[-1] - lower) / (upper - lower)


def _oscillating_closes(n_rows: int, base: float = 100.0, amplitude: float = 1.0) -> list[float]:
    return [base + (amplitude if i % 2 == 0 else -amplitude) for i in range(n_rows)]


def test_close_below_lower_band_is_bullish():
    closes = _oscillating_closes(19) + [80.0]
    history = _rows_from_closes("AAA", closes)

    pctb = _reference_pctb(closes)
    assert pctb < 0

    scores = t06_bollinger_pctb.score(history)
    assert "AAA" in scores
    assert scores["AAA"] == pytest.approx(-pctb, abs=1e-9)
    assert scores["AAA"] > 0


def test_close_above_upper_band_is_bearish():
    closes = _oscillating_closes(19) + [120.0]
    history = _rows_from_closes("AAA", closes)

    pctb = _reference_pctb(closes)
    assert pctb > 1

    scores = t06_bollinger_pctb.score(history)
    assert "AAA" in scores
    assert scores["AAA"] == pytest.approx(1 - pctb, abs=1e-9)
    assert scores["AAA"] < 0


def test_close_inside_bands_abstains():
    closes = _oscillating_closes(20)
    history = _rows_from_closes("AAA", closes)

    pctb = _reference_pctb(closes)
    assert 0 <= pctb <= 1

    scores = t06_bollinger_pctb.score(history)
    assert "AAA" not in scores


def test_flat_series_abstains():
    # Zero standard deviation collapses the bands to a single price -
    # %B is undefined, not infinitely outside the bands.
    closes = [100.0] * 25
    history = _rows_from_closes("AAA", closes)
    scores = t06_bollinger_pctb.score(history)
    assert "AAA" not in scores


def test_insufficient_history_abstains():
    closes = _oscillating_closes(t06_bollinger_pctb.MIN_ROWS - 1)
    history = _rows_from_closes("AAA", closes)
    scores = t06_bollinger_pctb.score(history)
    assert "AAA" not in scores


def test_empty_history_returns_empty_series():
    scores = t06_bollinger_pctb.score(pd.DataFrame())
    assert scores.empty


def test_has_future_prefilter_drops_ineligible_symbols():
    closes = _oscillating_closes(19) + [80.0]
    eligible = _rows_from_closes("AAA", closes)
    eligible["has_future"] = True
    ineligible = _rows_from_closes("ZZZ", closes)
    ineligible["has_future"] = False
    history = pd.concat([eligible, ineligible], ignore_index=True)

    scores = t06_bollinger_pctb.score(history)

    assert "AAA" in scores
    assert "ZZZ" not in scores


def test_rules_fired_reports_abstain_with_reason():
    closes = _oscillating_closes(20)
    history = _rows_from_closes("AAA", closes)
    reasoning = t06_bollinger_pctb.rules_fired(history, "AAA")
    assert "abstain" in reasoning


def test_rules_fired_reports_flat_bands_abstain():
    closes = [100.0] * 25
    history = _rows_from_closes("AAA", closes)
    reasoning = t06_bollinger_pctb.rules_fired(history, "AAA")
    assert "abstain" in reasoning
    assert "flat bands" in reasoning


def test_rules_fired_reports_bullish_direction():
    closes = _oscillating_closes(19) + [80.0]
    history = _rows_from_closes("AAA", closes)
    reasoning = t06_bollinger_pctb.rules_fired(history, "AAA")
    assert "bullish" in reasoning


def test_rules_fired_insufficient_history():
    closes = _oscillating_closes(t06_bollinger_pctb.MIN_ROWS - 1)
    history = _rows_from_closes("AAA", closes)
    reasoning = t06_bollinger_pctb.rules_fired(history, "AAA")
    assert "insufficient history" in reasoning


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result
