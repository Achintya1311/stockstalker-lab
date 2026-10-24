import pandas as pd

from strategies import o02_order_block_oi_confirmed as o02
from tests.test_o01_order_block import _bull_setup, _flat, _history

# O01 fires bullish (+1.0) for both; RETEST_UP's own last session also rises (agrees with a build-up
# reading), DISAGREE_RETEST's last session falls (can never agree, whatever the OI sign).
RETEST_UP = [(105.0, 100.5), (100.5, 101.0)]
DISAGREE_RETEST = [(105.0, 104.0), (104.0, 101.0)]

# O01 fires bearish (-1.0); last session also falls, agreeing with a short build-up reading.
BEARISH_DOWN = _flat(60) + [(99.0, 101.0), (101.0, 95.0), (95.0, 99.5), (99.5, 99.0)]


def _with_oi(spec, symbol="AAA", oi_chg: float = 500.0, oi_level: float = 10_000.0) -> pd.DataFrame:
    history = _history(spec, symbol)
    history["oi_futstk"] = oi_level
    history["oi_chg_futstk"] = oi_chg
    return history


def test_bullish_zone_kept_when_last_session_is_a_long_build_up():
    h = _with_oi(_bull_setup(RETEST_UP), oi_chg=500.0)  # price up, OI up: long build-up, agrees with bullish side
    s = o02.score(h)
    assert len(s) == 1 and s.iloc[0] > 0


def test_bullish_zone_abstains_on_short_covering_even_though_price_also_rose():
    # last session: price up (short covering, D01 weight 0.5) but OI itself fell - not a build-up.
    h = _with_oi(_bull_setup(RETEST_UP), oi_chg=-300.0)
    assert o02.score(h).empty


def test_bearish_zone_kept_when_last_session_is_a_short_build_up():
    # last session: price down with OI up: price down + OI up = short build-up, agrees with bearish side.
    h = _with_oi(BEARISH_DOWN, oi_chg=500.0)
    s = o02.score(h)
    assert len(s) == 1 and s.iloc[0] < 0


def test_abstains_when_build_up_disagrees_with_o01_side():
    # bullish O01 zone, but the last session's own price fell: D01's direction is forced bearish
    # (short build-up) no matter the OI sign, so it can never agree with O01's bullish side.
    h = _with_oi(_bull_setup(DISAGREE_RETEST), oi_chg=500.0)
    assert o02.score(h).empty


def test_abstains_when_o01_itself_abstains():
    h = _with_oi(_flat(70), oi_chg=500.0)  # no order block at all
    assert o02.score(h).empty


def test_abstains_when_future_data_missing_for_oi():
    h = _with_oi(_bull_setup(RETEST_UP), oi_chg=500.0)
    h["has_future"] = False
    assert o02.score(h).empty


def test_symbols_do_not_leak_into_each_other():
    a = _with_oi(_bull_setup(RETEST_UP), "AAA", oi_chg=500.0)
    b = _with_oi(_flat(70), "BBB", oi_chg=500.0)
    both = o02.score(pd.concat([a, b], ignore_index=True))
    assert "AAA" in both and "BBB" not in both
    assert both["AAA"] == o02.score(a)["AAA"]


def test_rules_fired_wording():
    h = _with_oi(_bull_setup(RETEST_UP), oi_chg=500.0)
    assert "confirmed by D01 build-up" in o02.rules_fired(h, "AAA")

    abstained = _with_oi(_bull_setup(RETEST_UP), oi_chg=-300.0)
    assert "abstain" in o02.rules_fired(abstained, "AAA")

    no_zone = _with_oi(_flat(70), oi_chg=500.0)
    assert "no valid zone" in o02.rules_fired(no_zone, "AAA")


def test_causality_audit_passes():
    from strategies.o02_order_block_oi_confirmed_audit import check_cross_symbol_causality

    assert check_cross_symbol_causality()["passed"]
