import numpy as np
import pandas as pd

from strategies import o00_order_block_placebo, o01_order_block_retest, ob_core


def _bars(spec):
    """spec: list of (open, close); high/low = body +/- 0.2."""
    o = np.array([s[0] for s in spec], float)
    c = np.array([s[1] for s in spec], float)
    return o, np.maximum(o, c) + 0.2, np.minimum(o, c) - 0.2, c


def _flat(n, px=100.0):
    return [(px, px + (0.1 if i % 2 else -0.1)) for i in range(n)]


def _history(spec, symbol="AAA"):
    o, h, l, c = _bars(spec)
    dates = pd.bdate_range("2020-01-01", periods=len(spec)).strftime("%Y-%m-%d")
    prev = np.concatenate(([c[0]], c[:-1]))
    return pd.DataFrame({"date": dates, "symbol": symbol, "open": o, "high": h, "low": l, "close": c, "prevclose": prev, "volume": 1e6, "has_future": True})


def _bull_setup(tail):
    # 40 flat bars, one down candle (the zone, 99.0-101.0 body), then a +6 impulse that breaks the range, then `tail`
    return _flat(60) + [(101.0, 99.0), (99.0, 105.0)] + tail


def test_detects_bullish_zone_as_the_last_down_candle_before_the_impulse():
    o, h, l, c = _bars(_bull_setup([(105.0, 105.5)] * 3))
    z = ob_core.detect(o, h, l, c)
    assert z["side"] == 1 and z["bars_ago"] == 3
    assert (z["zone_low"], z["zone_high"]) == (98.8, 101.2)


def test_retest_scores_bullish_and_far_price_abstains():
    near = _history(_bull_setup([(105.0, 104.0), (104.0, 101.0)]))      # back inside/near the zone
    far = _history(_bull_setup([(105.0, 106.0)] * 3))                    # drifted away
    assert o01_order_block_retest.score(near).iloc[0] > 0.5
    assert o01_order_block_retest.score(far).empty


def test_close_through_the_zone_mitigates_it():
    # the drop closes below the zone (98.8): the demand block is dead. The drop is itself a new bearish impulse.
    broken = _history(_bull_setup([(105.0, 98.0), (98.0, 99.0)]))
    assert (o01_order_block_retest.score(broken) >= 0).sum() == 0


def test_bearish_mirror_scores_negative():
    spec = _flat(60) + [(99.0, 101.0), (101.0, 95.0), (95.0, 96.0), (96.0, 99.0)]
    s = o01_order_block_retest.score(_history(spec))
    assert len(s) == 1 and s.iloc[0] < 0


def test_placebo_fires_without_an_impulse_where_o01_does_not():
    spec = _flat(60) + [(100.0, 100.4), (100.4, 100.1)]  # small drift, no impulse
    h = _history(spec)
    assert o01_order_block_retest.score(h).empty
    assert not o00_order_block_placebo.score(h).empty


def test_symbols_do_not_leak_into_each_other():
    a, b = _history(_bull_setup([(105.0, 104.0), (104.0, 101.0)]), "AAA"), _history(_flat(70), "BBB")
    both = o01_order_block_retest.score(pd.concat([a, b], ignore_index=True))
    assert both["AAA"] == o01_order_block_retest.score(a)["AAA"] and "BBB" not in both
