"""CLI: run every queued experiment in `experiments/pending/` against the cached dataset.

Invoked by `replay.yml` as `python3 -m engine.run_queue --data data/dataset.parquet`.
Each experiment is a YAML file describing a strategy module, the split it is
authorised to run on, a horizon, and a date range. For each one this:

1. Imports the strategy module (must expose `score(history) -> pd.Series`,
   SPEC.md section 5).
2. Picks the dates to run: every trading date in range for `horizon: day`,
   or the first trading date of each ISO week for `horizon: week`.
3. Runs `engine.replay.run_dates`, which authorises and truncates every date
   before the strategy ever sees it.
4. Writes the pick log and its SHA-256 (taken before any outcome is looked
   at) to `experiments/done/<id>/`, then removes the pending file.

Only `split: train` experiments get a public pick log. A `split: validation`
experiment (which must name its scored `train_experiment`) is answered through
the reusable holdout instead (`engine.experiment_report.answer_validation`):
only released values reach `ledger/` and `experiments/done/<id>/holdout.json`,
and it stays pending while the weekly budget cannot cover it. Any other split
is refused with `experiments/done/<id>/refused.json` (test looks belong to the
promotion job, the exam to `picks/`).

After the queue, every train experiment without current results is scored
(`results.json`/`results.md` next to its pick log), recorded as trials in
`ledger/trials.csv`, and `reports/train_leaderboard.md` is rebuilt.

Whenever a dataset is loaded and it carries the columns B5's scoring needs,
this also (re)writes `reports/market_line_train.md` (`engine.reports`) and
`reports/selftest.md` (`engine.selftest`, B6), so a push that touches
`engine/`, `strategies/`, `experiments/pending/` or `gates/` and triggers
`replay.yml` regenerates both from the real cached dataset - independently
of whether anything is queued.
"""

from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path

import pandas as pd

from engine.champion_report import REQUIRED_COLUMNS, maybe_write_champion_report
from engine.experiment_report import LEADERBOARD, TRIALS_LEDGER, Context, answer_validation, record_trials, score_done, write_leaderboard
from engine.holdout_report import LEDGER_PATH as HOLDOUT_LEDGER, maybe_log_holdout_query
from engine.replay import SplitViolation, hash_picks, load_splits, run_dates
from engine.reports import maybe_write_market_line_report
from engine.selftest import maybe_write_selftest_report

PENDING_DIR = Path("experiments/pending")
DONE_DIR = Path("experiments/done")
MARKET_LINE_REPORT = Path("reports/market_line_train.md")
SELFTEST_REPORT = Path("reports/selftest.md")
CHAMPION_REPORT = Path("reports/champion_v1_train.md")


def load_experiment(path: Path) -> dict:
    import yaml

    with open(path) as f:
        return yaml.safe_load(f)


def resolve_strategy(module_path: str):
    return importlib.import_module(module_path)


def pick_dates_for_horizon(available_dates: list[str], start: str, end: str, horizon: str) -> list[str]:
    """Trading dates in `[start, end]` to generate picks for.

    `day` picks every trading date; `week` picks only the first trading date
    of each ISO calendar week (Monday's open, per SPEC.md section 1), so the
    same engine serves both horizons without a separate weekly dataset.
    """
    dates = sorted(d for d in available_dates if start <= d <= end)
    if horizon == "day":
        return dates
    if horizon == "week":
        weekly, seen_weeks = [], set()
        for d in dates:
            key = pd.Timestamp(d).isocalendar()[:2]  # (iso_year, iso_week)
            if key not in seen_weeks:
                seen_weeks.add(key)
                weekly.append(d)
        return weekly
    raise ValueError(f"unknown horizon {horizon!r}; must be 'day' or 'week'")


def run_experiment(dataset: pd.DataFrame, exp: dict, splits: dict) -> tuple[pd.DataFrame, str]:
    strategy = resolve_strategy(exp["strategy"])
    available = sorted(dataset["date"].unique())
    dates = pick_dates_for_horizon(
        available, str(exp["dates"]["start"]), str(exp["dates"]["end"]), exp["horizon"]
    )
    picks = run_dates(dataset, strategy, dates, exp["split"], splits)
    return picks, hash_picks(picks)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--pending", default=str(PENDING_DIR))
    ap.add_argument("--done", default=str(DONE_DIR))
    ap.add_argument("--market-line-report", default=str(MARKET_LINE_REPORT))
    ap.add_argument("--selftest-report", default=str(SELFTEST_REPORT))
    ap.add_argument("--champion-report", default=str(CHAMPION_REPORT))
    ap.add_argument("--holdout-ledger", default=str(HOLDOUT_LEDGER))
    ap.add_argument("--leaderboard", default=str(LEADERBOARD))
    ap.add_argument("--trials-ledger", default=str(TRIALS_LEDGER))
    args = ap.parse_args()

    pending_dir, done_dir = Path(args.pending), Path(args.done)
    data_path = Path(args.data)

    dataset = None
    if data_path.exists():
        dataset = pd.read_parquet(data_path)
        if maybe_write_market_line_report(dataset, Path(args.market_line_report)):
            print(f"wrote {args.market_line_report}")
        if maybe_write_selftest_report(dataset, Path(args.selftest_report)):
            print(f"wrote {args.selftest_report}")
        if maybe_write_champion_report(dataset, Path(args.champion_report)):
            print(f"wrote {args.champion_report}")
        if maybe_log_holdout_query(dataset, Path(args.holdout_ledger)):
            print(f"wrote {args.holdout_ledger}")

    queue = sorted(pending_dir.glob("*.yml")) if pending_dir.exists() else []
    if dataset is None:
        print(f"no dataset at {data_path}; leaving queue untouched" if queue else "no experiments queued")
        return
    splits = load_splits()
    experiments = [(path, load_experiment(path)) for path in queue]
    if not queue:
        print("no experiments queued")

    validation = []
    for exp_path, exp in experiments:
        exp_id = exp.setdefault("id", exp_path.stem)
        if exp.get("split") == "validation":
            validation.append((exp_path, exp))
            continue
        if exp.get("split") != "train":
            out_dir = done_dir / exp_id
            out_dir.mkdir(parents=True, exist_ok=True)
            reason = f"split {exp.get('split')!r} is not run from the queue; only train, or validation through the holdout"
            (out_dir / "refused.json").write_text(json.dumps({"id": exp_id, "reason": reason}, indent=2) + "\n")
            exp_path.unlink()
            print(f"{exp_id}: refused - {reason}")
            continue
        try:
            picks, pick_hash = run_experiment(dataset, exp, splits)
        except SplitViolation as e:
            print(f"{exp_id}: refused - {e}")
            continue

        out_dir = done_dir / exp_id
        out_dir.mkdir(parents=True, exist_ok=True)
        # JSON, not parquet: `.gitignore`'s blanket `*.parquet` rule (for the
        # NSE dataset) would otherwise silently swallow the pick log, leaving
        # only its hash committed with nothing on disk to check it against.
        (out_dir / "picks.json").write_text(picks.to_json(orient="records", indent=2) + "\n")
        manifest = {
            "id": exp_id,
            "strategy": exp["strategy"],
            "split": exp["split"],
            "horizon": exp["horizon"],
            "n_picks": int(len(picks)),
            "n_dates": int(picks["date"].nunique()) if not picks.empty else 0,
            "pick_log_sha256": pick_hash,
        }
        (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        exp_path.unlink()
        print(f"{exp_id}: {manifest['n_picks']} picks over {manifest['n_dates']} dates -> {out_dir}")

    if not REQUIRED_COLUMNS.issubset(dataset.columns):
        return
    ctx = Context(dataset)
    for exp_id in score_done(ctx, done_dir):
        print(f"{exp_id}: scored -> {done_dir / exp_id / 'results.json'}")
    print(f"{record_trials(done_dir, Path(args.trials_ledger))} trial(s) -> {args.trials_ledger}")
    print(f"{write_leaderboard(done_dir, Path(args.leaderboard), Path(args.trials_ledger))} rows -> {args.leaderboard}")

    for exp_path, exp in validation:
        try:
            picks, _ = run_experiment(dataset, exp, splits)
        except SplitViolation as e:
            print(f"{exp['id']}: refused - {e}")
            continue
        status = answer_validation(picks, exp, ctx, done_dir, Path(args.holdout_ledger))
        print(f"{exp['id']}: {status}")
        if not status.startswith("waiting"):
            exp_path.unlink()


if __name__ == "__main__":
    main()
