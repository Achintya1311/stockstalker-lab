import numpy as np
import pandas as pd

from strategies import champion_v1
from strategies.champion_v1_audit import check_cross_symbol_causality


def _trending_symbol(symbol: str, n_rows: int, daily_move: float, base_volume: float = 1_000_000.0) -> pd.DataFrame:
    """A deterministic, steadily trending series with a volume trend matching
    the price trend (rising volume on the uptrend, falling on the downtrend) -
    a known expected signal: every component (trend, momentum, volume) should
    point the same way, so the blended score's sign is unambiguous."""
    dates = pd.bdate_range("2015-01-01", periods=n_rows).strftime("%Y-%m-%d")
    closes = 100.0 * (1.0 + daily_move) ** np.arange(n_rows)
    volumes = base_volume * (1.0 + daily_move) ** np.arange(n_rows)

    rows = []
    prev_close = float(closes[0])
    for date, close, volume in zip(dates, closes, volumes):
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
                "volume": float(volume),
            }
        )
        prev_close = close
    return pd.DataFrame(rows)


def test_strong_steady_uptrend_scores_bullish():
    history = _trending_symbol("AAA", champion_v1.MIN_ROWS + 10, daily_move=0.01)
    scores = champion_v1.score(history)
    assert "AAA" in scores
    assert scores["AAA"] > 0


def test_strong_steady_downtrend_scores_bearish():
    history = _trending_symbol("AAA", champion_v1.MIN_ROWS + 10, daily_move=-0.01)
    scores = champion_v1.score(history)
    assert "AAA" in scores
    assert scores["AAA"] < 0


def test_flat_series_scores_neutral():
    # Constant price and volume: no trend, no momentum, no volume signal - the
    # known expected signal here is exactly zero, not "small".
    history = _trending_symbol("AAA", champion_v1.MIN_ROWS + 10, daily_move=0.0)
    scores = champion_v1.score(history)
    assert "AAA" in scores
    assert scores["AAA"] == 0.0


def test_too_little_history_abstains():
    history = _trending_symbol("AAA", champion_v1.MIN_ROWS - 1, daily_move=0.01)
    scores = champion_v1.score(history)
    assert "AAA" not in scores


def test_empty_history_returns_empty_series():
    scores = champion_v1.score(pd.DataFrame(columns=["date", "symbol", "open", "high", "low", "close", "prevclose", "volume"]))
    assert scores.empty


def test_score_is_per_symbol_not_coupled_across_the_universe():
    bullish = _trending_symbol("AAA", champion_v1.MIN_ROWS + 10, daily_move=0.01)
    bearish = _trending_symbol("BBB", champion_v1.MIN_ROWS + 10, daily_move=-0.01)
    scores = champion_v1.score(pd.concat([bullish, bearish], ignore_index=True))
    assert scores["AAA"] > 0
    assert scores["BBB"] < 0


def test_rules_fired_reports_the_same_direction_as_score():
    history = _trending_symbol("AAA", champion_v1.MIN_ROWS + 10, daily_move=0.01)
    reasoning = champion_v1.rules_fired(history, "AAA")
    assert "bullish" in reasoning
    assert "blended" in reasoning


def test_rules_fired_reports_abstain_on_insufficient_history():
    history = _trending_symbol("AAA", champion_v1.MIN_ROWS - 1, daily_move=0.01)
    reasoning = champion_v1.rules_fired(history, "AAA")
    assert "abstain" in reasoning


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result
