import numpy as np
import pandas as pd

from strategies import f16_position_turnover_corr as f16
from strategies.f13_accel_range_top_audit import walk
from strategies.f16_position_turnover_corr_audit import check_cross_symbol_causality

N = f16.MIN_ROWS + 3
UP = [1 / 3, 2 / 3, 1.0, 1 / 3, 2 / 3, 1.0]


def panels(rk: dict, rt: dict):
    idx = pd.Index([f"d{i}" for i in range(6)], name="date")
    return pd.DataFrame(rk, index=idx), pd.DataFrame(rt, index=idx)


def hist() -> pd.DataFrame:
    return pd.concat([walk(s, N, i) for i, s in enumerate("ABCD")], ignore_index=True)


def test_hand_computed_scores(monkeypatch):
    """A: turnover rank moves with range position (corr +1) -> -1 bearish.
    B: against it (corr -1) -> +1 bullish. C: flat position rank -> abstains."""
    rk, rt = panels({"A": UP, "B": UP, "C": [0.5] * 6}, {"A": UP, "B": UP[::-1], "C": UP})
    monkeypatch.setattr(f16, "rank_panels", lambda h: (rk, rt))
    sc = f16.score(hist())
    assert abs(sc["A"] + 1) < 1e-12
    b = -np.corrcoef(UP, UP[::-1])[0, 1]
    assert abs(sc["B"] - b) < 1e-12 and sc["B"] > 0
    assert "C" not in sc.index


def test_rank_panels_shape_and_range():
    rk, rt = f16.rank_panels(hist())
    assert rk.shape == (6, 4) and rt.shape == (6, 4)
    assert ((rk > 0) & (rk <= 1)).all().all() and ((rt > 0) & (rt <= 1)).all().all()


def test_percent_k_hand_value():
    """With 12 flat bars of high 101 / low 99 and a close of 100, %K is 0.5."""
    rows = []
    dates = pd.bdate_range("2016-01-01", periods=f16.MIN_ROWS).strftime("%Y-%m-%d")
    for s, close in (("A", 100.0), ("B", 100.5)):
        for d in dates:
            rows.append({"date": d, "symbol": s, "open": 100.0, "high": 101.0, "low": 99.0, "close": close,
                         "prevclose": close, "volume": 1e6, "turnover": 1e9})
    h = pd.DataFrame(rows)
    rk, _ = f16.rank_panels(h)
    assert (rk["A"] == 0.5).all() and (rk["B"] == 1.0).all()


def test_short_history_abstains():
    assert f16.score(hist().groupby("symbol").tail(f16.MIN_ROWS - 1)).empty


def test_symbol_missing_a_session_is_dropped():
    h = hist()
    h = h.drop(h[(h["symbol"] == "D") & (h["date"] == h["date"].max())].index)
    assert "D" not in f16.score(h).index


def test_symbols_without_a_future_on_the_last_date_leave():
    h = hist()
    h.loc[(h["symbol"] == "D") & (h["date"] == h["date"].max()), "has_future"] = False
    assert "D" not in f16.score(h).index


def test_needs_turnover():
    assert f16.score(hist().drop(columns="turnover")).empty


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_rules_fired_names_the_side(monkeypatch):
    rk, rt = panels({"A": UP, "B": UP}, {"A": UP, "B": UP[::-1]})
    monkeypatch.setattr(f16, "rank_panels", lambda h: (rk, rt))
    assert f16.rules_fired(hist(), "A").endswith("bearish")
    assert f16.rules_fired(hist(), "B").endswith("bullish")
    assert "abstain" in f16.rules_fired(hist(), "ZZZ")
