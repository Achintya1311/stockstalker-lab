import numpy as np
import pandas as pd

from strategies import i02_low_vol_level
from strategies.i02_low_vol_level_audit import _synthetic_symbol, check_cross_symbol_causality

N = i02_low_vol_level.MIN_ROWS


def _alternating(symbol: str, step: float, n_rows: int = N) -> pd.DataFrame:
    """Close alternates up and down by a factor exp(step): every daily log
    return is +step or -step, so sigma is exactly `step` (known expected signal)."""
    dates = pd.bdate_range("2015-01-01", periods=n_rows).strftime("%Y-%m-%d")
    logs = np.where(np.arange(n_rows) % 2 == 0, 0.0, step)
    closes = 100.0 * np.exp(logs)
    rows = []
    prev = float(closes[0])
    for d, c in zip(dates, closes):
        c = float(c)
        rows.append({"date": d, "symbol": symbol, "open": prev, "high": max(prev, c), "low": min(prev, c),
                     "close": c, "prevclose": prev, "volume": 1e6})
        prev = c
    return pd.DataFrame(rows)


def test_sigma_matches_the_constructed_step():
    sig = i02_low_vol_level.raw_sigma(_alternating("AAA", 0.02))
    assert abs(sig["AAA"] - 0.02) < 1e-12


def test_calmest_is_bullish_most_volatile_is_bearish():
    hist = pd.concat([_alternating("CALM", 0.005), _alternating("MID", 0.02), _alternating("WILD", 0.05)])
    sc = i02_low_vol_level.score(hist)
    assert sc["CALM"] > 0
    assert sc["WILD"] < 0
    assert sc["MID"] == 0  # the median symbol sits exactly on the centre
    assert abs(sc["CALM"] - np.log(0.02 / 0.005)) < 1e-12


def test_short_history_abstains():
    hist = pd.concat([_alternating("AAA", 0.02, N - 1), _alternating("BBB", 0.02)])
    sc = i02_low_vol_level.score(hist)
    assert "AAA" not in sc
    assert "BBB" in sc


def test_flat_series_abstains():
    hist = _alternating("FLAT", 0.0)
    assert i02_low_vol_level.score(hist).empty


def test_only_trailing_window_is_read():
    """Changing rows older than the last MIN_ROWS must not move sigma."""
    base = _alternating("AAA", 0.02, N + 30)
    changed = base.copy()
    changed.loc[:9, ["open", "high", "low", "close", "prevclose"]] *= 1.7
    a = i02_low_vol_level.raw_sigma(base)["AAA"]
    b = i02_low_vol_level.raw_sigma(changed)["AAA"]
    assert abs(a - b) < 1e-12


def test_non_fno_symbols_are_dropped_when_flag_present():
    hist = pd.concat([_alternating("FNO", 0.02), _alternating("CASH", 0.01)])
    hist["has_future"] = hist["symbol"] == "FNO"
    assert list(i02_low_vol_level.score(hist).index) == ["FNO"]


def test_rules_fired_wording():
    hist = pd.concat([_alternating("CALM", 0.005), _alternating("WILD", 0.05)])
    text = i02_low_vol_level.rules_fired(hist, "CALM")
    assert "bullish" in text and "1 of 2" in text
    assert "abstain" in i02_low_vol_level.rules_fired(hist, "NONE")


def test_causality_audit_passes():
    assert check_cross_symbol_causality()["passed"]


def test_random_walks_rank_by_their_volatility():
    hist = pd.concat([_synthetic_symbol("LOW", N + 5, 1, 0.005), _synthetic_symbol("HIGH", N + 5, 2, 0.04)])
    sc = i02_low_vol_level.score(hist)
    assert sc["LOW"] > sc["HIGH"]
