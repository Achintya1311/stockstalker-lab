"""Synthetic tests for the C1 gates G1-G8 and the trigger x gate cells (`strategies/g_gates.py`).

Per gate: one case where it keeps, one where it drops, one with too little data (no verdict). Then: keep
and complement partition the trigger's side picks, future rows never change a verdict, the generated
modules match the table, and the shared causality audit passes.
"""

from __future__ import annotations

import importlib

import numpy as np
import pandas as pd
import pytest

from engine.replay import truncate
from scripts import gen_g_cells
from strategies import g_gates as G
from strategies.g_gates_audit import _poison_from, run_all, synthetic_panel


def frame(symbol, closes, opens=None, volumes=None, oi_chg=None, highs=None, lows=None, start="2015-01-01"):
    closes = np.asarray(closes, dtype=float)
    n = len(closes)
    prev = np.r_[closes[0], closes[:-1]]
    opens = prev if opens is None else np.asarray(opens, dtype=float)
    out = pd.DataFrame({
        "date": pd.bdate_range(start, periods=n).strftime("%Y-%m-%d"),
        "symbol": symbol,
        "open": opens,
        "high": np.maximum(opens, closes) if highs is None else highs,
        "low": np.minimum(opens, closes) if lows is None else lows,
        "close": closes,
        "prevclose": prev,
        "volume": np.full(n, 1e6) if volumes is None else np.asarray(volumes, dtype=float),
        "has_future": True,
    })
    if oi_chg is not None:
        out["oi_futstk"] = 100_000.0
        out["oi_chg_futstk"] = oi_chg
    return out


def trend(n, daily):
    return 100.0 * (1.0 + daily) ** np.arange(n)


def calm_then(n, last_move, start=100.0):
    """Alternating +-1% days (sigma 1%) then a final day of `last_move`."""
    steps = np.r_[np.where(np.arange(n - 1) % 2 == 0, 0.01, -0.01), last_move]
    return start * np.cumprod(1.0 + np.r_[0.0, steps[1:]])


# ---------------------------------------------------------------- G1 trend side


def test_g1_keeps_the_pick_on_the_trend_side_and_drops_the_other():
    up = frame("UP", trend(230, 0.002))
    assert G.g1(up, {"UP": 1}) == {"UP": True}
    assert G.g1(up, {"UP": -1}) == {"UP": False}
    down = frame("DN", trend(230, -0.002))
    assert G.g1(down, {"DN": -1}) == {"DN": True}


def test_g1_has_no_verdict_under_200_rows():
    assert G.g1(frame("UP", trend(150, 0.002)), {"UP": 1}) == {}


# ---------------------------------------------------------------- G2 not fading a leader


def _ranked_universe(n_rows=230):
    # Ten stocks with steady daily drifts from -0.25% to +0.20%: TOP is the strongest and above its average.
    drifts = np.linspace(-0.0025, 0.002, 10)
    names = ["BOT"] + [f"M{i}" for i in range(8)] + ["TOP"]
    return pd.concat([frame(n, trend(n_rows, d)) for n, d in zip(names, drifts)], ignore_index=True)


def test_g2_drops_a_bearish_pick_on_a_leader_and_a_bullish_pick_on_a_laggard():
    h = _ranked_universe()
    assert G.g2(h, {"TOP": -1}) == {"TOP": False}
    assert G.g2(h, {"BOT": 1}) == {"BOT": False}


def test_g2_keeps_a_bearish_pick_outside_the_top_30_percent_or_with_trend_on_its_side():
    h = _ranked_universe()
    assert G.g2(h, {"BOT": -1, "M3": -1, "TOP": 1}) == {"BOT": True, "M3": True, "TOP": True}


def test_g2_needs_a_63_day_reading_and_the_200_day_average_only_when_the_rank_is_extreme():
    short = _ranked_universe(n_rows=50)
    assert G.g2(short, {"TOP": -1}) == {}
    mid = _ranked_universe(n_rows=120)  # 63-day rank exists, 200-day average does not
    assert G.g2(mid, {"TOP": -1, "M3": -1}) == {"M3": True}


# ---------------------------------------------------------------- G3 stock-specific move


def _e2a_universe(peer_last_move):
    a = frame("AAA", calm_then(40, 0.05))
    peers = [frame(f"P{i}", calm_then(40, peer_last_move)) for i in range(4)]
    return pd.concat([a, *peers], ignore_index=True)


def test_g3_e2a_keeps_a_move_that_is_still_over_one_sigma_after_the_market_and_drops_a_shared_one():
    assert G.g3(_e2a_universe(0.0), {"AAA": -1}, "e2a") == {"AAA": True}       # residual about +4 sigma
    assert G.g3(_e2a_universe(0.045), {"AAA": -1}, "e2a") == {"AAA": False}    # market +4.6%, residual about +0.4 sigma


def test_g3_t04_and_a01_need_the_residual_move_on_the_faded_side():
    fall = frame("AAA", calm_then(40, -0.03))
    flat_peers = [frame(f"P{i}", calm_then(40, 0.0)) for i in range(4)]
    worse_peers = [frame(f"P{i}", calm_then(40, -0.05)) for i in range(4)]
    assert G.g3(pd.concat([fall, *flat_peers]), {"AAA": 1}, "t04") == {"AAA": True}
    assert G.g3(pd.concat([fall, *worse_peers]), {"AAA": 1}, "t04") == {"AAA": False}
    up = frame("AAA", trend(10, 0.01))
    assert G.g3(pd.concat([up, *[frame(f"P{i}", trend(10, 0.0)) for i in range(3)]]), {"AAA": -1}, "a01") == {"AAA": True}
    assert G.g3(pd.concat([up, *[frame(f"P{i}", trend(10, 0.02)) for i in range(3)]]), {"AAA": -1}, "a01") == {"AAA": False}


def test_g3_has_no_verdict_with_too_little_history_or_for_a05b():
    assert G.g3(pd.concat([frame("AAA", calm_then(15, 0.05)), frame("P0", calm_then(15, 0.0))]), {"AAA": -1}, "e2a") == {}
    assert G.g3(frame("AAA", trend(4, 0.01)), {"AAA": -1}, "a01") == {}
    assert G.g3(_e2a_universe(0.0), {"AAA": 1}, "a05b") == {}


# ---------------------------------------------------------------- G4 no-news proxy


def _gapped(last_gap, n=30):
    closes = np.full(n, 100.0)
    gaps = np.r_[0.0, np.where(np.arange(n - 2) % 2 == 0, 0.005, -0.005), last_gap]  # sigma 0.5%
    return frame("AAA", closes, opens=100.0 * (1.0 + gaps))


def test_g4_drops_a_pick_whose_trigger_day_gapped_over_one_sigma_with_the_move():
    assert G.g4(_gapped(+0.02), {"AAA": -1}) == {"AAA": False}   # bearish pick, gap up 4 sigma: news-like
    assert G.g4(_gapped(-0.02), {"AAA": 1}) == {"AAA": False}


def test_g4_keeps_a_small_gap_or_a_gap_against_the_move():
    assert G.g4(_gapped(+0.002), {"AAA": -1}) == {"AAA": True}
    assert G.g4(_gapped(-0.02), {"AAA": -1}) == {"AAA": True}


def test_g4_has_no_verdict_with_too_few_gaps():
    assert G.g4(_gapped(0.02, n=10), {"AAA": -1}) == {}


# ---------------------------------------------------------------- G5 market stress


def _vol_regime(calm_last, n=300, seed=3):
    rng = np.random.default_rng(seed)
    quiet, loud = 0.005, 0.03
    sig = np.r_[np.full(n - 20, loud if calm_last else quiet), np.full(20, quiet if calm_last else loud)]
    frames = []
    for k in range(3):
        r = rng.normal(0, 1, n) * sig
        frames.append(frame(f"S{k}", 100.0 * np.exp(np.cumsum(r))))
    return pd.concat(frames, ignore_index=True)


def test_g5_keeps_every_pick_when_the_market_is_stressed_and_drops_them_when_calm():
    assert G.g5(_vol_regime(calm_last=False), {"S0": 1, "S1": -1}) == {"S0": True, "S1": True}
    assert G.g5(_vol_regime(calm_last=True), {"S0": 1}) == {"S0": False}


def test_g5_has_no_verdict_under_270_market_days():
    assert G.g5(_vol_regime(calm_last=False, n=200), {"S0": 1}) == {}


# ---------------------------------------------------------------- G6 order-block location


def _order_block(final_close):
    """50 quiet bars, a down candle (the zone), a 3-point up impulse breaking the 10-bar high, then a drift."""
    o, c = [], []
    for i in range(50):
        o.append(100.0)
        c.append(100.2 if i % 2 == 0 else 99.8)
    o.append(100.3); c.append(99.7)            # zone candle: low 99.7, high 100.3
    o.append(99.7); c.append(103.0)            # impulse
    for _ in range(7):
        o.append(102.6); c.append(102.5)
    o.append(102.5); c.append(final_close)
    o, c = np.array(o), np.array(c)
    return frame("AAA", c, opens=o, highs=np.maximum(o, c) + 0.1, lows=np.minimum(o, c) - 0.1)


def test_g6_keeps_a_bullish_pick_at_or_above_a_fresh_demand_zone():
    h = _order_block(102.4)
    assert G.g6(h, {"AAA": 1}) == {"AAA": True}
    assert G.g6(h, {"AAA": -1}) == {"AAA": False}   # the zone disagrees with a bearish pick


def test_g6_drops_when_the_zone_was_closed_through():
    assert G.g6(_order_block(99.0), {"AAA": 1}) == {"AAA": False}


def test_g6_has_no_verdict_under_60_bars():
    h = _order_block(102.4)
    assert G.g6(h[h["date"] > h["date"].iloc[10]], {"AAA": 1}) == {}


# ---------------------------------------------------------------- G7 OI state


def test_g7_keeps_only_where_d01c_agrees_with_the_pick():
    long_buildup = frame("AAA", [100.0, 101.0], oi_chg=[0.0, 500.0])   # price up, OI up: D01C bearish
    assert G.g7(long_buildup, {"AAA": -1}) == {"AAA": True}
    assert G.g7(long_buildup, {"AAA": 1}) == {"AAA": False}


def test_g7_has_no_verdict_without_oi():
    assert G.g7(frame("AAA", [100.0, 101.0]), {"AAA": -1}) == {}


# ---------------------------------------------------------------- G8 volume surge


def test_g8_keeps_a_trigger_day_over_one_and_a_half_times_its_20_day_average():
    v = np.r_[np.full(20, 1e6), 2e6]
    assert G.g8(frame("AAA", np.full(21, 100.0), volumes=v), {"AAA": 1}) == {"AAA": True}
    v[-1] = 1.4e6
    assert G.g8(frame("AAA", np.full(21, 100.0), volumes=v), {"AAA": 1}) == {"AAA": False}


def test_g8_has_no_verdict_under_21_sessions():
    assert G.g8(frame("AAA", np.full(15, 100.0), volumes=np.full(15, 1e6)), {"AAA": 1}) == {}


# ---------------------------------------------------------------- cells


def test_cell_table_is_32_minus_the_skipped_cells():
    assert len(G.CELLS) == 28 and len(G.SKIPPED) == 4
    assert ("e2a", "g7") in G.SKIPPED and ("t04", "g1") in G.SKIPPED
    with pytest.raises(ValueError):
        G.cell("t04", "g1")


@pytest.fixture(scope="module")
def panel():
    return synthetic_panel(n_symbols=12, n_rows=330)


@pytest.mark.parametrize("trigger,gate", [c for c in G.CELLS if c[0] in ("a01", "a05b")])
def test_keep_and_complement_partition_the_triggers_side_picks(panel, trigger, gate):
    base, v = G.verdicts(trigger, gate, panel)
    keep, drop = G.cell_score(trigger, gate, True, panel), G.cell_score(trigger, gate, False, panel)
    side = G.TRIGGERS[trigger].side
    assert not base.empty and (base * side > 0).all()
    assert set(keep.index).isdisjoint(drop.index)
    assert set(keep.index) | set(drop.index) == {s for s in base.index if s in v}
    assert (pd.concat([keep, drop]).sort_index() == base[list(v)].sort_index()).all()   # scores unchanged


def test_cells_drop_the_other_table_side(panel):
    full = G.TRIGGERS["a01"].mod.score(panel)
    assert (full > 0).any() and (full < 0).any()
    for keep in (True, False):
        assert (G.cell_score("a01", "g1", keep, panel) < 0).all()


@pytest.mark.parametrize("gate", sorted(G.GATES))
def test_truncating_future_rows_never_changes_a_verdict(panel, gate):
    for d in sorted(panel["date"].unique())[-3:]:
        clean, poisoned = truncate(panel, d), truncate(_poison_from(panel, d), d)
        for trigger in G.TRIGGERS:
            sides = {s: G.TRIGGERS[trigger].side for s in clean["symbol"].unique()}
            assert G.GATES[gate](clean, sides, trigger) == G.GATES[gate](poisoned, sides, trigger)


def test_generated_modules_match_the_table_and_import():
    assert gen_g_cells.main(["--check"]) == 0
    for trigger, gate in G.CELLS:
        for suffix in ("", "_not"):
            mod = importlib.import_module(f"strategies.g_{trigger}_{gate}{suffix}")
            assert callable(mod.score) and callable(mod.rules_fired)


def test_rules_fired_names_the_cell_and_never_prints_a_level(panel):
    s = G.cell_score("a01", "g7", True, panel).index[0]
    mod = importlib.import_module("strategies.g_a01_g7")
    text = mod.rules_fired(panel, s)
    assert text.startswith("G_A01_G7: A01 bearish pick") and "A01 weekly reversal" in text
    other = importlib.import_module("strategies.g_a01_g7_not").rules_fired(panel, s)
    assert "abstain" in other


def test_causality_audit_passes():
    result = run_all()
    assert result["passed"], result
