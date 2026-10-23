"""Scores finished replays in `experiments/done/` (SPEC.md sections 3 and 6).

Two pick selections are scored for each side of every train experiment:

- `top`: on each date, the `picks_per_table` (config/universe.yml) largest
  positive scores (bullish) and largest negative scores (bearish) among
  in-universe symbols, ranked by absolute score as `picks/select.py` does.
  This is what the public tables publish, so the provisional go-live rule
  (SPEC.md section 10) and the gates read this selection.
- `all`: every in-universe positive / negative score, the broad signal
  (the convention `engine/champion_report.py` uses). A strategy can show
  edge in `top` that is diluted to nothing in `all`, or the reverse.

Per side: picks, coverage, accuracy, market line, edge, the t statistic of
the per-date edge, directional move after costs, edge by calendar year and
the share of positive years (gate 3), and the leak alarm (SPEC.md section 6).
No random baseline: gate 6 is checked once, on test.

Only train experiments are scored openly. Validation experiments never reach
this module's open scorer: `engine/run_queue.py` answers them through the
reusable holdout (`answer_validation`), which records released values only.

Results go next to each pick log (`experiments/done/<id>/results.json` and
`results.md`), rescored only when missing or when SCORER_VERSION changes.

Every scored train experiment is also a trial: one row per side goes into
`ledger/trials.csv` (`record_trials`), so gate 2's bar rises with everything
tried. `reports/train_leaderboard.md` is rebuilt from every results file each
run, ranked by t, with that bar shown. A row is a provisional-rule candidate
only with at least 500 picks (the same bar as gate 4), positive edge and
positive directional move.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd

from engine.holdout import thresholdout_query
from engine.holdout_report import LEDGER_FIELDS, THRESHOLD, TOLERANCE, _already_logged
from engine.scoring import (
    directional_move_after_costs,
    hit,
    load_universe_config,
    market_line,
    moves_for_horizon,
    universe_membership,
)
from gates.budgets import holdout_budget_remaining
from gates.gates import MIN_TEST_PICKS, leak_alarm_triggered, required_t
from gates.trials import LEDGER_PATH as TRIALS_LEDGER, cumulative_trial_count, record_trial

SCORER_VERSION = 1
SIDES = {1: "bullish", -1: "bearish"}
LEADERBOARD = Path("reports/train_leaderboard.md")
MIN_CANDIDATE_PICKS = MIN_TEST_PICKS
NOT_STRATEGIES = {"strategies.engine_smoketest"}  # engine checks, not hypotheses: no trial, no leaderboard row


class Context:
    """Moves and universe computed once per dataset, shared by every experiment."""

    def __init__(self, dataset: pd.DataFrame):
        self.dataset = dataset
        self.universe = universe_membership(dataset)
        self.in_universe = self.universe.loc[self.universe["in_universe"], ["date", "symbol"]]
        self.k = int(load_universe_config()["picks_per_table"])
        self._moves: dict[str, pd.DataFrame] = {}
        self._lines: dict[tuple[str, int], pd.Series] = {}

    def moves(self, horizon: str) -> pd.DataFrame:
        if horizon not in self._moves:
            self._moves[horizon] = moves_for_horizon(self.dataset, horizon)
        return self._moves[horizon]

    def line(self, horizon: str, side: int) -> pd.Series:
        if (horizon, side) not in self._lines:
            self._lines[(horizon, side)] = market_line(self.moves(horizon), self.universe, side)
        return self._lines[(horizon, side)]


def select(picks: pd.DataFrame, side: int, k: int | None) -> pd.DataFrame:
    """`date, symbol, side` rows for one side; the `k` largest |score| per date, or all if k is None.
    `picks` must already be restricted to the universe."""
    s = picks[picks["score"] > 0] if side > 0 else picks[picks["score"] < 0]
    if k is not None:
        s = s.assign(_abs=s["score"].abs()).sort_values(["date", "_abs", "symbol"], ascending=[True, False, True])
        s = s.groupby("date", sort=False).head(k)
    return s[["date", "symbol"]].assign(side=side)


def side_metrics(side_picks: pd.DataFrame, side: int, horizon: str, ctx: Context, n_dates: int) -> dict:
    joined = side_picks.merge(ctx.moves(horizon), on=["date", "symbol"], how="inner")
    if joined.empty:
        return {"n_picks": 0}
    joined["hit"] = hit(joined["move"], side)
    # Per-date edge, the same alignment as engine.scoring.edge (tests check they agree).
    per_date = joined.groupby("date")["hit"].mean().to_frame("hit_rate").join(
        ctx.line(horizon, side).rename("market_line"), how="inner"
    )
    diff = per_date["hit_rate"] - per_date["market_line"]
    by_year = diff.groupby(pd.to_datetime(diff.index).year)
    picks_by_year = joined.groupby(pd.to_datetime(joined["date"]).dt.year)
    years = [
        {"year": int(y), "n_picks": int(len(picks_by_year.get_group(y))),
         "accuracy": float(picks_by_year.get_group(y)["hit"].mean()), "edge": float(d.mean())}
        for y, d in by_year
    ]
    accuracy, edge_value = float(joined["hit"].mean()), float(diff.mean())
    sd = float(diff.std(ddof=1)) if len(diff) > 1 else float("nan")
    return {
        "n_picks": int(len(joined)),
        "n_dates": int(len(per_date)),
        "coverage": len(per_date) / n_dates if n_dates else None,
        "accuracy": accuracy,
        "market_line": float(per_date["market_line"].mean()),
        "edge": edge_value,
        "edge_t": edge_value / (sd / np.sqrt(len(diff))) if sd and sd > 0 else None,
        "directional_move": directional_move_after_costs(joined[["date", "symbol", "side"]], ctx.moves(horizon)),
        "positive_year_share": float(np.mean([y["edge"] > 0 for y in years])) if years else None,
        "by_year": years,
        "leak_alarm": bool(leak_alarm_triggered(accuracy, edge_value)),
    }


def score_picks(picks: pd.DataFrame, horizon: str, ctx: Context) -> dict:
    picks = picks.merge(ctx.in_universe, on=["date", "symbol"], how="inner")
    n_dates = int(picks["date"].nunique())
    return {
        sel: {SIDES[side]: side_metrics(select(picks, side, k), side, horizon, ctx, n_dates) for side in SIDES}
        for sel, k in (("top", ctx.k), ("all", None))
    }


def _load_picks(path: Path) -> pd.DataFrame:
    # Not pd.read_json: it would turn the `date` strings into timestamps, which never match the dataset's.
    return pd.DataFrame(json.loads(path.read_text()), columns=["date", "symbol", "score"])


def _pct(x) -> str:
    return "n/a" if x is None else f"{x * 100:.2f}"


def render(manifest: dict, results: dict, k: int) -> str:
    lines = [f"# {manifest['id']}: train results", "",
             f"`{manifest['strategy']}`, {manifest['horizon']} horizon, {manifest['split']} split. "
             f"`top` = the {k} picks a table would publish each date; `all` = every positive or negative score. "
             "Edge and market line in points; definitions in SPEC.md section 3.", ""]
    for sel in ("top", "all"):
        for side in SIDES.values():
            m = results[sel][side]
            lines.append(f"## {sel} / {side}")
            lines.append("")
            if not m.get("n_picks"):
                lines += ["No in-universe picks.", ""]
                continue
            t = "n/a" if m["edge_t"] is None else f"{m['edge_t']:.2f}"
            lines += [
                f"{m['n_picks']} picks on {m['n_dates']} dates (coverage {_pct(m['coverage'])}%). "
                f"Accuracy {_pct(m['accuracy'])}% vs market line {_pct(m['market_line'])}%: "
                f"edge {_pct(m['edge'])} (t {t}). Directional move after costs {_pct(m['directional_move'])}. "
                f"Positive years {_pct(m['positive_year_share'])}%." + (" **LEAK ALARM.**" if m["leak_alarm"] else ""),
                "", "| Year | Picks | Accuracy | Edge |", "|---|---|---|---|",
            ]
            lines += [f"| {y['year']} | {y['n_picks']} | {_pct(y['accuracy'])}% | {_pct(y['edge'])} |" for y in m["by_year"]]
            lines.append("")
    return "\n".join(lines)


def score_done(ctx: Context, done_dir: Path) -> list[str]:
    """Score every train experiment lacking current results; return the ids scored."""
    scored = []
    for d in sorted(p for p in done_dir.iterdir() if p.is_dir()) if done_dir.exists() else []:
        manifest_path, picks_path, out = d / "manifest.json", d / "picks.json", d / "results.json"
        if not (manifest_path.exists() and picks_path.exists()):
            continue
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("split") != "train":
            continue
        if out.exists() and json.loads(out.read_text()).get("scorer_version") == SCORER_VERSION:
            continue
        results = score_picks(_load_picks(picks_path), manifest["horizon"], ctx)
        payload = {"id": manifest["id"], "strategy": manifest["strategy"], "split": manifest["split"],
                   "horizon": manifest["horizon"], "pick_log_sha256": manifest.get("pick_log_sha256"),
                   "scorer_version": SCORER_VERSION, "picks_per_table": ctx.k, "selections": results}
        out.write_text(json.dumps(payload, indent=2) + "\n")
        (d / "results.md").write_text(render(manifest, results, ctx.k))
        scored.append(manifest["id"])
    return scored


def _results(done_dir: Path):
    for f in sorted(done_dir.glob("*/results.json")):
        r = json.loads(f.read_text())
        if r["strategy"] not in NOT_STRATEGIES:
            yield r


def record_trials(done_dir: Path, ledger: Path = TRIALS_LEDGER) -> int:
    """One `ledger/trials.csv` row per (train experiment, side), on the `top` selection.
    Append-only and idempotent by trial id; returns the number of rows added."""
    seen = set()
    if ledger.exists() and ledger.stat().st_size:
        with open(ledger, newline="") as f:
            seen = {row["trial_id"] for row in csv.DictReader(f)}
    added = 0
    for r in _results(done_dir):
        for side, m in r["selections"]["top"].items():
            trial_id = f"{r['id']}-{side}"
            if trial_id in seen or not m.get("n_picks"):
                continue
            record_trial({"trial_id": trial_id, "timestamp": pd.Timestamp.now(tz="UTC").isoformat(),
                          "strategy_id": r["strategy"], "version": r.get("version", ""), "horizon": r["horizon"],
                          "side": side, "split": r["split"], "edge": m["edge"], "t_stat": m["edge_t"],
                          "all_gates_passed": "n/a", "notes": "train, top selection; recorded by engine/experiment_report.py"},
                         ledger)
            added += 1
    return added


def write_leaderboard(done_dir: Path, out_path: Path = LEADERBOARD, ledger: Path = TRIALS_LEDGER) -> int:
    """One row per (experiment, side) for the `top` selection, highest t first."""
    rows = [(r["id"], r["horizon"], side, m) for r in _results(done_dir)
            for side, m in r["selections"]["top"].items() if m.get("n_picks")]
    rows.sort(key=lambda row: row[3]["edge_t"] if row[3]["edge_t"] is not None else float("-inf"), reverse=True)
    n_trials = max(cumulative_trial_count(ledger), 1)
    bar = required_t(n_trials)
    lines = ["# Train leaderboard (top picks per table)", "",
             "Train split only (2015 to 2020), the picks a table would publish, ranked by t (how hard the result is "
             "to explain by luck). A **candidate** for the provisional rule (SPEC.md section 10) has at least "
             f"{MIN_CANDIDATE_PICKS} picks, positive edge and positive directional move after costs; it still needs "
             "a validation query. Rebuilt by `engine/run_queue.py` on every replay.", "",
             f"Trials recorded: {n_trials}. Gate 2's bar at that count: t >= {bar:.2f}.", "",
             "| Experiment | Horizon | Side | Picks | Accuracy | Market line | Edge | t | Clears bar | Dir. move | Positive years | |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for exp_id, horizon, side, m in rows:
        t = "n/a" if m["edge_t"] is None else f"{m['edge_t']:.2f}"
        clears = "yes" if m["edge_t"] is not None and m["edge_t"] >= bar else ""
        if m["leak_alarm"]:
            flag = "LEAK ALARM"
        elif m["n_picks"] < MIN_CANDIDATE_PICKS:
            flag = "too few picks"
        elif m["edge"] > 0 and m["directional_move"] > 0:
            flag = "candidate"
        else:
            flag = ""
        lines.append(f"| {exp_id} | {horizon} | {side} | {m['n_picks']} | {_pct(m['accuracy'])}% | {_pct(m['market_line'])}% "
                     f"| {_pct(m['edge'])} | {t} | {clears} | {_pct(m['directional_move'])} | {_pct(m['positive_year_share'])}% | {flag} |")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")
    return len(rows)


def answer_validation(picks: pd.DataFrame, exp: dict, ctx: Context, done_dir: Path, ledger: Path,
                      now: pd.Timestamp | None = None) -> str:
    """Answer a validation experiment through Thresholdout, one query per side (top selection).

    Returns "done", or a reason to leave the experiment pending. Only train and
    released values are written; the true validation edge is used once and dropped.
    """
    exp_id, train_id = exp["id"], exp.get("train_experiment")
    train_path = done_dir / str(train_id) / "results.json"
    if not train_path.exists():
        return f"waiting: train results for {train_id!r} not found (set train_experiment to a scored train id)"
    train = json.loads(train_path.read_text())
    if train["horizon"] != exp["horizon"]:
        return f"refused: horizon {exp['horizon']} differs from train experiment's {train['horizon']}"
    todo = [s for s in SIDES.values() if not _already_logged(ledger, f"{exp_id}-{s}")]
    if not todo:
        return "done"  # already answered; never re-ask
    if holdout_budget_remaining(now, path=ledger) < len(todo):
        return "waiting: this week's holdout budget cannot cover both sides"
    holdout = score_picks(picks, exp["horizon"], ctx)["top"]
    released = {}
    ledger.parent.mkdir(parents=True, exist_ok=True)
    for side in todo:
        train_edge, holdout_edge = train["selections"]["top"][side].get("edge"), holdout[side].get("edge")
        if train_edge is None or holdout_edge is None:
            continue
        ans = thresholdout_query(train_edge, holdout_edge, threshold=THRESHOLD, tolerance=TOLERANCE)
        row = {"query_id": f"{exp_id}-{side}", "timestamp": pd.Timestamp.now(tz="UTC").isoformat(),
               "metric": "edge_top", "horizon": exp["horizon"], "side": side, "threshold": THRESHOLD,
               "tolerance": TOLERANCE, "train_value": ans.train_value, "released_value": ans.released_value,
               "budget_spent": ans.budget_spent}
        write_header = not ledger.exists() or ledger.stat().st_size == 0
        with open(ledger, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=LEDGER_FIELDS)
            if write_header:
                w.writeheader()
            w.writerow(row)
        released[side] = {"train_edge": ans.train_value, "released_edge": ans.released_value}
    out = done_dir / exp_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "holdout.json").write_text(json.dumps(
        {"id": exp_id, "strategy": exp["strategy"], "horizon": exp["horizon"], "train_experiment": train_id,
         "selection": "top", "released": released}, indent=2) + "\n")
    return "done"
