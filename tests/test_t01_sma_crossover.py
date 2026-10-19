import pandas as pd
import pytest

from strategies import t01_sma_crossover
from strategies.t01_sma_crossover_audit import check_cross_symbol_causality


def _plateau_then_shift(symbol: str, base: float, tail_value: float, base_volume: float = 1_000_000.0) -> pd.DataFrame:
    """`t01_sma_crossover.MIN_ROWS` rows at `base`, except the last `FAST` of
    them are `tail_value` instead - a known expected signal: with exactly
    `SLOW` rows total and the last `FAST` replaced, the slow SMA is a fixed
    weighted mean of `base` and `tail_value` and the fast SMA is exactly
    `tail_value` (all `FAST` of its own rows share that one value), so the
    crossover spread is fully determined by `base` and `tail_value` alone.
    """
    n_rows = t01_sma_crossover.MIN_ROWS
    fast = t01_sma_crossover.FAST
    dates = pd.bdate_range("2015-01-01", periods=n_rows).strftime("%Y-%m-%d")
    closes = [base] * (n_rows - fast) + [tail_value] * fast

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


def _expected_spread(base: float, tail_value: float) -> float:
    n_rows, fast = t01_sma_crossover.MIN_ROWS, t01_sma_crossover.FAST
    slow_mean = (base * (n_rows - fast) + tail_value * fast) / n_rows
    fast_mean = tail_value
    return (fast_mean - slow_mean) / abs(slow_mean)


def test_a_rising_tail_scores_bullish():
    history = _plateau_then_shift("AAA", base=100.0, tail_value=110.0)
    scores = t01_sma_crossover.score(history)
    assert "AAA" in scores
    assert scores["AAA"] > 0


def test_a_falling_tail_scores_bearish():
    history = _plateau_then_shift("AAA", base=100.0, tail_value=90.0)
    scores = t01_sma_crossover.score(history)
    assert "AAA" in scores
    assert scores["AAA"] < 0


def test_flat_series_scores_exactly_zero():
    history = _plateau_then_shift("AAA", base=100.0, tail_value=100.0)
    scores = t01_sma_crossover.score(history)
    assert scores["AAA"] == 0.0


def test_score_magnitude_matches_the_hand_derived_spread():
    # Known expected signal, exactly: 30 rows at 100.0 then 20 at 110.0 gives
    # slow_mean = (30*100 + 20*110) / 50 = 104.0, fast_mean = 110.0, so
    # spread = (110 - 104) / 104 = 6/104.
    history = _plateau_then_shift("AAA", base=100.0, tail_value=110.0)
    scores = t01_sma_crossover.score(history)
    assert scores["AAA"] == pytest.approx(_expected_spread(100.0, 110.0), rel=1e-9)
    assert scores["AAA"] == pytest.approx(6.0 / 104.0, rel=1e-9)


def test_too_little_history_abstains():
    history = _plateau_then_shift("AAA", base=100.0, tail_value=110.0)
    history = history.iloc[:-1]  # one row short of MIN_ROWS
    scores = t01_sma_crossover.score(history)
    assert "AAA" not in scores


def test_empty_history_returns_empty_series():
    scores = t01_sma_crossover.score(
        pd.DataFrame(columns=["date", "symbol", "open", "high", "low", "close", "prevclose", "volume"])
    )
    assert scores.empty


def test_score_is_per_symbol_not_coupled_across_the_universe():
    rising = _plateau_then_shift("AAA", base=100.0, tail_value=110.0)
    falling = _plateau_then_shift("BBB", base=100.0, tail_value=90.0)
    scores = t01_sma_crossover.score(pd.concat([rising, falling], ignore_index=True))
    assert scores["AAA"] > 0
    assert scores["BBB"] < 0


def test_rules_fired_reports_the_same_direction_as_score():
    history = _plateau_then_shift("AAA", base=100.0, tail_value=110.0)
    reasoning = t01_sma_crossover.rules_fired(history, "AAA")
    assert "bullish" in reasoning
    assert "spread" in reasoning


def test_rules_fired_reports_abstain_on_insufficient_history():
    history = _plateau_then_shift("AAA", base=100.0, tail_value=110.0).iloc[:-1]
    reasoning = t01_sma_crossover.rules_fired(history, "AAA")
    assert "abstain" in reasoning


def test_score_keeps_an_eligible_symbol_with_has_future_column_present():
    history = _plateau_then_shift("AAA", base=100.0, tail_value=110.0)
    history["has_future"] = True
    scores = t01_sma_crossover.score(history)
    assert scores["AAA"] > 0


def test_score_prefilter_does_not_change_an_eligible_symbols_score():
    rising = _plateau_then_shift("AAA", base=100.0, tail_value=110.0)
    ineligible = _plateau_then_shift("ZZZ", base=100.0, tail_value=90.0)

    with_future_column = pd.concat([rising, ineligible], ignore_index=True)
    with_future_column["has_future"] = with_future_column["symbol"] == "AAA"

    without_future_column = rising  # no ineligible symbol, no has_future column at all

    assert t01_sma_crossover.score(with_future_column)["AAA"] == t01_sma_crossover.score(without_future_column)["AAA"]


def test_score_prefilter_drops_a_symbol_with_no_future_anywhere():
    rising = _plateau_then_shift("AAA", base=100.0, tail_value=110.0)
    ineligible = _plateau_then_shift("ZZZ", base=100.0, tail_value=90.0)

    history = pd.concat([rising, ineligible], ignore_index=True)
    history["has_future"] = history["symbol"] == "AAA"

    scores = t01_sma_crossover.score(history)
    assert "ZZZ" not in scores


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result
