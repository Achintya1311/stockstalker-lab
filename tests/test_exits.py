"""Exit-plan payoff scoring (`engine/exits.py`; owner-approved additive engine change, 14 Nov 2026).

Covers: each exit kind on hand-built price paths (target, stop, both in one session, gaps, time exit,
trailing stop, bearish mirror), ATR with no look-ahead, windows past the split end, the vectorised
simulation against a plain per-pick reference, the `exit:` yml schema, the queue / results / trials /
leaderboard path, the held ymls (held -> pending -> done), the report script, and the proof that with no
`exit:` block every queue output is byte-identical to the engine before this change.
"""

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from engine.exits import (
    STOP, TARGET, TIME, ExitData, block_length, parse_exit_plan, payoff_summary, score_exit, time_control,
    wilder_atr, worst_losing_run,
)
from engine.scoring import DELIVERY_COST, FUTURES_COST
from tests._queue_outputs import fingerprint, run as run_queue

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = Path(__file__).resolve().parent / "golden" / "no_exit_golden.json"

FIXED = {"kind": "fixed", "stop_atr": 2.0, "target_r": 2.0, "max_sessions": 10, "sides": ["bullish", "bearish"]}
TRAIL = {"kind": "trail", "stop_atr": 3.0, "max_sessions": 20, "sides": ["bullish", "bearish"]}
TIMEP = {"kind": "time", "stop_atr": 2.0, "max_sessions": 10, "sides": ["bullish", "bearish"]}
PRE = 20  # flat sessions before the pick: open = close = 100, high 101, low 99, so ATR(14) = 2 exactly


def _path_dataset(after, pre=PRE, mirror=False, symbol="AAA", n_after=None):
    """One symbol: `pre` flat sessions, then the pick date and the sessions in `after` [(o, h, l, c), ...],
    padded with flat sessions at the last close up to `n_after` sessions. `mirror` reflects prices
    about 100 (a bearish copy of a bullish path)."""
    n_after = n_after or max(len(after), 25)
    bars = [(100.0, 101.0, 99.0, 100.0)] * pre + list(after)
    last = bars[-1][3]
    bars += [(last, last + 0.5, last - 0.5, last)] * (pre + n_after - len(bars))
    if mirror:
        bars = [(200 - o, 200 - l, 200 - h, 200 - c) for o, h, l, c in bars]
    dates = list(pd.bdate_range("2015-01-01", periods=len(bars)).strftime("%Y-%m-%d"))
    df = pd.DataFrame([{"date": d, "symbol": symbol, "open": o, "high": h, "low": l, "close": c}
                       for d, (o, h, l, c) in zip(dates, bars)])
    df["prevclose"] = df["close"].shift(1).fillna(df["open"])
    return df, dates[pre]


def _one(after, plan, side=1, **kw):
    df, pick = _path_dataset(after, mirror=(side < 0), **kw)
    xd = ExitData(df)
    sim = xd.simulate(plan, side, [pick], ["AAA"])
    return {k: v[0] for k, v in sim.items()}


def _r(exit_price, entry=100.0, risk=4.0, side=1):
    cost = DELIVERY_COST if side > 0 else FUTURES_COST
    return ((exit_price - entry) * side / entry - cost) * entry / risk


# ---- fixed ---------------------------------------------------------------------

def test_fixed_target_hit():
    out = _one([(100, 101, 99, 100), (100, 103, 99.5, 102), (102, 109, 101, 107)], FIXED)
    assert out["reason"] == TARGET and out["hold"] == 3
    assert out["r"] == pytest.approx(_r(108.0))  # target = 100 + 2R, R = 2 ATR = 4
    assert out["pct"] == pytest.approx(0.08 - DELIVERY_COST)


def test_fixed_stop_hit():
    out = _one([(100, 101, 99, 100), (100, 100.5, 95, 97)], FIXED)
    assert out["reason"] == STOP and out["hold"] == 2
    assert out["r"] == pytest.approx(_r(96.0)) == pytest.approx(-1 - DELIVERY_COST * 25)


def test_fixed_both_touched_in_one_session_counts_the_stop():
    out = _one([(100, 109, 95, 104)], FIXED)
    assert out["reason"] == STOP and out["hold"] == 1 and out["r"] == pytest.approx(_r(96.0))


def test_fixed_gap_through_stop_fills_at_the_open():
    out = _one([(100, 101, 99, 100), (100, 101, 98, 99), (93, 94, 92, 93.5)], FIXED)
    assert out["reason"] == STOP and out["hold"] == 3 and out["r"] == pytest.approx(_r(93.0))
    assert out["r"] < -1.5


def test_fixed_gap_through_target_fills_at_the_open():
    out = _one([(100, 101, 99, 100), (111, 112, 95, 96)], FIXED)  # opens above target, then a low under the stop
    assert out["reason"] == TARGET and out["r"] == pytest.approx(_r(111.0))


def test_fixed_time_exit_at_the_close_of_the_last_session():
    after = [(100, 101, 99, 100 + 0.3 * i) for i in range(12)]
    out = _one(after, FIXED)
    assert out["reason"] == TIME and out["hold"] == 10
    assert out["r"] == pytest.approx(_r(100 + 0.3 * 9))


# ---- trail and time ------------------------------------------------------------

def test_trailing_stop_follows_the_best_close_and_never_falls():
    # R = 3 ATR = 6. Closes climb to 110, so the stop rises to 104; a dip to 103 exits at 104.
    after = [(100, 101, 99, 100), (100, 104, 99.5, 103), (103, 107, 102.5, 106), (106, 111, 105.5, 110),
             (110, 110.5, 105, 106), (106, 106.5, 103, 104.5)]
    out = _one(after, TRAIL)
    assert out["reason"] == STOP and out["hold"] == 6 and out["r"] == pytest.approx(_r(104.0, risk=6.0))
    # A drop to 105 on session 5 does not trigger (stop 104); the initial stop is 94 (a low of 95 survives).
    early = _one([(100, 101, 95, 100)] + after[1:], TRAIL)
    assert early["hold"] == 6


def test_trailing_stop_gap_fills_at_the_open():
    after = [(100, 101, 99, 100), (100, 110, 99.5, 110), (101, 102, 100, 101)]  # stop 104 after the 110 close
    out = _one(after, TRAIL)
    assert out["reason"] == STOP and out["hold"] == 3 and out["r"] == pytest.approx(_r(101.0, risk=6.0))


def test_trailing_time_exit():
    after = [(100 + i, 101 + i, 99.5 + i, 100.5 + i) for i in range(25)]
    out = _one(after, TRAIL)
    assert out["reason"] == TIME and out["hold"] == 20 and out["r"] == pytest.approx(_r(119.5, risk=6.0))


def test_time_kind_has_no_stop():
    after = [(100, 101, 99, 100), (100, 100.5, 80, 85)] + [(85, 86, 84, 85)] * 10
    out = _one(after, TIMEP)
    assert out["reason"] == TIME and out["hold"] == 10 and out["r"] == pytest.approx(_r(85.0))


# ---- bearish mirror ------------------------------------------------------------

@pytest.mark.parametrize("plan", [FIXED, TRAIL, TIMEP])
@pytest.mark.parametrize("after", [
    [(100, 101, 99, 100), (100, 103, 99.5, 102), (102, 109, 101, 107)],
    [(100, 101, 99, 100), (100, 100.5, 95, 97)],
    [(100, 109, 95, 104)],
    [(100, 101, 99, 100), (93, 94, 92, 93.5)],
    [(100, 101, 99, 100), (100, 110, 99.5, 110), (101, 102, 100, 101)],
    [(100 + 0.4 * i, 101 + 0.4 * i, 99.8 + 0.4 * i, 100.3 + 0.4 * i) for i in range(25)],
])
def test_bearish_is_the_mirror_of_bullish(plan, after):
    bull, bear = _one(after, plan, side=1), _one(after, plan, side=-1)
    assert bear["reason"] == bull["reason"] and bear["hold"] == bull["hold"]
    assert bear["r"] + FUTURES_COST * 100 / (plan["stop_atr"] * 2) == pytest.approx(
        bull["r"] + DELIVERY_COST * 100 / (plan["stop_atr"] * 2))
    assert bear["pct"] + FUTURES_COST == pytest.approx(bull["pct"] + DELIVERY_COST)


# ---- ATR: Wilder, no look-ahead ------------------------------------------------

def test_wilder_atr_by_hand():
    h = np.array([11, 12, 13, 12, 14.0]); l = np.array([9, 10, 11, 10, 11.0]); c = np.array([10, 11, 12, 11, 13.0])
    tr = np.array([2, 2, 2, 2, 3.0])  # row 3: max(2, |12-12|, |10-12|) = 2; row 4: max(3, 3, 0) = 3
    got = wilder_atr(h, l, c, period=3)
    assert np.isnan(got[:2]).all() and got[2] == pytest.approx(2.0)
    assert got[3] == pytest.approx(2.0) and got[4] == pytest.approx(2.0 + (3.0 - 2.0) / 3)
    assert tr.sum() > 0


def test_exitdata_atr_matches_wilder_on_rows_strictly_before_the_pick():
    rng = np.random.default_rng(3)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, 60)))
    o = c * (1 + rng.normal(0, 0.005, 60)); h = np.maximum(o, c) * 1.01; l = np.minimum(o, c) * 0.99
    dates = list(pd.bdate_range("2015-01-01", periods=60).strftime("%Y-%m-%d"))
    df = pd.DataFrame({"date": dates, "symbol": "AAA", "open": o, "high": h, "low": l, "close": c})
    xd = ExitData(df)
    ref = wilder_atr(h, l, c)
    for k in (14, 15, 30, 59):
        assert xd.ATR[k, 0] == pytest.approx(ref[k - 1])  # pick on row k uses rows 0..k-1
    assert np.isnan(xd.ATR[13, 0])


def test_risk_unit_does_not_see_the_pick_date_or_later():
    calm = [(100, 101, 99, 100), (100, 101, 99, 100), (100, 101, 99, 100)]
    wild = [(100, 140, 99.5, 100), (100, 160, 99.5, 150), (150, 200, 120, 190)]
    df1, pick = _path_dataset(calm)
    df2, _ = _path_dataset(wild)
    a1, a2 = ExitData(df1), ExitData(df2)
    i = list(a1.dates).index(pick)
    assert a1.ATR[i, 0] == a2.ATR[i, 0] == pytest.approx(2.0)


def test_adjusted_prices_keep_a_split_inside_the_window_from_firing_the_stop():
    df, pick = _path_dataset([(100, 101, 99, 100), (100, 101, 99, 100)] + [(100, 101, 99, 100)] * 10)
    i = df.index[df["date"] == pick][0]
    later = df.index > i + 1
    df.loc[later, ["open", "high", "low", "close"]] /= 2  # a 2:1 split two sessions after entry
    df["prevclose"] = df["close"].shift(1).fillna(df["open"])
    df.loc[i + 2, "prevclose"] = df.loc[i + 1, "close"] / 2  # the exchange's rebased PREVCLOSE
    out = ExitData(df).simulate(FIXED, 1, [pick], ["AAA"])
    assert out["reason"][0] == TIME and out["r"][0] == pytest.approx(_r(100.0))


# ---- windows, missing sessions, the vectorised path ----------------------------

def test_window_past_the_split_end_or_the_data_is_dropped():
    df, pick = _path_dataset([(100, 101, 99, 100)] * 5, n_after=12)
    xd = ExitData(df)
    i = list(xd.dates).index(pick)
    end_ok, end_short = xd.dates[i + 9], xd.dates[i + 8]
    assert np.isfinite(xd.simulate(FIXED, 1, [pick], ["AAA"], split_end=end_ok)["r"][0])
    assert np.isnan(xd.simulate(FIXED, 1, [pick], ["AAA"], split_end=end_short)["r"][0])
    assert np.isnan(xd.simulate(TRAIL, 1, [pick], ["AAA"])["r"][0])  # 20 sessions > the 12 in the data
    assert np.isnan(xd.simulate(FIXED, 1, [xd.dates[5]], ["AAA"])["r"][0])  # no ATR yet


def test_a_session_with_no_row_is_skipped_and_the_time_exit_uses_the_last_close():
    df, pick = _path_dataset([(100, 101, 99, 100 + 0.2 * i) for i in range(12)])
    other = df.assign(symbol="BBB")
    i = df.index[df["date"] == pick][0]
    gone = df.drop(index=[i + 3, i + 9])  # session 4 and the last session missing for AAA
    xd = ExitData(pd.concat([gone, other], ignore_index=True))
    out = xd.simulate(TIMEP, 1, [pick], ["AAA"])
    assert out["hold"][0] == 9 and out["r"][0] == pytest.approx(_r(100 + 0.2 * 8))


def _reference(plan, side, o, h, l, c, entry, atr, cost):
    """Plain per-pick loop, written independently of the vectorised code."""
    risk = plan["stop_atr"] * atr
    if side < 0:
        o, h, l, c, entry = -o, -l, -h, -c, -entry
    stop, tgt, best = entry - risk, entry + plan.get("target_r", np.inf) * risk, entry
    last = None
    for j in range(plan["max_sessions"]):
        if not np.isfinite(c[j]):
            continue
        if plan["kind"] == "trail":
            stop = best - risk
        if plan["kind"] != "time":
            if j > 0 and o[j] <= stop:
                return o[j], STOP, j + 1, entry, risk
            if plan["kind"] == "fixed" and j > 0 and o[j] >= tgt:
                return o[j], TARGET, j + 1, entry, risk
            if l[j] <= stop:
                return stop, STOP, j + 1, entry, risk
            if plan["kind"] == "fixed" and h[j] >= tgt:
                return tgt, TARGET, j + 1, entry, risk
        best = max(best, c[j])
        last = j
    return c[last], TIME, last + 1, entry, risk


@pytest.mark.parametrize("plan", [FIXED, TRAIL, TIMEP, {**FIXED, "target_r": 1.0, "max_sessions": 3}])
@pytest.mark.parametrize("side", [1, -1])
def test_vectorised_simulation_matches_a_per_pick_reference(plan, side):
    rng = np.random.default_rng(11)
    n_days, syms = 140, [f"S{k}" for k in range(6)]
    rows = []
    for s in syms:
        c = 100 * np.exp(np.cumsum(rng.normal(0, 0.025, n_days)))
        o = np.r_[100, c[:-1]] * np.exp(rng.normal(0, 0.012, n_days))
        h = np.maximum(o, c) * np.exp(np.abs(rng.normal(0, 0.012, n_days)))
        l = np.minimum(o, c) * np.exp(-np.abs(rng.normal(0, 0.012, n_days)))
        rows += [{"date": d, "symbol": s, "open": o[i], "high": h[i], "low": l[i], "close": c[i]}
                 for i, d in enumerate(pd.bdate_range("2015-01-01", periods=n_days).strftime("%Y-%m-%d"))]
    df = pd.DataFrame(rows).sample(frac=0.97, random_state=1)  # a few missing sessions
    xd = ExitData(df)
    picks = df[(df["date"] >= xd.dates[15]) & (df["date"] <= xd.dates[110])][["date", "symbol"]]
    sim = xd.simulate(plan, side, picks["date"], picks["symbol"])
    cost = DELIVERY_COST if side > 0 else FUTURES_COST
    di, si = pd.Index(xd.dates).get_indexer(picks["date"]), pd.Index(xd.symbols).get_indexer(picks["symbol"])
    checked = 0
    for k in range(len(picks)):
        atr = xd.ATR[di[k], si[k]]
        if not np.isfinite(atr):
            assert np.isnan(sim["r"][k])
            continue
        w = slice(di[k], di[k] + plan["max_sessions"])
        px, why, held, fe, risk = _reference(plan, side, xd.O[w, si[k]], xd.H[w, si[k]], xd.L[w, si[k]],
                                             xd.C[w, si[k]], xd.O[di[k], si[k]], atr, cost)
        e = xd.O[di[k], si[k]]
        assert sim["reason"][k] == why and sim["hold"][k] == held
        assert sim["r"][k] == pytest.approx(((px - fe) / e - cost) * e / risk)
        checked += 1
    assert checked > 300
    assert {STOP, TIME} <= set(sim["reason"][np.isfinite(sim["r"])]) or plan["kind"] == "time"


# ---- metrics -------------------------------------------------------------------

def test_payoff_summary_and_worst_losing_run_by_hand():
    r = np.array([2.0, -1.0, -1.0, 0.0, 1.5, -1.0, 2.0])
    m = payoff_summary(r, r / 25, np.array([3, 1, 2, 10, 4, 2, 5]), np.array([1, 0, 0, 2, 2, 0, 1]))
    assert m["n_picks"] == 7 and m["share_right"] == pytest.approx(3 / 7)
    assert m["avg_r"] == pytest.approx(r.mean()) and m["median_r"] == 0.0
    assert m["profit_factor"] == pytest.approx(5.5 / 3.0)
    assert m["share_stop"] == pytest.approx(3 / 7) and m["share_target"] == pytest.approx(2 / 7)
    assert m["worst_losing_run"] == 3  # -1, -1, 0: a zero outcome is not right
    assert worst_losing_run([1.0, 2.0]) == 0 and payoff_summary([1.0], [0.01], [1], [1])["profit_factor"] is None


def test_block_length_covers_one_hold():
    assert block_length(FIXED, "day") == 10 and block_length(TRAIL, "day") == 20
    assert block_length(FIXED, "week") == 8 and block_length(TRAIL, "month") == 8


def test_score_exit_baseline_and_control():
    from tests._horizon_dataset import make_dataset
    ds = make_dataset()
    from engine.experiment_report import Context, select
    ctx = Context(ds)
    xd = ExitData(ds)
    dates = sorted(ds["date"].unique())[40:200]
    picks = pd.DataFrame([{"date": d, "symbol": s, "score": (1 if (i + k) % 3 else -1) * (k + 1)}
                          for i, d in enumerate(dates) for k, s in enumerate(["S01", "S04", "S07", "S10"])])
    picks = picks.merge(ctx.in_universe, on=["date", "symbol"])
    side_picks = {"bullish": select(picks, 1, 5), "bearish": select(picks, -1, 5)}
    out = score_exit(side_picks, FIXED, xd, ctx.in_universe, "day", split_end="2015-12-31")
    bull = out["sides"]["bullish"]
    assert out["control"] == time_control(FIXED) and bull["control"]["share_time"] == 1.0
    assert bull["n_picks"] > 100 and abs(bull["share_stop"] + bull["share_target"] + bull["share_time"] - 1) < 1e-12
    assert bull["interval"][0] < bull["avg_r_above_baseline"] < bull["interval"][1]
    assert "blocks of 10 consecutive pick dates" in bull["interval_method"]
    assert max(y["year"] for y in bull["by_year"]) == 2015
    # Baseline by hand: per date, the picks' mean R minus every universe stock's mean R under the plan.
    sp = side_picks["bullish"].sort_values(["date", "symbol"])
    sim = xd.simulate(FIXED, 1, sp["date"], sp["symbol"], "2015-12-31")
    p = sp.assign(r=sim["r"]).dropna()
    u = ctx.in_universe[ctx.in_universe["date"].isin(p["date"])]
    u = u.assign(r=xd.simulate(FIXED, 1, u["date"], u["symbol"], "2015-12-31")["r"]).dropna()
    diff = (p.groupby("date")["r"].mean() - u.groupby("date")["r"].mean()).dropna()
    assert bull["avg_r_above_baseline"] == pytest.approx(diff.mean())
    assert bull["baseline_avg_r"] == pytest.approx(u.groupby("date")["r"].mean().loc[diff.index].mean())
    t_only = score_exit(side_picks, {**TIMEP, "sides": ["bearish"]}, xd, ctx.in_universe, "day")
    assert set(t_only["sides"]) == {"bearish"} and t_only["control"] is None
    assert "control" not in t_only["sides"]["bearish"]


# ---- yml schema ----------------------------------------------------------------

def test_parse_exit_plan_accepts_the_three_kinds_and_normalises():
    assert parse_exit_plan({"kind": "fixed", "stop_atr": 2, "target_r": 2, "max_sessions": 10}) == {
        "kind": "fixed", "stop_atr": 2.0, "target_r": 2.0, "max_sessions": 10, "sides": ["bullish", "bearish"]}
    assert parse_exit_plan({"kind": "trail", "stop_atr": 3, "max_sessions": 20, "sides": ["bearish"]})["sides"] == ["bearish"]
    assert parse_exit_plan({"kind": "time", "max_sessions": 10})["stop_atr"] == 2.0


@pytest.mark.parametrize("block", [
    None, [], {"kind": "limit", "max_sessions": 5},
    {"kind": "fixed", "stop_atr": 2, "max_sessions": 10},                       # no target
    {"kind": "fixed", "target_r": 2, "max_sessions": 10},                       # no stop
    {"kind": "trail", "stop_atr": 3, "target_r": 2, "max_sessions": 20},        # trail takes no target
    {"kind": "time", "target_r": 2, "max_sessions": 10},
    {"kind": "fixed", "stop_atr": -1, "target_r": 2, "max_sessions": 10},
    {"kind": "fixed", "stop_atr": 2, "target_r": 2, "max_sessions": 0},
    {"kind": "fixed", "stop_atr": 2, "target_r": 2, "max_sessions": 2.5},
    {"kind": "fixed", "stop_atr": True, "target_r": 2, "max_sessions": 10},
    {"kind": "time", "max_sessions": 10, "sides": ["long"]},
    {"kind": "time", "max_sessions": 10, "sides": []},
    {"kind": "time", "max_sessions": 10, "price": 120},
])
def test_parse_exit_plan_rejects_bad_blocks(block):
    with pytest.raises(ValueError):
        parse_exit_plan(block)


LIVE_RULES = {"a01": ("strategies.a01_weekly_reversal", "week", "bearish", "batch_1"),
              "a05b": ("strategies.a05b_max_effect_ranked", "week", "bullish", "batch_1"),
              "e2a": ("strategies.e2a_a02_crowded", "day", "bearish", "batch_2"),
              "t04": ("strategies.t04_connors_rsi2", "day", "bullish", "batch_2")}
PRESETS = {"fixed": {"kind": "fixed", "stop_atr": 2.0, "target_r": 2.0, "max_sessions": 10},
           "trail": {"kind": "trail", "stop_atr": 3.0, "max_sessions": 20},
           "time": {"kind": "time", "stop_atr": 2.0, "max_sessions": 10}}


def test_held_exit_ymls_are_train_runs_of_the_live_rules_in_their_batches():
    import importlib
    held, pending, done = (ROOT / "experiments" / x for x in ("held/exit", "pending", "done"))
    for rule, (module, horizon, side, batch) in LIVE_RULES.items():
        for preset, plan in PRESETS.items():
            exp_id = f"exit-{rule}-{preset}-{horizon}"
            # held/exit/<batch>/ first, pending/ once queued, gone when the result lands in done/
            where = [p for p in (held / batch / f"{exp_id}.yml", pending / f"{exp_id}.yml") if p.exists()]
            assert where or (done / exp_id).exists(), exp_id
            assert len(where) <= 1, exp_id
            for y in where:
                exp = yaml.safe_load(y.read_text())
                assert exp["id"] == y.stem and exp["strategy"] == module and exp["horizon"] == horizon
                assert exp["split"] == "train"
                assert {str(v) for v in exp["dates"].values()} == {"2015-01-01", "2020-12-31"}
                assert parse_exit_plan(exp["exit"]) == {**plan, "sides": [side]}
                assert hasattr(importlib.import_module(module), "score")
    found = sorted(p.stem for p in held.rglob("*.yml"))
    assert set(found) <= {f"exit-{r}-{p}-{v[1]}" for r, v in LIVE_RULES.items() for p in PRESETS}
    for y in list(held.rglob("*.yml")) + list(pending.glob("*.yml")):
        assert yaml.safe_load(y.read_text()).get("split") != "validation" or "exit" not in yaml.safe_load(y.read_text())


# ---- the queue: no exit = byte-identical; with exit = an extra block ----------

def test_no_exit_block_keeps_every_queue_output_byte_identical(tmp_path, monkeypatch):
    run_queue(tmp_path, monkeypatch)
    assert fingerprint(tmp_path) == json.loads(GOLDEN.read_text())
    for f in (tmp_path / "done").glob("*/results.json"):
        assert "exit" not in json.loads(f.read_text())


def test_exit_block_adds_payoff_without_changing_the_hit_rate_results(tmp_path, monkeypatch):
    plan = {"kind": "fixed", "stop_atr": 2, "target_r": 2, "max_sessions": 10, "sides": ["bearish"]}
    run_queue(tmp_path, monkeypatch, extra={"q-day": {"exit": plan}, "q-month": {"exit": {**plan, "kind": "time",
                                                                                           "sides": ["bullish"]} | {"target_r": None}}})
    want = json.loads(GOLDEN.read_text())
    got = fingerprint(tmp_path)
    # q-month's block is invalid (time takes no target_r): refused, nothing replayed.
    assert json.loads((tmp_path / "done" / "q-month" / "refused.json").read_text())["reason"].startswith("invalid exit")
    assert not (tmp_path / "done" / "q-month" / "picks.json").exists()
    for name in ("done/q-week/manifest.json", "done/q-week/results.json", "done/q-day/picks.json"):
        assert got[name] == want[name]
    manifest = json.loads((tmp_path / "done" / "q-day" / "manifest.json").read_text())
    assert manifest["exit"] == parse_exit_plan(plan)
    res = json.loads((tmp_path / "done" / "q-day" / "results.json").read_text())
    old_md = (tmp_path / "done" / "q-day" / "results.md").read_text()
    assert set(res["exit"]["sides"]) == {"bearish"} and res["exit"]["sides"]["bearish"]["n_picks"] > 0
    assert res["exit"]["sides"]["bearish"]["control"]["share_time"] == 1.0
    assert "## Exit plan payoff (train-only observation)" in old_md and "time-only control" in old_md
    without = {k: v for k, v in res.items() if k != "exit"}
    ref = tmp_path / "ref"
    ref.mkdir()
    run_queue(ref, monkeypatch)
    assert without == json.loads((ref / "done" / "q-day" / "results.json").read_text())
    assert old_md.startswith((ref / "done" / "q-day" / "results.md").read_text())
    board = (tmp_path / "board.md").read_text()
    assert "| q-day |" not in board and "| q-week |" in board
    with open(tmp_path / "trials.csv", newline="") as f:
        rows = {r["trial_id"]: r for r in csv.DictReader(f)}
    assert "q-day-bearish" in rows and "q-day-bullish" not in rows and "exit plan" in rows["q-day-bearish"]["notes"]
    assert {"q-week-bullish", "q-week-bearish"} <= set(rows)


def test_exit_block_on_a_validation_experiment_is_refused(tmp_path, monkeypatch):
    run_queue(tmp_path, monkeypatch, extra={"q-week": {"split": "validation", "train_experiment": "q-day",
                                                       "dates": {"start": "2016-04-01", "end": "2016-06-30"},
                                                       "exit": {"kind": "time", "max_sessions": 5}}})
    reason = json.loads((tmp_path / "done" / "q-week" / "refused.json").read_text())["reason"]
    assert "train-only" in reason and not (tmp_path / "holdout.csv").exists()


def test_exit_report_writes_one_row_per_rule_and_preset_with_its_control(tmp_path, monkeypatch):
    plan = {"kind": "trail", "stop_atr": 3, "max_sessions": 20, "sides": ["bullish"]}
    run_queue(tmp_path, monkeypatch, extra={"q-week": {"exit": plan}, "q-day": {"exit": {**plan, "kind": "time"}}})
    from scripts import exit_report
    held = tmp_path / "held" / "batch_1"
    held.mkdir(parents=True)
    (held / "exit-zz-fixed-day.yml").write_text("id: exit-zz-fixed-day\n")
    text = exit_report.render(tmp_path / "done", tmp_path / "held", tmp_path / "pending")
    table = [l for l in text.splitlines() if l.startswith("| q-")]
    assert len(table) == 2
    week = next(l for l in table if "| week |" in l)
    assert "trail: stop 3 ATR" in week and week.count("|") == len(exit_report.COLUMNS) + 1
    assert "`exit-zz-fixed-day`" in text
    for word in ("buy", "sell", "target price", "entry price"):
        assert word not in text.lower()
