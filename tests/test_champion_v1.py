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


def _wilder_smooth_reference_loop(values: pd.Series, period: int) -> pd.Series:
    """The pre-vectorization implementation, kept here (not in
    `strategies/champion_v1.py`) purely as a reference the vectorized
    `_wilder_smooth` is checked against - see that function's docstring
    for why it was replaced."""
    arr = values.to_numpy(dtype=float)
    out = np.full(arr.shape, np.nan)
    if arr.size > period:
        out[period] = arr[1 : period + 1].mean()
        for i in range(period + 1, arr.size):
            out[i] = (out[i - 1] * (period - 1) + arr[i]) / period
    return pd.Series(out, index=values.index)


def test_wilder_smooth_matches_reference_loop():
    rng = np.random.default_rng(0)
    # Longer and noisier than any fixture elsewhere in this file, on purpose:
    # the vectorized ewm() recursion and the original Python loop factor the
    # same arithmetic differently, so agreement needs proving over more rows
    # than `MIN_ROWS` to rule out an off-by-one at the seed boundary.
    values = pd.Series(rng.normal(size=400))

    vectorized = champion_v1._wilder_smooth(values, champion_v1.RSI_PERIOD)
    reference = _wilder_smooth_reference_loop(values, champion_v1.RSI_PERIOD)

    pd.testing.assert_series_equal(vectorized, reference, rtol=1e-9, atol=1e-12)


def test_wilder_smooth_handles_too_short_a_series():
    values = pd.Series(np.arange(champion_v1.RSI_PERIOD, dtype=float))
    result = champion_v1._wilder_smooth(values, champion_v1.RSI_PERIOD)
    assert result.isna().all()


def test_score_drops_a_symbol_that_never_had_a_future():
    """The `has_future` prefilter must never exclude a symbol that would
    otherwise be scored (that's `_restrict_to_universe`'s job, downstream,
    on the real date-specific universe) - but it should skip a symbol that
    could never pass it, no matter how clean its own trend looks."""
    history = _trending_symbol("AAA", champion_v1.MIN_ROWS + 10, daily_move=0.01)
    history["has_future"] = False
    scores = champion_v1.score(history)
    assert "AAA" not in scores


def test_score_keeps_an_eligible_symbol_with_has_future_column_present():
    history = _trending_symbol("AAA", champion_v1.MIN_ROWS + 10, daily_move=0.01)
    history["has_future"] = True
    scores = champion_v1.score(history)
    assert scores["AAA"] > 0


def test_score_prefilter_does_not_change_an_eligible_symbols_score():
    """The prefilter drops ineligible symbols before `compute_adjustment_factors`
    runs; it must not change what an eligible symbol's own score comes out
    to, since that would mean the prefilter leaked into the actual signal."""
    bullish = _trending_symbol("AAA", champion_v1.MIN_ROWS + 10, daily_move=0.01)
    ineligible = _trending_symbol("ZZZ", champion_v1.MIN_ROWS + 10, daily_move=-0.01)

    with_future_column = pd.concat([bullish, ineligible], ignore_index=True)
    with_future_column["has_future"] = with_future_column["symbol"] == "AAA"

    without_future_column = bullish  # no ineligible symbol, no has_future column at all

    assert champion_v1.score(with_future_column)["AAA"] == champion_v1.score(without_future_column)["AAA"]
