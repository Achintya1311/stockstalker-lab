import pandas as pd

from strategies import h04_return_seasonality as h04
from strategies.h04_return_seasonality_audit import check_cross_symbol_causality, monthly_path

END = "2017-12-29"  # Friday; pick week starts 1 Jan 2018 (January)


def test_target_month_is_next_mondays_month():
    assert h04.target_month(pd.Timestamp("2017-12-29")) == 1
    assert h04.target_month(pd.Timestamp("2018-03-23")) == 3
    assert h04.target_month(pd.Timestamp("2018-03-29")) == 4  # Thursday: next Monday is 2 April


def test_mean_of_earlier_januaries_exact():
    hist = pd.concat([monthly_path("UP", END, 0.10), monthly_path("DN", END, -0.06)])
    sc = h04.score(hist)
    # January 2015 has no previous month-end, so the earlier years are 2016 and 2017
    assert abs(sc["UP"] - 0.10) < 1e-9 and abs(sc["DN"] + 0.06) < 1e-9


def test_other_months_do_not_count():
    a = h04.score(monthly_path("X", END, 0.04, other_move=0.0))["X"]
    b = h04.score(monthly_path("X", END, 0.04, other_move=0.03))["X"]
    assert abs(a - 0.04) < 1e-9 and abs(b - 0.04) < 1e-9


def test_fewer_than_two_earlier_years_abstains():
    assert h04.score(monthly_path("X", "2016-12-30", 0.05)).empty  # only January 2016 is usable


def test_unfinished_month_is_not_counted():
    # last row in January 2018: January 2018's own return must not be used for the January target
    hist = monthly_path("X", "2018-01-26", 0.5)
    assert abs(h04.score(hist)["X"] - 0.5) < 1e-9


def test_non_fno_dropped_when_flag_present():
    hist = pd.concat([monthly_path("A", END, 0.1), monthly_path("B", END, 0.2)])
    hist["has_future"] = hist["symbol"] != "B"
    assert list(h04.score(hist).index) == ["A"]


def test_cross_symbol_causality():
    assert check_cross_symbol_causality()["passed"]


def test_rules_fired_names_the_side():
    assert h04.rules_fired(monthly_path("X", END, 0.1), "X").endswith("bullish")
    assert h04.rules_fired(monthly_path("X", END, -0.1), "X").endswith("bearish")
