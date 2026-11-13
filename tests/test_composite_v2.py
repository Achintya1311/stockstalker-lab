"""Synthetic tests for COMPOSITE_V2 (`strategies/composite_v2.py`), its audit, generator, held replays and report.

Vote semantics, boost keeps every pick and never flips a sign, threshold defaults equal the C1 gates, vote and
threshold picks are a subset of the trigger's, symmetry of config keys across the two tables of a horizon, the
budget and the held folders, and the pre-declared selection in the report.
"""

from __future__ import annotations

import csv
import importlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from engine.replay import truncate
from scripts import composite_v2_report as rep
from scripts import gen_composite_v2 as gen
from strategies import composite_v2 as C
from strategies import g_gates as G
from strategies.composite_v2_audit import run_all
from strategies.g_gates_audit import synthetic_panel

ROOT = Path(__file__).resolve().parent.parent
HELD = ROOT / "experiments" / "held" / "v2"
PENDING = ROOT / "experiments" / "pending"
DONE = ROOT / "experiments" / "done"
CARD = ROOT / "cards" / "COMPOSITE_V2.yml"
CATALOG = ROOT / "cards" / "catalog.csv"
C1_JSON = ROOT / "reports" / "composite_ingredients.json"

BASE = pd.Series({"A": 3.0, "B": 2.0, "C": 1.0, "D": 0.5, "E": 0.25})
# day bullish candidates: g3 g4 g7 g9 g10
FAKE = {
    "g3": {"A": True, "B": True, "C": False, "D": True},
    "g4": {"A": True, "B": False, "C": False},
    "g7": {"A": True, "B": True, "C": False},
    "g9": {"A": True, "C": False},
    "g10": {"A": True, "B": False, "C": False},
}
# passes: A 5, B 2, C 0, D 1, E none judged


@pytest.fixture
def fake_gates(monkeypatch):
    calls = []

    def make(name):
        def gate(history, sides, trigger=None, **kw):
            calls.append((name, dict(sides), trigger, kw))
            return dict(FAKE[name])
        return gate

    monkeypatch.setattr(G, "trigger_side_scores", lambda trigger, history: BASE.copy())
    monkeypatch.setattr(G, "GATES", {**G.GATES, **{g: make(g) for g in FAKE}})
    return calls


# ---------------------------------------------------------------- table and symmetry


def test_candidates_are_the_c1_cells_whose_keep_beat_the_complement():
    assert C.CANDIDATES == {
        "day_bearish": ("g1", "g2", "g3", "g4", "g8", "g10"),
        "day_bullish": ("g3", "g4", "g7", "g9", "g10"),
        "week_bullish": ("g1", "g4", "g5", "g6", "g9", "g10"),
        "week_bearish": ("g1", "g2", "g3", "g7", "g8", "g10"),
    }
    if not C1_JSON.exists():
        pytest.skip("no C1 report")
    cells = json.loads(C1_JSON.read_text())["cells"]
    table_of = {t: tb for tb, t in C.TABLES.items()}
    for c in cells:
        trig = next(k for k, v in G.TRIGGERS.items() if v.label == c["trigger"])
        g = c["gate"].lower()
        beat = c["keep_edge_pts"] > c["complement_edge_pts"]
        assert (g in C.CANDIDATES[table_of[trig]]) == beat, c["cell"]
        assert C.C1_KEEP_VS_COMPLEMENT[table_of[trig]][g] == (c["keep_edge_pts"], c["complement_edge_pts"])


def test_budget_and_counts():
    per = {t: sum(1 for tt, _ in C.CONFIGS if tt == t) for t in C.TABLES}
    assert per == {"day_bullish": 14, "day_bearish": 14, "week_bullish": 17, "week_bearish": 15}
    assert per["day_bullish"] + per["day_bearish"] <= 28 and per["week_bullish"] + per["week_bearish"] <= 60


def test_symmetry_every_key_exists_on_both_tables_where_the_gate_exists():
    for horizon, tables in C.HORIZON_TABLES.items():
        for s in C.SETTINGS[horizon]:
            built = [t for t in tables if (t, s.key) in C.CONFIGS]
            assert built, s.key
            for t in tables:
                trig = C.TABLES[t]
                if s.family == "threshold":
                    assert ((t, s.key) in C.CONFIGS) == ((trig, s.gate) in G.CELLS)
                elif s.family == "boost":
                    assert (t, s.key) in C.CONFIGS
                else:
                    assert ((t, s.key) in C.CONFIGS) == (s.value <= len(C.CANDIDATES[t]))
            keys = {C.config_key(t, C.CONFIGS[(t, s.key)]) for t in built}
            assert keys == {f"{horizon}_{s.key}"}
    one_sided = sorted(f"{h}_{s.key}" for h, ts in C.HORIZON_TABLES.items() for s in C.SETTINGS[h]
                       if sum((t, s.key) in C.CONFIGS for t in ts) == 1)
    assert one_sided == ["day_g2_cut0p6", "day_g2_cut0p8", "day_g9_near0p8", "day_g9_near0p9",
                         "week_g9_near0p8", "week_g9_near0p9"]


def test_no_vote_repeats_composite_v1():
    for (t, k), s in C.CONFIGS.items():
        if s.family == "vote" and s.value == len(C.CANDIDATES[t]):
            assert set(C.CANDIDATES[t]) != set(C.V1.COMPOSITES[t][1])


def test_g2_bullish_side_mirrors_the_cut():
    s = C.CONFIGS[("week_bullish", "g2_cut0p6")]
    assert C.gate_kwargs("week_bullish", s) == {"leader_bottom": 0.4}
    assert C.gate_kwargs("week_bearish", C.CONFIGS[("week_bearish", "g2_cut0p6")]) == {"leader_top": 0.6}


# ---------------------------------------------------------------- semantics


def test_vote_semantics(fake_gates):
    base, per_gate = C.candidate_verdicts("day_bullish", pd.DataFrame())
    assert [c[0] for c in fake_gates] == ["g3", "g4", "g7", "g9", "g10"]  # each gate asked once
    assert all(c[2] == "t04" and c[1] == {s: 1 for s in BASE.index} for c in fake_gates)
    expect = {1: ["A", "B", "D"], 2: ["A", "B"], 3: ["A"], 4: ["A"], 5: ["A"]}
    for k, kept in expect.items():
        assert sorted(C.vote_from(base, per_gate, k).index) == kept
        assert sorted(C.config_score("day_bullish", f"vote_k{k}", pd.DataFrame()).index) == kept
    # E: no gate judged it -> abstains even at k = 0
    assert "E" not in C.vote_from(base, per_gate, 0).index and "C" in C.vote_from(base, per_gate, 0).index


def test_vote_and_boost_share_one_set_of_verdicts(fake_gates):
    out = C.all_settings_from("day_bullish", pd.DataFrame())
    assert len(fake_gates) == 5
    assert set(out) == {k for t, k in C.CONFIGS if t == "day_bullish" and C.CONFIGS[(t, k)].family in ("vote", "boost")}


def test_boost_keeps_every_pick_and_never_flips_sign(fake_gates):
    for w in C.BOOST_WEIGHTS:
        s = C.boost_from(BASE, {g: FAKE[g] for g in FAKE}, w)
        assert list(s.index) == list(BASE.index)
        assert s["A"] == pytest.approx(3.0 * (1 + 5 * w)) and s["E"] == 0.25 and s["C"] == 1.0
    neg = -BASE
    s = C.boost_from(neg, FAKE, 1.0)
    assert (np.sign(s) == np.sign(neg)).all() and (s.abs() >= neg.abs()).all()


def test_boost_changes_the_top_order(fake_gates):
    s = C.config_score("day_bullish", "boost_w1p0", pd.DataFrame())
    assert s.abs().sort_values(ascending=False).index[:2].tolist() == ["A", "B"]
    assert BASE["D"] < BASE["C"] and s["D"] >= s["C"]  # D (1 pass) catches up with C (0 passes)


def test_threshold_and_vote_picks_are_a_subset_with_unchanged_scores(fake_gates):
    for (t, k), s in C.CONFIGS.items():
        if t != "day_bullish" or s.family == "boost":
            continue
        got = C.config_score(t, k, pd.DataFrame())
        assert set(got.index) <= set(BASE.index) and all(got[x] == BASE[x] for x in got.index)


def test_threshold_passes_the_real_keyword(fake_gates):
    C.config_score("day_bullish", "g9_near0p8", pd.DataFrame())
    assert fake_gates[-1][0] == "g9" and fake_gates[-1][3] == {"near_high": 0.8}


def test_no_trigger_picks_gives_empty_scores(monkeypatch):
    monkeypatch.setattr(G, "trigger_side_scores", lambda trigger, history: pd.Series(dtype=float))
    for t, k in C.CONFIGS:
        assert C.config_score(t, k, pd.DataFrame()).empty


def test_unknown_config_is_refused():
    with pytest.raises(ValueError):
        C.config("day_bullish", "g2_cut0p6")  # G2 does not exist for T04


# ---------------------------------------------------------------- threshold defaults equal C1


@pytest.fixture(scope="module")
def panel():
    return synthetic_panel(n_symbols=12, n_rows=330)


def test_threshold_keywords_at_their_default_equal_the_c1_gate(panel):
    for d in sorted(panel["date"].unique())[-3:]:
        h = truncate(panel, d)
        syms = sorted(h["symbol"].unique())
        for side in (1, -1):
            sides = {s: side for s in syms}
            assert G.g2(h, sides) == G.g2(h, sides, leader_top=None, leader_bottom=None)
            assert G.g2(h, sides) == G.g2(h, sides, leader_top=0.70, leader_bottom=0.30)
            assert G.g5(h, sides) == G.g5(h, sides, stress_quantile=0.5)
            assert G.g8(h, sides) == G.g8(h, sides, volume_multiple=1.5)
            assert G.g9(h, sides) == G.g9(h, sides, near_high=0.85)
        r = G.stress_reading(G._adjusted_tail(h))
        if r is not None:
            assert G.stress_reading(G._adjusted_tail(h), 0.5) == pytest.approx(r)


def test_thresholds_move_in_the_expected_direction(panel):
    h = truncate(panel, sorted(panel["date"].unique())[-1])
    sides = {s: 1 for s in h["symbol"].unique()}
    loose, tight = G.g8(h, sides, volume_multiple=1.25), G.g8(h, sides, volume_multiple=2.0)
    assert all(loose[s] or not tight[s] for s in tight)
    loose, tight = G.g9(h, sides, near_high=0.80), G.g9(h, sides, near_high=0.90)
    assert all(loose[s] or not tight[s] for s in tight)
    lo, hi = G.g5(h, sides, stress_quantile=0.4), G.g5(h, sides, stress_quantile=0.6)
    assert all(lo[s] or not hi[s] for s in hi)


def test_shared_tail_is_off_by_default_and_changes_nothing(panel):
    h = truncate(panel, sorted(panel["date"].unique())[-1])
    assert G._TAIL_CACHE is None
    plain = G._adjusted_tail(h)
    with G.shared_tail():
        a = G._adjusted_tail(h)
        assert G._adjusted_tail(h) is a
        with G.shared_tail():
            assert G._adjusted_tail(h) is a
    assert G._TAIL_CACHE is None
    pd.testing.assert_frame_equal(plain, a)


def test_on_a_real_panel_structure_holds(panel):
    for d in sorted(panel["date"].unique())[-2:]:
        h = truncate(panel, d)
        for table in C.TABLES:
            base = G.trigger_side_scores(C.TABLES[table], h)
            for key, s in C.all_settings_from(table, h).items():
                assert s.sort_index().equals(C.config_score(table, key, h).sort_index())
                if key.startswith("boost"):
                    assert set(s.index) == set(base.index)
                else:
                    assert set(s.index) <= set(base.index)


def test_modules_import_and_wrap_the_right_config(panel):
    h = truncate(panel, sorted(panel["date"].unique())[-1])
    for table, key in C.CONFIGS:
        mod = importlib.import_module(f"strategies.{gen.module_name(table, key)}")
        assert callable(mod.score) and callable(mod.rules_fired)
        assert mod.score.__doc__.startswith(C.config_id(table, key) + ":")
    for table, key in [("week_bullish", "boost_w0p5"), ("week_bearish", "vote_k1"), ("day_bearish", "g8_x1p25")]:
        mod = importlib.import_module(f"strategies.{gen.module_name(table, key)}")
        got = mod.score(h)
        assert got.sort_index().equals(C.config_score(table, key, h).sort_index())
        for s in list(got.index)[:2] + ["NOPE"]:
            text = mod.rules_fired(h, s)
            assert text.startswith(C.config_id(table, key) + ":")
            for word in ("buy", "sell", "target", "stop loss"):
                assert word not in text.lower()


def test_generator_check_is_clean():
    assert gen.main(["--check"]) == 0


def test_causality_audit_passes():
    result = run_all()
    assert result["passed"], result


# ---------------------------------------------------------------- held replays, card, catalog


def test_held_replays_cover_every_config_in_the_declared_folders_and_none_pending():
    folders = gen.folders()
    counts = {f: sum(1 for v in folders.values() if v == f) for f in ("week", "day_a", "day_b")}
    assert counts == {"week": 32, "day_a": 14, "day_b": 14}
    # families A and B fill day_a first; both tables of a key share a folder
    day_a = [k for (t, k), f in folders.items() if f == "day_a"]
    assert all(C.CONFIGS[(t, k)].family in ("vote", "boost") for (t, k), f in folders.items() if f == "day_a")
    for (t, k), f in folders.items():
        other = [f2 for (t2, k2), f2 in folders.items() if k2 == k and C.horizon_of(t2) == C.horizon_of(t)]
        assert len(set(other)) == 1
    assert day_a
    for (table, key), folder in folders.items():
        exp_id = gen.experiment_id(table, key)
        # held/ first, pending/ once queued, gone when the result lands in done/
        path = HELD / folder / f"{exp_id}.yml"
        if not path.exists():
            path = PENDING / f"{exp_id}.yml"
        if not path.exists():
            assert (DONE / exp_id).exists()
            continue
        assert yaml.safe_load(path.read_text()) == {
            "id": exp_id,
            "strategy": f"strategies.{gen.module_name(table, key)}",
            "split": "train",
            "horizon": C.horizon_of(table),
            "dates": {"start": "2015-01-01", "end": "2020-12-31"},
        }


def test_queue_writes_nothing_twice(tmp_path):
    exp = tmp_path / "experiments"
    catalog = tmp_path / "catalog.csv"
    catalog.write_bytes(CATALOG.read_bytes())
    first = gen.queue(exp, catalog)
    assert len(first) == len(C.CONFIGS) and not (exp / "pending").exists()
    assert gen.queue(exp, catalog) == []
    assert catalog.read_bytes() == CATALOG.read_bytes()  # every row already present


def test_card_and_catalog_rows_cover_every_config():
    card = yaml.safe_load(CARD.read_text())
    ids = {c["id"] for c in card["configs"]}
    assert ids == {C.config_id(t, k) for t, k in C.CONFIGS} and len(ids) == 60
    for c in card["configs"]:
        t = c["table"].replace(" ", "_")
        k = next(kk for tt, kk in C.CONFIGS if tt == t and C.config_id(tt, kk) == c["id"])
        assert c["key"] == C.config_key(t, C.CONFIGS[(t, k)]) and c["replay"] == gen.experiment_id(t, k)
        assert c["folder"] == f"experiments/held/v2/{gen.folders()[(t, k)]}"
    sel = card["default_params"]["selection"]
    assert sel["fit_years"] == list(rep.FIT_YEARS) and sel["check_years"] == list(rep.CHECK_YEARS)
    assert sel["min_date_coverage_of_trigger"] == rep.MIN_COVERAGE and sel["min_fit_years"] == rep.MIN_FIT_YEARS
    assert {k: list(v) for k, v in C.CANDIDATES.items()} == card["default_params"]["candidates"]
    rows = {r[0]: r for r in csv.reader(CATALOG.read_text().splitlines()) if r}
    for t, k in C.CONFIGS:
        assert C.config_id(t, k) in rows and rows[C.config_id(t, k)][-1] == "held"
    text = CARD.read_text().lower()
    for word in (" buy", " sell", "target"):
        assert word not in text


# ---------------------------------------------------------------- report

YEARS = list(range(2015, 2021))


def _block(edge, year_edges, n_dates=100):
    return {"n_picks": 5 * n_dates, "n_dates": n_dates, "edge": edge, "edge_t": 2.0,
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
    assert t["configs"] == [] and len(t["pending"]) == 60
    assert all(not s["final"] for s in t["selections"])
    md = rep.render_md(t)
    assert "(none yet)" in md and "provisional" in md
    assert rep.main(["--done", str(done), "--md", str(tmp_path / "a.md"), "--json", str(tmp_path / "a.json")]) == 0


def _fill_day(done, overrides):
    flat = [0.02] * 6
    _write(done, "t04-connors-rsi2-day", "bullish", _block(0.02, flat, 100))
    _write(done, "e2a-day", "bearish", _block(0.02, flat, 100))
    for t, k in C.CONFIGS:
        if C.horizon_of(t) != "day":
            continue
        side = "bullish" if t.endswith("bullish") else "bearish"
        _write(done, gen.experiment_id(t, k), side, overrides.get((t, k), _block(0.02, flat, 100)))


def test_report_picks_the_best_key_eligible_on_both_sides(tmp_path):
    done = tmp_path / "done"
    good = _block(0.03, [0.03] * 6, 80)
    better_one_side = _block(0.05, [0.05] * 6, 80)
    _fill_day(done, {
        ("day_bullish", "vote_k2"): good, ("day_bearish", "vote_k2"): good,
        ("day_bullish", "boost_w1p0"): _block(0.025, [0.025] * 6, 100),
        ("day_bearish", "boost_w1p0"): _block(0.025, [0.025] * 6, 100),
        ("day_bullish", "vote_k3"): better_one_side,  # eligible on bullish only
        ("day_bearish", "vote_k4"): _block(0.06, [0.06] * 6, 30),  # coverage 30%: not eligible
        ("day_bearish", "vote_k5"): _block(0.06, [0.06] * 4 + [0.01, 0.06], 80),  # 2019 below: not eligible
    })
    t = rep.build(done)
    day = next(s for s in t["selections"] if s["horizon"] == "day")
    assert day["final"] and day["selected_key"] == "day_vote_k2"
    assert day["tables"]["day_bullish"]["config"] == "COMPOSITE_V2_DAY_BULLISH_VOTE_K2"
    assert not day["tables"]["day_bearish"]["one_side_only"]
    assert set(day["keys_eligible_on_both"]) == {"day_vote_k2", "day_boost_w1p0"}
    rows = {r["config"]: r for r in t["configs"]}
    assert not rows["COMPOSITE_V2_DAY_BEARISH_VOTE_K4"]["eligible_coverage"]
    assert not rows["COMPOSITE_V2_DAY_BEARISH_VOTE_K5"]["eligible_check"]
    assert rows["COMPOSITE_V2_DAY_BULLISH_VOTE_K2"]["fit_gain_pts"] == 1.0
    week = next(s for s in t["selections"] if s["horizon"] == "week")
    assert not week["final"]


def test_report_falls_back_to_one_side_and_to_the_trigger(tmp_path):
    done = tmp_path / "done"
    _fill_day(done, {
        ("day_bullish", "g9_near0p8"): _block(0.04, [None, 0.04, 0.04, 0.04, 0.04, 0.04], 60),  # 3 fit years: ok
        ("day_bullish", "g9_near0p9"): _block(0.05, [None, None, 0.05, 0.05, 0.05, 0.05], 60),  # 2 fit years: no
    })
    t = rep.build(done)
    day = next(s for s in t["selections"] if s["horizon"] == "day")
    assert day["selected_key"] is None
    b, e = day["tables"]["day_bullish"], day["tables"]["day_bearish"]
    assert b["config"] == "COMPOSITE_V2_DAY_BULLISH_G9_NEAR0P8" and b["one_side_only"]
    assert e["decision"] == "keep plain E2A" and e["config"] is None
    assert "one side only" in rep.render_md(t).lower() or "| yes |" in rep.render_md(t)
