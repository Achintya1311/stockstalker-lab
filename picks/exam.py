"""Exam backfill (B9's "Exam" step, `state/queue.md`):

"in live mode, if `<dir>/exam/` does not exist, replay 1 Aug 2026 to the
day before the first live session with the same sources, in the same file
layout under `<dir>/exam/`, already scored."

The day before the first live session is exactly `asof` (the previous
close `run.py` computed the real live pick from): the first live session
is `calendar.next_trading_session(asof)`, so `asof` is its immediate
predecessor trading day by construction. Every exam date is still
authorised through `engine.replay.authorize` against the real "exam"
split (`config/splits.yml`, 2026-08-01 to go-live) - same causal
truncation guarantee as any other backtest, not a shortcut because the
outcomes happen to already be known.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from engine.replay import authorize
from picks.outcomes import score_picks_file
from picks.payload import build_tables, make_payload

EXAM_SPLIT = "exam"
EXAM_START = "2026-08-01"


def _dates_for_horizon(available: list[str], start: str, end: str, horizon: str) -> list[str]:
    """Mirrors `engine.run_queue.pick_dates_for_horizon` / `engine.champion_report`'s
    copy of the same logic - kept local rather than imported, same reason
    those two give: avoiding an import cycle back into this backfill.
    """
    dates = sorted(d for d in available if start <= d <= end)
    if horizon != "week":
        return dates
    weekly, seen = [], set()
    for d in dates:
        key = pd.Timestamp(d).isocalendar()[:2]
        if key not in seen:
            seen.add(key)
            weekly.append(d)
    return weekly


def _backfill_horizon(dataset: pd.DataFrame, source: dict, horizon: str, out_dir: Path, generated_at: str) -> int:
    available = sorted(dataset["date"].unique())
    end = str(dataset["date"].max())
    written = 0
    for session in _dates_for_horizon(available, EXAM_START, end, horizon):
        authorize(session, EXAM_SPLIT)
        asof_rows = dataset.loc[dataset["date"] < session, "date"]
        if asof_rows.empty:
            continue  # no prior history to truncate to (mirrors engine.replay for a split's first date)
        asof = str(asof_rows.max())
        tables, labels = build_tables(dataset, source, horizon, session, asof)
        payload = make_payload(horizon, session, asof, generated_at, labels, tables)
        score_picks_file(payload, dataset)  # historical: the outcome is always already known
        path = out_dir / horizon / f"{session}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n")
        written += 1
    return written


def run_exam_backfill(dataset: pd.DataFrame, source: dict, out_dir: Path, generated_at: str) -> int:
    """Writes `<out_dir>/day/*.json` and `<out_dir>/week/*.json` for every
    exam-split session through `asof`. Returns the number of files
    written. Callers must only invoke this when `out_dir` does not yet
    exist - the one-time, no-overwrite guard is `run.py`'s job (checking
    existence here too would just move the same race one function down).
    """
    written = _backfill_horizon(dataset, source, "day", out_dir, generated_at)
    written += _backfill_horizon(dataset, source, "week", out_dir, generated_at)
    return written
