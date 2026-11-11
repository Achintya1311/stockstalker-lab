import numpy as np
import pandas as pd

from picks.tech import rsi_band, tech_for, wilder_rsi
from tests.test_o01_order_block import _bull_setup, _flat, _history


def _trend(n, step, vol=1e6, last_vol=None):
    c = 100.0 + step * np.arange(n)
    dates = pd.bdate_range("2019-01-01", periods=n).strftime("%Y-%m-%d")
    prev = np.concatenate(([c[0]], c[:-1]))
    v = np.full(n, vol)
    if last_vol is not None:
        v[-1] = last_vol
    return pd.DataFrame({"date": dates, "symbol": "AAA", "open": prev, "high": np.maximum(prev, c) + 0.5,
                         "low": np.minimum(prev, c) - 0.5, "close": c, "prevclose": prev, "volume": v})


def test_rising_series_is_above_both_averages_overbought_at_range_top_with_volume_multiple():
    t = tech_for(_trend(220, 0.5, last_vol=3e6), "AAA")
    assert t["trend50"] == t["trend200"] == "above"
    assert t["rsi14"] == 100.0 and t["rsi_band"] == "overbought"
    assert t["vol_x20"] == 3.0
    assert 90 <= t["range20"] <= 100


def test_falling_series_reads_below_and_oversold_near_range_bottom():
    t = tech_for(_trend(220, -0.2), "AAA")
    assert t["trend50"] == t["trend200"] == "below" and t["rsi_band"] == "oversold"
    assert t["range20"] <= 10 and t["vol_x20"] == 1.0


def test_short_history_drops_long_fields_and_too_short_gives_none():
    assert tech_for(_trend(15, 0.5), "AAA") is None
    t = tech_for(_trend(60, 0.5), "AAA")
    assert "trend200" not in t and t["trend50"] == "above"


def test_order_block_distance_is_zero_inside_the_zone_and_carries_its_side():
    t = tech_for(_history(_bull_setup([(105.0, 104.0), (104.0, 101.0)])), "AAA")
    assert t["ob_side"] == "demand" and t["ob_dist"] == 0.0
    far = tech_for(_history(_bull_setup([(105.0, 106.0)] * 3)), "AAA")
    assert far["ob_side"] == "demand" and far["ob_dist"] > 0
    assert "ob_side" not in tech_for(_history(_flat(70)), "AAA")


def test_no_raw_price_leaks_and_bands_cover_the_scale():
    t = tech_for(_trend(220, 0.5), "AAA")
    assert set(t) <= {"trend50", "trend200", "rsi14", "rsi_band", "vol_x20", "range20", "ob_dist", "ob_side"}
    assert [rsi_band(v) for v in (10, 40, 50, 60, 80)] == ["oversold", "weak", "neutral", "firm", "overbought"]
    assert wilder_rsi(np.array([1.0, 2.0])) is None
