from strategies import champion_v1
from tests._picks_dataset import make_dataset, trading_dates

from picks.payload import make_payload
from picks.xray import BIN_EDGES, build_xray

SOURCE = {"tables": {k: {"strategy": "champion_v1@v1", "label": "provisional", "why": "x"} for k in ("day_bullish", "day_bearish")}}


def _setup():
    dates = trading_dates(champion_v1.MIN_ROWS + 10)
    ds = make_dataset({"UP": 0.01, "UP2": 0.02, "DOWN": -0.01, "FLAT": 0.0}, dates)
    return ds, dates[-2], dates[-1]


def test_xray_ranks_each_side_among_its_own_names_and_publishes_no_prices():
    ds, asof, session = _setup()
    x = build_xray(ds, SOURCE, session, asof)
    by = {r["s"]: r for r in x["stocks"]}
    assert set(by) == {"UP", "UP2", "DOWN", "FLAT"} and x["n"] == 4
    assert by["UP2"]["b"] == 100 and by["UP"]["b"] < by["UP2"]["b"]      # stronger trend ranks higher among bullish names
    assert by["DOWN"]["d"] == 100 and by["DOWN"]["b"] is None            # bearish name has no bullish rank
    assert all(set(r) == {"s", "b", "d"} for r in x["stocks"])           # ranks only: no price fields


def test_breadth_counts_every_eligible_stock_once_and_matches_up_down():
    ds, asof, session = _setup()
    b = build_xray(ds, SOURCE, session, asof)["breadth"]
    assert sum(b["counts"]) == b["n"] == 4 and len(b["counts"]) == len(BIN_EDGES) + 1
    assert b["up"] + b["down"] <= b["n"]


def test_make_payload_adds_xray_only_when_given():
    base = make_payload("day", "2026-10-20", "2026-10-19", "t", {"provisional"}, {"bullish": [], "bearish": []})
    assert "xray" not in base
    assert make_payload("day", "2026-10-20", "2026-10-19", "t", {"provisional"}, {"bullish": [], "bearish": []}, xray={"n": 0})["xray"] == {"n": 0}
