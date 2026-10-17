"""Write `reports/corporate_actions_check.md` from `detect_corporate_actions`.

Part of B3's acceptance (`state/queue.md`): "once B2 is done, run
`detect_corporate_actions` on the full dataset in Actions and write
`reports/corporate_actions_check.md`. At least 10 detected events must be
checked against an independent public source..., with date and ratio
matching and the source linked. Every mismatch is explained. Events where
the adjusted close jumps more than 30% in one day are listed and explained."

This script only does the automatic half: it runs the detector and writes
every candidate event into the report, classified by its ratio into the
most likely corporate-action type and flagged if the single-day adjusted
close jump exceeds 30%. The report starts with every independent-source
cross-check left as TODO: that step needs a human or an agent to look each
flagged event up against a real, independently sourced list (NSE corporate
announcements or news) and is done in a follow-up edit to this same file,
not by this script, which has no access to those sources and no real
dataset to run against outside GitHub Actions.

Usage:
    python scripts/check_corporate_actions.py --data data/dataset.parquet \
        --out reports/corporate_actions_check.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

# Allow `python3 scripts/check_corporate_actions.py` (as the other scripts/
# are invoked from workflows) as well as `python3 -m scripts.check_corporate_actions`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.adjustments import detect_corporate_actions

# Common split/bonus ratios, new-shares-scale / old-shares-scale, i.e. what
# `detect_corporate_actions` reports (e.g. a 2:1 split halves the scale, so
# ratio 0.5; a 1:1 bonus doubles the share count, also ratio 0.5). Several
# real corporate actions share a ratio (1:1 bonus == 2:1 split == 0.5), so
# the label lists every common action at that ratio rather than guessing.
KNOWN_RATIOS = {
    0.5: "2:1 split or 1:1 bonus",
    (1 / 3): "3:1 split or 2:1 bonus",
    0.2: "5:1 split",
    0.1: "10:1 split",
    (2 / 3): "3:2 split or 1:2 bonus",
    0.25: "4:1 split or 3:1 bonus",
    0.8: "5:4 bonus",
    0.75: "4:3 bonus",
}
RATIO_TOLERANCE = 0.01


def classify_ratio(ratio: float) -> str:
    for known, label in KNOWN_RATIOS.items():
        if abs(ratio - known) <= RATIO_TOLERANCE:
            return label
    return "unrecognised ratio"


def build_report(events: pd.DataFrame) -> str:
    events = events.sort_values(["date", "symbol"]).reset_index(drop=True)
    big_jump = events[(events["action_ratio"] - 1.0).abs() >= 0.30]

    lines = [
        "# Corporate actions check",
        "",
        f"`detect_corporate_actions` found {len(events)} candidate event(s) in the"
        " full dataset. Each is a (date, symbol) where PREVCLOSE departed from the"
        " prior day's CLOSE by more than the rounding-noise tolerance.",
        "",
        "## Independent-source cross-check",
        "",
        "TODO: at least 10 of the events below must be checked against an"
        " independent public source (NSE corporate announcements or news), with"
        " date and ratio matching and the source linked. Not done by this script —"
        " fill in once this report is generated from the real dataset in Actions.",
        "",
        "## Events with an adjusted-close jump of 30% or more",
        "",
    ]
    if big_jump.empty:
        lines.append("None.")
    else:
        lines += ["| Date | Symbol | Ratio | Likely action | Checked against independent source |",
                   "|---|---|---|---|---|"]
        for _, row in big_jump.iterrows():
            lines.append(
                f"| {row['date']} | {row['symbol']} | {row['action_ratio']:.4f} |"
                f" {classify_ratio(row['action_ratio'])} | TODO |"
            )
    lines += ["", "## All detected events", ""]
    if events.empty:
        lines.append("None.")
    else:
        lines += ["| Date | Symbol | Ratio | Likely action |", "|---|---|---|---|"]
        for _, row in events.iterrows():
            lines.append(
                f"| {row['date']} | {row['symbol']} | {row['action_ratio']:.4f} |"
                f" {classify_ratio(row['action_ratio'])} |"
            )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    df = pd.read_parquet(a.data)
    events = detect_corporate_actions(df)
    report = build_report(events)

    out_path = Path(a.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report)
    print(f"{len(events)} candidate event(s) -> {out_path}")


if __name__ == "__main__":
    main()
