import numpy as np
import pandas as pd
import pytest

from strategies import f19_body_volatility_fade as f19
from strategies.f13_accel_range_top_audit import walk, with_turnover
from strategies.f19_body_volatility_fade_audit import check_cross_symbol_causality, jumper
from strategies.t17_keltner_breakout_audit import frame

N = f19.MIN_ROWS + 5


def bars(symbol, opens, closes):
    dates = pd.bdate_range("2016-01-01", periods=len(closes)).strftime("%Y-%m-%d")
    prev = np.r_[closes[0], closes[:-1]]
    rows = [{"date": d, "symbol": symbol, "open": o, "high": max(o, c) * 1.01, "low": min(o, c) * 0.99,
             "close": c, "prevclose": p, "volume": 1e6, "turnover": 1e9}
            for d, o, c, p in zip(dates, opens, closes, prev)]
    return pd.DataFrame(rows)


def test_hand_computed_raw_value():
    closes = np.array([100, 101, 102, 101, 103, 104, 103, 105, 106, 108], float)
    opens = closes - np.array([1, -1, 2, -2, 1, 1, -1, 2, 1, 2], float)
    raw = f19.raw_values(bars("A", opens, closes))
    body = 100 * (closes - opens) / closes
    expected = np.abs(body[-5:]).std(ddof=1) + body[-1] + np.corrcoef(closes, opens)[0, 1]
    assert raw["A"] == pytest.approx(expected)


def test_large_up_body_is_bearish_and_large_down_body_bullish():
    others = [walk(f"S{i}", N, 80 + i) for i in range(5)]
    up = jumper(N, 0.08, "UP")
    down = jumper(N, -0.08, "DOWN")
    sc = f19.score(pd.concat(others + [up, down], ignore_index=True))
    assert sc["UP"] < 0 and sc["DOWN"] > 0
    assert sc["UP"] == sc.min() and sc["DOWN"] == sc.max()


def test_scores_are_median_centred_ranks():
    others = [walk(f"S{i}", N, 90 + i) for i in range(7)]
    sc = f19.score(pd.concat(others, ignore_index=True))
    assert len(sc) == 6  # 7 stocks, the median one is exactly zero and abstains
    assert sc.max() == pytest.approx(-sc.min())


def test_short_history_abstains():
    h = pd.concat([walk(f"S{i}", f19.MIN_ROWS - 1, i) for i in range(4)], ignore_index=True)
    assert f19.score(h).empty


def test_flat_prices_abstain():
    flat = bars("FLAT", np.full(N, 100.0), np.full(N, 100.0))
    h = pd.concat([flat] + [walk(f"S{i}", N, i).assign(date=flat["date"]) for i in range(3)], ignore_index=True)
    assert "FLAT" not in f19.raw_values(h).index


def test_symbol_without_a_future_on_the_last_date_drops_out():
    h = pd.concat([walk(f"S{i}", N, 20 + i) for i in range(4)], ignore_index=True)
    last = h["date"].max()
    h.loc[(h["symbol"] == "S0") & (h["date"] == last), "has_future"] = False
    assert "S0" not in f19.score(h).index


def test_empty_history():
    assert f19.score(pd.DataFrame()).empty


def test_rules_fired_wording():
    h = pd.concat([walk(f"S{i}", N, 40 + i) for i in range(4)] + [jumper(N, 0.08)], ignore_index=True)
    text = f19.rules_fired(h, "BBB")
    assert "bearish" in text and "Alpha#18" in text
    assert "abstain" in f19.rules_fired(h, "MISSING")
    for word in ("buy", "sell", "target", "stop", "entry"):
        assert word not in text.lower()


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result
