import csv
import json
import sys

import pandas as pd
import pytest
import yaml

from engine.experiment_report import (
    SCORER_VERSION,
    Context,
    answer_validation,
    record_trials,
    score_done,
    score_picks,
    select,
    write_leaderboard,
)
from engine.holdout_report import LEDGER_FIELDS
from engine.scoring import edge
from tests._picks_dataset import make_dataset, trading_dates

DATES = trading_dates(60)
PICK_DATES = DATES[30:]
MOVES = {"UP": 0.01, "UP2": 0.005, "DOWN": -0.01, "FLAT": 0.0}
SCORES = {"UP": 2.0, "UP2": 1.0, "DOWN": -2.0, "FLAT": 0.0}


def _picks():
    return pd.DataFrame([{"date": d, "symbol": s, "score": v} for d in PICK_DATES for s, v in SCORES.items()])


@pytest.fixture(scope="module")
def ctx():
    return Context(make_dataset(MOVES, DATES))


def test_select_keeps_the_k_largest_absolute_scores_per_date_and_drops_zero():
    picks = pd.DataFrame({"date": ["d"] * 8, "symbol": list("ABCDEFGH"), "score": [7, 6, 5, 4, 3, 2, 1, 0]})
    assert list(select(picks, 1, 5)["symbol"]) == ["A", "B", "C", "D", "E"]
    assert len(select(picks, 1, None)) == 7  # zero is neither side
    assert select(picks, -1, 5).empty


def test_known_signal_gives_expected_accuracy_edge_and_leak_alarm(ctx):
    r = score_picks(_picks(), "day", ctx)["top"]
    bull, bear = r["bullish"], r["bearish"]
    # Bullish picks UP and UP2 always rise; 2 of 4 universe names rise each day.
    assert bull["accuracy"] == 1.0 and bull["market_line"] == pytest.approx(0.5) and bull["edge"] == pytest.approx(0.5)
    # Bearish pick DOWN always falls; 1 of 4 falls each day.
    assert bear["accuracy"] == 1.0 and bear["edge"] == pytest.approx(0.75)
    assert bull["n_picks"] == 2 * len(PICK_DATES) and bull["coverage"] == 1.0
    assert bull["leak_alarm"] and bear["leak_alarm"]  # perfect accuracy must trip the alarm
    assert bull["directional_move"] > 0


def test_edge_matches_engine_scoring_edge(ctx):
    picks = _picks().merge(ctx.in_universe, on=["date", "symbol"])
    for side, name in ((1, "bullish"), (-1, "bearish")):
        for sel, k in (("top", 1), ("all", None)):
            ctx.k = k if k else 5
            got = score_picks(_picks(), "day", ctx)[sel][name]["edge"]
            want = edge(select(picks, side, ctx.k if sel == "top" else None), ctx.moves("day"), ctx.universe)
            assert got == pytest.approx(want)
    ctx.k = 5


def _write_experiment(done_dir, exp_id, split="train"):
    d = done_dir / exp_id
    d.mkdir(parents=True)
    (d / "manifest.json").write_text(json.dumps({"id": exp_id, "strategy": "s", "split": split, "horizon": "day"}))
    (d / "picks.json").write_text(_picks().to_json(orient="records"))


def test_score_done_scores_train_once_and_skips_other_splits(ctx, tmp_path):
    _write_experiment(tmp_path, "a")
    _write_experiment(tmp_path, "b", split="validation")
    assert score_done(ctx, tmp_path) == ["a"]
    assert not (tmp_path / "b" / "results.json").exists()
    assert score_done(ctx, tmp_path) == []  # already current
    r = json.loads((tmp_path / "a" / "results.json").read_text())
    assert r["scorer_version"] == SCORER_VERSION and r["selections"]["top"]["bullish"]["edge"] == pytest.approx(0.5)
    r["scorer_version"] = -1
    (tmp_path / "a" / "results.json").write_text(json.dumps(r))
    assert score_done(ctx, tmp_path) == ["a"]  # stale version is rescored


def _fake_results(done_dir, exp_id, strategy, sides):
    d = done_dir / exp_id
    d.mkdir(parents=True)
    top = {side: {"n_picks": n, "edge": e, "edge_t": t, "accuracy": 0.55, "market_line": 0.5,
                  "directional_move": dm, "positive_year_share": 1.0, "leak_alarm": False}
           for side, (n, e, t, dm) in sides.items()}
    (d / "results.json").write_text(json.dumps({"id": exp_id, "strategy": strategy, "split": "train",
                                                "horizon": "day", "selections": {"top": top}}))


def test_leaderboard_ranks_by_t_flags_small_samples_and_drops_engine_checks(tmp_path):
    done = tmp_path / "done"
    _fake_results(done, "big", "strategies.big", {"bullish": (4000, 0.03, 4.5, 0.001), "bearish": (4000, 0.01, 1.0, -0.001)})
    _fake_results(done, "tiny", "strategies.tiny", {"bullish": (40, 0.12, 1.4, 0.008), "bearish": (40, -0.02, -0.5, -0.002)})
    _fake_results(done, "smoke", "strategies.engine_smoketest", {"bullish": (10, 0.08, 0.5, 0.001), "bearish": (10, 0.0, None, 0.0)})
    ledger = tmp_path / "trials.csv"
    assert record_trials(done, ledger) == 4  # engine check excluded
    assert record_trials(done, ledger) == 0  # never re-recorded
    assert write_leaderboard(done, tmp_path / "board.md", ledger) == 4
    board = (tmp_path / "board.md").read_text()
    order = [board.index(f"| {r} |") for r in ("big | day | bullish", "tiny | day | bullish", "big | day | bearish")]
    assert order == sorted(order)  # t 4.5, then 1.4, then 1.0, despite tiny's larger edge
    assert "smoke" not in board
    assert "Trials recorded: 4. Gate 2's bar at that count: t >= 3." in board
    big_bull = next(l for l in board.splitlines() if l.startswith("| big | day | bullish"))
    tiny_bull = next(l for l in board.splitlines() if l.startswith("| tiny | day | bullish"))
    assert "| yes |" in big_bull and big_bull.endswith("| candidate |")
    assert tiny_bull.endswith("| too few picks |")


def _ledger_rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def test_answer_validation_waits_spends_once_and_never_re_asks(ctx, tmp_path):
    ledger = tmp_path / "ledger.csv"
    exp = {"id": "a-val", "strategy": "s", "horizon": "day", "train_experiment": "a"}
    assert answer_validation(_picks(), exp, ctx, tmp_path, ledger).startswith("waiting")
    _write_experiment(tmp_path, "a")
    score_done(ctx, tmp_path)
    assert answer_validation(_picks(), exp, ctx, tmp_path, ledger) == "done"
    rows = _ledger_rows(ledger)
    assert [r["query_id"] for r in rows] == ["a-val-bullish", "a-val-bearish"]
    released = json.loads((tmp_path / "a-val" / "holdout.json").read_text())["released"]
    assert set(released) == {"bullish", "bearish"}
    assert answer_validation(_picks(), exp, ctx, tmp_path, ledger) == "done"
    assert len(_ledger_rows(ledger)) == 2


def test_answer_validation_waits_when_the_weekly_budget_cannot_cover_both_sides(ctx, tmp_path):
    _write_experiment(tmp_path, "a")
    score_done(ctx, tmp_path)
    ledger = tmp_path / "ledger.csv"
    now = pd.Timestamp.now(tz="UTC").isoformat()
    with open(ledger, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LEDGER_FIELDS)
        w.writeheader()
        for i in range(59):  # config/splits.yml allows 60 a week
            w.writerow({"query_id": f"q{i}", "timestamp": now})
    exp = {"id": "a-val", "strategy": "s", "horizon": "day", "train_experiment": "a"}
    assert answer_validation(_picks(), exp, ctx, tmp_path, ledger).startswith("waiting")
    assert len(_ledger_rows(ledger)) == 59


def test_main_refuses_test_split_and_never_writes_a_validation_pick_log(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(tmp_path))
    (tmp_path / "flat_strategy.py").write_text(
        "import pandas as pd\n\ndef score(history):\n"
        "    s = history['symbol'].unique()\n    return pd.Series([1.0] * len(s), index=s)\n")
    data = tmp_path / "dataset.parquet"
    make_dataset(MOVES, DATES).to_parquet(data, index=False)
    pending, done = tmp_path / "pending", tmp_path / "done"
    pending.mkdir()
    base = {"strategy": "flat_strategy", "horizon": "day", "dates": {"start": DATES[30], "end": DATES[-1]}}
    (pending / "t.yml").write_text(yaml.dump({**base, "id": "t", "split": "test"}))
    (pending / "v.yml").write_text(yaml.dump({**base, "id": "v", "split": "validation", "train_experiment": "missing"}))
    splits = {"train": {"start": DATES[0], "end": DATES[29]},
              "validation": {"start": DATES[30], "end": DATES[-1], "max_queries_per_week": 60}}
    monkeypatch.setattr("engine.run_queue.load_splits", lambda *a, **k: splits)
    monkeypatch.setattr(sys, "argv", ["run_queue.py", "--data", str(data), "--pending", str(pending),
                                      "--done", str(done), "--leaderboard", str(tmp_path / "board.md"),
                                      "--market-line-report", str(tmp_path / "ml.md"),
                                      "--selftest-report", str(tmp_path / "st.md"),
                                      "--champion-report", str(tmp_path / "ch.md"),
                                      "--holdout-ledger", str(tmp_path / "ledger.csv")])
    from engine.run_queue import main
    main()
    assert (done / "t" / "refused.json").exists() and not (pending / "t.yml").exists()
    assert (pending / "v.yml").exists()  # waiting for its train results
    assert not (done / "v" / "picks.json").exists()
