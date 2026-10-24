import numpy as np
import pandas as pd

from strategies import o05_order_block_weekly, ob_core


def _bars(spec):
    """spec: list of (open, close); high/low = body +/- 0.2."""
    o = np.array([s[0] for s in spec], float)
    c = np.array([s[1] for s in spec], float)
    return o, np.maximum(o, c) + 0.2, np.minimum(o, c) - 0.2, c


def _flat(n, px=100.0):
    return [(px, px + (0.1 if i % 2 else -0.1)) for i in range(n)]


def _weekly_dates(n):
    # One trading day per ISO week (7 calendar days apart, starting on a Monday), so each
    # row lands in its own week and that week's bar equals this single day's own OHLC - lets
    # the zone-detection tests below reuse test_o01_order_block's exact daily fixtures and
    # assertions unchanged, just re-labelled at week granularity.
    return pd.date_range("2020-01-06", periods=n, freq="7D").strftime("%Y-%m-%d")


def _history(spec, symbol="AAA"):
    o, h, l, c = _bars(spec)
    dates = _weekly_dates(len(spec))
    prev = np.concatenate(([c[0]], c[:-1]))
    return pd.DataFrame({"date": dates, "symbol": symbol, "open": o, "high": h, "low": l, "close": c, "prevclose": prev, "volume": 1e6, "has_future": True})


def _bull_setup_weekly(tail):
    # mirrors test_o01_order_block._bull_setup but at week granularity: 60 flat weeks, one
    # down week (the zone, 99.0-101.0 body), an impulsive up week that breaks the range, then `tail`.
    return _flat(60) + [(101.0, 99.0), (99.0, 105.0)] + tail


def test_resample_weekly_aggregates_open_high_low_close_within_the_iso_week():
    # Two real 3-day ISO weeks (Mon 6 Jan - Wed 8 Jan 2020, then Mon 13 - Wed 15 Jan 2020):
    # open = the week's first bar's open, high/low = the week's extremes, close = the week's last close.
    dates = ["2020-01-06", "2020-01-07", "2020-01-08", "2020-01-13", "2020-01-14", "2020-01-15"]
    o = np.array([100.0, 101.0, 99.0, 105.0, 107.0, 104.0])
    h = np.array([102.0, 103.0, 100.0, 108.0, 109.0, 106.0])
    l = np.array([99.0, 100.0, 97.0, 104.0, 106.0, 103.0])
    c = np.array([101.0, 99.5, 98.0, 106.0, 105.0, 104.5])
    wo, wh, wl, wc = ob_core.resample_weekly(dates, o, h, l, c)
    assert list(wo) == [100.0, 105.0]
    assert list(wh) == [103.0, 109.0]
    assert list(wl) == [97.0, 103.0]
    assert list(wc) == [98.0, 104.5]


def test_resample_weekly_keeps_a_partial_final_week_as_its_own_bar():
    # The last ISO week here has only one visible day (no future day completes it) - it must
    # still form a usable bar from just what's there, the same way the latest daily bar always is.
    dates = ["2020-01-06", "2020-01-07", "2020-01-13"]
    o = np.array([100.0, 101.0, 105.0])
    h = np.array([102.0, 103.0, 106.0])
    l = np.array([99.0, 100.0, 104.0])
    c = np.array([101.0, 99.5, 105.5])
    wo, wh, wl, wc = ob_core.resample_weekly(dates, o, h, l, c)
    assert len(wo) == 2
    assert (wo[1], wh[1], wl[1], wc[1]) == (105.0, 106.0, 104.0, 105.5)


def test_detects_bullish_zone_on_weekly_bars():
    h = _history(_bull_setup_weekly([(105.0, 105.5)] * 3))
    o, hi, lo, c = ob_core.resample_weekly(h["date"], h["open"].to_numpy(float), h["high"].to_numpy(float), h["low"].to_numpy(float), h["close"].to_numpy(float))
    z = ob_core.detect(o, hi, lo, c)
    assert z["side"] == 1 and z["bars_ago"] == 3
    assert (z["zone_low"], z["zone_high"]) == (98.8, 101.2)


def test_retest_scores_bullish_and_far_price_abstains():
    near = _history(_bull_setup_weekly([(105.0, 104.0), (104.0, 101.0)]))  # back inside/near the zone
    far = _history(_bull_setup_weekly([(105.0, 106.0)] * 3))               # drifted away
    assert o05_order_block_weekly.score(near).iloc[0] > 0.5
    assert o05_order_block_weekly.score(far).empty


def test_close_through_the_zone_mitigates_it():
    broken = _history(_bull_setup_weekly([(105.0, 98.0), (98.0, 99.0)]))
    assert (o05_order_block_weekly.score(broken) >= 0).sum() == 0


def test_bearish_mirror_scores_negative():
    spec = _flat(60) + [(99.0, 101.0), (101.0, 95.0), (95.0, 96.0), (96.0, 99.0)]
    s = o05_order_block_weekly.score(_history(spec))
    assert len(s) == 1 and s.iloc[0] < 0


def test_too_few_daily_rows_abstains():
    spec = _bull_setup_weekly([(105.0, 104.0), (104.0, 101.0)])[-50:]  # under MIN_ROWS daily rows
    assert o05_order_block_weekly.score(_history(spec)).empty


def test_too_few_weekly_bars_abstains_even_with_plenty_of_daily_rows():
    # 5 real trading days per week: 70 daily rows (clears MIN_ROWS=60) but only 14 weekly
    # bars (under MIN_WEEKS=60) - must abstain on the weekly-bar count, not the daily one.
    dates = pd.bdate_range("2020-01-06", periods=70).strftime("%Y-%m-%d")
    spec = _flat(66) + [(101.0, 99.0), (99.0, 105.0)] + [(105.0, 104.0), (104.0, 101.0)]
    o, h, l, c = _bars(spec)
    prev = np.concatenate(([c[0]], c[:-1]))
    hist = pd.DataFrame({"date": dates, "symbol": "AAA", "open": o, "high": h, "low": l, "close": c, "prevclose": prev, "volume": 1e6, "has_future": True})
    assert o05_order_block_weekly.score(hist).empty


def test_symbols_do_not_leak_into_each_other():
    a = _history(_bull_setup_weekly([(105.0, 104.0), (104.0, 101.0)]), "AAA")
    b = _history(_flat(70), "BBB")
    both = o05_order_block_weekly.score(pd.concat([a, b], ignore_index=True))
    assert both["AAA"] == o05_order_block_weekly.score(a)["AAA"] and "BBB" not in both


def test_rules_fired_wording():
    h = _history(_bull_setup_weekly([(105.0, 104.0), (104.0, 101.0)]))
    text = o05_order_block_weekly.rules_fired(h, "AAA")
    assert text.startswith("O05: bullish weekly order block")
    assert o05_order_block_weekly.rules_fired(_history(_flat(70)), "AAA") == "O05: no valid weekly zone at price, abstain"


def test_causality_audit_passes():
    from strategies.o05_order_block_weekly_audit import check_cross_symbol_causality

    assert check_cross_symbol_causality()["passed"]
