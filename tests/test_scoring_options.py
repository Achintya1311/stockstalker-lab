"""Opt-in scoring options `yardstick` and `top_n` (owner-approved engine change, 15 Nov 2026; BULLISH_PLAN B2, B3).

Covers: the relative hit against the universe median (right, wrong, ties, bearish mirror), the relative market
line (exact share, ties), relative scoring through `score_picks` by hand, `top_n` (N picks, fewer when fewer
candidates), the yml schema (unknown keys and bad values refused), refusal on a validation split, the queue
path (manifest keys, results, trials notes, no leaderboard row), byte-identical outputs when both keys are
absent or written at their defaults (`tests/golden/no_exit_golden.json`), the picks/source skip, the held
ymls (held -> pending -> done) and `scripts/bull_report.py`.
"""

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from engine.experiment_report import Context, answer_validation, score_picks, select
from engine.run_queue import parse_scoring_options
from engine.scoring import relative_hit, relative_market_line, universe_median_move
from tests._horizon_dataset import make_dataset
from tests._queue_outputs import fingerprint, run as run_queue

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = Path(__file__).resolve().parent / "golden" / "no_exit_golden.json"


def _frames(moves_by_symbol: dict, date="2015-03-02"):
    moves = pd.DataFrame({"date": date, "symbol": list(moves_by_symbol), "move": list(moves_by_symbol.values())})
    universe = moves[["date", "symbol"]].assign(in_universe=True)
    return moves, universe


# ---- relative hit and market line ----------------------------------------------

def test_relative_hit_right_wrong_ties_and_bearish_mirror():
    move = pd.Series([0.03, -0.01, 0.01, 0.00])
    median = pd.Series([0.01] * 4)
    assert relative_hit(move, median, 1).tolist() == [True, False, False, False]  # equal to median = miss
    assert relative_hit(move, median, -1).tolist() == [False, True, False, True]
    # A falling stock can be a right bullish pick when the median fell more.
    assert relative_hit(pd.Series([-0.01]), pd.Series([-0.04]), 1).tolist() == [True]


def test_relative_market_line_is_the_exact_share_beating_the_median():
    moves, uni = _frames({"A": 0.05, "B": 0.02, "C": 0.01, "D": -0.01, "E": -0.03})  # odd n: median C
    assert universe_median_move(moves, uni).iloc[0] == pytest.approx(0.01)
    assert relative_market_line(moves, uni, 1).iloc[0] == pytest.approx(2 / 5)
    assert relative_market_line(moves, uni, -1).iloc[0] == pytest.approx(2 / 5)
    moves, uni = _frames({"A": 0.02, "B": 0.01, "C": 0.01, "D": 0.01, "E": -0.02, "F": -0.03})  # ties at median
    assert relative_market_line(moves, uni, 1).iloc[0] == pytest.approx(1 / 6)
    assert relative_market_line(moves, uni, -1).iloc[0] == pytest.approx(2 / 6)
    moves, uni = _frames({s: v for s, v in zip("ABCDEF", [0.03, 0.02, 0.01, -0.01, -0.02, -0.03])})
    assert relative_market_line(moves, uni, 1).iloc[0] == pytest.approx(0.5)  # even n, no ties: 50% exactly
    # Out-of-universe stocks do not count.
    uni.loc[uni["symbol"] == "A", "in_universe"] = False
    assert relative_market_line(moves, uni, 1).iloc[0] == pytest.approx(2 / 5)


@pytest.fixture(scope="module")
def ctx():
    return Context(make_dataset())


def _hand_relative(ctx, picks, side, horizon):
    moves = ctx.moves(horizon).merge(ctx.in_universe, on=["date", "symbol"])
    med = moves.groupby("date")["move"].median()
    j = picks.merge(moves, on=["date", "symbol"])
    j["hit"] = ((j["move"] - j["date"].map(med)) * side) > 0
    line = moves.assign(b=((moves["move"] - moves["date"].map(med)) * side) > 0).groupby("date")["b"].mean()
    per = j.groupby("date")["hit"].mean()
    return float(j["hit"].mean()), float(line.loc[per.index].mean()), float((per - line.loc[per.index]).mean())


@pytest.mark.parametrize("horizon", ["day", "week", "month"])
def test_relative_scoring_matches_a_hand_computation(ctx, horizon):
    ds = ctx.dataset
    dates = sorted(ctx.moves(horizon)["date"].unique())[25:45]
    rng = np.random.default_rng(1)
    picks = pd.DataFrame([(d, s, float(rng.normal())) for d in dates for s in sorted(ds["symbol"].unique())],
                         columns=["date", "symbol", "score"])
    res = score_picks(picks, horizon, ctx, yardstick="relative")
    absolute = score_picks(picks, horizon, ctx)
    for side, name in ((1, "bullish"), (-1, "bearish")):
        top = select(picks.merge(ctx.in_universe, on=["date", "symbol"]), side, ctx.k)
        acc, line, edge = _hand_relative(ctx, top, side, horizon)
        m = res["top"][name]
        assert m["accuracy"] == pytest.approx(acc) and m["market_line"] == pytest.approx(line)
        assert m["edge"] == pytest.approx(edge)
        assert 0.4 < m["market_line"] <= 0.5
        # Directional move after costs is the usual one; picks are the same picks.
        a = absolute["top"][name]
        assert m["directional_move"] == a["directional_move"] and m["n_picks"] == a["n_picks"]
        assert "excess_move" in m and "excess_move" not in a
        if horizon == "month":
            assert m["interval_method"] == a["interval_method"] and m["edge_interval"] is not None


def test_top_n_keeps_n_picks_and_fewer_when_fewer_candidates(ctx):
    picks = pd.DataFrame({"date": ["d1"] * 12 + ["d2"] * 3, "symbol": [f"S{i:02d}" for i in range(12)] + ["S00", "S01", "S02"],
                          "score": list(np.linspace(1, 12, 12)) + [1.0, 2.0, -3.0]})
    got = select(picks, 1, 10)
    assert (got["date"] == "d1").sum() == 10 and (got["date"] == "d2").sum() == 2
    assert set(got.loc[got["date"] == "d1", "symbol"]) == {f"S{i:02d}" for i in range(2, 12)}
    days = sorted(ctx.moves("day")["date"].unique())[30:40]
    p = pd.DataFrame([(d, s, i - 5.5) for d in days for i, s in enumerate(sorted(ctx.dataset["symbol"].unique()))],
                     columns=["date", "symbol", "score"])
    assert score_picks(p, "day", ctx, top_n=3)["top"]["bullish"]["n_picks"] == 30
    assert score_picks(p, "day", ctx, top_n=10)["top"]["bullish"]["n_picks"] == 60  # only 6 positive scores a day
    assert score_picks(p, "day", ctx)["top"]["bullish"]["n_picks"] == 50


# ---- yml schema -----------------------------------------------------------------

BASE = {"id": "x", "strategy": "s", "split": "train", "horizon": "week", "dates": {"start": "a", "end": "b"}}


def test_parse_scoring_options_returns_only_non_default_values():
    assert parse_scoring_options(BASE) == {}
    assert parse_scoring_options({**BASE, "yardstick": "absolute", "top_n": 5}) == {}
    assert parse_scoring_options({**BASE, "yardstick": "relative", "top_n": 10}) == {"yardstick": "relative", "top_n": 10}
    assert parse_scoring_options({**BASE, "exit": {}, "train_experiment": "t"}) == {}


@pytest.mark.parametrize("extra", [{"yardstik": "relative"}, {"topn": 10}, {"yardstick": "median"},
                                   {"yardstick": None}, {"top_n": 0}, {"top_n": 51}, {"top_n": "10"},
                                   {"top_n": True}, {"top_n": 10.0}])
def test_parse_scoring_options_rejects_unknown_keys_and_bad_values(extra):
    with pytest.raises(ValueError):
        parse_scoring_options({**BASE, **extra})


# ---- the queue --------------------------------------------------------------------

def test_absent_or_default_options_keep_every_queue_output_byte_identical(tmp_path, monkeypatch):
    run_queue(tmp_path, monkeypatch)
    assert fingerprint(tmp_path) == json.loads(GOLDEN.read_text())
    ref = tmp_path / "explicit"
    ref.mkdir()
    run_queue(ref, monkeypatch, extra={k: {"yardstick": "absolute", "top_n": 5} for k in ("q-day", "q-week", "q-month")})
    assert fingerprint(ref) == json.loads(GOLDEN.read_text())


def test_options_reach_manifest_results_and_trials_but_not_the_leaderboard(tmp_path, monkeypatch):
    run_queue(tmp_path, monkeypatch, extra={"q-week": {"yardstick": "relative"}, "q-month": {"top_n": 3}})
    want, got = json.loads(GOLDEN.read_text()), fingerprint(tmp_path)
    for name in ("done/q-day/results.json", "done/q-week/picks.json", "done/q-month/picks.json"):
        assert got[name] == want[name]  # the replay itself is unchanged
    done = tmp_path / "done"
    assert json.loads((done / "q-week" / "manifest.json").read_text())["yardstick"] == "relative"
    assert json.loads((done / "q-month" / "manifest.json").read_text())["top_n"] == 3
    week = json.loads((done / "q-week" / "results.json").read_text())
    month = json.loads((done / "q-month" / "results.json").read_text())
    assert week["yardstick"] == "relative" and "top_n" not in week and week["picks_per_table"] == 5
    assert month["top_n"] == 3 and month["picks_per_table"] == 3 and "yardstick" not in month
    assert 0.4 < week["selections"]["top"]["bullish"]["market_line"] <= 0.5
    assert "yardstick relative" in (done / "q-week" / "results.md").read_text()
    n_dates = month["selections"]["top"]["bullish"]["n_dates"]
    assert month["selections"]["top"]["bullish"]["n_picks"] <= 3 * n_dates
    board = (tmp_path / "board.md").read_text()
    assert "| q-day |" in board and "| q-week |" not in board and "| q-month |" not in board
    with open(tmp_path / "trials.csv", newline="") as f:
        rows = {r["trial_id"]: r for r in csv.DictReader(f)}
    assert "yardstick relative" in rows["q-week-bullish"]["notes"]
    assert "top_n 3" in rows["q-month-bearish"]["notes"]
    assert "opt-in" not in rows["q-day-bullish"]["notes"]


@pytest.mark.parametrize("extra,word", [({"yardstick": "relative"}, "train-only"), ({"top_n": 10}, "train-only"),
                                        ({"yardstik": "relative"}, "unknown experiment keys")])
def test_options_on_a_validation_split_or_misspelt_are_refused(tmp_path, monkeypatch, extra, word):
    run_queue(tmp_path, monkeypatch, extra={"q-week": {"split": "validation", "train_experiment": "q-day",
                                                       "dates": {"start": "2016-04-01", "end": "2016-06-30"}, **extra}})
    reason = json.loads((tmp_path / "done" / "q-week" / "refused.json").read_text())["reason"]
    assert word in reason and not (tmp_path / "holdout.csv").exists()
    assert not (tmp_path / "pending" / "q-week.yml").exists()


def test_answer_validation_refuses_a_train_experiment_scored_on_another_yardstick(tmp_path, ctx):
    (tmp_path / "t").mkdir()
    (tmp_path / "t" / "results.json").write_text(json.dumps({"horizon": "week", "yardstick": "relative",
                                                             "selections": {"top": {}}}))
    exp = {"id": "v", "strategy": "s", "horizon": "week", "train_experiment": "t"}
    status = answer_validation(pd.DataFrame(columns=["date", "symbol", "score"]), exp, ctx, tmp_path, tmp_path / "h.csv")
    assert status.startswith("refused") and not (tmp_path / "h.csv").exists()


def test_picks_source_skips_opt_in_replays(tmp_path):
    from picks.source import experiment_id
    for eid, extra in (("e2a-day", {}), ("e2a-rel", {"yardstick": "relative"}), ("e2a-top", {"top_n": 10})):
        (tmp_path / eid).mkdir()
        (tmp_path / eid / "manifest.json").write_text(json.dumps(
            {"id": eid, "strategy": "strategies.e2a_a02_crowded", "split": "train", "horizon": "day", **extra}))
    assert experiment_id("e2a_a02_crowded@v1", "day", tmp_path) == "e2a-day"


# ---- held ymls and the report ---------------------------------------------------

HELD_BULL = {
    "b2-m01-relative-week": ("strategies.m01_momentum_12_1", "week", {"yardstick": "relative"}),
    "b2-m01-relative-month": ("strategies.m01_momentum_12_1", "month", {"yardstick": "relative"}),
    "b2-a04-relative-week": ("strategies.a04_52_week_high", "week", {"yardstick": "relative"}),
    "b2-a04-relative-month": ("strategies.a04_52_week_high", "month", {"yardstick": "relative"}),
    "b2-m02-relative-month": ("strategies.m02_leader_pullback", "month", {"yardstick": "relative"}),
    "b3-m01-top10-month": ("strategies.m01_momentum_12_1", "month", {"top_n": 10}),
    "b3-m01-top15-month": ("strategies.m01_momentum_12_1", "month", {"top_n": 15}),
    "b3-m01-top20-month": ("strategies.m01_momentum_12_1", "month", {"top_n": 20}),
}
LIVE_MODULES = {"strategies.t04_connors_rsi2", "strategies.e2a_a02_crowded", "strategies.composite_v1_day_bearish",
                "strategies.a05b_max_effect_ranked", "strategies.a01_weekly_reversal"}


def test_held_bull_ymls_are_train_runs_with_their_options():
    import importlib
    held, pending, done = (ROOT / "experiments" / x for x in ("held/bull/week_month", "pending", "done"))
    for exp_id, (module, horizon, options) in HELD_BULL.items():
        # held/bull/week_month/ first, pending/ once queued, gone when the result lands in done/
        where = [p for p in (held / f"{exp_id}.yml", pending / f"{exp_id}.yml") if p.exists()]
        assert where or (done / exp_id).exists(), exp_id
        assert len(where) <= 1, exp_id
        for y in where:
            exp = yaml.safe_load(y.read_text())
            assert exp["id"] == y.stem and exp["strategy"] == module and exp["horizon"] == horizon
            assert exp["split"] == "train" and module not in LIVE_MODULES
            assert {str(v) for v in exp["dates"].values()} == {"2015-01-01", "2020-12-31"}
            assert parse_scoring_options(exp) == options
            assert hasattr(importlib.import_module(module), "score")


def test_bull_report_rows_pass_column_and_waiting(tmp_path, monkeypatch):
    run_queue(tmp_path, monkeypatch, extra={"q-week": {"yardstick": "relative"}})
    done = tmp_path / "done"
    (done / "q-week").rename(done / "b2-q-relative-week")
    r = json.loads((done / "b2-q-relative-week" / "results.json").read_text())
    r["id"] = "b2-q-relative-week"
    (done / "b2-q-relative-week" / "results.json").write_text(json.dumps(r))
    good = {**r, "id": "b3-good-month", "horizon": "month", "top_n": 10, "selections": {"top": {"bullish": {
        "n_picks": 900, "n_dates": 250, "accuracy": 0.6, "market_line": 0.5, "edge": 0.05, "edge_t": 3.1,
        "edge_interval": [0.02, 0.08], "directional_move": 0.004,
        "by_year": [{"year": y, "edge": 0.05 if y != 2018 else -0.01} for y in range(2015, 2021)]}}}}
    good.pop("yardstick", None)
    (done / "b3-good-month").mkdir()
    (done / "b3-good-month" / "results.json").write_text(json.dumps(good))
    held = tmp_path / "held"
    held.mkdir()
    (held / "b1-zz-week.yml").write_text("id: b1-zz-week\n")
    from scripts import bull_report
    text = bull_report.render(done, held, tmp_path / "pending")
    table = [l for l in text.splitlines() if l.startswith("| b")]
    assert len(table) == 3
    rel = next(l for l in table if l.startswith("| b2-q-relative-week |"))
    assert "| relative | 5 |" in rel and rel.count("|") == len(bull_report.COLUMNS) + 1
    goodrow = next(l for l in table if l.startswith("| b3-good-month |"))
    assert goodrow.endswith("| **yes** |") and "| 5 / 6 |" in goodrow and "+2.00 to +8.00" in goodrow
    assert "| b1-zz-week | not run yet |" in text and "| q-" not in text
    assert "Passing: b3-good-month." in text and "+4.36" in text
    for word in ("buy", "sell", "target price", "entry price", "stop loss"):
        assert word not in text.lower()
