import pandas as pd
import pytest

from strategies import consensus_wb_v2 as cons
from strategies.consensus_dbu_v1_audit import _symbol
from strategies.consensus_wb_v2_audit import check_cross_symbol_causality


def _history(n=8):
    return pd.concat([_symbol(f"S{i}", 260, seed=50 + i) for i in range(n)], ignore_index=True)


def test_members_are_the_four_week_bearish_readings():
    assert list(cons.MEMBERS) == ["h02", "t05c", "f15", "q01c"]


def test_side_anchoring_keeps_a_weak_bearish_reading_on_the_bearish_side():
    # A one-sided member: three bearish readings. Under v1's rule the weakest would rank 1/3 (< 0.5).
    col = pd.Series({"A": -3.0, "B": -2.0, "C": -1.0, "D": None})
    v = cons.side_anchored(col)
    assert v["A"] == pytest.approx(1.0)
    assert v["C"] == pytest.approx(0.5 + 0.5 / 3)
    assert (v[["A", "B", "C"]] > 0.5).all()
    assert v["D"] == 0.5


def test_side_anchoring_maps_bullish_below_neutral_and_zero_to_neutral():
    col = pd.Series({"A": 2.0, "B": 1.0, "C": 0.0, "D": -1.0})
    v = cons.side_anchored(col)
    assert v["A"] == pytest.approx(0.0)
    assert v["B"] == pytest.approx(0.25)
    assert v["C"] == 0.5
    assert v["D"] == pytest.approx(1.0)


def test_known_signal_the_stock_every_member_calls_most_bearish_scores_highest():
    readings = pd.DataFrame(
        {
            "h02": [-0.9, -0.1, 0.4, 0.2],
            "t05c": [-0.02, None, None, None],
            "f15": [-0.3, -0.1, 0.2, None],
            "q01c": [-0.05, -0.01, None, None],
        },
        index=["A", "B", "C", "D"],
    )
    s = cons._scores_from_mean(cons.combine(readings))
    assert s.idxmin() == "A"
    assert s["A"] == pytest.approx(-1.0)  # top bearish on all four members: mean 1
    assert "C" not in s.index and "D" not in s.index
    assert (s < 0).all()


def test_score_runs_end_to_end_and_is_bearish_only():
    history = _history()
    readings = cons.member_scores(history)
    assert list(readings.columns) == ["h02", "t05c", "f15", "q01c"]
    s = cons.score(history)
    assert not s.empty
    assert (s < 0).all() and (s >= -1.0).all()


def test_member_scores_match_the_members_themselves():
    history = _history()
    readings = cons.member_scores(history)
    for name, module in cons.MEMBERS.items():
        direct = module.score(history).dropna()
        assert readings[name].dropna().to_dict() == pytest.approx(direct.to_dict())


def test_empty_history():
    assert cons.score(pd.DataFrame()).empty


def test_rules_fired_wording():
    history = _history()
    assert "abstain" in cons.rules_fired(history, "MISSING")
    s = cons.score(history)
    text = cons.rules_fired(history, s.idxmin())
    assert "bearish" in text and "consensus_wb_v2" in text
    for word in ("buy", "sell", "target", "stop", "entry"):
        assert word not in text.lower()


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result
