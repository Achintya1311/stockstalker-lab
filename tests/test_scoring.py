import numpy as np
import pandas as pd
import pytest

from engine.scoring import (
    DELIVERY_COST,
    FUTURES_COST,
    day_moves,
    directional_move_after_costs,
    edge,
    hit,
    market_line,
    moves_for_horizon,
    random_baseline_percentile,
    universe_membership,
    week_moves,
)


# ---- hit ----------------------------------------------------------------

def test_hit_bullish_on_a_rise():
    assert hit(pd.Series([0.02]), 1).iloc[0] is np.True_ or hit(pd.Series([0.02]), 1).iloc[0] == True  # noqa: E712


def test_hit_bullish_on_a_fall_is_a_miss():
    assert bool(hit(pd.Series([-0.01]), 1).iloc[0]) is False


def test_hit_flat_is_always_a_miss_whichever_side():
    assert bool(hit(pd.Series([0.0]), 1).iloc[0]) is False
    assert bool(hit(pd.Series([0.0]), -1).iloc[0]) is False


def test_hit_bearish_on_a_fall():
    assert bool(hit(pd.Series([-0.02]), -1).iloc[0]) is True


def test_hit_bearish_on_a_rise_is_a_miss():
    assert bool(hit(pd.Series([0.02]), -1).iloc[0]) is False


# ---- day_moves / week_moves ----------------------------------------------

def test_day_moves_is_close_over_open_minus_one():
    dataset = pd.DataFrame({
        "date": ["2015-01-02", "2015-01-02"],
        "symbol": ["AAA", "BBB"],
        "open": [100.0, 50.0],
        "close": [102.0, 49.0],
    })
    out = day_moves(dataset).set_index("symbol")["move"]
    assert out["AAA"] == pytest.approx(0.02)
    assert out["BBB"] == pytest.approx(-0.02)


def test_week_moves_spans_mondays_open_to_fridays_close():
    # 2015-01-05 (Mon) .. 2015-01-09 (Fri) is one ISO week.
    dataset = pd.DataFrame({
        "date": ["2015-01-05", "2015-01-06", "2015-01-07", "2015-01-08", "2015-01-09"],
        "symbol": ["AAA"] * 5,
        "open": [100.0, 101.0, 103.0, 104.0, 105.0],
        "close": [101.0, 103.0, 104.0, 105.0, 110.0],
    })
    out = week_moves(dataset)
    assert len(out) == 1
    row = out.iloc[0]
    assert row["date"] == "2015-01-05"
    assert row["move"] == pytest.approx(110.0 / 100.0 - 1.0)


def test_moves_for_horizon_rejects_unknown_horizon():
    with pytest.raises(ValueError):
        moves_for_horizon(pd.DataFrame({"date": [], "symbol": [], "open": [], "close": []}), "month")


# ---- universe_membership ---------------------------------------------------

def test_universe_membership_requires_both_future_and_liquidity_floor():
    dates = [f"2015-01-{d:02d}" for d in range(1, 21)]  # 20 trading dates
    rows = []
    for d in dates:
        rows.append({"date": d, "symbol": "RICH_NO_FUTURE", "has_future": False, "turnover": 1e9})
        rows.append({"date": d, "symbol": "RICH_WITH_FUTURE", "has_future": True, "turnover": 1e9})
        rows.append({"date": d, "symbol": "POOR_WITH_FUTURE", "has_future": True, "turnover": 1e3})
    dataset = pd.DataFrame(rows)
    out = universe_membership(dataset, min_median_turnover_20d_cr=25.0)
    last_day = out[out["date"] == dates[-1]].set_index("symbol")["in_universe"]
    assert last_day["RICH_WITH_FUTURE"] is True or bool(last_day["RICH_WITH_FUTURE"]) is True
    assert bool(last_day["RICH_NO_FUTURE"]) is False  # no active future, however liquid
    assert bool(last_day["POOR_WITH_FUTURE"]) is False  # below the turnover floor


def test_universe_membership_needs_a_full_20_day_window():
    # Only 5 days of history: the rolling 20-day median can't be computed yet (min_periods=20).
    dates = [f"2015-01-{d:02d}" for d in range(1, 6)]
    rows = [{"date": d, "symbol": "AAA", "has_future": True, "turnover": 1e9} for d in dates]
    dataset = pd.DataFrame(rows)
    out = universe_membership(dataset, min_median_turnover_20d_cr=25.0)
    assert not out["in_universe"].any()


# ---- market_line ------------------------------------------------------------

def test_market_line_hand_computed():
    # One date, 4 symbols in the universe: 3 rise, 1 falls -> bullish market line 0.75, bearish 0.25.
    moves = pd.DataFrame({
        "date": ["2015-01-02"] * 4,
        "symbol": ["A", "B", "C", "D"],
        "move": [0.01, 0.02, 0.03, -0.01],
    })
    universe = pd.DataFrame({
        "date": ["2015-01-02"] * 4,
        "symbol": ["A", "B", "C", "D"],
        "in_universe": [True, True, True, True],
    })
    bullish = market_line(moves, universe, 1)
    bearish = market_line(moves, universe, -1)
    assert bullish["2015-01-02"] == pytest.approx(0.75)
    assert bearish["2015-01-02"] == pytest.approx(0.25)


def test_market_line_excludes_symbols_outside_the_universe():
    moves = pd.DataFrame({
        "date": ["2015-01-02"] * 2,
        "symbol": ["IN", "OUT"],
        "move": [0.01, -0.5],  # OUT would drag the line down hard if counted
    })
    universe = pd.DataFrame({
        "date": ["2015-01-02"] * 2,
        "symbol": ["IN", "OUT"],
        "in_universe": [True, False],
    })
    bullish = market_line(moves, universe, 1)
    assert bullish["2015-01-02"] == pytest.approx(1.0)


# ---- edge ------------------------------------------------------------------

def test_edge_hand_computed():
    # Two dates. Strategy picks (bullish, side=+1) hit 2/2 on day1 and 0/2 on day2 -> hit rate 0.5 per date averaged = (1.0 + 0.0)/2 = 0.5.
    # Market line (bullish) is 0.5 both days. Edge = mean(1.0-0.5, 0.0-0.5) = mean(0.5, -0.5) = 0.0.
    moves = pd.DataFrame({
        "date": ["d1", "d1", "d1", "d1", "d2", "d2", "d2", "d2"],
        "symbol": ["A", "B", "C", "D"] * 2,
        "move": [0.01, 0.01, -0.01, -0.01, 0.01, 0.01, -0.01, -0.01],
    })
    universe = pd.DataFrame({
        "date": moves["date"],
        "symbol": moves["symbol"],
        "in_universe": True,
    })
    picks = pd.DataFrame({
        "date": ["d1", "d1", "d2", "d2"],
        "symbol": ["A", "B", "C", "D"],
        "side": [1, 1, 1, 1],
    })
    assert edge(picks, moves, universe) == pytest.approx(0.0)


def test_edge_rejects_mixed_sides():
    moves = pd.DataFrame({"date": ["d1"], "symbol": ["A"], "move": [0.01]})
    universe = pd.DataFrame({"date": ["d1"], "symbol": ["A"], "in_universe": [True]})
    picks = pd.DataFrame({"date": ["d1", "d1"], "symbol": ["A", "A"], "side": [1, -1]})
    with pytest.raises(ValueError):
        edge(picks, moves, universe)


# ---- directional_move_after_costs ------------------------------------------

def test_directional_move_after_costs_hand_computed():
    picks = pd.DataFrame({
        "date": ["d1", "d1"],
        "symbol": ["BULL", "BEAR"],
        "side": [1, -1],
    })
    moves = pd.DataFrame({
        "date": ["d1", "d1"],
        "symbol": ["BULL", "BEAR"],
        "move": [0.01, -0.01],
    })
    # BULL: move*side = 0.01, delivery cost subtracted. BEAR: move*side = 0.01, futures cost subtracted.
    expected = ((0.01 - DELIVERY_COST) + (0.01 - FUTURES_COST)) / 2
    assert directional_move_after_costs(picks, moves) == pytest.approx(expected)


def test_delivery_cost_is_more_expensive_than_futures_cost():
    # Delivery pays two-sided STT + stamp duty; futures pays sell-leg STT only.
    assert DELIVERY_COST > FUTURES_COST


def test_directional_move_after_costs_raises_on_no_overlap():
    picks = pd.DataFrame({"date": ["d1"], "symbol": ["A"], "side": [1]})
    moves = pd.DataFrame({"date": ["d2"], "symbol": ["A"], "move": [0.01]})
    with pytest.raises(ValueError):
        directional_move_after_costs(picks, moves)


# ---- random_baseline_percentile --------------------------------------------

def test_random_baseline_percentile_hand_computed_when_picks_cover_the_whole_universe():
    # If the pick count on a date equals the universe size, every random draw
    # without replacement is forced to select the entire universe too - so
    # when the real picks ARE the whole universe, every random list has
    # exactly the same hit rate as the real one. The real rate can then never
    # be strictly greater than a random one: percentile is exactly 0.0.
    moves = pd.DataFrame({
        "date": ["d1"] * 4,
        "symbol": ["A", "B", "C", "D"],
        "move": [0.01, 0.02, -0.01, 0.03],
    })
    universe = pd.DataFrame({
        "date": ["d1"] * 4,
        "symbol": ["A", "B", "C", "D"],
        "in_universe": [True, True, True, True],
    })
    picks = pd.DataFrame({
        "date": ["d1"] * 4,
        "symbol": ["A", "B", "C", "D"],
        "side": [1, 1, 1, 1],
    })
    pct = random_baseline_percentile(picks, moves, universe, n_random=200, rng=np.random.default_rng(0))
    assert pct == pytest.approx(0.0)


def test_random_baseline_percentile_is_high_for_a_strategy_that_always_hits_a_small_universe():
    # 1 pick/date from a 10-symbol universe where only 1 symbol ever rises;
    # the strategy always picks that one symbol. Random single draws hit it
    # only ~1/10 of the time, so the real hit rate (1.0) should beat almost
    # all 1,000 random lists.
    dates = [f"d{i}" for i in range(20)]
    rows_moves, rows_universe, rows_picks = [], [], []
    symbols = [f"S{j}" for j in range(10)]
    for d in dates:
        for j, sym in enumerate(symbols):
            move = 0.05 if j == 0 else -0.01
            rows_moves.append({"date": d, "symbol": sym, "move": move})
            rows_universe.append({"date": d, "symbol": sym, "in_universe": True})
        rows_picks.append({"date": d, "symbol": "S0", "side": 1})
    moves = pd.DataFrame(rows_moves)
    universe = pd.DataFrame(rows_universe)
    picks = pd.DataFrame(rows_picks)
    pct = random_baseline_percentile(picks, moves, universe, n_random=1000, rng=np.random.default_rng(42))
    assert pct > 0.8
