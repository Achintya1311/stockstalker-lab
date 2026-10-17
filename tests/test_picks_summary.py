import json
from pathlib import Path

from picks.summary import build_summary


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def test_build_summary_counts_hits_and_picks_per_table(tmp_path):
    out_dir = tmp_path / "live"
    _write(
        out_dir / "day" / "2026-10-19.json",
        {
            "horizon": "day",
            "session": "2026-10-19",
            "tables": {
                "bullish": [{"symbol": "AAA", "hit": True}, {"symbol": "BBB", "hit": False}],
                "bearish": [{"symbol": "CCC", "hit": True}],
            },
        },
    )
    _write(
        out_dir / "day" / "2026-10-20.json",
        {
            "horizon": "day",
            "session": "2026-10-20",
            "tables": {"bullish": [{"symbol": "AAA", "hit": True}], "bearish": []},
        },
    )

    summary = build_summary(out_dir, dataset=None)
    bullish = summary["live"]["day_bullish"]
    assert bullish["n_picks"] == 3
    assert bullish["n_scored"] == 3
    assert bullish["n_hits"] == 2
    assert bullish["by_month"]["2026-10"] == {"n_picks": 3, "n_hits": 2}


def test_build_summary_leaves_out_late_picks_from_hit_counts_but_keeps_pick_counts(tmp_path):
    out_dir = tmp_path / "live"
    _write(
        out_dir / "day" / "2026-10-19.json",
        {
            "horizon": "day",
            "session": "2026-10-19",
            "tables": {"bullish": [{"symbol": "AAA", "hit": True, "late": True}], "bearish": []},
        },
    )
    bullish = build_summary(out_dir, dataset=None)["live"]["day_bullish"]
    assert bullish["n_picks"] == 1
    assert bullish["n_scored"] == 0
    assert bullish["n_hits"] == 0


def test_build_summary_unscored_picks_count_toward_picks_not_hits(tmp_path):
    out_dir = tmp_path / "live"
    _write(
        out_dir / "day" / "2026-10-22.json",
        {"horizon": "day", "session": "2026-10-22", "tables": {"bullish": [{"symbol": "AAA"}], "bearish": []}},
    )
    bullish = build_summary(out_dir, dataset=None)["live"]["day_bullish"]
    assert bullish == {
        "n_picks": 1,
        "n_scored": 0,
        "n_hits": 0,
        "by_week": {"2026-W43": {"n_picks": 1, "n_hits": 0}},
        "by_month": {"2026-10": {"n_picks": 1, "n_hits": 0}},
        "market_line": None,
    }


def test_build_summary_separates_exam_from_live_totals(tmp_path):
    out_dir = tmp_path / "live"
    _write(
        out_dir / "day" / "2026-10-19.json",
        {"horizon": "day", "session": "2026-10-19", "tables": {"bullish": [{"symbol": "AAA", "hit": True}], "bearish": []}},
    )
    _write(
        out_dir / "exam" / "day" / "2026-08-03.json",
        {"horizon": "day", "session": "2026-08-03", "tables": {"bullish": [{"symbol": "ZZZ", "hit": False}], "bearish": []}},
    )

    summary = build_summary(out_dir, dataset=None)
    assert summary["live"]["day_bullish"]["n_picks"] == 1
    assert summary["exam"]["day_bullish"]["n_picks"] == 1
    assert summary["live"]["day_bullish"]["n_hits"] == 1
    assert summary["exam"]["day_bullish"]["n_hits"] == 0
