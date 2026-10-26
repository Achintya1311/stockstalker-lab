import numpy as np
import pandas as pd

from strategies import t25_heikin_ashi as t25
from strategies.t25_heikin_ashi_audit import check_cross_symbol_causality, trending

N = t25.MIN_ROWS


def test_heikin_ashi_formulas():
    o = np.array([10.0, 11.0]); h = np.array([12.0, 13.0]); l = np.array([9.0, 10.0]); c = np.array([11.0, 12.0])
    ho, hh, hl, hc = t25.heikin_ashi(o, h, l, c)
    assert hc[0] == 10.5 and ho[0] == 10.5
    assert ho[1] == (10.5 + 10.5) / 2 and hc[1] == 11.5
    assert hh[1] == 13.0 and hl[1] == 10.0


def test_steady_uptrend_fires_bullish():
    sc = t25.score(trending("UP", N, 0.01))
    assert sc["UP"] > 0


def test_steady_downtrend_fires_bearish():
    sc = t25.score(trending("DOWN", N, -0.01))
    assert sc["DOWN"] < 0


def test_stronger_run_scores_higher():
    hist = pd.concat([trending("FAST", N, 0.02), trending("SLOW", N, 0.005)])
    sc = t25.score(hist)
    assert sc["FAST"] > sc["SLOW"] > 0


def test_a_lower_wick_breaks_the_run():
    hist = trending("UP", N, 0.01)
    # a deep intraday low on the last bar puts a lower wick under its HA candle
    hist.loc[hist.index[-1], "low"] = hist["low"].iloc[-1] * 0.8
    assert t25.score(hist).empty


def test_reversal_ends_the_bullish_run():
    up = trending("X", N, 0.01)
    down = trending("X", 3, -0.03)
    down["open"] = down["open"] * up["close"].iloc[-1] / 100.0
    for col in ("high", "low", "close", "prevclose"):
        down[col] = down[col] * up["close"].iloc[-1] / 100.0
    down["date"] = pd.bdate_range(pd.Timestamp(up["date"].iloc[-1]) + pd.offsets.BDay(1), periods=3).strftime("%Y-%m-%d")
    sc = t25.score(pd.concat([up, down], ignore_index=True))
    assert "X" not in sc or sc["X"] < 0  # three sharp red days end the bullish run


def test_short_history_abstains():
    assert t25.score(trending("UP", N - 1, 0.01)).empty


def test_old_rows_do_not_matter():
    base = trending("UP", N + 40, 0.01)
    changed = base.copy()
    changed.loc[:9, "high"] *= 1.5
    assert t25.score(base)["UP"] == t25.score(changed)["UP"]


def test_non_fno_symbols_are_dropped_when_flag_present():
    hist = pd.concat([trending("F", N, 0.01), trending("CASH", N, 0.01)])
    hist["has_future"] = hist["symbol"] == "F"
    assert list(t25.score(hist).index) == ["F"]


def test_rules_fired_wording():
    hist = trending("UP", N, 0.01)
    assert "bullish" in t25.rules_fired(hist, "UP")
    assert "abstain" in t25.rules_fired(hist, "NONE")


def test_causality_audit_passes():
    assert check_cross_symbol_causality()["passed"]
