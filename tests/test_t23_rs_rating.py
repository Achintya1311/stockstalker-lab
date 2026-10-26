import numpy as np
import pandas as pd

from strategies import t23_rs_rating as t23
from strategies.t23_rs_rating_audit import check_cross_symbol_causality

N = t23.MIN_ROWS


def _frame(symbol: str, closes) -> pd.DataFrame:
    dates = pd.bdate_range("2015-01-01", periods=len(closes)).strftime("%Y-%m-%d")
    rows = []
    prev = float(closes[0])
    for d, c in zip(dates, closes):
        c = float(c)
        rows.append({"date": d, "symbol": symbol, "open": prev, "high": max(prev, c), "low": min(prev, c),
                     "close": c, "prevclose": prev, "volume": 1e6})
        prev = c
    return pd.DataFrame(rows)


def _trend(symbol: str, drift: float, n: int = N) -> pd.DataFrame:
    return _frame(symbol, 100.0 * np.exp(drift * np.arange(n)))


def test_perf_matches_hand_computation():
    hist = _trend("AAA", 0.001)
    c = hist["close"].to_numpy()
    want = 0.4 * (c[-1] / c[-64] - 1) + 0.2 * (c[-1] / c[-127] - 1) + 0.2 * (c[-1] / c[-190] - 1) + 0.2 * (c[-1] / c[-253] - 1)
    assert abs(t23.raw_perf(hist)["AAA"] - want) < 1e-12


def test_latest_quarter_counts_double():
    """Two stocks with the same 12-month return: the one whose gain came in the
    last quarter rates higher."""
    flat_then_up = np.r_[np.full(N - 63, 100.0), np.linspace(100.0, 130.0, 63)]
    up_then_flat = np.r_[np.linspace(100.0, 130.0, 63), np.full(N - 63, 130.0)]
    hist = pd.concat([_frame("LATE", flat_then_up), _frame("EARLY", up_then_flat)])
    perf = t23.raw_perf(hist)
    assert perf["LATE"] > perf["EARLY"]
    sc = t23.score(hist)
    assert sc["LATE"] > 0 > sc["EARLY"]


def test_scores_are_symmetric_and_ordered():
    hist = pd.concat([_trend(s, d) for s, d in [("A", 0.002), ("B", 0.001), ("C", 0.0), ("D", -0.001)]])
    sc = t23.score(hist)
    assert list(sc.sort_values().index) == ["D", "C", "B", "A"]
    assert abs(sc.sum()) < 1e-12
    assert abs(sc["A"] - 0.75) < 1e-12 and abs(sc["D"] + 0.75) < 1e-12


def test_ties_share_the_rank():
    hist = pd.concat([_trend("A", 0.001), _trend("B", 0.001), _trend("C", -0.001)])
    sc = t23.score(hist)
    assert sc["A"] == sc["B"]


def test_single_symbol_and_short_history_abstain():
    assert t23.score(_trend("A", 0.001)).empty
    hist = pd.concat([_trend("SHORT", 0.001, N - 1), _trend("A", 0.001), _trend("B", -0.001)])
    assert "SHORT" not in t23.score(hist)


def test_non_fno_symbols_are_dropped_when_flag_present():
    hist = pd.concat([_trend("F1", 0.001), _trend("F2", -0.001), _trend("CASH", 0.003)])
    hist["has_future"] = hist["symbol"] != "CASH"
    assert set(t23.score(hist).index) == {"F1", "F2"}


def test_rules_fired_wording():
    hist = pd.concat([_trend("UP", 0.002), _trend("DOWN", -0.002)])
    assert "bullish" in t23.rules_fired(hist, "UP")
    assert "abstain" in t23.rules_fired(hist, "NONE")


def test_causality_audit_passes():
    assert check_cross_symbol_causality()["passed"]
