"""Writes `<out_dir>/summary.json` (B9's "Summary" step, `state/queue.md`):

"hits and picks per table per week and month, totals for exam and for
live, and the market line per table for context. No P&L."

Reads back the picks files `run.py` already wrote/scored under
`<out_dir>/{day,week}` (live) and `<out_dir>/exam/{day,week}` (exam) -
this module never recomputes a pick or a hit, only counts what is
already on disk, so it can never disagree with the files a person or the
site would actually read.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

from engine.scoring import market_line, moves_for_horizon, universe_membership

TABLE_SIDE = {"bullish": 1, "bearish": -1}
SECTIONS = ("exam", "live")


def _picks_files(section_dir: Path) -> list[dict]:
    out = []
    for horizon_dir in ("day", "week"):
        d = section_dir / horizon_dir
        if not d.exists():
            continue
        for p in sorted(d.glob("*.json")):
            out.append(json.loads(p.read_text()))
    return out


def _period_keys(session: str) -> tuple[str, str]:
    ts = pd.Timestamp(session)
    iso = ts.isocalendar()
    return f"{iso.year}-W{iso.week:02d}", ts.strftime("%Y-%m")


def _empty_bucket() -> dict:
    return {"n_picks": 0, "n_scored": 0, "n_hits": 0, "by_week": defaultdict(int), "by_month": defaultdict(int)}


def _tally(files: list[dict]) -> dict:
    """`{"day_bullish": {...}, "day_bearish": {...}, ...}`, each a bucket
    from `_empty_bucket()` plus the raw `{(period_key): n_picks}` counts
    `by_week`/`by_month` hold - `_finalize` turns those into `{picks,
    hits}` pairs once every file has been tallied, since a hit count
    alone (without `by_week_hits` tracked separately below) can't be
    reconstructed afterwards.
    """
    tables = defaultdict(lambda: {"n_picks": 0, "n_scored": 0, "n_hits": 0, "weeks": defaultdict(lambda: [0, 0]), "months": defaultdict(lambda: [0, 0])})
    for data in files:
        horizon, session = data["horizon"], data["session"]
        week_key, month_key = _period_keys(session)
        for side_name, picks in data.get("tables", {}).items():
            bucket = tables[f"{horizon}_{side_name}"]
            for pick in picks:
                bucket["n_picks"] += 1
                bucket["weeks"][week_key][0] += 1
                bucket["months"][month_key][0] += 1
                if pick.get("late") or "hit" not in pick:
                    continue
                bucket["n_scored"] += 1
                bucket["weeks"][week_key][1] += pick["hit"]
                bucket["months"][month_key][1] += pick["hit"]
                bucket["n_hits"] += int(pick["hit"])
    return tables


def _finalize(tables: dict) -> dict:
    out = {}
    for key, bucket in tables.items():
        out[key] = {
            "n_picks": bucket["n_picks"],
            "n_scored": bucket["n_scored"],
            "n_hits": bucket["n_hits"],
            "by_week": {k: {"n_picks": v[0], "n_hits": v[1]} for k, v in sorted(bucket["weeks"].items())},
            "by_month": {k: {"n_picks": v[0], "n_hits": v[1]} for k, v in sorted(bucket["months"].items())},
        }
    return out


def _market_line_for(dataset: pd.DataFrame | None, horizon: str, side: int, sessions: set[str]) -> float | None:
    """Mean market line (SPEC.md section 3) over exactly the session dates
    this table was actually scored on - context for whether the table's
    own hit rate beat a do-nothing baseline on those same dates, not a
    whole-history average.
    """
    if dataset is None or not sessions:
        return None
    line = market_line(moves_for_horizon(dataset, horizon), universe_membership(dataset), side)
    line = line.reindex([d for d in sessions if d in line.index]).dropna()
    return float(line.mean()) if not line.empty else None


def build_summary(out_dir: Path, dataset: pd.DataFrame | None = None) -> dict:
    summary: dict = {}
    for section in SECTIONS:
        files = _picks_files(out_dir / section if section == "exam" else out_dir)
        tables = _finalize(_tally(files))
        sessions_by_table: dict[str, set[str]] = defaultdict(set)
        for data in files:
            for side_name in data.get("tables", {}):
                sessions_by_table[f"{data['horizon']}_{side_name}"].add(data["session"])
        for key, bucket in tables.items():
            horizon, side_name = key.split("_", 1)
            bucket["market_line"] = _market_line_for(dataset, horizon, TABLE_SIDE[side_name], sessions_by_table[key])
        summary[section] = tables
    return summary


def write_summary(out_dir: Path, dataset: pd.DataFrame | None = None) -> Path:
    path = out_dir / "summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_summary(out_dir, dataset), indent=2) + "\n")
    return path
