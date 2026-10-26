import numpy as np
import pandas as pd

from strategies import i01_momentum_score as i01
from strategies.i01_momentum_score_audit import _synthetic_symbol, check_cross_symbol_causality

N = i01.MIN_ROWS


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


def _zigzag_trend(symbol: str, step: float, drift: float, n: int = N) -> pd.DataFrame:
    """Log price = drift * t plus an alternating +/- step/2 wiggle, so the
    series has a known trend and non-zero volatility."""
    t = np.arange(n)
    logs = drift * t + np.where(t % 2 == 0, -step / 2, step / 2)
    return _frame(symbol, 100.0 * np.exp(logs))


def test_ratios_match_hand_computation():
    hist = _zigzag_trend("AAA", 0.02, 0.001)
    ratios = i01.raw_ratios(hist)
    close = hist["close"].to_numpy()
    sigma = np.std(np.diff(np.log(close[-253:]))) * np.sqrt(252)
    assert abs(ratios.loc["AAA", "m6"] - (close[-1] / close[-127] - 1) / sigma) < 1e-12
    assert abs(ratios.loc["AAA", "m12"] - (close[-1] / close[-253] - 1) / sigma) < 1e-12


def test_strongest_trend_is_bullish_weakest_is_bearish():
    hist = pd.concat([
        _zigzag_trend("UP", 0.02, 0.002),
        _zigzag_trend("FLAT", 0.02, 0.0),
        _zigzag_trend("DOWN", 0.02, -0.002),
    ])
    sc = i01.score(hist)
    assert sc["UP"] > 0 > sc["DOWN"]
    assert sc["UP"] > sc["FLAT"] > sc["DOWN"]


def test_volatility_divides_the_return():
    """Same trend, higher volatility: lower score."""
    hist = pd.concat([_zigzag_trend("CALM", 0.01, 0.001), _zigzag_trend("WILD", 0.08, 0.001)])
    sc = i01.score(hist)
    assert sc["CALM"] > sc["WILD"]


def test_scores_are_centred():
    hist = pd.concat([_zigzag_trend(s, 0.02, d) for s, d in [("A", 0.002), ("B", 0.0005), ("C", -0.001)]])
    assert abs(i01.score(hist).sum()) < 1e-12


def test_single_symbol_abstains():
    assert i01.score(_zigzag_trend("AAA", 0.02, 0.001)).empty


def test_short_history_abstains():
    hist = pd.concat([_zigzag_trend("SHORT", 0.02, 0.001, N - 1), _zigzag_trend("A", 0.02, 0.001),
                      _zigzag_trend("B", 0.02, -0.001)])
    sc = i01.score(hist)
    assert "SHORT" not in sc and {"A", "B"} <= set(sc.index)


def test_non_fno_symbols_are_dropped_when_flag_present():
    hist = pd.concat([_zigzag_trend("F1", 0.02, 0.001), _zigzag_trend("F2", 0.02, -0.001),
                      _zigzag_trend("CASH", 0.02, 0.003)])
    hist["has_future"] = hist["symbol"] != "CASH"
    assert set(i01.score(hist).index) == {"F1", "F2"}


def test_rules_fired_wording():
    hist = pd.concat([_zigzag_trend("UP", 0.02, 0.002), _zigzag_trend("DOWN", 0.02, -0.002)])
    assert "bullish" in i01.rules_fired(hist, "UP")
    assert "abstain" in i01.rules_fired(hist, "NONE")


def test_causality_audit_passes():
    assert check_cross_symbol_causality()["passed"]


def test_random_walks_rank_by_drift():
    hist = pd.concat([_synthetic_symbol("W", N + 5, 1, 0.003), _synthetic_symbol("L", N + 5, 2, -0.003)])
    sc = i01.score(hist)
    assert sc["W"] > sc["L"]
