import numpy as np
import pandas as pd
import pytest

from strategies import a06_low_volatility
from strategies.a06_low_volatility_audit import check_cross_symbol_causality


def _series_with_baseline_and_recent(
    symbol: str,
    baseline_step: float,
    recent_step: float,
    leading_rows: int = 0,
    base_price: float = 100.0,
    base_volume: float = 1_000_000.0,
) -> pd.DataFrame:
    """A series whose trailing `MIN_ROWS` window has a known expected ratio.

    The baseline window (`BASELINE_WINDOW` returns, immediately before the
    recent window) alternates `+baseline_step, -baseline_step, ...`: an
    even-length sequence with zero mean, whose population standard
    deviation (`ddof=0`) is exactly `baseline_step` -
    `sqrt(mean(x**2)) == sqrt(baseline_step**2)` when every term is
    `+-baseline_step`. The recent window (`RECENT_WINDOW` returns, right
    after it) alternates the same way with `recent_step`, so its sigma is
    exactly `recent_step`. Expected `ratio = recent_step / baseline_step`.

    `leading_rows` extra rows at a flat price are optionally prepended
    before the baseline window, to prove they can't change the score (the
    module only reads the trailing `MIN_ROWS` rows).
    """
    assert a06_low_volatility.BASELINE_WINDOW % 2 == 0
    assert a06_low_volatility.RECENT_WINDOW % 2 == 0

    closes = [base_price]
    for i in range(a06_low_volatility.BASELINE_WINDOW):
        step = baseline_step if i % 2 == 0 else -baseline_step
        closes.append(closes[-1] * (1 + step))
    for i in range(a06_low_volatility.RECENT_WINDOW):
        step = recent_step if i % 2 == 0 else -recent_step
        closes.append(closes[-1] * (1 + step))

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


def test_calmer_than_baseline_scores_bullish():
    # ratio = 0.005 / 0.01 = 0.5 -> score = 1 - 0.5 = +0.5 (bullish): calmer than normal.
    history = _series_with_baseline_and_recent("AAA", baseline_step=0.01, recent_step=0.005)
    scores = a06_low_volatility.score(history)
    assert scores["AAA"] == pytest.approx(0.5, rel=1e-6)


def test_more_turbulent_than_baseline_scores_bearish():
    # ratio = 0.02 / 0.01 = 2.0 -> score = 1 - 2.0 = -1.0 (bearish): more turbulent than normal.
    history = _series_with_baseline_and_recent("AAA", baseline_step=0.01, recent_step=0.02)
    scores = a06_low_volatility.score(history)
    assert scores["AAA"] == pytest.approx(-1.0, rel=1e-6)


def test_score_magnitude_matches_the_known_formula():
    # ratio = 0.0075 / 0.005 = 1.5 -> score = 1 - 1.5 = -0.5.
    history = _series_with_baseline_and_recent("AAA", baseline_step=0.005, recent_step=0.0075)
    scores = a06_low_volatility.score(history)
    assert scores["AAA"] == pytest.approx(-0.5, rel=1e-6)


def test_same_volatility_as_baseline_scores_neutral():
    # ratio = 1.0 -> score = 0.0.
    history = _series_with_baseline_and_recent("AAA", baseline_step=0.01, recent_step=0.01)
    scores = a06_low_volatility.score(history)
    assert scores["AAA"] == pytest.approx(0.0, abs=1e-9)


def test_zero_baseline_volatility_abstains():
    history = _series_with_baseline_and_recent("AAA", baseline_step=0.0, recent_step=0.01)
    scores = a06_low_volatility.score(history)
    assert "AAA" not in scores


def test_leading_history_does_not_change_the_score():
    short = _series_with_baseline_and_recent("AAA", baseline_step=0.01, recent_step=0.02)
    long = _series_with_baseline_and_recent("AAA", baseline_step=0.01, recent_step=0.02, leading_rows=30)
    assert a06_low_volatility.score(short)["AAA"] == pytest.approx(
        a06_low_volatility.score(long)["AAA"], rel=1e-9
    )


def test_too_little_history_abstains():
    history = _series_with_baseline_and_recent("AAA", baseline_step=0.01, recent_step=0.02)
    history = history.iloc[1:]  # drop one row: now below MIN_ROWS
    scores = a06_low_volatility.score(history)
    assert "AAA" not in scores


def test_empty_history_returns_empty_series():
    scores = a06_low_volatility.score(
        pd.DataFrame(columns=["date", "symbol", "open", "high", "low", "close", "prevclose", "volume"])
    )
    assert scores.empty


def test_score_is_per_symbol_not_coupled_across_the_universe():
    calm = _series_with_baseline_and_recent("AAA", baseline_step=0.01, recent_step=0.005)
    turbulent = _series_with_baseline_and_recent("BBB", baseline_step=0.01, recent_step=0.02)
    scores = a06_low_volatility.score(pd.concat([calm, turbulent], ignore_index=True))
    assert scores["AAA"] > 0
    assert scores["BBB"] < 0


def test_rules_fired_reports_the_same_direction_as_score():
    history = _series_with_baseline_and_recent("AAA", baseline_step=0.01, recent_step=0.02)
    reasoning = a06_low_volatility.rules_fired(history, "AAA")
    assert "bearish" in reasoning
    assert "score" in reasoning


def test_rules_fired_reports_abstain_on_insufficient_history():
    history = _series_with_baseline_and_recent("AAA", baseline_step=0.01, recent_step=0.02)
    history = history.iloc[1:]
    reasoning = a06_low_volatility.rules_fired(history, "AAA")
    assert "abstain" in reasoning


def test_rules_fired_reports_abstain_on_zero_baseline_volatility():
    history = _series_with_baseline_and_recent("AAA", baseline_step=0.0, recent_step=0.01)
    reasoning = a06_low_volatility.rules_fired(history, "AAA")
    assert "abstain" in reasoning


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result


def test_score_drops_a_symbol_that_never_had_a_future():
    history = _series_with_baseline_and_recent("AAA", baseline_step=0.01, recent_step=0.02)
    history["has_future"] = False
    scores = a06_low_volatility.score(history)
    assert "AAA" not in scores


def test_score_keeps_an_eligible_symbol_with_has_future_column_present():
    history = _series_with_baseline_and_recent("AAA", baseline_step=0.01, recent_step=0.02)
    history["has_future"] = True
    scores = a06_low_volatility.score(history)
    assert scores["AAA"] == pytest.approx(-1.0, rel=1e-6)


def test_score_prefilter_does_not_change_an_eligible_symbols_score():
    eligible = _series_with_baseline_and_recent("AAA", baseline_step=0.01, recent_step=0.02)
    ineligible = _series_with_baseline_and_recent("ZZZ", baseline_step=0.01, recent_step=0.005)

    with_future_column = pd.concat([eligible, ineligible], ignore_index=True)
    with_future_column["has_future"] = with_future_column["symbol"] == "AAA"

    without_future_column = eligible  # no ineligible symbol, no has_future column at all

    assert a06_low_volatility.score(with_future_column)["AAA"] == a06_low_volatility.score(
        without_future_column
    )["AAA"]
