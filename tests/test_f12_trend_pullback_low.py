import numpy as np
import pandas as pd

from strategies import f12_trend_pullback_low as f12
from strategies.f12_trend_pullback_low_audit import check_cross_symbol_causality, walk
from strategies.t17_keltner_breakout_audit import frame

N = f12.MIN_ROWS + 3


def stock(symbol: str, daily: float, lows10, volume5) -> pd.DataFrame:
    """Constant daily growth; the last 10 lows and last 5 volumes set by hand."""
    df = frame(symbol, 100.0 * np.cumprod(np.full(N, 1.0 + daily)))
    df.loc[df.index[-10:], "low"] = lows10
    df["volume"] = 1e6
    df.loc[df.index[-5:], "volume"] = volume5
    return df


A_LOWS = [101, 100, 102, 103, 104, 99, 98, 100, 101, 102]    # older min 100, newer min 98: fresh low
B_LOWS = [101, 100, 102, 103, 104, 103, 105, 106, 107, 108]  # older min 100, newer min 103: rising lows


def hist() -> pd.DataFrame:
    a = stock("A", 0.002, A_LOWS, [1, 2, 3, 4, 5])  # last volume highest: ts-rank 1.0
    b = stock("B", 0.001, B_LOWS, [5, 4, 3, 2, 1])  # last volume lowest: ts-rank 0.2
    return pd.concat([a, b], ignore_index=True)


def test_hand_computed_scores():
    """A has the stronger 11-month trend (rank 1.0), B rank 0.5. A: (100 - 98) / close x 1 x 1;
    B: (100 - 103) / close x 0.5 x 0.2."""
    h = hist()
    close_a = float(h[h.symbol == "A"]["close"].iloc[-1])
    close_b = float(h[h.symbol == "B"]["close"].iloc[-1])
    sc = f12.score(h)
    assert abs(sc["A"] - 2.0 / close_a) < 1e-12
    assert abs(sc["B"] - (-3.0 / close_b) * 0.5 * 0.2) < 1e-12


def test_trend_skips_the_last_month():
    df = stock("A", 0.002, A_LOWS, [1, 2, 3, 4, 5]).rename(columns={"close": "adj_close", "low": "adj_low"})
    _, trend, _ = f12.parts(df)
    assert abs(trend - 0.002) < 1e-12


def test_unchanged_lows_abstain():
    flat = [100] * 10
    assert "A" not in f12.score(pd.concat([stock("A", 0.002, flat, [1, 2, 3, 4, 5]), hist()[lambda d: d.symbol == "B"]]))


def test_short_history_abstains():
    assert f12.score(hist()[lambda d: d.symbol == "A"].tail(f12.MIN_ROWS - 1)).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    h = pd.concat([hist(), walk("CASH", N, 1)], ignore_index=True)
    h["has_future"] = h["symbol"] != "CASH"
    assert set(f12.score(h).index) == {"A", "B"}


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_rules_fired_names_the_side():
    assert f12.rules_fired(hist(), "A").endswith("bullish")
    assert f12.rules_fired(hist(), "B").endswith("bearish")
