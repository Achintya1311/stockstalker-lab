"""Synthetic tests for M01 (12-1 momentum, ranked) and M02 (pullback in a leader), month-horizon cards."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.replay import truncate
from strategies import g_gates as G
from strategies import m01_momentum_12_1 as M01
from strategies import m02_leader_pullback as M02


def frame(symbol, closes, has_future=True, split_at=None):
    """Rows for one symbol; `split_at` applies a 1:2 split (raw prices halve, PREVCLOSE carries the base)."""
    adj = np.asarray(closes, dtype=float)
    raw = adj.copy()
    if split_at is not None:
        raw[split_at:] = raw[split_at:] / 2.0
    prev = np.r_[raw[0], raw[:-1]]
    if split_at is not None:
        prev[split_at] = raw[split_at - 1] / 2.0
    n = len(raw)
    return pd.DataFrame({
        "date": pd.bdate_range("2015-01-01", periods=n).strftime("%Y-%m-%d"), "symbol": symbol,
        "open": prev, "high": np.maximum(prev, raw), "low": np.minimum(prev, raw), "close": raw,
        "prevclose": prev, "volume": 1e6, "has_future": has_future,
    })


def drift(n, d, start=100.0):
    return start * (1.0 + d) ** np.arange(n)


# ---------------------------------------------------------------- M01


def _m01_universe(n=300):
    drifts = np.linspace(-0.002, 0.002, 10)
    frames = [frame(f"S{i}", drift(n, d)) for i, d in enumerate(drifts)]
    return pd.concat(frames, ignore_index=True)


def test_m01_ranks_strongest_bullish_and_weakest_bearish():
    s = M01.score(_m01_universe())
    assert len(s) == 10
    assert s.idxmax() == "S9" and s.idxmin() == "S0"
    assert s["S9"] == pytest.approx(0.9) and s["S0"] == pytest.approx(-0.9)
    assert list(s.sort_values().index) == [f"S{i}" for i in range(10)]
    assert (s > 0).sum() == 5 and (s < 0).sum() == 5


def test_m01_ignores_the_skipped_month():
    h = _m01_universe()
    n = h["date"].nunique()
    # S9 crashes over the last 21 sessions only: the 12-1 return (and its rank) must not change.
    closes = drift(n, 0.002)
    closes[-M01.SKIP_DAYS:] = closes[-M01.SKIP_DAYS - 1] * 0.5
    h = pd.concat([h[h["symbol"] != "S9"], frame("S9", closes)], ignore_index=True)
    assert M01.score(h).idxmax() == "S9"


def test_m01_is_split_adjusted():
    n = 300
    h = pd.concat([_m01_universe(n)[lambda f: f["symbol"] != "S9"], frame("S9", drift(n, 0.002), split_at=150)],
                  ignore_index=True)
    s = M01.score(h)
    assert s.idxmax() == "S9" and s["S9"] == pytest.approx(0.9)


def test_m01_abstains_without_history_or_without_a_future_on_the_last_date():
    h = _m01_universe()
    assert M01.score(truncate(h, h["date"].unique()[M01.MIN_ROWS - 1])).empty
    h.loc[(h["symbol"] == "S3") & (h["date"] == h["date"].max()), "has_future"] = False
    assert "S3" not in M01.score(h).index


def test_m01_never_reads_rows_after_the_pick_date():
    h = _m01_universe(320)
    as_of = sorted(h["date"].unique())[300]
    seen = truncate(h, as_of)
    poisoned = h.copy()
    poisoned.loc[poisoned["date"] >= as_of, ["close", "open"]] *= 7.0
    pd.testing.assert_series_equal(M01.score(seen), M01.score(truncate(poisoned, as_of)))


def test_m01_reasoning_names_no_side_words():
    h = _m01_universe()
    text = M01.rules_fired(h, "S9")
    assert "bullish" in text and "buy" not in text.lower() and "sell" not in text.lower()


# ---------------------------------------------------------------- M02


def _m02_universe(n=300, leader_last=-0.01):
    drifts = np.linspace(-0.004, -0.002, 9)
    frames = [frame(f"L{i}", drift(n, d)) for i, d in enumerate(drifts)]
    lead = drift(n, 0.003)
    lead[-1] = lead[-2] * (1.0 + leader_last)
    frames.append(frame("LEAD", lead))
    return frames


def test_m02_picks_a_leader_that_closed_lower_with_its_percentile():
    h = pd.concat(_m02_universe(), ignore_index=True)
    s = M02.score(h)
    adj = G._adjusted_tail(h)
    assert list(s.index) == ["LEAD"]
    assert s["LEAD"] == pytest.approx(G.leader_percentiles(adj)["LEAD"]) and s["LEAD"] > G.LEADER_TOP
    assert (s > 0).all()  # bullish only, ever


def test_m02_abstains_when_the_leader_closed_higher():
    h = pd.concat(_m02_universe(leader_last=+0.01), ignore_index=True)
    assert M02.score(h).empty


def test_m02_abstains_more_than_15_percent_below_the_252_day_high():
    frames = _m02_universe()
    n = 300
    # FALL: a strong run, then 25% off its high over the last 30 sessions; still top 30% and above its average.
    fall = drift(n, 0.006)
    fall[-30:] = fall[-31] * np.linspace(0.99, 0.75, 30)
    frames[-1] = frame("FALL", fall)
    h = pd.concat(frames, ignore_index=True)
    r = M02._readings(h).loc["FALL"]
    assert r["pct"] > G.LEADER_TOP and r["trend"] == 1 and r["last_ret"] < 0 and r["near_high"] < 0.85
    assert "FALL" not in M02.score(h).index


def test_m02_abstains_below_the_200_day_average_and_for_laggards():
    frames = _m02_universe()
    h = pd.concat(frames, ignore_index=True)
    r = M02._readings(h)
    assert not r.loc["L0", "ok"]  # bottom of the ranking, falling
    assert "L0" not in M02.score(h).index
    short = pd.concat([f.iloc[-200:] for f in frames], ignore_index=True)  # under 252 rows: no reading
    assert M02.score(short).empty


def test_m02_never_reads_rows_after_the_pick_date():
    h = pd.concat(_m02_universe(320), ignore_index=True)
    as_of = sorted(h["date"].unique())[300]
    poisoned = h.copy()
    poisoned.loc[poisoned["date"] >= as_of, ["close", "open"]] *= 3.0
    pd.testing.assert_series_equal(M02.score(truncate(h, as_of)), M02.score(truncate(poisoned, as_of)))


def test_m02_reuses_g_gates_rather_than_copying():
    import inspect
    src = inspect.getsource(M02)
    assert "from strategies import g_gates as G" in src and "def leader_percentiles" not in src
