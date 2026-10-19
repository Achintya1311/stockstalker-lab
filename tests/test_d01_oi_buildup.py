import pandas as pd
import pytest

from strategies import d01_oi_buildup
from strategies.d01_oi_buildup_audit import check_cross_symbol_causality


def _row(symbol, date, prevclose, close, oi_level, oi_chg, has_future=True):
    return {
        "date": date,
        "symbol": symbol,
        "open": prevclose,
        "high": max(prevclose, close),
        "low": min(prevclose, close),
        "close": close,
        "prevclose": prevclose,
        "volume": 1_000_000.0,
        "has_future": has_future,
        "oi_futstk": oi_level,
        "oi_chg_futstk": oi_chg,
    }


def test_long_buildup_price_up_oi_up_scores_bullish_full_weight():
    # price_move = 1/100 = 0.01; prior_oi = 10000 - 500 = 9500;
    # oi_pct_chg = 500/9500 = 0.0526315...; weight = 1.0 (OI up).
    history = pd.DataFrame([_row("AAA", "2015-01-05", 100.0, 101.0, 10_000.0, 500.0)])
    scores = d01_oi_buildup.score(history)
    assert scores["AAA"] == pytest.approx(500 / 9_500, rel=1e-6)
    assert scores["AAA"] > 0


def test_short_buildup_price_down_oi_up_scores_bearish_full_weight():
    history = pd.DataFrame([_row("AAA", "2015-01-05", 100.0, 98.0, 10_000.0, 500.0)])
    scores = d01_oi_buildup.score(history)
    assert scores["AAA"] == pytest.approx(-(500 / 9_500), rel=1e-6)
    assert scores["AAA"] < 0


def test_long_unwinding_price_down_oi_down_scores_bearish_half_weight():
    # prior_oi = 9500 - (-500) = 10000; oi_pct_chg = -500/10000 = -0.05;
    # weight = 0.5 (OI down) -> score = -1 * 0.05 * 0.5 = -0.025.
    history = pd.DataFrame([_row("AAA", "2015-01-05", 100.0, 98.0, 9_500.0, -500.0)])
    scores = d01_oi_buildup.score(history)
    assert scores["AAA"] == pytest.approx(-0.025, rel=1e-6)


def test_short_covering_price_up_oi_down_scores_bullish_half_weight():
    history = pd.DataFrame([_row("AAA", "2015-01-05", 100.0, 101.0, 9_500.0, -500.0)])
    scores = d01_oi_buildup.score(history)
    assert scores["AAA"] == pytest.approx(0.025, rel=1e-6)


def test_unwinding_covering_is_weaker_than_an_equal_sized_buildup():
    buildup = pd.DataFrame([_row("AAA", "2015-01-05", 100.0, 101.0, 10_000.0, 500.0)])
    covering = pd.DataFrame([_row("BBB", "2015-01-05", 100.0, 101.0, 9_500.0, -500.0)])
    scores_buildup = d01_oi_buildup.score(buildup)
    scores_covering = d01_oi_buildup.score(covering)
    assert scores_buildup["AAA"] > scores_covering["BBB"] > 0


def test_zero_price_move_abstains():
    history = pd.DataFrame([_row("AAA", "2015-01-05", 100.0, 100.0, 10_000.0, 500.0)])
    scores = d01_oi_buildup.score(history)
    assert "AAA" not in scores


def test_non_positive_prior_oi_abstains():
    # prior_oi = oi_level - oi_chg = 500 - 500 = 0.
    history = pd.DataFrame([_row("AAA", "2015-01-05", 100.0, 101.0, 500.0, 500.0)])
    scores = d01_oi_buildup.score(history)
    assert "AAA" not in scores


def test_zero_prevclose_abstains():
    history = pd.DataFrame([_row("AAA", "2015-01-05", 0.0, 101.0, 10_000.0, 500.0)])
    scores = d01_oi_buildup.score(history)
    assert "AAA" not in scores


def test_symbol_never_having_a_future_abstains():
    history = pd.DataFrame([_row("AAA", "2015-01-05", 100.0, 101.0, 10_000.0, 500.0, has_future=False)])
    scores = d01_oi_buildup.score(history)
    assert "AAA" not in scores


def test_missing_oi_columns_abstains_rather_than_erroring():
    history = pd.DataFrame([
        {
            "date": "2015-01-05",
            "symbol": "AAA",
            "open": 100.0,
            "high": 101.0,
            "low": 100.0,
            "close": 101.0,
            "prevclose": 100.0,
            "volume": 1_000_000.0,
            "has_future": True,
        }
    ])
    scores = d01_oi_buildup.score(history)
    assert "AAA" not in scores


def test_empty_history_returns_empty_series():
    scores = d01_oi_buildup.score(
        pd.DataFrame(columns=["date", "symbol", "open", "high", "low", "close", "prevclose",
                               "volume", "has_future", "oi_futstk", "oi_chg_futstk"])
    )
    assert scores.empty


def test_score_uses_only_the_last_visible_row_per_symbol():
    # An earlier long build-up row should not affect the score once a later,
    # differently-classified row exists: only the last visible row counts.
    history = pd.DataFrame([
        _row("AAA", "2015-01-05", 100.0, 101.0, 10_000.0, 500.0),   # long build-up (would be bullish)
        _row("AAA", "2015-01-06", 101.0, 99.0, 10_500.0, -300.0),   # long unwinding (bearish)
    ])
    scores = d01_oi_buildup.score(history)
    assert scores["AAA"] < 0


def test_score_is_per_symbol_not_coupled_across_the_universe():
    bullish = pd.DataFrame([_row("AAA", "2015-01-05", 100.0, 101.0, 10_000.0, 500.0)])
    bearish = pd.DataFrame([_row("BBB", "2015-01-05", 100.0, 98.0, 10_000.0, 500.0)])
    scores = d01_oi_buildup.score(pd.concat([bullish, bearish], ignore_index=True))
    assert scores["AAA"] > 0
    assert scores["BBB"] < 0


def test_rules_fired_reports_long_buildup():
    history = pd.DataFrame([_row("AAA", "2015-01-05", 100.0, 101.0, 10_000.0, 500.0)])
    reasoning = d01_oi_buildup.rules_fired(history, "AAA")
    assert "long build-up" in reasoning
    assert "bullish" in reasoning


def test_rules_fired_reports_short_buildup():
    history = pd.DataFrame([_row("AAA", "2015-01-05", 100.0, 98.0, 10_000.0, 500.0)])
    reasoning = d01_oi_buildup.rules_fired(history, "AAA")
    assert "short build-up" in reasoning
    assert "bearish" in reasoning


def test_rules_fired_reports_long_unwinding():
    history = pd.DataFrame([_row("AAA", "2015-01-05", 100.0, 98.0, 9_500.0, -500.0)])
    reasoning = d01_oi_buildup.rules_fired(history, "AAA")
    assert "long unwinding" in reasoning
    assert "bearish" in reasoning


def test_rules_fired_reports_short_covering():
    history = pd.DataFrame([_row("AAA", "2015-01-05", 100.0, 101.0, 9_500.0, -500.0)])
    reasoning = d01_oi_buildup.rules_fired(history, "AAA")
    assert "short covering" in reasoning
    assert "bullish" in reasoning


def test_rules_fired_reports_abstain_on_zero_move():
    history = pd.DataFrame([_row("AAA", "2015-01-05", 100.0, 100.0, 10_000.0, 500.0)])
    reasoning = d01_oi_buildup.rules_fired(history, "AAA")
    assert "abstain" in reasoning


def test_rules_fired_reports_abstain_on_empty_history():
    reasoning = d01_oi_buildup.rules_fired(
        pd.DataFrame(columns=["date", "symbol"]), "AAA"
    )
    assert "abstain" in reasoning


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result


def test_score_drops_a_symbol_that_never_had_a_future():
    history = pd.DataFrame([_row("AAA", "2015-01-05", 100.0, 101.0, 10_000.0, 500.0, has_future=False)])
    scores = d01_oi_buildup.score(history)
    assert "AAA" not in scores


def test_score_prefilter_does_not_change_an_eligible_symbols_score():
    eligible = pd.DataFrame([_row("AAA", "2015-01-05", 100.0, 101.0, 10_000.0, 500.0)])
    ineligible = pd.DataFrame([_row("ZZZ", "2015-01-05", 100.0, 98.0, 10_000.0, 500.0, has_future=False)])

    with_ineligible = pd.concat([eligible, ineligible], ignore_index=True)

    assert d01_oi_buildup.score(with_ineligible)["AAA"] == d01_oi_buildup.score(eligible)["AAA"]
