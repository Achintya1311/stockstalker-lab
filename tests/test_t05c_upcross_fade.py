import numpy as np
import pandas as pd
import pytest

from strategies import t05_macd_crossover, t05c_upcross_fade
from strategies.t05c_upcross_fade_audit import check_cross_symbol_causality
from tests.test_t05_macd_crossover import _rows_from_closes

UP_CROSS = list(np.linspace(140.0, 80.0, 60)) + [78.0, 88.0]    # T05 fresh up-cross on the last bar
DOWN_CROSS = list(np.linspace(80.0, 140.0, 60)) + [142.0, 132.0]  # T05 fresh down-cross on the last bar


def test_up_cross_scores_bearish_with_t05_magnitude():
    history = _rows_from_closes("AAA", UP_CROSS)
    base = t05_macd_crossover.score(history)["AAA"]
    assert base > 0
    assert t05c_upcross_fade.score(history)["AAA"] == pytest.approx(-base, abs=1e-12)


def test_down_cross_abstains():
    history = _rows_from_closes("AAA", DOWN_CROSS)
    assert t05_macd_crossover.score(history)["AAA"] < 0
    assert "AAA" not in t05c_upcross_fade.score(history).index


def test_never_bullish_and_matches_t05_up_crosses_only():
    history = pd.concat([
        _rows_from_closes("AAA", UP_CROSS),
        _rows_from_closes("BBB", DOWN_CROSS),
        _rows_from_closes("CCC", list(np.linspace(80.0, 140.0, 62))),  # steady trend, no fresh cross
        _rows_from_closes("DDD", UP_CROSS[-10:]),                       # too short
    ], ignore_index=True)
    base, flipped = t05_macd_crossover.score(history), t05c_upcross_fade.score(history)
    assert list(flipped.index) == ["AAA"]
    assert (flipped < 0).all()
    pd.testing.assert_series_equal(flipped, -base[base > 0])


def test_empty_history():
    assert t05c_upcross_fade.score(pd.DataFrame()).empty


def test_rules_fired_wording():
    up = t05c_upcross_fade.rules_fired(_rows_from_closes("AAA", UP_CROSS), "AAA")
    down = t05c_upcross_fade.rules_fired(_rows_from_closes("AAA", DOWN_CROSS), "AAA")
    assert up.startswith("T05C MACD up-cross fade") and "(bearish)" in up
    assert down.startswith("T05C MACD up-cross fade") and "abstain" in down
    for text in (up, down):
        for word in ("buy", "sell", "target", "stop"):
            assert word not in text.lower()


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result
