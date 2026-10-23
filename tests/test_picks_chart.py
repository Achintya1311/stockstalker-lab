import numpy as np
import pandas as pd

from picks.chart import BARS, chart_for
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
