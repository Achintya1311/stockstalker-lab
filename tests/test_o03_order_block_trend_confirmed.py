import numpy as np
import pandas as pd

from strategies import o03_order_block_trend_confirmed as o03
from tests.test_o01_order_block import _flat, _history


def _linear_bg(start: float, end: float, n: int = 60) -> list[tuple[float, float]]:
    closes = np.linspace(start, end, n)
    opens = np.concatenate(([start + (start - closes[0])], closes[:-1]))
    return list(zip(opens.tolist(), closes.tolist()))


# Backgrounds long and gentle enough to move T01's SMA(20,50) spread without tripping ob_core's own
# impulse detector (each bar's body is far below 1.5 ATR) or ageing out of O01's MIN_ROWS=60 tail window.
_UP_BG = _linear_bg(85.0, 99.8)
_DOWN_BG = _linear_bg(115.0, 100.2)

_BULL_ZONE = [(101.0, 99.0), (99.0, 105.0)]
_RETEST_UP = [(105.0, 100.5), (100.5, 101.0)]
_BEARISH_ZONE_AND_TAIL = [(99.0, 101.0), (101.0, 95.0), (95.0, 99.5), (99.5, 99.0)]


def test_bullish_zone_kept_when_trend_also_agrees():
    h = _history(_UP_BG + _BULL_ZONE + _RETEST_UP, "AAA")
    s = o03.score(h)
    assert len(s) == 1 and s.iloc[0] > 0


def test_bullish_zone_abstains_when_trend_disagrees():
    h = _history(_DOWN_BG + _BULL_ZONE + _RETEST_UP, "AAA")
    assert o03.score(h).empty


def test_bearish_zone_kept_when_trend_also_agrees():
    h = _history(_DOWN_BG + _BEARISH_ZONE_AND_TAIL, "AAA")
    s = o03.score(h)
    assert len(s) == 1 and s.iloc[0] < 0


def test_bearish_zone_abstains_when_trend_disagrees():
    h = _history(_UP_BG + _BEARISH_ZONE_AND_TAIL, "AAA")
    assert o03.score(h).empty


def test_abstains_when_o01_itself_abstains():
    h = _history(_UP_BG + _flat(4), "AAA")  # no order block at all
    assert o03.score(h).empty


def test_symbols_do_not_leak_into_each_other():
    a = _history(_UP_BG + _BULL_ZONE + _RETEST_UP, "AAA")
    b = _history(_UP_BG + _flat(4), "BBB")
    both = o03.score(pd.concat([a, b], ignore_index=True))
    assert "AAA" in both and "BBB" not in both
    assert both["AAA"] == o03.score(a)["AAA"]


def test_rules_fired_wording():
    agree = _history(_UP_BG + _BULL_ZONE + _RETEST_UP, "AAA")
    assert "confirmed by T01 trend" in o03.rules_fired(agree, "AAA")

    disagree = _history(_DOWN_BG + _BULL_ZONE + _RETEST_UP, "AAA")
    assert "trend disagrees" in o03.rules_fired(disagree, "AAA")

    no_zone = _history(_UP_BG + _flat(4), "AAA")
    assert "no valid zone" in o03.rules_fired(no_zone, "AAA")


def test_causality_audit_passes():
    from strategies.o03_order_block_trend_confirmed_audit import check_cross_symbol_causality

    assert check_cross_symbol_causality()["passed"]
