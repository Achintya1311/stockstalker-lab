import numpy as np
import pandas as pd

from strategies import f02_volume_signed_reversal as f02
from strategies.f02_volume_signed_reversal_audit import check_cross_symbol_causality, last_move

N = 12


def test_hand_computed_scores_on_all_four_cases():
    """score = -sign(dv) x r1 with r1 the log return: +-0.04 exactly."""
    hist = pd.concat([
        last_move("FALL_UPVOL", N, -0.04, 2.0),   # reversal: bullish +0.04
        last_move("RISE_UPVOL", N, 0.04, 2.0),    # reversal: bearish -0.04
        last_move("RISE_DOWNVOL", N, 0.04, 0.5),  # continuation: bullish +0.04
        last_move("FALL_DOWNVOL", N, -0.04, 0.5), # continuation: bearish -0.04
    ])
    sc = f02.score(hist)
    for sym, want in [("FALL_UPVOL", 0.04), ("RISE_UPVOL", -0.04), ("RISE_DOWNVOL", 0.04), ("FALL_DOWNVOL", -0.04)]:
        assert abs(sc[sym] - want) < 1e-12


def test_unchanged_volume_or_close_abstains():
    flat_volume = last_move("V", N, 0.04, 1.0)
    flat_close = last_move("C", N, 0.0, 2.0)
    assert f02.score(pd.concat([flat_volume, flat_close])).empty


def test_short_history_abstains():
    assert f02.score(last_move("A", N, 0.04, 2.0).tail(1)).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    f = last_move("F", N, -0.04, 2.0)
    hist = pd.concat([f, f.assign(symbol="CASH")])
    hist["has_future"] = hist["symbol"] == "F"
    assert list(f02.score(hist).index) == ["F"]


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_rules_fired_names_kind_and_side():
    text = f02.rules_fired(last_move("A", N, -0.04, 2.0), "A")
    assert "rising volume" in text and "reversal" in text and text.endswith("bullish")
