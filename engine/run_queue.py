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
   at — there is no outcome-scoring here at all yet, that is B5) to
   `experiments/done/<id>/`, then removes the pending file.

Scoring picks against outcomes is out of scope for this module (B5); this
only produces hashed, authorised pick logs.
"""

from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path

import pandas as pd

from engine.replay import SplitViolation, hash_picks, load_splits, run_dates

PENDING_DIR = Path("experiments/pending")
DONE_DIR = Path("experiments/done")


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
    args = ap.parse_args()

    pending_dir, done_dir = Path(args.pending), Path(args.done)
    queue = sorted(pending_dir.glob("*.yml")) if pending_dir.exists() else []
    if not queue:
        print("no experiments queued")
        return

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"no dataset at {data_path}; leaving queue untouched")
        return
    dataset = pd.read_parquet(data_path)
    splits = load_splits()

    for exp_path in queue:
        exp = load_experiment(exp_path)
        exp_id = exp.get("id", exp_path.stem)
        try:
            picks, pick_hash = run_experiment(dataset, exp, splits)
        except SplitViolation as e:
            print(f"{exp_id}: refused - {e}")
            continue

        out_dir = done_dir / exp_id
        out_dir.mkdir(parents=True, exist_ok=True)
        picks.to_parquet(out_dir / "picks.parquet", index=False)
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


if __name__ == "__main__":
    main()
