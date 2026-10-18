import numpy as np
import pandas as pd
import pytest

from strategies import a05_max_effect
from strategies.a05_max_effect_audit import check_cross_symbol_causality


def _series_with_baseline_and_month(
    symbol: str,
    baseline_step: float,
    month_return: float,
    leading_rows: int = 0,
    base_price: float = 100.0,
    base_volume: float = 1_000_000.0,
) -> pd.DataFrame:
    """A series whose trailing `MIN_ROWS` window has a known expected `z`.

    The baseline window (`SIGMA_WINDOW` returns, immediately before the MAX
    window) alternates `+baseline_step, -baseline_step, ...`: an even-length
    sequence with zero mean, whose population standard deviation (`ddof=0`)
    is exactly `baseline_step` - `sqrt(mean(x**2)) == sqrt(baseline_step**2)`
    when every term is `+-baseline_step`. The MAX window (`MAX_WINDOW`
    returns, right after it) is every return equal to `month_return`, so its
    max is `month_return` itself. Expected `z = month_return / baseline_step`.

    `leading_rows` extra rows at a flat price are optionally prepended
    before the baseline window, to prove they can't change the score (the
    module only reads the trailing `MIN_ROWS` rows).
    """
    assert a05_max_effect.SIGMA_WINDOW % 2 == 0

    closes = [base_price]
    for i in range(a05_max_effect.SIGMA_WINDOW):
        step = baseline_step if i % 2 == 0 else -baseline_step
        closes.append(closes[-1] * (1 + step))
    for _ in range(a05_max_effect.MAX_WINDOW):
        closes.append(closes[-1] * (1 + month_return))

    leading = [base_price] * leading_rows
    closes = leading + closes
    n_rows = len(closes)
    dates = pd.bdate_range("2015-01-01", periods=n_rows).strftime("%Y-%m-%d")

    rows = []
    prev_close = closes[0]
    for date, close in zip(dates, closes):
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


def test_a_large_best_day_relative_to_baseline_scores_bearish():
    # z = 0.10 / 0.01 = 10 -> score = -10 (bearish): a lottery-like month.
    history = _series_with_baseline_and_month("AAA", baseline_step=0.01, month_return=0.10)
    scores = a05_max_effect.score(history)
    assert scores["AAA"] == pytest.approx(-10.0, rel=1e-6)


def test_a_muted_best_day_relative_to_baseline_scores_bullish():
    # z = -0.02 / 0.01 = -2 -> score = +2 (bullish): a muted, below-baseline month.
    history = _series_with_baseline_and_month("AAA", baseline_step=0.01, month_return=-0.02)
    scores = a05_max_effect.score(history)
    assert scores["AAA"] == pytest.approx(2.0, rel=1e-6)


def test_score_magnitude_matches_the_known_formula():
    # z = 0.025 / 0.005 = 5 -> score = -5.
    history = _series_with_baseline_and_month("AAA", baseline_step=0.005, month_return=0.025)
    scores = a05_max_effect.score(history)
    assert scores["AAA"] == pytest.approx(-5.0, rel=1e-6)


def test_zero_baseline_volatility_abstains():
    history = _series_with_baseline_and_month("AAA", baseline_step=0.0, month_return=0.05)
    scores = a05_max_effect.score(history)
    assert "AAA" not in scores


def test_leading_history_does_not_change_the_score():
    short = _series_with_baseline_and_month("AAA", baseline_step=0.01, month_return=0.04)
    long = _series_with_baseline_and_month("AAA", baseline_step=0.01, month_return=0.04, leading_rows=30)
    assert a05_max_effect.score(short)["AAA"] == pytest.approx(a05_max_effect.score(long)["AAA"], rel=1e-9)


def test_too_little_history_abstains():
    history = _series_with_baseline_and_month("AAA", baseline_step=0.01, month_return=0.04)
    history = history.iloc[1:]  # drop one row: now below MIN_ROWS
    scores = a05_max_effect.score(history)
    assert "AAA" not in scores


def test_empty_history_returns_empty_series():
    scores = a05_max_effect.score(
        pd.DataFrame(columns=["date", "symbol", "open", "high", "low", "close", "prevclose", "volume"])
    )
    assert scores.empty


def test_score_is_per_symbol_not_coupled_across_the_universe():
    lottery = _series_with_baseline_and_month("AAA", baseline_step=0.01, month_return=0.10)
    muted = _series_with_baseline_and_month("BBB", baseline_step=0.01, month_return=-0.02)
    scores = a05_max_effect.score(pd.concat([lottery, muted], ignore_index=True))
    assert scores["AAA"] < 0
    assert scores["BBB"] > 0


def test_rules_fired_reports_the_same_direction_as_score():
    history = _series_with_baseline_and_month("AAA", baseline_step=0.01, month_return=0.10)
    reasoning = a05_max_effect.rules_fired(history, "AAA")
    assert "bearish" in reasoning
    assert "score" in reasoning


def test_rules_fired_reports_abstain_on_insufficient_history():
    history = _series_with_baseline_and_month("AAA", baseline_step=0.01, month_return=0.10)
    history = history.iloc[1:]
    reasoning = a05_max_effect.rules_fired(history, "AAA")
    assert "abstain" in reasoning


def test_rules_fired_reports_abstain_on_zero_baseline_volatility():
    history = _series_with_baseline_and_month("AAA", baseline_step=0.0, month_return=0.05)
    reasoning = a05_max_effect.rules_fired(history, "AAA")
    assert "abstain" in reasoning


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result


def test_score_drops_a_symbol_that_never_had_a_future():
    history = _series_with_baseline_and_month("AAA", baseline_step=0.01, month_return=0.10)
    history["has_future"] = False
    scores = a05_max_effect.score(history)
    assert "AAA" not in scores


def test_score_keeps_an_eligible_symbol_with_has_future_column_present():
    history = _series_with_baseline_and_month("AAA", baseline_step=0.01, month_return=0.10)
    history["has_future"] = True
    scores = a05_max_effect.score(history)
    assert scores["AAA"] == pytest.approx(-10.0, rel=1e-6)


def test_score_prefilter_does_not_change_an_eligible_symbols_score():
    eligible = _series_with_baseline_and_month("AAA", baseline_step=0.01, month_return=0.10)
    ineligible = _series_with_baseline_and_month("ZZZ", baseline_step=0.01, month_return=-0.02)

    with_future_column = pd.concat([eligible, ineligible], ignore_index=True)
    with_future_column["has_future"] = with_future_column["symbol"] == "AAA"

    without_future_column = eligible  # no ineligible symbol, no has_future column at all

    assert a05_max_effect.score(with_future_column)["AAA"] == a05_max_effect.score(without_future_column)["AAA"]
