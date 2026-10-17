"""`ledger/trials.csv` (B8, `state/queue.md`): every strategy variant evaluated.

Per the lab's hard rules: "Record every strategy variant you evaluate as a
row in `ledger/trials.csv`. Never delete ledger rows. Versions are
immutable." The cumulative row count is also gate 2's trial count
(`gates.gates.required_t`, SPEC.md section 6: "the trial count is the
cumulative count in `ledger/trials.csv`. The bar rises as more is tried.")
- so every trial, pass or fail, must be logged before its own gate check
can be scored, and logging is append-only by construction (`record_trial`
never rewrites an existing row).

A "trial" here is one (strategy_id, version, horizon, side) combination
evaluated against the gates in `gates.gates` - whichever split (train,
validation or test) it was judged on. Mirrors the append pattern
`engine.holdout_report.maybe_log_holdout_query` already uses for
`ledger/holdout_queries.csv`.
"""

from __future__ import annotations

import csv
from pathlib import Path

LEDGER_PATH = Path("ledger/trials.csv")

FIELDS = [
    "trial_id",
    "timestamp",
    "strategy_id",
    "version",
    "horizon",
    "side",
    "split",
    "edge",
    "t_stat",
    "all_gates_passed",
    "notes",
]


def record_trial(row: dict, path: Path = LEDGER_PATH) -> None:
    """Append one trial row. `row` must carry every key in `FIELDS`."""
    missing = set(FIELDS) - set(row)
    if missing:
        raise ValueError(f"trial row missing required field(s): {sorted(missing)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow({k: row[k] for k in FIELDS})


def cumulative_trial_count(path: Path = LEDGER_PATH) -> int:
    """Row count in the trials ledger - gate 2's `n_trials` (SPEC.md section 6).

    0 if the ledger has never been written (no trial has ever been logged):
    the *next* trial to be logged is then trial number 1, so callers should
    pass `cumulative_trial_count(path) + 1` as `gates.required_t`'s
    `n_trials` when scoring a trial not yet recorded.
    """
    if not path.exists() or path.stat().st_size == 0:
        return 0
    with open(path, newline="") as f:
        return sum(1 for _ in csv.DictReader(f))
