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
