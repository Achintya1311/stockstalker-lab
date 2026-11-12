"""Synthetic tests for the C1 results table (`scripts/composite_ingredients.py`) on a temp experiments/done."""

from __future__ import annotations

import json
import re

import pytest

from scripts import composite_ingredients as ci
from scripts.gen_g_cells import experiment_id
from strategies.g_gates import CELLS, SKIPPED

YEARS = ci.TRAIN_YEARS


def _block(edge, year_edges, n_dates=100, n_picks=500, t=2.0):
    return {
        "n_picks": n_picks, "n_dates": n_dates, "edge": edge, "edge_t": t, "directional_move": 0.001,
        "by_year": [{"year": y, "n_picks": 10, "edge": e} for y, e in zip(YEARS, year_edges) if e is not None],
    }


def _write(done, exp_id, side_word, block, split="train", picks=None):
    d = done / exp_id
    d.mkdir(parents=True)
    other = "bearish" if side_word == "bullish" else "bullish"
    res = {"id": exp_id, "split": split, "selections": {
        "top": {side_word: block, other: {"n_picks": 0}}, "all": {side_word: block, other: {"n_picks": 0}}}}
    (d / "results.json").write_text(json.dumps(res))
    (d / "picks.json").write_text(json.dumps(picks or [{"date": "2015-01-05", "symbol": "AAA", "score": 1.0}]))


@pytest.fixture
def done(tmp_path):
    done = tmp_path / "done"
    flat = [0.02] * 6
    _write(done, "e2a-day", "bearish", _block(0.02, flat, n_dates=200))
    _write(done, "t04-connors-rsi2-day", "bullish", _block(0.02, flat))
    _write(done, "a05b-max-effect-ranked-week", "bullish", _block(0.02, flat))
    _write(done, "a01-weekly-reversal-week", "bearish", _block(0.02, flat))
    # A01 x G1: better than the trigger in 5 years, beats its complement -> qualifies.
    _write(done, experiment_id("a01", "g1", True), "bearish", _block(0.04, [0.03, 0.03, 0.03, 0.03, 0.03, 0.01], n_dates=50))
    _write(done, experiment_id("a01", "g1", False), "bearish", _block(0.00, [0.0] * 6))
    # A01 x G2: better than the trigger, but its complement is better still -> fails C.
    _write(done, experiment_id("a01", "g2", True), "bearish", _block(0.04, [0.04] * 6))
    _write(done, experiment_id("a01", "g2", False), "bearish", _block(0.05, [0.05] * 6))
    # E2A x G1: only 3 years above the trigger -> fails A and B.
    _write(done, experiment_id("e2a", "g1", True), "bearish", _block(0.03, [0.05, 0.05, 0.05, 0.0, 0.0, 0.0], n_dates=50))
    _write(done, experiment_id("e2a", "g1", False), "bearish", _block(0.01, [0.0] * 6))
    # A05B x G2: keep landed, complement not yet -> pending.
    _write(done, experiment_id("a05b", "g2", True), "bullish", _block(0.04, [0.04] * 6))
    return done


def test_table_reads_cells_and_applies_the_screen(done):
    t = ci.build(done)
    rows = {r["cell"]: r for r in t["cells"]}
    assert set(rows) == {"G_A01_G1", "G_A01_G2", "G_E2A_G1"}
    a = rows["G_A01_G1"]
    assert a["trigger_edge_pts"] == 2.0 and a["keep_edge_pts"] == 4.0 and a["complement_edge_pts"] == 0.0
    assert a["years_keep_gt_trigger"] == 5 and a["years_keep_gt_complement"] == 6 and a["years_compared_complement"] == 6
    assert a["date_share"] == 0.5 and a["sign_test_p_keep_gt_complement"] == round(1 / 64, 3)
    assert a["keep_minus_trigger_by_year_pts"]["2020"] == -1.0
    assert a["qualifies"] is True
    b = rows["G_A01_G2"]
    assert b["crit_a_interval_substitute"] is False and b["crit_c_beats_complement"] is False and b["qualifies"] is False
    e = rows["G_E2A_G1"]
    assert e["years_keep_gt_trigger"] == 3 and e["date_share"] == 0.25 and e["qualifies"] is False


def test_pending_and_skipped_are_listed(done):
    t = ci.build(done)
    pending = {p["cell"]: p for p in t["pending"]}
    assert len(pending) == len(CELLS) - 3
    assert pending["G_A05B_G2"]["missing"] == [experiment_id("a05b", "g2", False)]
    assert len(t["skipped"]) == len(SKIPPED)


def test_no_interval_without_per_pick_outcomes(done):
    t = ci.build(done)
    assert t["per_pick_outcomes_in_picks_json"] is False
    assert all(r["difference_interval"] is None for r in t["cells"])
    assert "no bootstrap interval" in ci.render_md(t)


def test_validation_results_are_refused(tmp_path):
    _write(tmp_path, "x", "bullish", _block(0.01, [0.01] * 6), split="validation")
    with pytest.raises(ValueError):
        ci.load_results(tmp_path, "x")


def test_main_writes_sebi_safe_markdown_and_json(done, tmp_path):
    md, js = tmp_path / "out.md", tmp_path / "out.json"
    assert ci.main(["--done", str(done), "--md", str(md), "--json", str(js)]) == 0
    text = md.read_text()
    assert len([l for l in text.splitlines()[2:7] if l.strip()]) == 5   # five-line plain header
    assert not re.search(r"\b(buy|sell|target|entry|stop)\w*\b", text, flags=re.I)
    assert json.loads(js.read_text())["cells"][0]["cell"] == "G_E2A_G1"
    assert "G_A01_G1 | +2.00 | +4.00 | +0.00" in text


def test_sign_test():
    assert ci.sign_test_p(6, 6) == 1 / 64 and ci.sign_test_p(0, 6) == 1.0 and ci.sign_test_p(0, 0) is None
