import pandas as pd
import pytest

from strategies import consensus_db_v1 as cons
from strategies import consensus_wb_v1
from strategies.a05_max_effect_audit import _synthetic_symbol
from strategies.a09_gap_fade_audit import _gap_window_then_move
from strategies.consensus_db_v1_audit import _with_oi, check_cross_symbol_causality


def _history():
    return pd.concat([_synthetic_symbol(f"S{i}", 120, seed=i) for i in range(6)], ignore_index=True)


def test_uses_the_week_card_combination_rule_on_its_own_members():
    assert list(cons.MEMBERS) == ["e2a", "d01c", "a09"]
    readings = pd.DataFrame(
        {"e2a": [-2.0, None, 1.0], "d01c": [-1.0, -3.0, 2.0], "a09": [None, -1.0, 1.0]}, index=["A", "B", "C"]
    )
    # Same pure rule as consensus_wb_v1: identical inputs give identical means.
    pd.testing.assert_series_equal(consensus_wb_v1.combine(readings), consensus_wb_v1.combine(readings.copy()))
    mean = consensus_wb_v1.combine(readings)
    assert mean.idxmax() in {"A", "B"} and mean.idxmin() == "C"


def test_score_runs_end_to_end_and_is_bearish_only():
    history = _history()
    readings = cons.member_scores(history)
    assert list(readings.columns) == ["e2a", "d01c", "a09"]
    assert (cons.score(history) < 0).all()


def test_a_gap_up_fade_reads_bearish_for_the_firing_members():
    # A09's deterministic fixture: a +5% gap after a +-1% window is a z = +5 gap up, which A09 fades.
    up = _with_oi(_gap_window_then_move("UP", 10, 0.01, 0.05))
    quiet = _with_oi(_gap_window_then_move("QUIET", 10, 0.01, 0.0))
    s = cons.score(pd.concat([up, quiet], ignore_index=True))
    assert "UP" in s.index and s["UP"] < 0


def test_member_scores_match_the_members_themselves():
    history = _history()
    readings = cons.member_scores(history)
    for name, module in cons.MEMBERS.items():
        direct = module.score(history)
        pd.testing.assert_series_equal(
            readings[name].dropna().sort_index(), direct.sort_index(), check_names=False
        )


def test_empty_history():
    assert cons.score(pd.DataFrame()).empty


def test_rules_fired_wording():
    history = _history()
    text = cons.rules_fired(history, "MISSING")
    assert "abstain" in text
    s = cons.score(history)
    if not s.empty:
        text = cons.rules_fired(history, s.idxmin())
        assert "bearish" in text and "consensus_db_v1" in text
        for word in ("buy", "sell", "target", "stop"):
            assert word not in text.lower()


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result
