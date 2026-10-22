import pandas as pd
import pytest

from strategies import t03_rsi_thresholds
from strategies.t03_rsi_thresholds_audit import check_cross_symbol_causality


def _constant_steps(symbol: str, n_rows: int, step: float, base: float = 100.0, base_volume: float = 1_000_000.0) -> pd.DataFrame:
    """`n_rows` rows, each close exactly `step` away from the previous one -
    a known expected signal: with every move the same sign and size, Wilder's
    smoothing converges so that `avg_gain`/`avg_loss` is fully determined by
    `step`'s sign (all gains and no losses, or the reverse), giving an exact,
    hand-derivable RSI at the boundary (0 or 100) rather than an
    approximation.
    """
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


def test_a_steadily_rising_series_hits_rsi_100_and_scores_fully_bearish():
    # Every move is a gain, no losses at all: avg_loss == 0 and avg_gain > 0,
    # so RSI -> 100 exactly (overbought, not oversold) - the mirror of the
    # falling case below, confirming the formula's boundary behaviour both ways.
    history = _constant_steps("AAA", t03_rsi_thresholds.MIN_ROWS, step=1.0)
    scores = t03_rsi_thresholds.score(history)
    assert "AAA" in scores
    assert scores["AAA"] == pytest.approx(-1.0, rel=1e-9)


def test_a_steadily_falling_series_scores_fully_bullish():
    # Every move is a loss, no gains at all: avg_gain == 0, avg_loss > 0, so
    # RSI -> 0 exactly, the most oversold the formula can report:
    # score = (30 - 0) / 30 = 1.0.
    history = _constant_steps("AAA", t03_rsi_thresholds.MIN_ROWS, step=-1.0)
    scores = t03_rsi_thresholds.score(history)
    assert "AAA" in scores
    assert scores["AAA"] == pytest.approx(1.0, rel=1e-9)


def test_a_flat_series_has_rsi_50_and_abstains():
    # No gains and no losses: the explicit avg_gain==0 and avg_loss==0 branch
    # sets RSI=50, squarely inside the 30-70 band, so the symbol abstains.
    history = _flat_series("AAA", t03_rsi_thresholds.MIN_ROWS)
    scores = t03_rsi_thresholds.score(history)
    assert "AAA" not in scores


def test_too_little_history_abstains():
    history = _constant_steps("AAA", t03_rsi_thresholds.MIN_ROWS, step=-1.0)
    history = history.iloc[:-1]  # one row short of MIN_ROWS
    scores = t03_rsi_thresholds.score(history)
    assert "AAA" not in scores


def test_empty_history_returns_empty_series():
    scores = t03_rsi_thresholds.score(
        pd.DataFrame(columns=["date", "symbol", "open", "high", "low", "close", "prevclose", "volume"])
    )
    assert scores.empty


def test_score_is_per_symbol_not_coupled_across_the_universe():
    falling = _constant_steps("AAA", t03_rsi_thresholds.MIN_ROWS, step=-1.0)
    rising = _constant_steps("BBB", t03_rsi_thresholds.MIN_ROWS, step=1.0)
    scores = t03_rsi_thresholds.score(pd.concat([falling, rising], ignore_index=True))
    assert scores["AAA"] > 0
    assert scores["BBB"] < 0


def test_rules_fired_reports_the_same_direction_as_score():
    history = _constant_steps("AAA", t03_rsi_thresholds.MIN_ROWS, step=-1.0)
    reasoning = t03_rsi_thresholds.rules_fired(history, "AAA")
    assert "bullish" in reasoning
    assert "RSI" in reasoning


def test_rules_fired_reports_abstain_on_insufficient_history():
    history = _constant_steps("AAA", t03_rsi_thresholds.MIN_ROWS, step=-1.0).iloc[:-1]
    reasoning = t03_rsi_thresholds.rules_fired(history, "AAA")
    assert "abstain" in reasoning


def test_rules_fired_reports_abstain_when_inside_the_band():
    history = _flat_series("AAA", t03_rsi_thresholds.MIN_ROWS)
    reasoning = t03_rsi_thresholds.rules_fired(history, "AAA")
    assert "abstain" in reasoning
    assert "30-70" in reasoning


def test_score_keeps_an_eligible_symbol_with_has_future_column_present():
    history = _constant_steps("AAA", t03_rsi_thresholds.MIN_ROWS, step=-1.0)
    history["has_future"] = True
    scores = t03_rsi_thresholds.score(history)
    assert scores["AAA"] > 0


def test_score_prefilter_does_not_change_an_eligible_symbols_score():
    falling = _constant_steps("AAA", t03_rsi_thresholds.MIN_ROWS, step=-1.0)
    ineligible = _constant_steps("ZZZ", t03_rsi_thresholds.MIN_ROWS, step=1.0)

    with_future_column = pd.concat([falling, ineligible], ignore_index=True)
    with_future_column["has_future"] = with_future_column["symbol"] == "AAA"

    without_future_column = falling  # no ineligible symbol, no has_future column at all

    assert t03_rsi_thresholds.score(with_future_column)["AAA"] == t03_rsi_thresholds.score(without_future_column)["AAA"]


def test_score_prefilter_drops_a_symbol_with_no_future_anywhere():
    falling = _constant_steps("AAA", t03_rsi_thresholds.MIN_ROWS, step=-1.0)
    ineligible = _constant_steps("ZZZ", t03_rsi_thresholds.MIN_ROWS, step=1.0)

    history = pd.concat([falling, ineligible], ignore_index=True)
    history["has_future"] = history["symbol"] == "AAA"

    scores = t03_rsi_thresholds.score(history)
    assert "ZZZ" not in scores


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result
