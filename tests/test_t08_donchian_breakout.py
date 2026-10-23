import pandas as pd
import pytest

from strategies import t08_donchian_breakout_20 as t08_20
from strategies import t08_donchian_breakout_55 as t08_55
from strategies.t08_donchian_breakout_audit import check_cross_symbol_causality


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


def _ranging_then(window: int, breakout_close: float | None, tail_value: float = 100.0) -> list[float]:
    """`window` sessions oscillating in a fixed range around 100, then an
    optional final bar at `breakout_close`. The range alternates
    99.0/101.0 so the prior-window high/low are well-defined and not
    tied to the final bar's own value."""
    closes = []
    for i in range(window):
        closes.append(101.0 if i % 2 == 0 else 99.0)
    if breakout_close is not None:
        closes.append(breakout_close)
    else:
        closes.append(tail_value)
    return closes


@pytest.mark.parametrize("module", [t08_20, t08_55])
def test_new_high_above_prior_window_is_bullish(module):
    closes = _ranging_then(module.WINDOW, breakout_close=105.0)
    history = _rows_from_closes("AAA", closes)

    scores = module.score(history)

    assert "AAA" in scores
    assert scores["AAA"] == pytest.approx((105.0 - 101.0) / 101.0, abs=1e-9)
    assert scores["AAA"] > 0


@pytest.mark.parametrize("module", [t08_20, t08_55])
def test_new_low_below_prior_window_is_bearish(module):
    closes = _ranging_then(module.WINDOW, breakout_close=95.0)
    history = _rows_from_closes("AAA", closes)

    scores = module.score(history)

    assert "AAA" in scores
    assert scores["AAA"] == pytest.approx((95.0 - 99.0) / 99.0, abs=1e-9)
    assert scores["AAA"] < 0


@pytest.mark.parametrize("module", [t08_20, t08_55])
def test_close_inside_prior_range_abstains(module):
    closes = _ranging_then(module.WINDOW, breakout_close=100.0)
    history = _rows_from_closes("AAA", closes)

    scores = module.score(history)

    assert "AAA" not in scores


@pytest.mark.parametrize("module", [t08_20, t08_55])
def test_tie_with_prior_high_abstains(module):
    # Exactly matching the prior window's high is not a NEW high.
    closes = _ranging_then(module.WINDOW, breakout_close=101.0)
    history = _rows_from_closes("AAA", closes)

    scores = module.score(history)

    assert "AAA" not in scores


@pytest.mark.parametrize("module", [t08_20, t08_55])
def test_tie_with_prior_low_abstains(module):
    closes = _ranging_then(module.WINDOW, breakout_close=99.0)
    history = _rows_from_closes("AAA", closes)

    scores = module.score(history)

    assert "AAA" not in scores


@pytest.mark.parametrize("module", [t08_20, t08_55])
def test_insufficient_history_abstains(module):
    closes = _ranging_then(module.WINDOW, breakout_close=105.0)[:-1]  # window rows only, no final bar
    history = _rows_from_closes("AAA", closes)

    scores = module.score(history)

    assert "AAA" not in scores


@pytest.mark.parametrize("module", [t08_20, t08_55])
def test_empty_history_returns_empty_series(module):
    scores = module.score(pd.DataFrame())
    assert scores.empty


@pytest.mark.parametrize("module", [t08_20, t08_55])
def test_has_future_prefilter_drops_ineligible_symbols(module):
    closes = _ranging_then(module.WINDOW, breakout_close=105.0)
    eligible = _rows_from_closes("AAA", closes)
    eligible["has_future"] = True
    ineligible = _rows_from_closes("ZZZ", closes)
    ineligible["has_future"] = False
    history = pd.concat([eligible, ineligible], ignore_index=True)

    scores = module.score(history)

    assert "AAA" in scores
    assert "ZZZ" not in scores


@pytest.mark.parametrize("module", [t08_20, t08_55])
def test_rules_fired_reports_abstain_with_range(module):
    closes = _ranging_then(module.WINDOW, breakout_close=100.0)
    history = _rows_from_closes("AAA", closes)
    reasoning = module.rules_fired(history, "AAA")
    assert "within prior" in reasoning
    assert "abstain" in reasoning


@pytest.mark.parametrize("module", [t08_20, t08_55])
def test_rules_fired_reports_bullish_direction(module):
    closes = _ranging_then(module.WINDOW, breakout_close=105.0)
    history = _rows_from_closes("AAA", closes)
    reasoning = module.rules_fired(history, "AAA")
    assert "bullish" in reasoning


@pytest.mark.parametrize("module", [t08_20, t08_55])
def test_rules_fired_reports_bearish_direction(module):
    closes = _ranging_then(module.WINDOW, breakout_close=95.0)
    history = _rows_from_closes("AAA", closes)
    reasoning = module.rules_fired(history, "AAA")
    assert "bearish" in reasoning


@pytest.mark.parametrize("module", [t08_20, t08_55])
def test_rules_fired_insufficient_history(module):
    closes = _ranging_then(module.WINDOW, breakout_close=105.0)[:-1]
    history = _rows_from_closes("AAA", closes)
    reasoning = module.rules_fired(history, "AAA")
    assert "insufficient history" in reasoning


def test_causality_audit_passes_window_20():
    result = check_cross_symbol_causality(window=20, n_rows=40)
    assert result["passed"], result


def test_causality_audit_passes_window_55():
    result = check_cross_symbol_causality(window=55, n_rows=80)
    assert result["passed"], result
