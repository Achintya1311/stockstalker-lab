import numpy as np
import pandas as pd

from strategies import h03_turnover_variability as h03
from strategies.h03_turnover_variability_audit import check_cross_symbol_causality, stock

N = h03.WINDOW + 5


def _universe():
    return pd.concat([stock("STEADY", N, 1, 0.05), stock("MID", N, 2, 0.4), stock("ERRATIC", N, 3, 1.2)])


def test_steady_trading_bullish_erratic_bearish():
    sc = h03.score(_universe())
    assert sc["ERRATIC"] < 0 < sc["STEADY"]


def test_hand_computed_cv_and_score():
    hist = _universe()
    t = hist[hist.symbol == "ERRATIC"]["turnover"].to_numpy()[-h03.WINDOW:]
    cv = t.std() / t.mean()
    cvs = h03.turnover_cv(hist)
    assert abs(cvs["ERRATIC"] - cv) < 1e-12
    assert abs(h03.score(hist)["ERRATIC"] - (np.log(cvs.median()) - np.log(cv))) < 1e-12


def test_only_last_window_counts():
    hist = _universe()
    first_date = hist["date"].min()
    hist.loc[(hist.symbol == "STEADY") & (hist.date == first_date), "turnover"] = 1e15
    assert abs(h03.score(hist)["STEADY"] - h03.score(_universe())["STEADY"]) < 1e-12


def test_gap_in_window_abstains():
    hist = _universe()
    drop = hist[(hist.symbol == "MID")].index[-10]
    assert "MID" not in h03.score(hist.drop(index=drop)).index


def test_short_history_abstains():
    hist = pd.concat([stock("A", h03.WINDOW - 1, 1, 0.1), stock("B", h03.WINDOW - 1, 2, 0.9)])
    assert h03.score(hist).empty


def test_missing_turnover_column_abstains():
    assert h03.score(_universe().drop(columns="turnover")).empty


def test_non_fno_symbols_are_dropped_when_flag_present():
    hist = _universe()
    hist["has_future"] = hist["symbol"] != "ERRATIC"
    assert "ERRATIC" not in h03.score(hist).index


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_rules_fired_names_the_side():
    hist = _universe()
    assert h03.rules_fired(hist, "ERRATIC").endswith("bearish")
    assert h03.rules_fired(hist, "STEADY").endswith("bullish")
