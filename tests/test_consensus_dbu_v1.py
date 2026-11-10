import pandas as pd
import pytest

from strategies import consensus_dbu_v1 as cons
from strategies import consensus_wb_v1
from strategies.consensus_dbu_v1_audit import _symbol, check_cross_symbol_causality


def _history(n=6):
    return pd.concat([_symbol(f"S{i}", 260, seed=10 + i) for i in range(n)], ignore_index=True)


def test_members_are_the_four_day_bullish_readings():
    assert list(cons.MEMBERS) == ["t04", "q06", "f14", "t10nr7"]


def test_known_signal_the_stock_every_member_ranks_most_bullish_scores_highest():
    readings = pd.DataFrame(
        {
            "t04": [0.9, 0.1, -0.5, None],
            "q06": [0.8, 0.2, -0.4, 0.1],
            "f14": [0.05, 0.01, -0.02, None],
            "t10nr7": [0.01, None, -0.01, None],
        },
        index=["A", "B", "C", "D"],
    )
    s = cons._scores_from_mean(cons.bullish_mean_rank(readings))
    assert s.idxmax() == "A"
    assert "C" not in s.index  # bearish on every member: not a bullish pick
    assert (s > 0).all()
    # A: ranks 1, 1, 1, 1 of the stocks each member read -> mean 1 -> score +1.
    assert s["A"] == pytest.approx(1.0)


def test_is_the_week_card_rule_on_negated_readings():
    readings = pd.DataFrame({"t04": [1.0, -1.0, None], "q06": [0.5, 0.2, -0.3]}, index=["A", "B", "C"])
    pd.testing.assert_series_equal(cons.bullish_mean_rank(readings), consensus_wb_v1.combine(-readings))


def test_abstention_counts_as_neutral():
    # B is read only by t04 (top rank there) and is neutral on the other three: mean (1 + 0.5 * 3) / 4.
    readings = pd.DataFrame(
        {"t04": [0.5, 0.9], "q06": [0.3, None], "f14": [0.02, None], "t10nr7": [0.01, None]}, index=["A", "B"]
    )
    mean = cons.bullish_mean_rank(readings)
    assert mean["B"] == pytest.approx((1.0 + 0.5 * 3) / 4)
    assert mean["A"] == pytest.approx((0.5 + 1.0 + 1.0 + 1.0) / 4)


def test_score_runs_end_to_end_and_is_bullish_only():
    history = _history()
    readings = cons.member_scores(history)
    assert list(readings.columns) == ["t04", "q06", "f14", "t10nr7"]
    s = cons.score(history)
    assert not s.empty
    assert (s > 0).all() and (s <= 1.0).all()


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
    text = cons.rules_fired(history, s.idxmax())
    assert "bullish" in text and "consensus_dbu_v1" in text
    for word in ("buy", "sell", "target", "stop", "entry"):
        assert word not in text.lower()


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result
