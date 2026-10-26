import pandas as pd

from strategies import champion_v1
from tests._picks_dataset import make_dataset, trading_dates

from picks.select import eligible_symbols, pick_table, select_side


def test_select_side_keeps_only_the_matching_sign_ranked_by_magnitude():
    scores = pd.Series({"AAA": 0.9, "BBB": 0.2, "CCC": -0.5, "DDD": 0.6})
    bullish = select_side(scores, side=1, eligible={"AAA", "BBB", "CCC", "DDD"}, n=2)
    assert list(bullish.index) == ["AAA", "DDD"]  # the two largest positive scores, strongest first


def test_select_side_drops_symbols_outside_the_eligible_set():
    scores = pd.Series({"AAA": 0.9, "BBB": 0.8})
    bullish = select_side(scores, side=1, eligible={"BBB"}, n=5)
    assert list(bullish.index) == ["BBB"]


def test_select_side_bearish_ranks_the_most_negative_first():
    scores = pd.Series({"AAA": -0.9, "BBB": -0.2})
    bearish = select_side(scores, side=-1, eligible={"AAA", "BBB"}, n=5)
    assert list(bearish.index) == ["AAA", "BBB"]


def test_eligible_symbols_excludes_a_symbol_without_an_active_future():
    dates = trading_dates(25)
    dataset = make_dataset({"AAA": 0.0, "BBB": 0.0}, dates)
    dataset.loc[dataset["symbol"] == "BBB", "has_future"] = False
    asof = dates[-1]
    assert eligible_symbols(dataset, asof) == {"AAA"}


def test_eligible_symbols_excludes_a_symbol_below_the_turnover_floor():
    dates = trading_dates(25)
    dataset = make_dataset({"AAA": 0.0, "BBB": 0.0}, dates)
    dataset.loc[dataset["symbol"] == "BBB", "turnover"] = 1.0  # far below the 25 cr floor
    asof = dates[-1]
    assert eligible_symbols(dataset, asof) == {"AAA"}


def test_pick_table_selects_the_trending_symbol_on_the_matching_side():
    dates = trading_dates(champion_v1.MIN_ROWS + 10)
    dataset = make_dataset({"UP": 0.01, "DOWN": -0.01, "FLAT": 0.0}, dates)
    asof = dates[-2]
    session = dates[-1]

    bullish = pick_table(dataset, champion_v1, "champion_v1@v1", session, side=1, asof=asof, n=5)
    assert [p["symbol"] for p in bullish] == ["UP"]
    assert bullish[0]["strategy"] == "champion_v1@v1"
    assert "bullish" in bullish[0]["reasoning"]

    bearish = pick_table(dataset, champion_v1, "champion_v1@v1", session, side=-1, asof=asof, n=5)
    assert [p["symbol"] for p in bearish] == ["DOWN"]


def test_pick_table_never_sees_the_session_date_itself():
    # Causal truncation: exactly MIN_ROWS rows exist, so champion_v1 would
    # score the symbol if (and only if) it could see every row including
    # the session's own - truncating at the session date must leave it one
    # row short and force an abstain.
    dates = trading_dates(champion_v1.MIN_ROWS)
    dataset = make_dataset({"UP": 0.01}, dates)
    assert len(champion_v1.score(dataset)) == 1  # sanity: the untruncated frame does score it

    picks = pick_table(dataset, champion_v1, "champion_v1@v1", session=dates[-1], side=1, asof=dates[-2], n=5)
    assert picks == []


class _Fixed:
    """A stand-in strategy with fixed scores (the dataset is only used for dates and the universe)."""

    def __init__(self, scores: dict):
        self._scores = pd.Series(scores, dtype=float)

    def score(self, history):
        return self._scores

    def rules_fired(self, history, symbol):
        return f"fixed {self._scores[symbol]:+.2f}"


def _universe(symbols):
    dates = trading_dates(25)
    return make_dataset({s: 0.0 for s in symbols}, dates), dates


def test_select_side_skips_excluded_and_refills():
    scores = pd.Series({"AAA": 0.9, "BBB": 0.8, "CCC": 0.7})
    picked = select_side(scores, side=1, eligible={"AAA", "BBB", "CCC"}, n=2, exclude=frozenset({"AAA"}))
    assert list(picked.index) == ["BBB", "CCC"]


def test_a_stock_in_both_tables_is_dropped_from_both_and_refilled():
    from picks.select import pick_both_sides

    dataset, dates = _universe(["AAA", "BBB", "CCC", "DDD", "EEE"])
    bull = _Fixed({"AAA": 0.9, "BBB": 0.8, "CCC": 0.1})
    bear = _Fixed({"AAA": -0.9, "DDD": -0.8, "EEE": -0.1})
    bullish, bearish, dropped = pick_both_sides(dataset, (bull, "b@v1"), (bear, "r@v1"), dates[-1], dates[-2], n=2)
    assert dropped == ["AAA"]
    assert [p["symbol"] for p in bullish] == ["BBB", "CCC"]
    assert [p["symbol"] for p in bearish] == ["DDD", "EEE"]


def test_refill_that_creates_a_new_shared_stock_is_also_dropped():
    from picks.select import pick_both_sides

    dataset, dates = _universe(["AAA", "BBB", "CCC", "DDD", "EEE"])
    # Dropping AAA brings CCC into both top-2 lists; CCC must go too.
    bull = _Fixed({"AAA": 0.9, "BBB": 0.8, "CCC": 0.7, "EEE": 0.1})
    bear = _Fixed({"AAA": -0.9, "DDD": -0.8, "CCC": -0.7})
    bullish, bearish, dropped = pick_both_sides(dataset, (bull, "b@v1"), (bear, "r@v1"), dates[-1], dates[-2], n=2)
    assert dropped == ["AAA", "CCC"]
    assert {p["symbol"] for p in bullish} & {p["symbol"] for p in bearish} == set()
    assert [p["symbol"] for p in bullish] == ["BBB", "EEE"]
    assert [p["symbol"] for p in bearish] == ["DDD"]


def test_no_shared_stock_means_nothing_dropped():
    from picks.select import pick_both_sides

    dataset, dates = _universe(["AAA", "BBB"])
    same = _Fixed({"AAA": 0.5, "BBB": -0.5})
    bullish, bearish, dropped = pick_both_sides(dataset, (same, "s@v1"), (same, "s@v1"), dates[-1], dates[-2], n=5)
    assert dropped == []
    assert [p["symbol"] for p in bullish] == ["AAA"] and [p["symbol"] for p in bearish] == ["BBB"]
