import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors
from strategies import h01_amihud_illiquidity as h01
from strategies.h01_amihud_illiquidity_audit import check_cross_symbol_causality, stock

N = h01.WINDOW + 5


def _universe():
    return pd.concat([stock("LIQUID", N, 1, 0.01, 1e10), stock("MID", N, 2, 0.01, 1e8), stock("THIN", N, 3, 0.01, 1e6)])


def test_illiquid_bullish_liquid_bearish():
    sc = h01.score(_universe())
    assert sc["THIN"] > 0 > sc["LIQUID"]


def test_hand_computed_ratio_and_score():
    hist = _universe()
    adj = compute_adjustment_factors(hist)
    c = adj[adj.symbol == "THIN"].sort_values("date")["adj_close"].to_numpy()
    t = hist[hist.symbol == "THIN"].sort_values("date")["turnover"].to_numpy()
    r = np.abs(np.diff(np.log(c)))[-h01.WINDOW:]
    expected = float((r / t[-h01.WINDOW:]).mean())
    a = h01.amihud(hist)
    assert abs(a["THIN"] - expected) / expected < 1e-12
    assert abs(h01.score(hist)["THIN"] - (np.log(a["THIN"]) - np.log(a.median()))) < 1e-12


def test_only_last_window_counts():
    hist = _universe()
    first_date = hist["date"].min()
    hist.loc[(hist.symbol == "THIN") & (hist.date == first_date), "turnover"] = 1.0
    assert abs(h01.score(hist)["THIN"] - h01.score(_universe())["THIN"]) < 1e-12


def test_gap_in_window_abstains():
    hist = _universe()
    drop = hist[hist.symbol == "MID"].index[-10]
    assert "MID" not in h01.score(hist.drop(index=drop)).index


def test_zero_turnover_abstains():
    hist = _universe()
    idx = hist[hist.symbol == "MID"].index[-3]
    hist.loc[idx, "turnover"] = 0.0
    assert "MID" not in h01.score(hist).index


def test_short_history_abstains():
    hist = pd.concat([stock("A", h01.WINDOW, 1, 0.01, 1e9), stock("B", h01.WINDOW, 2, 0.01, 1e7)])
    assert h01.score(hist).empty


def test_missing_turnover_column_abstains():
    assert h01.score(_universe().drop(columns="turnover")).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    hist = _universe()
    hist["has_future"] = hist["symbol"] != "THIN"
    assert "THIN" not in h01.score(hist).index


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_rules_fired_names_the_side():
    hist = _universe()
    assert h01.rules_fired(hist, "THIN").endswith("bullish")
    assert h01.rules_fired(hist, "LIQUID").endswith("bearish")
