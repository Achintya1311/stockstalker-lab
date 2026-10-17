from strategies import champion_v1
from tests._picks_dataset import make_dataset, trading_dates

from picks.payload import build_tables, disclaimer_for, make_payload, table_label

SOURCE = {
    "tables": {
        "day_bullish": {"strategy": "champion_v1@v1", "label": "provisional", "why": "x"},
        "day_bearish": {"strategy": "champion_v1@v1", "label": "provisional", "why": "x"},
    }
}


def test_table_label_agrees_when_both_sides_share_a_label():
    assert table_label({"provisional"}) == "provisional"
    assert table_label({"gated"}) == "gated"


def test_table_label_is_mixed_when_sides_disagree():
    assert table_label({"provisional", "gated"}) == "mixed"


def test_disclaimer_always_carries_the_base_text():
    assert "Not investment advice" in disclaimer_for({"gated"})


def test_disclaimer_adds_the_provisional_line_when_either_side_is_provisional():
    gated_only = disclaimer_for({"gated"})
    mixed = disclaimer_for({"gated", "provisional"})
    assert "Provisional strategy" not in gated_only
    assert "Provisional strategy" in mixed
    assert "Provisional strategy" in disclaimer_for({"provisional"})


def test_build_tables_fills_bullish_and_bearish_from_their_own_configured_strategy():
    dates = trading_dates(champion_v1.MIN_ROWS + 10)
    dataset = make_dataset({"UP": 0.01, "DOWN": -0.01}, dates)
    asof, session = dates[-2], dates[-1]

    tables, labels = build_tables(dataset, SOURCE, "day", session, asof)
    assert [p["symbol"] for p in tables["bullish"]] == ["UP"]
    assert [p["symbol"] for p in tables["bearish"]] == ["DOWN"]
    assert labels == {"provisional"}


def test_make_payload_shape_matches_the_contract():
    payload = make_payload("day", "2026-10-20", "2026-10-19", "2026-10-19T20:00:00Z", {"provisional"}, {"bullish": [], "bearish": []})
    assert payload["session"] == "2026-10-20"
    assert payload["horizon"] == "day"
    assert payload["asof"] == "2026-10-19"
    assert payload["label"] == "provisional"
    assert set(payload["tables"]) == {"bullish", "bearish"}
    assert "No" in payload["disclaimer"] or "Not" in payload["disclaimer"]
