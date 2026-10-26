"""CLI entry point for B9 (`state/queue.md`), invoked by `.github/workflows/live.yml`:

    python3 -m picks.run --data <parquet> --out <dir> --mode live|dry

Order, per the contract: score every already-committed picks file whose
outcome is now known, then pick the next session (and the next week's,
on the week's last trading day), then (live mode only) the one-time exam
backfill, then the summary. Every step after sourcing is independent of
`--mode` except: dry mode falls back to champion v1 when
`config/live_source.json` is missing (so the code can be exercised on
real data before go-live), live mode does nothing at all when it's
missing (SPEC.md section 10's "chosen by Friday 30 Oct" - before that,
a live run must not invent a source and must not fail the workflow).
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from picks.calendar import next_trading_session, starts_new_iso_week
from picks.exam import run_exam_backfill
from picks.outcomes import mark_late, score_picks_file
from picks.payload import build_tables, make_payload
from picks.source import LIVE_SOURCE_PATH, load_live_source
from picks.xray import build_xray
from picks.summary import write_summary

HORIZON_DIRS = ("day", "week")


def _rescore_existing(out_dir: Path, dataset: pd.DataFrame) -> int:
    rescored = 0
    for horizon_dir in HORIZON_DIRS:
        d = out_dir / horizon_dir
        if not d.exists():
            continue
        for path in sorted(d.glob("*.json")):
            data = json.loads(path.read_text())
            scored = score_picks_file(data, dataset)
            lated = mark_late(data, path)
            if scored or lated:
                path.write_text(json.dumps(data, indent=2) + "\n")
                rescored += 1
    return rescored


def _write_if_absent(path: Path, payload: dict) -> bool:
    """Never overwrites an existing picks file - a session's picks, once
    written, are the committed record of what was actually picked; a
    later run only scores them (`_rescore_existing`), never redecides them.
    """
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return True


def generate_next_sessions(dataset: pd.DataFrame, source: dict, out_dir: Path, generated_at: str) -> list[str]:
    asof = str(dataset["date"].max())
    session = next_trading_session(asof)
    written = []

    day_tables, day_labels = build_tables(dataset, source, "day", session, asof)
    day_payload = make_payload("day", session, asof, generated_at, day_labels, day_tables, xray=build_xray(dataset, source, session, asof))
    if _write_if_absent(out_dir / "day" / f"{session}.json", day_payload):
        written.append(f"day/{session}.json")

    if starts_new_iso_week(asof, session):
        week_tables, week_labels = build_tables(dataset, source, "week", session, asof)
        week_payload = make_payload("week", session, asof, generated_at, week_labels, week_tables)
        if _write_if_absent(out_dir / "week" / f"{session}.json", week_payload):
            written.append(f"week/{session}.json")

    return written


def run(data_path: Path, out_dir: Path, mode: str, source_path: Path = LIVE_SOURCE_PATH) -> None:
    if not data_path.exists():
        print(f"no dataset at {data_path}; nothing to score or pick")
        return
    dataset = pd.read_parquet(data_path)

    source = load_live_source(mode, source_path, source_path.with_name("live_source.draft.json"))
    if source is None:
        print("no config/live_source.json yet; live mode does nothing until it is committed")
        return

    generated_at = datetime.now(timezone.utc).isoformat()

    rescored = _rescore_existing(out_dir, dataset)
    print(f"rescored {rescored} existing picks file(s)")

    written = generate_next_sessions(dataset, source, out_dir, generated_at)
    for w in written:
        print(f"wrote {out_dir / w}")
    if not written:
        print("next session's picks already exist; nothing new written")

    if mode == "live":
        exam_dir = out_dir / "exam"
        if not exam_dir.exists():
            n = run_exam_backfill(dataset, source, exam_dir, generated_at)
            print(f"exam backfill: wrote {n} file(s) to {exam_dir}")

    summary_path = write_summary(out_dir, dataset)
    print(f"wrote {summary_path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", choices=["live", "dry"], required=True)
    args = ap.parse_args()
    run(Path(args.data), Path(args.out), args.mode)


if __name__ == "__main__":
    main()
