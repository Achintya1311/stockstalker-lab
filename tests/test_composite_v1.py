"""Synthetic tests for COMPOSITE_V1 (`strategies/composite_v1.py`), its audit, its queue files and its report.

AND semantics, abstain semantics, picks a subset of the trigger's with unchanged scores, complement disjoint
from the composite, the declared table unchanged, modules and held replays in sync with the card.
"""

from __future__ import annotations

import csv
import importlib
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from engine.replay import truncate
from scripts import composite_v1_report as rep
from strategies import composite_v1 as C
from strategies import g_gates as G
from strategies.composite_v1_audit import run_all
from strategies.g_gates_audit import synthetic_panel

ROOT = Path(__file__).resolve().parent.parent
HELD = ROOT / "experiments" / "held" / "c2"
PENDING = ROOT / "experiments" / "pending"
CARD = ROOT / "cards" / "COMPOSITE_V1.yml"
CATALOG = ROOT / "cards" / "catalog.csv"

BASE = pd.Series({"A": 3.0, "B": 2.0, "C": 1.0, "D": 0.5, "E": 0.25})
# day bullish = T04 AND G3 AND G4 AND G7 AND G9
FAKE = {
    "g3": {"A": True, "B": True, "C": False, "D": True, "E": True},
    "g4": {"A": True, "B": True, "C": True, "D": True},           # E: no verdict
    "g7": {"A": True, "B": False, "C": True, "D": True, "E": True},
    "g9": {"A": True, "B": True, "C": True, "E": False},           # D: no verdict
}


@pytest.fixture
def fake_gates(monkeypatch):
    calls = []

    def make(name):
        def gate(history, sides, trigger=None):
            calls.append((name, dict(sides), trigger))
            return dict(FAKE[name])
        return gate

    monkeypatch.setattr(G, "trigger_side_scores", lambda trigger, history: BASE.copy())
    monkeypatch.setattr(G, "GATES", {**G.GATES, **{g: make(g) for g in FAKE}})
    return calls


def test_the_declared_table_is_exactly_the_c1_selection():
    assert C.COMPOSITES == {
        "day_bearish": ("e2a", ("g2",)),
        "day_bullish": ("t04", ("g3", "g4", "g7", "g9")),
        "week_bullish": ("a05b", ("g5",)),
        "week_bearish": ("a01", ("g8",)),
    }


def test_a_pick_is_kept_only_when_every_gate_holds(fake_gates):
    keep = C.composite_score("day_bullish", True, pd.DataFrame())
    assert list(keep.index) == ["A"]


def test_a_pick_any_gate_cannot_judge_abstains_in_both(fake_gates):
    _, v = C.verdicts("day_bullish", pd.DataFrame())
    assert set(v) == {"A", "B", "C"}
    keep = C.composite_score("day_bullish", True, pd.DataFrame())
    comp = C.composite_score("day_bullish", False, pd.DataFrame())
    assert "D" not in keep.index and "D" not in comp.index
    assert "E" not in keep.index and "E" not in comp.index


def test_complement_is_the_judged_picks_where_not_all_gates_hold_and_disjoint(fake_gates):
    keep = C.composite_score("day_bullish", True, pd.DataFrame())
    comp = C.composite_score("day_bullish", False, pd.DataFrame())
    assert sorted(comp.index) == ["B", "C"]
    assert not set(keep.index) & set(comp.index)


def test_scores_are_the_trigger_scores_unchanged(fake_gates):
    for keep in (True, False):
        s = C.composite_score("day_bullish", keep, pd.DataFrame())
        assert set(s.index) <= set(BASE.index)
        assert all(s[k] == BASE[k] for k in s.index)


def test_every_gate_is_asked_about_every_trigger_pick_on_the_trigger_side(fake_gates):
    C.verdicts("day_bullish", pd.DataFrame())
    assert [c[0] for c in fake_gates] == ["g3", "g4", "g7", "g9"]
    for _, sides, trigger in fake_gates:
        assert trigger == "t04" and sides == {s: 1 for s in BASE.index}


def test_no_trigger_picks_gives_empty_scores(monkeypatch):
    monkeypatch.setattr(G, "trigger_side_scores", lambda trigger, history: pd.Series(dtype=float))
    for table in C.COMPOSITES:
        assert C.composite_score(table, True, pd.DataFrame()).empty
        assert C.composite_score(table, False, pd.DataFrame()).empty


def test_unknown_table_is_refused():
    with pytest.raises(ValueError):
        C.composite("month_bullish")


@pytest.fixture(scope="module")
def panel():
    return synthetic_panel(n_symbols=12, n_rows=330)


def test_on_a_real_panel_picks_are_a_subset_of_the_trigger_and_one_gate_tables_match_c1(panel):
    for d in sorted(panel["date"].unique())[-3:]:
        h = truncate(panel, d)
        for table, (trigger, gates) in C.COMPOSITES.items():
            base = G.trigger_side_scores(trigger, h)
            keep, comp = C.composite_score(table, True, h), C.composite_score(table, False, h)
            assert set(keep.index) <= set(base.index) and set(comp.index) <= set(base.index)
            assert not set(keep.index) & set(comp.index)
            if len(gates) == 1:
                assert keep.sort_index().equals(G.cell_score(trigger, gates[0], True, h).sort_index())
                assert comp.sort_index().equals(G.cell_score(trigger, gates[0], False, h).sort_index())


def test_modules_import_and_wrap_the_right_composite(panel):
    h = truncate(panel, sorted(panel["date"].unique())[-1])
    for table in C.COMPOSITES:
        for keep, suffix in ((True, ""), (False, "_not")):
            mod = importlib.import_module(f"strategies.composite_v1_{table}{suffix}")
            assert callable(mod.score) and callable(mod.rules_fired)
            assert mod.score.__doc__.startswith(C.composite_id(table, keep) + ":")
            assert mod.score(h).sort_index().equals(C.composite_score(table, keep, h).sort_index())


def test_rules_fired_names_the_composite_and_abstains_otherwise(panel):
    h = truncate(panel, sorted(panel["date"].unique())[-1])
    s = C.composite_score("week_bullish", True, h).index[0]
    text = importlib.import_module("strategies.composite_v1_week_bullish").rules_fired(h, s)
    assert text.startswith("COMPOSITE_V1_WEEK_BULLISH: A05B bullish pick where all of G5 hold")
    other = importlib.import_module("strategies.composite_v1_week_bullish_not").rules_fired(h, s)
    assert "abstain" in other
    for word in ("buy", "sell", "target", "stop loss"):
        assert word not in text.lower() and word not in other.lower()


def test_held_replays_match_the_card_and_none_are_pending():
    card = yaml.safe_load(CARD.read_text())
    ids = sorted(r for c in card["composites"] for r in c["replays"])
    assert sorted(p.stem for p in HELD.glob("*.yml")) == ids and len(ids) == 8
    for exp_id in ids:
        assert not (PENDING / f"{exp_id}.yml").exists()
        y = yaml.safe_load((HELD / f"{exp_id}.yml").read_text())
        table = next(t for t in C.COMPOSITES if exp_id in (rep.experiment_id(t, True), rep.experiment_id(t, False)))
        keep = exp_id == rep.experiment_id(table, True)
        assert y == {
            "id": exp_id,
            "strategy": f"strategies.composite_v1_{table}" + ("" if keep else "_not"),
            "split": "train",
            "horizon": G.TRIGGERS[C.COMPOSITES[table][0]].horizon,
            "dates": {"start": "2015-01-01", "end": "2020-12-31"},
        }


def test_card_and_catalog_rows_cover_every_composite():
    card = yaml.safe_load(CARD.read_text())
    assert {c["id"] for c in card["composites"]} == {C.composite_id(t) for t in C.COMPOSITES}
    rule = card["default_params"]["success_rule"]
    assert rule["min_years_composite_above_trigger"] == rep.MIN_YEARS
    assert rule["min_date_coverage_of_trigger"] == rep.MIN_COVERAGE
    rows = {r[0]: r for r in csv.reader(CATALOG.read_text().splitlines()) if r}
    for t in C.COMPOSITES:
        assert C.composite_id(t) in rows and C.composite_id(t, False) in rows[C.composite_id(t)][4]


def test_causality_audit_passes():
    result = run_all()
    assert result["passed"], result


# ---------------------------------------------------------------- report

YEARS = rep.TRAIN_YEARS


def _block(edge, year_edges, n_dates=100):
    return {"n_picks": 5 * n_dates, "n_dates": n_dates, "edge": edge, "edge_t": 2.0, "directional_move": 0.001,
            "by_year": [{"year": y, "edge": e} for y, e in zip(YEARS, year_edges) if e is not None]}


def _write(done, exp_id, side_word, block):
    d = done / exp_id
    d.mkdir(parents=True)
    other = "bearish" if side_word == "bullish" else "bullish"
    sel = {side_word: block, other: {"n_picks": 0}}
    (d / "results.json").write_text(json.dumps({"id": exp_id, "split": "train", "selections": {"top": sel, "all": sel}}))


def test_report_runs_with_everything_pending(tmp_path):
    done = tmp_path / "done"
    done.mkdir()
    t = rep.build(done)
    assert t["tables"] == [] and len(t["pending"]) == 4
    assert "(none yet)" in rep.render_md(t)
    assert rep.main(["--done", str(done), "--md", str(tmp_path / "a.md"), "--json", str(tmp_path / "a.json")]) == 0


def test_report_applies_the_card_rule(tmp_path):
    done = tmp_path / "done"
    flat = [0.02] * 6
    _write(done, "e2a-day", "bearish", _block(0.02, flat, n_dates=100))
    _write(done, "t04-connors-rsi2-day", "bullish", _block(0.02, flat, n_dates=100))
    _write(done, "a05b-max-effect-ranked-week", "bullish", _block(0.02, flat, n_dates=100))
    # day bearish: better in 4 years, 50% of dates -> passes
    _write(done, rep.experiment_id("day_bearish", True), "bearish", _block(0.03, [0.03] * 4 + [0.01, 0.01], n_dates=50))
    _write(done, rep.experiment_id("day_bearish", False), "bearish", _block(0.01, flat))
    # day bullish: better, but no 2015 picks and only 3 years above -> fails rule 2
    _write(done, rep.experiment_id("day_bullish", True), "bullish", _block(0.03, [None, 0.03, 0.03, 0.03, 0.01, 0.01], n_dates=60))
    # week bullish: better every year but only 30% of dates -> fails rule 3
    _write(done, rep.experiment_id("week_bullish", True), "bullish", _block(0.05, [0.05] * 6, n_dates=30))
    _write(done, rep.experiment_id("week_bullish", False), "bullish", _block(0.01, flat))
    t = rep.build(done)
    rows = {r["table"]: r for r in t["tables"]}
    assert rows["day bearish"]["passes"] and rows["day bearish"]["decision"] == "adopt composite"
    assert rows["day bearish"]["date_coverage"] == 0.5
    b = rows["day bullish"]
    assert b["rule_1_edge_above_trigger"] and not b["rule_2_years_above"] and b["years_composite_above_trigger"] == 3
    assert b["decision"] == "keep plain T04" and b["complement_edge_pts"] is None
    assert b["missing"] == [rep.experiment_id("day_bullish", False)]
    w = rows["week bullish"]
    assert w["rule_2_years_above"] and not w["rule_3_coverage"] and not w["passes"]
    assert [p["table"] for p in t["pending"]] == ["week bearish"]
    md = rep.render_md(t)
    assert "keep plain A05B" in md and "adopt composite" in md
