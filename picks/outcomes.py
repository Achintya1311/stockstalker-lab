"""Scoring already-committed picks files (B9's "Score first" step,
`state/queue.md`).

Per SPEC.md section 3: hit is the move strictly in the picked direction
(flat counts as a miss). `move_pct`/`move_rs` are the plain open-to-close
(day) or Monday-open-to-Friday-close (week) move, not the after-costs
`directional_move` internal metric (SPEC.md section 3 keeps that one
internal-only) - these are the public table's own "Move (% and ₹)" column
(SPEC.md section 10).
"""

from __future__ import annotations

import subprocess
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

IST = ZoneInfo("Asia/Kolkata")
MARKET_OPEN = time(9, 15)

SIDE_OF_TABLE = {"bullish": 1, "bearish": -1}


def day_session_available(dataset: pd.DataFrame, session: str) -> bool:
    return bool((dataset["date"] == session).any())


def week_session_available(dataset: pd.DataFrame, monday: str) -> bool:
    """True once the week starting at `monday` has fully passed - i.e. the
    dataset already holds a later ISO week, so that week's last trading
    day's close (the week pick's outcome) is known. Checking for the
    week's own presence is not enough: a week in progress has rows but not
    yet its Friday close.
    """
    target = pd.Timestamp(monday).isocalendar()
    latest = pd.to_datetime(dataset["date"]).max()
    if pd.isna(latest):
        return False
    latest_iso = latest.isocalendar()
    return (latest_iso.year, latest_iso.week) > (target.year, target.week)


def _outcome_rows(dataset: pd.DataFrame, horizon: str, session: str) -> pd.DataFrame:
    """`symbol, open, close` for the pick's own outcome window."""
    if horizon == "day":
        day = dataset.loc[dataset["date"] == session, ["symbol", "open", "close"]]
        return day.drop_duplicates("symbol").set_index("symbol")
    iso = pd.Timestamp(session).isocalendar()
    week_dates = pd.to_datetime(dataset["date"]).dt.isocalendar()
    in_week = dataset.loc[(week_dates.year == iso.year) & (week_dates.week == iso.week)]
    opens = in_week.loc[in_week.groupby("symbol")["date"].idxmin(), ["symbol", "open"]]
    closes = in_week.loc[in_week.groupby("symbol")["date"].idxmax(), ["symbol", "close"]]
    return opens.merge(closes, on="symbol").set_index("symbol")


def score_picks_file(data: dict, dataset: pd.DataFrame) -> bool:
    """Adds `open`, `close`, `move_pct`, `move_rs`, `hit` to every pick in
    `data["tables"]`, in place. Returns whether anything was added (false
    if the outcome is not available yet, or every pick already carries
    `hit` - re-scoring an already-scored file is a no-op, never a
    re-decision of its picks).
    """
    horizon, session = data["horizon"], data["session"]
    available = (
        day_session_available(dataset, session)
        if horizon == "day"
        else week_session_available(dataset, session)
    )
    if not available:
        return False

    outcomes = _outcome_rows(dataset, horizon, session)
    changed = False
    for table_name, picks in data.get("tables", {}).items():
        side = SIDE_OF_TABLE[table_name]
        for pick in picks:
            if "hit" in pick:
                continue
            row = outcomes.loc[pick["symbol"]] if pick["symbol"] in outcomes.index else None
            if row is None:
                continue
            open_, close_ = float(row["open"]), float(row["close"])
            move = close_ / open_ - 1.0
            pick.update(
                open=open_,
                close=close_,
                move_pct=move * 100.0,
                move_rs=close_ - open_,
                hit=bool((move * side) > 0),
            )
            changed = True
    return changed


_REPO_ROOT = Path(__file__).resolve().parent.parent


def first_commit_time(path: Path, repo_root: Path = _REPO_ROOT) -> datetime | None:
    """The commit time (tz-aware) the file at `path` was first added under
    git, or `None` if it has no commit yet (a run scoring its own
    just-written-but-not-yet-committed file) or git is unavailable.
    `repo_root` defaults to this checkout; tests point it at a throwaway
    repo instead of needing `path` to live inside the real one.
    """
    try:
        out = subprocess.run(
            ["git", "log", "--diff-filter=A", "--format=%cI", "--follow", "--", str(path)],
            capture_output=True,
            text=True,
            check=True,
            cwd=repo_root,
        ).stdout.strip()
    except Exception:
        return None
    lines = [l for l in out.splitlines() if l]
    if not lines:
        return None
    return min(datetime.fromisoformat(l) for l in lines)


def is_late(commit_time: datetime, session: str) -> bool:
    """True iff `commit_time` falls after 09:15 IST on `session` - SPEC.md
    section 10's "committed before 09:15 IST". Late picks are still shown
    (`state/queue.md`: "Add `late: true`... Late picks are shown but left
    out of hit rates") - this function only answers the timing question;
    excluding late picks from hit-rate aggregation is the summary step's job.
    """
    cutoff = datetime.combine(pd.Timestamp(session).date(), MARKET_OPEN, tzinfo=IST)
    return commit_time.astimezone(IST) > cutoff


def mark_late(data: dict, path: Path, repo_root: Path = _REPO_ROOT) -> bool:
    """Sets `late: true` on every pick if `path`'s first commit was after
    09:15 IST on `data["session"]`. No-op (returns False) if the commit
    time can't be determined yet, or if every pick already carries the key.
    """
    if all("late" in pick for picks in data.get("tables", {}).values() for pick in picks):
        return False
    commit_time = first_commit_time(path, repo_root)
    if commit_time is None:
        return False
    late = is_late(commit_time, data["session"])
    for picks in data.get("tables", {}).values():
        for pick in picks:
            pick["late"] = late
    return True
