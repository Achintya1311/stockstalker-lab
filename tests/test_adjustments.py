import pandas as pd
import pytest

from scripts.adjustments import compute_adjustment_factors, daily_factor, detect_corporate_actions


def _frame(symbol, dates, closes, prevcloses, opens=None, highs=None, lows=None):
    n = len(dates)
    return pd.DataFrame({
        "date": dates,
        "symbol": [symbol] * n,
        "open": opens or closes,
        "high": highs or closes,
        "low": lows or closes,
        "close": closes,
        "prevclose": prevcloses,
    })


def test_daily_factor_snaps_rounding_noise_to_one():
    prevclose = pd.Series([100.05, 99.97, 100.00])
    prior_close = pd.Series([100.00, 100.00, 100.00])
    out = daily_factor(prevclose, prior_close)
    assert (out == 1.0).all()


def test_daily_factor_keeps_real_ratio():
    prevclose = pd.Series([51.0])
    prior_close = pd.Series([102.0])
    out = daily_factor(prevclose, prior_close)
    assert out.iloc[0] == pytest.approx(0.5)


def test_first_row_per_symbol_is_unadjusted():
    df = _frame("ABC", ["2020-01-01"], [100.0], [float("nan")])
    out = compute_adjustment_factors(df)
    assert out["adj_factor"].iloc[0] == pytest.approx(1.0)
    assert out["adj_close"].iloc[0] == pytest.approx(100.0)


def test_normal_days_have_no_adjustment():
    df = _frame(
        "ABC",
        ["2020-01-01", "2020-01-02", "2020-01-03"],
        [100.0, 102.0, 101.0],
        [float("nan"), 100.0, 102.0],
    )
    out = compute_adjustment_factors(df)
    assert out["adj_factor"].to_list() == pytest.approx([1.0, 1.0, 1.0])
    assert out["adj_close"].to_list() == pytest.approx([100.0, 102.0, 101.0])


def test_two_for_one_split_rescales_history_and_preserves_continuity():
    # d1 normal, d2 normal, d3 a 2:1 split (price roughly halves), d4 normal.
    df = _frame(
        "ABC",
        ["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-04"],
        [100.0, 102.0, 52.0, 53.0],
        [float("nan"), 100.0, 51.0, 52.0],
    )
    out = compute_adjustment_factors(df).set_index("date")

    assert out.loc["2020-01-04", "adj_factor"] == pytest.approx(1.0)
    assert out.loc["2020-01-03", "adj_factor"] == pytest.approx(1.0)
    assert out.loc["2020-01-02", "adj_factor"] == pytest.approx(0.5)
    assert out.loc["2020-01-01", "adj_factor"] == pytest.approx(0.5)

    assert out.loc["2020-01-01", "adj_close"] == pytest.approx(50.0)
    assert out.loc["2020-01-02", "adj_close"] == pytest.approx(51.0)
    assert out.loc["2020-01-03", "adj_close"] == pytest.approx(52.0)
    assert out.loc["2020-01-04", "adj_close"] == pytest.approx(53.0)

    # The point of adjustment: no artificial jump across the split date.
    pre = out.loc["2020-01-02", "adj_close"]
    post = out.loc["2020-01-03", "adj_close"]
    assert abs(post / pre - 1.0) < 0.05


def test_one_for_one_bonus_then_later_normal_day():
    # 1:1 bonus roughly halves price too; then an unrelated later split.
    df = _frame(
        "ABC",
        ["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-04", "2020-01-05"],
        [200.0, 100.0, 101.0, 50.0, 51.0],
        [float("nan"), 100.5, 100.0, 50.5, 50.0],
    )
    out = compute_adjustment_factors(df).set_index("date")

    assert out.loc["2020-01-05", "adj_factor"] == pytest.approx(1.0)
    assert out.loc["2020-01-04", "adj_factor"] == pytest.approx(1.0)
    # The 2020-01-04 action (ratio 50.5/101 = 0.5) applies to every earlier row.
    assert out.loc["2020-01-03", "adj_factor"] == pytest.approx(0.5)
    # The 2020-01-02 action (ratio 100.5/200 = 0.5025 -> ~0.5) compounds with it.
    assert out.loc["2020-01-01", "adj_factor"] == pytest.approx(0.5 * 0.5025, rel=1e-3)


def test_multiple_symbols_are_independent():
    df = pd.concat([
        _frame("ABC", ["2020-01-01", "2020-01-02"], [100.0, 50.0], [float("nan"), 50.5]),
        _frame("XYZ", ["2020-01-01", "2020-01-02"], [100.0, 102.0], [float("nan"), 100.0]),
    ], ignore_index=True)
    out = compute_adjustment_factors(df)

    abc = out[out["symbol"] == "ABC"].set_index("date")
    xyz = out[out["symbol"] == "XYZ"].set_index("date")
    assert abc.loc["2020-01-01", "adj_factor"] == pytest.approx(0.505)
    assert xyz.loc["2020-01-01", "adj_factor"] == pytest.approx(1.0)


def test_open_high_low_scaled_by_same_factor_as_close():
    df = _frame(
        "ABC",
        ["2020-01-01", "2020-01-02"],
        closes=[100.0, 50.0],
        prevcloses=[float("nan"), 50.5],
        opens=[99.0, 49.0],
        highs=[101.0, 51.0],
        lows=[98.0, 48.0],
    )
    out = compute_adjustment_factors(df).set_index("date")
    factor = out.loc["2020-01-01", "adj_factor"]
    assert out.loc["2020-01-01", "adj_open"] == pytest.approx(99.0 * factor)
    assert out.loc["2020-01-01", "adj_high"] == pytest.approx(101.0 * factor)
    assert out.loc["2020-01-01", "adj_low"] == pytest.approx(98.0 * factor)


def test_series_gap_is_not_mistaken_for_a_corporate_action():
    # ABC trades 01-01 and 01-02, is filtered out of the dataset on 01-03
    # (e.g. it spent that day in NSE's BE/trade-to-trade series, which
    # build_dataset.py drops), then is back on 01-04. NSE's own PREVCLOSE
    # on 01-04 is continuous across the gap (it reflects the real 01-03
    # close, 51.0), so it does not equal this dataset's stale prior EQ
    # close (102.0 from 01-02) -- that is a dataset gap, not a split.
    # XYZ trades every day so the market's calendar includes 01-03.
    df = pd.concat([
        _frame("ABC", ["2020-01-01", "2020-01-02", "2020-01-04"],
               [100.0, 102.0, 52.0], [float("nan"), 100.0, 51.0]),
        _frame("XYZ", ["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-04"],
               [10.0, 10.0, 10.0, 10.0], [float("nan"), 10.0, 10.0, 10.0]),
    ], ignore_index=True)

    events = detect_corporate_actions(df)
    assert events[events["symbol"] == "ABC"].empty

    out = compute_adjustment_factors(df)
    abc = out[out["symbol"] == "ABC"].set_index("date")
    assert bool(abc.loc["2020-01-04", "series_gap"]) is True
    assert abc.loc["2020-01-04", "action_ratio"] == pytest.approx(1.0)
    assert abc.loc["2020-01-04", "adj_factor"] == pytest.approx(1.0)
    # Not a gap: no action ratio applied, so adj_close is unscaled.
    assert abc.loc["2020-01-02", "adj_factor"] == pytest.approx(1.0)
    assert abc.loc["2020-01-02", "adj_close"] == pytest.approx(102.0)


def test_consecutive_trading_day_is_not_flagged_as_a_gap():
    df = _frame(
        "ABC",
        ["2020-01-01", "2020-01-02", "2020-01-03"],
        [100.0, 102.0, 101.0],
        [float("nan"), 100.0, 102.0],
    )
    out = compute_adjustment_factors(df)
    assert not out["series_gap"].any()


def test_detect_corporate_actions_finds_only_the_real_event():
    df = pd.concat([
        _frame(
            "ABC",
            ["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-04"],
            [100.0, 102.0, 52.0, 53.0],
            [float("nan"), 100.0, 51.0, 52.0],
        ),
        _frame("XYZ", ["2020-01-01", "2020-01-02"], [100.0, 102.0], [float("nan"), 100.0]),
    ], ignore_index=True)
    events = detect_corporate_actions(df)
    assert len(events) == 1
    row = events.iloc[0]
    assert row["symbol"] == "ABC"
    assert row["date"] == "2020-01-03"
    assert row["action_ratio"] == pytest.approx(0.5)
