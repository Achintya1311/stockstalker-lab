import pandas as pd
import pytest

from strategies import a08_overnight_intraday_tug
from strategies.a08_overnight_intraday_tug_audit import check_cross_symbol_causality


def _series(
    n_rows: int,
    overnight: float,
    intraday: float,
    symbol: str = "AAA",
    start_close: float = 100.0,
    start_date: str = "2015-01-01",
) -> pd.DataFrame:
    """`n_rows` business days with a *constant* per-day overnight and intraday
    return, so the window average is exactly `overnight`/`intraday` with no
    floating-point drift - the known-expected-signal fixture every ported
    card uses (e.g. `strategies/a02_extreme_day_reversal_audit.py`'s
    `_window_then_move`), adapted to this card's two-leg return instead of a
    single close-to-close one.

    `open_t = prev_close * (1 + overnight)`, `close_t = open_t * (1 + intraday)`,
    `prevclose_t = prev_close` (an ordinary day, no corporate action), so
    `a08_overnight_intraday_tug.score`'s `adj_open`/`adj_close` are
    identical to this fixture's own `open`/`close` (no adjustment fires).
    """
    rows = []
    dates = pd.bdate_range(start_date, periods=n_rows).strftime("%Y-%m-%d")
    prev_close = start_close
    for date in dates:
        open_ = prev_close * (1 + overnight)
        close = open_ * (1 + intraday)
        rows.append(
            {
                "date": date,
                "symbol": symbol,
                "open": open_,
                "high": max(open_, close),
                "low": min(open_, close),
                "close": close,
                "prevclose": prev_close,
                "volume": 1_000_000.0,
            }
        )
        prev_close = close
    return pd.DataFrame(rows)


def test_strong_overnight_weak_intraday_scores_bearish():
    # avg_overnight=0.01, avg_intraday=-0.02 -> score = -0.02 - 0.01 = -0.03.
    history = _series(n_rows=a08_overnight_intraday_tug.MIN_ROWS, overnight=0.01, intraday=-0.02)
    scores = a08_overnight_intraday_tug.score(history)
    assert "AAA" in scores
    assert scores["AAA"] < 0


def test_weak_overnight_strong_intraday_scores_bullish():
    history = _series(n_rows=a08_overnight_intraday_tug.MIN_ROWS, overnight=-0.01, intraday=0.02)
    scores = a08_overnight_intraday_tug.score(history)
    assert "AAA" in scores
    assert scores["AAA"] > 0


def test_score_magnitude_matches_the_known_formula():
    # Known expected signal, exactly: a constant per-day overnight/intraday
    # return makes the window average exactly that constant, so
    # score = intraday - overnight = -0.02 - 0.01 = -0.03.
    history = _series(n_rows=a08_overnight_intraday_tug.MIN_ROWS, overnight=0.01, intraday=-0.02)
    scores = a08_overnight_intraday_tug.score(history)
    assert scores["AAA"] == pytest.approx(-0.03, rel=1e-9)


def test_equal_overnight_and_intraday_scores_zero_but_is_still_included():
    # tug = 0.0 is a real, computable score (not an abstain) - abstain is
    # reserved for too-little-history or a non-positive price, not a score
    # that happens to land on zero.
    history = _series(n_rows=a08_overnight_intraday_tug.MIN_ROWS, overnight=0.01, intraday=0.01)
    scores = a08_overnight_intraday_tug.score(history)
    assert "AAA" in scores
    assert scores["AAA"] == pytest.approx(0.0, abs=1e-9)


def test_leading_history_does_not_change_the_score():
    # Extra rows before the trailing WINDOW+1 window (a different, noisier
    # overnight/intraday mix) must not move the score: only the most recent
    # MIN_ROWS rows are read.
    tail = _series(n_rows=a08_overnight_intraday_tug.MIN_ROWS, overnight=0.01, intraday=-0.02)
    # Dates strictly before `tail`'s own start date, so the concatenated
    # series is in real chronological order per symbol (a shared, repeated
    # date axis would break `compute_adjustment_factors`'s own previous-
    # trading-day logic - a test-fixture risk, not a strategy one).
    leading = _series(n_rows=15, overnight=-0.05, intraday=0.08, start_close=50.0, start_date="2014-12-01")
    combined = pd.concat([leading, tail], ignore_index=True)

    scores_with_leading = a08_overnight_intraday_tug.score(combined)
    scores_without_leading = a08_overnight_intraday_tug.score(tail)
    assert scores_with_leading["AAA"] == pytest.approx(scores_without_leading["AAA"], rel=1e-9)


def test_too_little_history_abstains():
    history = _series(n_rows=a08_overnight_intraday_tug.MIN_ROWS - 1, overnight=0.01, intraday=-0.02)
    scores = a08_overnight_intraday_tug.score(history)
    assert "AAA" not in scores


def test_non_positive_price_abstains():
    history = _series(n_rows=a08_overnight_intraday_tug.MIN_ROWS, overnight=0.01, intraday=-0.02)
    history.loc[history.index[-1], "open"] = 0.0
    history.loc[history.index[-1], "high"] = 0.0
    history.loc[history.index[-1], "low"] = 0.0
    scores = a08_overnight_intraday_tug.score(history)
    assert "AAA" not in scores


def test_empty_history_returns_empty_series():
    scores = a08_overnight_intraday_tug.score(
        pd.DataFrame(columns=["date", "symbol", "open", "high", "low", "close", "prevclose", "volume"])
    )
    assert scores.empty


def test_score_is_per_symbol_not_coupled_across_the_universe():
    bearish = _series(n_rows=a08_overnight_intraday_tug.MIN_ROWS, overnight=0.02, intraday=-0.03, symbol="AAA")
    bullish = _series(n_rows=a08_overnight_intraday_tug.MIN_ROWS, overnight=-0.02, intraday=0.03, symbol="BBB")
    scores = a08_overnight_intraday_tug.score(pd.concat([bearish, bullish], ignore_index=True))
    assert scores["AAA"] < 0
    assert scores["BBB"] > 0


def test_rules_fired_reports_the_same_direction_as_score():
    history = _series(n_rows=a08_overnight_intraday_tug.MIN_ROWS, overnight=-0.01, intraday=0.02)
    reasoning = a08_overnight_intraday_tug.rules_fired(history, "AAA")
    assert "bullish" in reasoning
    assert "score" in reasoning


def test_rules_fired_reports_abstain_on_insufficient_history():
    history = _series(n_rows=a08_overnight_intraday_tug.MIN_ROWS - 1, overnight=0.01, intraday=-0.02)
    reasoning = a08_overnight_intraday_tug.rules_fired(history, "AAA")
    assert "abstain" in reasoning


def test_rules_fired_reports_abstain_on_non_positive_price():
    history = _series(n_rows=a08_overnight_intraday_tug.MIN_ROWS, overnight=0.01, intraday=-0.02)
    history.loc[history.index[-1], "open"] = 0.0
    reasoning = a08_overnight_intraday_tug.rules_fired(history, "AAA")
    assert "abstain" in reasoning


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result


def test_score_drops_a_symbol_that_never_had_a_future():
    history = _series(n_rows=a08_overnight_intraday_tug.MIN_ROWS, overnight=0.01, intraday=-0.02)
    history["has_future"] = False
    scores = a08_overnight_intraday_tug.score(history)
    assert "AAA" not in scores


def test_score_keeps_an_eligible_symbol_with_has_future_column_present():
    history = _series(n_rows=a08_overnight_intraday_tug.MIN_ROWS, overnight=0.01, intraday=-0.02)
    history["has_future"] = True
    scores = a08_overnight_intraday_tug.score(history)
    assert scores["AAA"] < 0


def test_score_prefilter_does_not_change_an_eligible_symbols_score():
    eligible = _series(n_rows=a08_overnight_intraday_tug.MIN_ROWS, overnight=0.01, intraday=-0.02, symbol="AAA")
    ineligible = _series(n_rows=a08_overnight_intraday_tug.MIN_ROWS, overnight=-0.01, intraday=0.02, symbol="ZZZ")

    with_future_column = pd.concat([eligible, ineligible], ignore_index=True)
    with_future_column["has_future"] = with_future_column["symbol"] == "AAA"

    without_future_column = eligible  # no ineligible symbol, no has_future column at all

    assert a08_overnight_intraday_tug.score(with_future_column)["AAA"] == a08_overnight_intraday_tug.score(without_future_column)["AAA"]
