import datetime as dt
import json

import yaml

from scripts.provisional_candidates import eligible, experiment_yaml, render, stage, validation_id


def _side(n, edge, move):
    return {"n_picks": n, "edge": edge, "edge_t": 1.0, "directional_move": move}


def _write(done, exp_id, horizon, bull, bear, strategy=None, split="train"):
    d = done / exp_id
    d.mkdir(parents=True)
    res = {"id": exp_id, "strategy": strategy or f"strategies.{exp_id.replace('-', '_')}", "split": split,
           "horizon": horizon, "selections": {"top": {"bullish": bull, "bearish": bear}}}
    (d / "results.json").write_text(json.dumps(res))


def test_only_the_provisional_letter_qualifies(tmp_path):
    _write(tmp_path, "good-week", "week", {"n_picks": 0}, _side(600, 0.03, 0.001))
    _write(tmp_path, "few-picks-week", "week", {"n_picks": 0}, _side(499, 0.09, 0.01))
    _write(tmp_path, "neg-move-week", "week", {"n_picks": 0}, _side(900, 0.05, -0.0001))
    _write(tmp_path, "zero-edge-week", "week", {"n_picks": 0}, _side(900, 0.0, 0.002))
    _write(tmp_path, "smoke-day", "day", _side(900, 0.5, 0.5), _side(900, 0.5, 0.5), strategy="strategies.engine_smoketest")
    rows = eligible(tmp_path)
    assert [r["id"] for r in rows[("week", "bearish")]] == ["good-week"]
    assert rows[("day", "bullish")] == [] and rows[("day", "bearish")] == [] and rows[("week", "bullish")] == []


def test_sorted_by_train_edge_and_sides_kept_apart(tmp_path):
    _write(tmp_path, "a-day", "day", _side(700, 0.01, 0.001), _side(700, 0.02, 0.001))
    _write(tmp_path, "b-day", "day", _side(700, 0.04, -0.01), _side(700, 0.05, 0.002))
    rows = eligible(tmp_path)
    assert [r["id"] for r in rows[("day", "bearish")]] == ["b-day", "a-day"]
    assert [r["id"] for r in rows[("day", "bullish")]] == ["a-day"]


def test_staged_file_is_a_validation_experiment_the_queue_can_read(tmp_path):
    done, out, ledger = tmp_path / "done", tmp_path / "stage", tmp_path / "ledger.csv"
    _write(done, "a-day", "day", _side(700, 0.01, 0.001), _side(700, 0.02, 0.001))
    files = stage(eligible(done), out, ledger, done)
    assert [f.name for f in files] == ["a-day-validation.yml"]  # one file covers both eligible sides
    exp = yaml.safe_load(files[0].read_text())
    assert exp == {"id": "a-day-validation", "strategy": "strategies.a_day", "split": "validation", "horizon": "day",
                   "train_experiment": "a-day", "dates": {"start": dt.date(2021, 1, 1), "end": dt.date(2023, 12, 31)}}  # same unquoted form as train ymls


def test_never_restages_an_answered_or_logged_query(tmp_path):
    done, out, ledger = tmp_path / "done", tmp_path / "stage", tmp_path / "ledger.csv"
    _write(done, "a-week", "week", {"n_picks": 0}, _side(700, 0.02, 0.001))
    _write(done, "b-week", "week", {"n_picks": 0}, _side(700, 0.03, 0.001))
    _write(done, "c-week", "week", {"n_picks": 0}, _side(700, 0.04, 0.001))
    (done / validation_id("a-week")).mkdir()
    (done / validation_id("a-week") / "holdout.json").write_text("{}")
    ledger.write_text("query_id,timestamp\nb-week-validation-bearish,2026-10-26T00:10:00+00:00\n")
    files = stage(eligible(done), out, ledger, done)
    assert [f.name for f in files] == ["c-week-validation.yml"]


def test_render_says_when_a_table_falls_back_to_champion(tmp_path):
    _write(tmp_path, "a-week", "week", {"n_picks": 0}, _side(700, 0.0248, 0.0015))
    md = render(eligible(tmp_path))
    assert "## day / bullish" in md and "champion v1" in md
    assert "| a-week | 700 | +2.48 | 1.00 | +0.150% |" in md


def test_yaml_header_names_the_tables():
    row = {"id": "x-week", "strategy": "strategies.x", "horizon": "week"}
    assert "week-bearish" in experiment_yaml(row, ["bearish"])
