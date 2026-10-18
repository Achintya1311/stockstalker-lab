import numpy as np
import pandas as pd
import pytest

from strategies import a03_momentum_12_1
from strategies.a03_momentum_12_1_audit import check_cross_symbol_causality


def _series_with_formation_move(
    symbol: str,
    n_rows: int,
    formation_move: float,
    skip_period_move: float = 0.0,
    base_volume: float = 1_000_000.0,
) -> pd.DataFrame:
    """A series flat before the formation window, with a known expected signal:

    `close.iloc[-a03_momentum_12_1.MIN_ROWS]` (the distant anchor) stays at
    100.0, and `close.iloc[-(a03_momentum_12_1.SKIP_DAYS + 1)]` (the recent
    anchor, i.e. the close one skipped-month back from the pick date) is
    exactly `100.0 * (1 + formation_move)` away from it - so the formation
    return (and the momentum score's sign and exact magnitude) is fully
    determined by `formation_move` alone. `skip_period_move` additionally
    moves every close *after* the recent anchor (the skipped month itself),
    which the formation return must ignore entirely.
    """
    dates = pd.bdate_range("2015-01-01", periods=n_rows).strftime("%Y-%m-%d")
    recent_anchor_idx = n_rows - a03_momentum_12_1.SKIP_DAYS - 1

    distant_value = 100.0
    recent_value = 100.0 * (1.0 + formation_move)
    closes = np.full(n_rows, distant_value)
    closes[recent_anchor_idx:] = recent_value
    if skip_period_move:
        closes[recent_anchor_idx + 1 :] = recent_value * (1.0 + skip_period_move)

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


def test_a_formation_gain_scores_bullish():
    history = _series_with_formation_move("AAA", a03_momentum_12_1.MIN_ROWS + 10, formation_move=0.20)
    scores = a03_momentum_12_1.score(history)
    assert "AAA" in scores
    assert scores["AAA"] > 0


def test_a_formation_loss_scores_bearish():
    history = _series_with_formation_move("AAA", a03_momentum_12_1.MIN_ROWS + 10, formation_move=-0.20)
    scores = a03_momentum_12_1.score(history)
    assert "AAA" in scores
    assert scores["AAA"] < 0


def test_flat_series_scores_exactly_zero():
    history = _series_with_formation_move("AAA", a03_momentum_12_1.MIN_ROWS + 10, formation_move=0.0)
    scores = a03_momentum_12_1.score(history)
    assert scores["AAA"] == 0.0


def test_score_magnitude_is_the_positive_formation_return():
    # Known expected signal, exactly: a 20% gain over the formation window
    # gives a formation return of +0.20, so the momentum score must be
    # exactly +0.20 (rtol/atol for float rounding only), not merely "positive".
    history = _series_with_formation_move("AAA", a03_momentum_12_1.MIN_ROWS + 10, formation_move=0.20)
    scores = a03_momentum_12_1.score(history)
    assert scores["AAA"] == pytest.approx(0.20, rel=1e-9)


def test_skip_period_move_does_not_change_the_score():
    # The move happens entirely inside the skipped month (strictly after the
    # recent anchor); the formation return - and the score - must not move.
    with_skip_move = _series_with_formation_move(
        "AAA", a03_momentum_12_1.MIN_ROWS + 10, formation_move=0.20, skip_period_move=0.15
    )
    without_skip_move = _series_with_formation_move(
        "AAA", a03_momentum_12_1.MIN_ROWS + 10, formation_move=0.20, skip_period_move=0.0
    )
    assert a03_momentum_12_1.score(with_skip_move)["AAA"] == pytest.approx(
        a03_momentum_12_1.score(without_skip_move)["AAA"], rel=1e-9
    )


def test_too_little_history_abstains():
    history = _series_with_formation_move("AAA", a03_momentum_12_1.MIN_ROWS - 1, formation_move=-0.20)
    scores = a03_momentum_12_1.score(history)
    assert "AAA" not in scores


def test_empty_history_returns_empty_series():
    scores = a03_momentum_12_1.score(
        pd.DataFrame(columns=["date", "symbol", "open", "high", "low", "close", "prevclose", "volume"])
    )
    assert scores.empty


def test_score_is_per_symbol_not_coupled_across_the_universe():
    loser = _series_with_formation_move("AAA", a03_momentum_12_1.MIN_ROWS + 10, formation_move=-0.20)
    winner = _series_with_formation_move("BBB", a03_momentum_12_1.MIN_ROWS + 10, formation_move=0.20)
    scores = a03_momentum_12_1.score(pd.concat([loser, winner], ignore_index=True))
    assert scores["AAA"] < 0
    assert scores["BBB"] > 0


def test_rules_fired_reports_the_same_direction_as_score():
    history = _series_with_formation_move("AAA", a03_momentum_12_1.MIN_ROWS + 10, formation_move=0.20)
    reasoning = a03_momentum_12_1.rules_fired(history, "AAA")
    assert "bullish" in reasoning
    assert "momentum score" in reasoning


def test_rules_fired_reports_abstain_on_insufficient_history():
    history = _series_with_formation_move("AAA", a03_momentum_12_1.MIN_ROWS - 1, formation_move=0.20)
    reasoning = a03_momentum_12_1.rules_fired(history, "AAA")
    assert "abstain" in reasoning


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result


def test_score_drops_a_symbol_that_never_had_a_future():
    history = _series_with_formation_move("AAA", a03_momentum_12_1.MIN_ROWS + 10, formation_move=0.20)
    history["has_future"] = False
    scores = a03_momentum_12_1.score(history)
    assert "AAA" not in scores


def test_score_keeps_an_eligible_symbol_with_has_future_column_present():
    history = _series_with_formation_move("AAA", a03_momentum_12_1.MIN_ROWS + 10, formation_move=0.20)
    history["has_future"] = True
    scores = a03_momentum_12_1.score(history)
    assert scores["AAA"] > 0


def test_score_prefilter_does_not_change_an_eligible_symbols_score():
    winner = _series_with_formation_move("AAA", a03_momentum_12_1.MIN_ROWS + 10, formation_move=0.20)
    ineligible = _series_with_formation_move("ZZZ", a03_momentum_12_1.MIN_ROWS + 10, formation_move=-0.20)

    with_future_column = pd.concat([winner, ineligible], ignore_index=True)
    with_future_column["has_future"] = with_future_column["symbol"] == "AAA"

    without_future_column = winner  # no ineligible symbol, no has_future column at all

    assert a03_momentum_12_1.score(with_future_column)["AAA"] == a03_momentum_12_1.score(without_future_column)["AAA"]
