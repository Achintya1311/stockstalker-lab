import numpy as np
import pandas as pd

from strategies import t19_obv_divergence as t19
from strategies.t19_obv_divergence_audit import check_cross_symbol_causality, diverging
from strategies.t21_minervini_template_audit import _frame

N = t19.MIN_ROWS


def test_bullish_divergence_fires():
    assert t19.score(diverging("A", True))["A"] > 0


def test_bearish_divergence_fires():
    assert t19.score(diverging("A", False))["A"] < 0


def test_confirmed_trend_abstains():
    """Steady decline on constant volume: lower low and lower OBV low, no divergence."""
    assert t19.score(_frame("A", 100.0 * np.exp(-0.003 * np.arange(N)))).empty


def test_score_is_obv_gap_over_volume():
    hist = diverging("A", True)
    tail = hist.iloc[-N:]
    c = tail["close"].to_numpy(); v = tail["volume"].to_numpy()
    obv = np.cumsum(np.sign(np.diff(c)) * v[1:])
    want = (obv[20:].min() - obv[:20].min()) / v[1:].sum()
    assert abs(t19.score(hist)["A"] - want) < 1e-12


def test_short_history_abstains():
    assert t19.score(diverging("A", True).iloc[-(N - 1):]).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    hist = pd.concat([diverging("F", True), diverging("CASH", True)])
    hist["has_future"] = hist["symbol"] == "F"
    assert list(t19.score(hist).index) == ["F"]


def test_rules_fired_wording():
    assert "bullish" in t19.rules_fired(diverging("A", True), "A")
    assert "abstain" in t19.rules_fired(_frame("B", 100.0 * np.exp(-0.003 * np.arange(N))), "B")


def test_causality_audit_passes():
    assert check_cross_symbol_causality()["passed"]
