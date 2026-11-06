import numpy as np
import pandas as pd

from strategies import f17_close_location_recency as f17
from strategies.f13_accel_range_top_audit import walk
from strategies.f17_close_location_recency_audit import check_cross_symbol_causality

N = f17.MIN_ROWS


def bars(symbol: str, closes, last_high: float, last_low: float, turnover: float = 1e9) -> pd.DataFrame:
    dates = pd.bdate_range("2016-01-01", periods=len(closes)).strftime("%Y-%m-%d")
    rows = [{"date": d, "symbol": symbol, "open": c, "high": c * 1.01, "low": c * 0.99, "close": c,
             "prevclose": c, "volume": 1e6, "turnover": turnover} for d, c in zip(dates, closes)]
    rows[-1]["high"], rows[-1]["low"] = last_high, last_low
    rows[-1]["prevclose"] = closes[-2]
    for i in range(1, len(rows)):
        rows[i]["prevclose"] = closes[i - 1]
    return pd.DataFrame(rows)


def hist() -> pd.DataFrame:
    a = np.linspace(110, 100, N)            # high is the oldest close (position 1); closes at the bar's high
    b = np.linspace(100, 110, N)            # high is the last close (position 10); closes at the bar's low
    c = np.r_[np.linspace(100, 108, 5), np.linspace(107, 103, N - 5)]  # high at position 5; mid-bar close
    return pd.concat([bars("A", a, a[-1], a[-1] - 2), bars("B", b, b[-1] + 2, b[-1]),
                      bars("C", c, c[-1] + 1, c[-1] - 1)], ignore_index=True)


def test_parts_match_hand_values():
    h = hist()
    a = h[h["symbol"] == "A"].assign(adj_close=lambda d: d["close"])
    flow, pos = f17.parts(a)
    assert abs(flow - 1e9) < 1e-3 and pos == 1.0


def test_hand_computed_scores():
    """Flow ranks A 1, C 2/3, B 1/3; high-position ranks A 1/3, C 2/3, B 1; both sum to 2.
    raw = pos/2 - flow: A -5/6, B +1/6, C -1/3 (the median): A -1/2 bearish, B +1/2 bullish, C abstains."""
    sc = f17.score(hist())
    assert abs(sc["A"] + 0.5) < 1e-12
    assert abs(sc["B"] - 0.5) < 1e-12
    assert "C" not in sc.index


def test_flat_bar_abstains():
    h = hist()
    last = h["date"].max()
    h.loc[(h["symbol"] == "C") & (h["date"] == last), ["high", "low"]] = h.loc[
        (h["symbol"] == "C") & (h["date"] == last), "close"].iloc[0]
    assert "C" not in f17.components(h).index


def test_short_history_abstains():
    assert f17.score(hist().groupby("symbol").tail(N - 1)).empty


def test_symbols_without_a_future_on_the_last_date_leave():
    h = pd.concat([hist().assign(has_future=True), walk("D", N, 3)], ignore_index=True)
    h["date"] = h["date"].astype(str)
    last = h["date"].max()
    h.loc[(h["symbol"] == "D") & (h["date"] == last), "has_future"] = False
    assert "D" not in f17.score(h).index


def test_needs_turnover():
    assert f17.score(hist().drop(columns="turnover")).empty


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_rules_fired_names_the_side():
    h = hist()
    assert f17.rules_fired(h, "A").endswith("bearish")
    assert "set 9 sessions before the last" in f17.rules_fired(h, "A")
    assert f17.rules_fired(h, "B").endswith("bullish")
    assert "abstain" in f17.rules_fired(h, "C")
