import numpy as np
import pandas as pd

from picks.chart import BARS, chart_for, swing_levels
from tests.test_o01_order_block import _bull_setup, _flat, _history


def test_chart_is_scaled_to_0_100_with_a_demand_zone_and_no_raw_prices():
    h = _history(_bull_setup([(105.0, 104.0), (104.0, 101.0)]))
    c = chart_for(h, "AAA")
    flat = np.array(c["bars"]).ravel()
    assert len(c["bars"]) == BARS and flat.min() >= 0 and flat.max() <= 100
    z = c["zone"]
    assert z["side"] == "demand" and 0 <= z["low"] < z["high"] <= 100


def test_short_history_has_no_chart_and_flat_history_no_zone():
    assert chart_for(_history(_flat(30)), "AAA") is None
    assert "zone" not in chart_for(_history(_flat(70)), "AAA")


def _bars(closes):
    return [[c, c + 1.0, c - 1.0, c] for c in closes]


def test_swing_levels_are_the_nearest_highs_above_and_lows_below_the_last_close():
    closes = [50, 52, 55, 60, 70, 60, 55, 52, 48, 40, 30, 40, 48, 52, 55, 80, 55, 52, 50, 50, 50, 50]
    lv = swing_levels(_bars(closes))
    res, sup = [x for x in lv if x["k"] == "r"], [x for x in lv if x["k"] == "s"]
    assert [(x["at"], x["from"]) for x in res] == [(71.0, 4), (81.0, 15)]   # nearest first
    assert [(x["at"], x["from"]) for x in sup] == [(29.0, 10)]
    assert all(set(x) == {"k", "at", "from"} for x in lv)


def test_swing_levels_merge_close_swings_and_cap_each_side():
    closes = [50, 50, 50, 50, 60, 70, 60, 50, 60, 71, 60, 50, 60, 80, 60, 50, 60, 90, 60, 50, 50, 50, 50]
    res = [x["at"] for x in swing_levels(_bars(closes)) if x["k"] == "r"]
    assert res == [71.0, 81.0]   # 72 merges into 71, 91 is beyond the cap of two


def test_flat_bars_have_no_levels_and_chart_levels_stay_inside_the_scale():
    assert swing_levels(_bars([50] * 20)) == []
    c = chart_for(_history(_bull_setup([(105.0, 104.0), (104.0, 101.0)])), "AAA")
    assert all(0 <= x["at"] <= 100 and 0 <= x["from"] < BARS for x in c.get("levels", []))
