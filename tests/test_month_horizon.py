"""Month horizon (owner-approved additive engine change, 14 Nov 2026).

Covers: day and week outputs byte-identical to the pre-change engine (frozen in
`tests/golden/horizon_golden.json`, produced by the engine before this change),
the four-week outcome window, no leakage across split boundaries, the block
interval method, costs, and the queue / report / leaderboard / trials /
validation paths at `horizon: month`.
"""

import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from engine.experiment_report import Context, record_trials, render, score_picks, write_leaderboard
from engine.replay import SplitViolation, run_dates
from engine.run_queue import month_pick_dates, pick_dates_for_horizon, run_experiment
from engine.scoring import (
    DELIVERY_COST,
    FUTURES_COST,
    MONTH_BLOCK,
    MONTH_INTERVAL_METHOD,
    block_bootstrap_interval,
    block_t,
    directional_move_after_costs,
    edge,
    market_line,
    month_moves,
    month_window_ends,
    moves_any_horizon,
    moves_for_horizon,
)
from tests._horizon_dataset import make_dataset, make_picks

GOLDEN = Path(__file__).resolve().parent / "golden" / "horizon_golden.json"


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


@pytest.fixture(scope="module")
def ds():
    return make_dataset()


@pytest.fixture(scope="module")
def ctx(ds):
    return Context(ds)


# ---- day and week unchanged ----------------------------------------------------

@pytest.mark.parametrize("horizon", ["day", "week"])
def test_day_and_week_outputs_are_byte_identical_to_the_pre_change_engine(horizon, ds, ctx):
    want = json.loads(GOLDEN.read_text())[horizon]
    dates = sorted(ds["date"].unique())
    pdates = pick_dates_for_horizon(dates, "2015-02-15", "2016-05-31", horizon)
    picks = make_picks(pdates)
    moves = moves_for_horizon(ds, horizon)
    res = score_picks(picks, horizon, ctx)
    bull = picks[picks["score"] > 0][["date", "symbol"]].assign(side=1)
    sides = picks.assign(side=(picks["score"] > 0) * 2 - 1)[["date", "symbol", "side"]]
    assert len(pdates) == want["n_pick_dates"] and _sha("\n".join(pdates)) == want["pick_dates_sha"]
    assert _sha(moves.to_csv(index=False)) == want["moves_csv_sha"]
    assert _sha(moves_any_horizon(ds, horizon).to_csv(index=False)) == want["moves_csv_sha"]
    assert _sha(ctx.moves(horizon).to_csv(index=False)) == want["moves_csv_sha"]
    assert _sha(market_line(moves, ctx.universe, 1).to_csv()) == want["market_line_bull_csv_sha"]
    assert edge(bull, moves, ctx.universe) == want["edge_bull"]
    assert directional_move_after_costs(sides, moves) == want["dir_move"]
    assert json.dumps(res, sort_keys=True) == want["score_picks_json"]
    assert "edge_interval" not in json.dumps(res) and "interval_method" not in json.dumps(res)
    manifest = {"id": "g", "strategy": "s", "horizon": horizon, "split": "train"}
    assert _sha(render(manifest, res, ctx.k)) == want["render_sha"]


def _write_strategy(tmp_path, monkeypatch, name="always_bull"):
    monkeypatch.syspath_prepend(str(tmp_path))
    (tmp_path / f"{name}.py").write_text(
        "import pandas as pd\n\ndef score(history):\n"
        "    s = history['symbol'].unique()\n    return pd.Series([1.0] * len(s), index=s)\n")
    return name


@pytest.mark.parametrize("horizon", ["day", "week"])
def test_run_experiment_day_and_week_take_the_old_path(horizon, ds, tmp_path, monkeypatch):
    name = _write_strategy(tmp_path, monkeypatch)
    import importlib
    splits = {"train": {"start": "2015-01-01", "end": "2015-12-31"}}
    exp = {"strategy": name, "split": "train", "horizon": horizon, "dates": {"start": "2015-03-01", "end": "2015-05-31"}}
    picks, h = run_experiment(ds, exp, splits)
    dates = pick_dates_for_horizon(sorted(ds["date"].unique()), "2015-03-01", "2015-05-31", horizon)
    old = run_dates(ds, importlib.import_module(name), dates, "train", splits)
    pd.testing.assert_frame_equal(picks, old)


# ---- the outcome window --------------------------------------------------------

def test_month_window_is_pick_open_to_last_trading_close_of_the_fourth_iso_week():
    dates = list(pd.bdate_range("2015-01-05", "2015-03-13").strftime("%Y-%m-%d"))
    dates.remove("2015-01-30")  # the 4th week of the first window ends on a Thursday
    dates.remove("2015-01-12")  # a week whose first trading date is a Tuesday
    ends = month_window_ends(dates)
    assert ends["2015-01-05"] == "2015-01-29"  # weeks 2, 3, 4, 5 of 2015; last trading date of week 5
    assert ends["2015-01-13"] == "2015-02-06"  # pick on Tuesday (Monday closed): week 3 + 3 weeks
    assert ends["2015-02-09"] == "2015-03-06"
    # The window of the week of 16 Feb ends on Friday 13 Mar, the last date in the calendar: not yet final.
    assert "2015-02-16" not in ends and "2015-02-23" not in ends
    assert all(e > d for d, e in ends.items())
    assert set(ends) <= set(pick_dates_for_horizon(dates, dates[0], dates[-1], "week"))


def test_month_window_with_an_empty_fourth_week_has_no_outcome():
    dates = [d for d in pd.bdate_range("2015-01-05", "2015-03-13").strftime("%Y-%m-%d")
             if not ("2015-01-26" <= d <= "2015-01-30")]
    assert "2015-01-05" not in month_window_ends(dates)


def test_month_moves_hand_computed():
    dates = list(pd.bdate_range("2015-01-05", "2015-02-13").strftime("%Y-%m-%d"))
    rows = [{"date": d, "symbol": "AAA", "open": 100.0 + i, "close": 101.0 + i} for i, d in enumerate(dates)]
    m = month_moves(pd.DataFrame(rows)).set_index("date")
    # Pick 5 Jan (i=0, open 100); outcome Fri 30 Jan (i=19, close 120).
    assert m.loc["2015-01-05", "outcome_date"] == "2015-01-30"
    assert m.loc["2015-01-05", "move"] == pytest.approx(120.0 / 100.0 - 1.0)
    assert list(m.index) == ["2015-01-05", "2015-01-12"]  # later windows end on or after the last date's week


# ---- no leakage across splits --------------------------------------------------

def _split_dataset():
    dates = list(pd.bdate_range("2015-01-01", "2015-07-31").strftime("%Y-%m-%d"))
    return pd.DataFrame([{"date": d, "symbol": s, "open": 100.0, "close": 100.0 + (i % 7) - 3 * (k == 1)}
                         for i, d in enumerate(dates) for k, s in enumerate(("AAA", "BBB"))])


@pytest.mark.parametrize("split", ["train", "validation", "test"])
def test_month_drops_the_last_three_pick_weeks_of_a_split_and_no_outcome_passes_its_end(split, tmp_path, monkeypatch):
    name = _write_strategy(tmp_path, monkeypatch)
    splits = {"train": {"start": "2015-01-01", "end": "2015-03-27"},       # Friday
              "validation": {"start": "2015-03-30", "end": "2015-05-29"},  # Monday .. Friday
              "test": {"start": "2015-06-01", "end": "2015-07-24"}}        # Monday .. Friday
    data = _split_dataset()
    lo, hi = str(splits[split]["start"]), str(splits[split]["end"])
    exp = {"strategy": name, "split": split, "horizon": "month", "dates": {"start": lo, "end": hi}}
    picks, h = run_experiment(data, exp, splits)
    weekly = pick_dates_for_horizon(sorted(data["date"].unique()), lo, hi, "week")
    kept = sorted(picks["date"].unique())
    assert set(weekly) - set(kept) >= set(weekly[-3:])
    assert weekly[-3:] == [d for d in weekly if d not in kept][-3:]
    assert weekly[-4] in kept  # the 4th-last pick week's window ends exactly on the split's last Friday
    ends = month_window_ends(sorted(data["date"].unique()))
    assert max(ends[d] for d in kept) <= hi
    assert max(ends[d] for d in kept) == hi
    assert len(h) == 64
    # Scoring drops them too when handed a log that still has them.
    ctx = Context(data.assign(has_future=True, turnover=1e9))
    raw = pd.DataFrame({"date": weekly, "symbol": "AAA", "score": 1.0})
    scored = score_picks(raw, "month", ctx, split_end=hi)["all"]["bullish"]
    assert scored.get("n_picks", 0) == len([d for d in kept if d in set(ctx.in_universe["date"])]) > 0


def test_month_split_ending_mid_week_also_drops_the_partial_pick_week(tmp_path, monkeypatch):
    dates = sorted(_split_dataset()["date"].unique())
    got = month_pick_dates(dates, "2015-01-01", "2015-03-31", "train",
                           {"train": {"start": "2015-01-01", "end": "2015-03-31"}})  # Tuesday
    assert got[-1] == "2015-03-02"  # 9, 16, 23 and 30 Mar all end after 31 Mar


def test_month_still_refuses_dates_outside_the_split(tmp_path, monkeypatch):
    name = _write_strategy(tmp_path, monkeypatch)
    exp = {"strategy": name, "split": "train", "horizon": "month", "dates": {"start": "2015-01-01", "end": "2015-05-29"}}
    with pytest.raises(SplitViolation):
        run_experiment(_split_dataset(), exp, {"train": {"start": "2015-01-01", "end": "2015-03-27"}})


# ---- scoring at month ----------------------------------------------------------

def _month_picks(ds):
    dates = pick_dates_for_horizon(sorted(ds["date"].unique()), "2015-02-15", "2016-04-30", "week")
    return make_picks(dates)


def test_month_scoring_uses_block_t_interval_and_one_cost_per_hold(ds, ctx):
    res = score_picks(_month_picks(ds), "month", ctx, split_end="2016-06-30")
    m = res["all"]["bullish"]
    assert m["interval_method"] == MONTH_INTERVAL_METHOD and f"{MONTH_BLOCK} consecutive" in MONTH_INTERVAL_METHOD
    lo, hi = m["edge_interval"]
    assert lo < m["edge"] < hi
    # Recompute edge, block t and the directional move by hand.
    picks = _month_picks(ds).merge(ctx.in_universe, on=["date", "symbol"])
    bull = picks[picks["score"] > 0][["date", "symbol"]].assign(side=1)
    moves = month_moves(ds)
    assert m["edge"] == pytest.approx(edge(bull, moves, ctx.universe))
    j = bull.merge(moves, on=["date", "symbol"])
    j["hit"] = j["move"] > 0
    diff = (j.groupby("date")["hit"].mean() - market_line(moves, ctx.universe, 1)).dropna().sort_index()
    assert m["edge_t"] == pytest.approx(block_t(diff.to_numpy()))
    assert m["directional_move"] == pytest.approx(float((j["move"] - DELIVERY_COST).mean()))
    bear = res["all"]["bearish"]
    jb = picks[picks["score"] < 0].merge(moves, on=["date", "symbol"])
    assert bear["directional_move"] == pytest.approx(float((-jb["move"] - FUTURES_COST).mean()))


def test_month_scoring_drops_picks_past_the_split_end(ds, ctx):
    full = score_picks(_month_picks(ds), "month", ctx)["all"]["bullish"]
    cut = score_picks(_month_picks(ds), "month", ctx, split_end="2015-12-31")["all"]["bullish"]
    assert cut["n_picks"] < full["n_picks"]
    assert max(y["year"] for y in cut["by_year"]) == 2015


def test_block_t_and_block_bootstrap_by_hand():
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0])
    means = np.array([2.5, 6.5])  # blocks of 4; the trailing 9 is dropped
    assert block_t(x, block=4) == pytest.approx(means.mean() / (means.std(ddof=1) / np.sqrt(2)))
    assert block_t(x[:7], block=4) is None
    assert block_bootstrap_interval(x, block=4) == block_bootstrap_interval(x, block=4)  # seeded
    assert block_bootstrap_interval(x[:4], block=4) is None
    lo, hi = block_bootstrap_interval(np.r_[x, x, x], block=4)
    assert 1.0 <= lo < 5.0 < hi <= 9.0
    assert MONTH_BLOCK >= 4


# ---- strategies run unchanged; queue, reports, ledgers, validation ------------

def test_a_week_strategy_runs_at_month_unchanged(ds):
    from strategies import a01_weekly_reversal
    splits = {"train": {"start": "2015-01-01", "end": "2015-12-31"}}
    exp = {"strategy": "strategies.a01_weekly_reversal", "split": "train", "horizon": "month",
           "dates": {"start": "2015-03-01", "end": "2015-12-31"}}
    picks, _ = run_experiment(ds, exp, splits)
    dates = month_pick_dates(sorted(ds["date"].unique()), "2015-03-01", "2015-12-31", "train", splits)
    pd.testing.assert_frame_equal(picks, run_dates(ds, a01_weekly_reversal, dates, "train", splits))
    assert not picks.empty


def test_main_runs_month_train_and_validation_and_feeds_leaderboard_and_trials(ds, tmp_path, monkeypatch):
    name = _write_strategy(tmp_path, monkeypatch, "month_signal")
    (tmp_path / "month_signal.py").write_text(
        "import numpy as np, pandas as pd\n\ndef score(history):\n"
        "    last = history[history['date'] == history['date'].max()].set_index('symbol')['close']\n"
        "    return pd.Series(np.where(np.arange(len(last)) % 2, 1.0, -1.0) * (1 + np.arange(len(last))), index=last.index)\n")
    data = tmp_path / "dataset.parquet"
    ds.to_parquet(data, index=False)
    pending, done = tmp_path / "pending", tmp_path / "done"
    pending.mkdir()
    splits = {"train": {"start": "2015-01-01", "end": "2015-11-27"},
              "validation": {"start": "2015-11-30", "end": "2016-05-27", "max_queries_per_week": 60}}
    base = {"strategy": name, "horizon": "month"}
    (pending / "m.yml").write_text(yaml.dump({**base, "id": "m", "split": "train",
                                               "dates": {"start": "2015-02-01", "end": "2015-11-27"}}))
    (pending / "mv.yml").write_text(yaml.dump({**base, "id": "mv", "split": "validation", "train_experiment": "m",
                                                "dates": {"start": "2015-11-30", "end": "2016-05-27"}}))
    monkeypatch.setattr("engine.run_queue.load_splits", lambda *a, **k: splits)
    monkeypatch.setattr("engine.experiment_report.load_splits", lambda *a, **k: splits)
    monkeypatch.setattr("engine.run_queue.maybe_write_champion_report", lambda *a, **k: False)
    monkeypatch.setattr("engine.run_queue.maybe_write_selftest_report", lambda *a, **k: False)
    monkeypatch.setattr("engine.run_queue.maybe_log_holdout_query", lambda *a, **k: False)
    trials, board, hl = tmp_path / "trials.csv", tmp_path / "board.md", tmp_path / "holdout.csv"
    monkeypatch.setattr(sys, "argv", ["run_queue.py", "--data", str(data), "--pending", str(pending),
                                      "--done", str(done), "--leaderboard", str(board), "--trials-ledger", str(trials),
                                      "--market-line-report", str(tmp_path / "ml.md"),
                                      "--holdout-ledger", str(hl)])
    from engine.run_queue import main
    main()
    manifest = json.loads((done / "m" / "manifest.json").read_text())
    assert manifest["horizon"] == "month" and "overlapping" in manifest["outcome_window"]
    picks = json.loads((done / "m" / "picks.json").read_text())
    ends = month_window_ends(sorted(ds["date"].unique()))
    assert max(ends[p["date"]] for p in picks) <= "2015-11-27"
    results = json.loads((done / "m" / "results.json").read_text())
    top = results["selections"]["top"]["bullish"]
    assert results["horizon"] == "month" and top["interval_method"] == MONTH_INTERVAL_METHOD
    assert "Month horizon: method" in (done / "m" / "results.md").read_text()
    assert "| m | month | bullish |" in board.read_text() and "block t" in board.read_text()
    with open(trials, newline="") as f:
        assert {(r["trial_id"], r["horizon"]) for r in csv.DictReader(f)} == {("m-bullish", "month"), ("m-bearish", "month")}
    with open(hl, newline="") as f:
        rows = list(csv.DictReader(f))
    assert [r["query_id"] for r in rows] == ["mv-bullish", "mv-bearish"] and {r["horizon"] for r in rows} == {"month"}
    assert not (done / "mv" / "picks.json").exists() and (done / "mv" / "holdout.json").exists()
    assert not (pending / "mv.yml").exists()


def test_held_c5_experiments_are_month_train_runs_of_catalogued_strategies():
    import importlib
    root = Path(__file__).resolve().parent.parent
    # held/ first, pending/ once queued, removed when the result lands in done/
    names = ["a01-weekly-reversal-month", "a04-52-week-high-month", "a05b-max-effect-ranked-month",
             "m01-momentum-12-1-month", "m02-leader-pullback-month"]
    ymls = [p for n in names for p in ((root / "experiments" / "held" / "c5" / f"{n}.yml"),
                                       (root / "experiments" / "pending" / f"{n}.yml")) if p.exists()]
    assert all(any(y.stem == n for y in ymls) or (root / "experiments" / "done" / n).exists() for n in names)
    with open(root / "cards" / "catalog.csv", newline="") as f:
        ids = {r["id"] for r in csv.DictReader(f)}
    assert {"A01", "A04", "A05B", "M01", "M02"} <= ids
    for y in ymls:
        exp = yaml.safe_load(y.read_text())
        assert exp["id"] == y.stem and exp["horizon"] == "month" and exp["split"] == "train"
        assert hasattr(importlib.import_module(exp["strategy"]), "score")
