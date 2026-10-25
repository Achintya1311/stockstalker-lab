import numpy as np
import pandas as pd
import pytest

from strategies import consensus_wb_v1 as cons
from strategies.a05_max_effect_audit import _synthetic_symbol
from strategies.consensus_wb_v1_audit import check_cross_symbol_causality


def _readings(rows: dict[str, tuple]) -> pd.DataFrame:
    return pd.DataFrame.from_dict(rows, orient="index", columns=list(cons.MEMBERS))


def test_agreement_of_all_three_ranks_first():
    # A is the most bearish for every member; D is the most bullish for every member.
    r = _readings({"A": (-3, -3, -3), "B": (-2, -2, -2), "C": (-1, -1, -1), "D": (1, 1, 1)})
    mean = cons.combine(r)
    assert mean["A"] == pytest.approx(1.0)
    assert mean.idxmax() == "A" and mean.idxmin() == "D"
    s = cons._scores_from_mean(mean)
    assert s["A"] == pytest.approx(-1.0)
    assert "D" not in s.index  # net bullish: left out of a bearish-only card


def test_abstention_counts_as_neutral_not_missing():
    # LONE: only d02c reads it, as its most bearish stock (rank 1.0), others abstain -> (1 + .5 + .5)/3.
    # ALL3: second-most bearish for every member -> (0.5 + 2/3 + 2/3)/3 with members' own peer sets.
    r = _readings({
        "LONE": (-5.0, np.nan, np.nan),
        "ALL3": (-1.0, -2.0, -2.0),
        "X": (np.nan, -3.0, -3.0),
        "Y": (np.nan, 1.0, 1.0),
    })
    mean = cons.combine(r)
    assert mean["LONE"] == pytest.approx((1.0 + 0.5 + 0.5) / 3)
    # d02c reads LONE and ALL3: ranks 1.0 and 0.5. a01/t15 read ALL3, X, Y: ranks 2/3, 1.0, 1/3.
    assert mean["ALL3"] == pytest.approx((0.5 + 2 / 3 + 2 / 3) / 3)
    assert mean["X"] == pytest.approx((0.5 + 1.0 + 1.0) / 3)
    assert mean["X"] > mean["LONE"]


def test_output_is_bearish_only_and_bounded():
    rng = np.random.default_rng(0)
    r = pd.DataFrame(rng.normal(size=(40, 3)), index=[f"S{i}" for i in range(40)], columns=list(cons.MEMBERS))
    s = cons._scores_from_mean(cons.combine(r))
    assert (s < 0).all() and (s >= -1.0).all()


def test_empty_readings_and_history():
    assert cons.combine(pd.DataFrame(columns=list(cons.MEMBERS))).empty
    assert cons.score(pd.DataFrame()).empty


def test_score_runs_end_to_end_on_synthetic_prices():
    # No OI columns: D02 abstains everywhere, so A01 and T15 carry the ranking. It must still run.
    history = pd.concat([_synthetic_symbol(f"S{i}", 120, seed=i) for i in range(6)], ignore_index=True)
    s = cons.score(history)
    assert (s < 0).all()
    readings = cons.member_scores(history)
    assert readings["d02c"].isna().all()
    assert readings["a01"].notna().sum() == 6


def test_rules_fired_wording():
    history = pd.concat([_synthetic_symbol(f"S{i}", 120, seed=i) for i in range(6)], ignore_index=True)
    s = cons.score(history)
    sym = s.idxmin()
    text = cons.rules_fired(history, sym)
    assert "bearish" in text and "consensus_wb_v1" in text
    for word in ("buy", "sell", "target", "stop"):
        assert word not in text.lower()
    assert "abstain" in cons.rules_fired(history, "MISSING")


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result
