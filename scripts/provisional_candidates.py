"""List the train experiments that meet SPEC.md section 10's provisional rule, and stage their validation queries.

The provisional rule (go-live without a gated strategy) picks, per table, the strategy with the highest
validation edge released by the holdout among those with at least 500 train picks, a positive train edge
and a positive train directional move, all for the `top` selection (`engine/experiment_report.py`).
This script applies the train half of that rule to every `experiments/done/*/results.json`, so no
eligible reading is missed by hand, and can write one `split: validation` experiment per eligible
strategy for `engine.run_queue` to answer through Thresholdout.

It reads only committed train results and never touches validation data. Spending a query is the
queue's job (`engine.experiment_report.answer_validation`, budgeted by `gates/budgets.py`): moving a
staged file into `experiments/pending/` is the step that spends it.

    python3 -m scripts.provisional_candidates --done experiments/done
    python3 -m scripts.provisional_candidates --done experiments/done --stage research/notes/validation_batch
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

MIN_PICKS = 500
VALIDATION = {"start": "2021-01-01", "end": "2023-12-31"}
TABLES = [("day", "bullish"), ("day", "bearish"), ("week", "bullish"), ("week", "bearish")]
NOT_STRATEGIES = {"strategies.engine_smoketest"}


def _rows(done_dir: Path):
    for path in sorted(done_dir.glob("*/results.json")):
        res = json.loads(path.read_text())
        if res.get("split") != "train" or res.get("strategy") in NOT_STRATEGIES:
            continue
        yield res


def eligible(done_dir: Path) -> dict[tuple[str, str], list[dict]]:
    """Per (horizon, side), the train experiments meeting the provisional letter, best train edge first."""
    out: dict[tuple[str, str], list[dict]] = {t: [] for t in TABLES}
    for res in _rows(done_dir):
        for side in ("bullish", "bearish"):
            s = res["selections"]["top"].get(side, {})
            n, edge, move = s.get("n_picks", 0), s.get("edge"), s.get("directional_move")
            if n >= MIN_PICKS and edge is not None and edge > 0 and move is not None and move > 0:
                out[(res["horizon"], side)].append(
                    {"id": res["id"], "strategy": res["strategy"], "horizon": res["horizon"], "side": side,
                     "n_picks": n, "edge": edge, "edge_t": s.get("edge_t"), "directional_move": move})
    for rows in out.values():
        rows.sort(key=lambda r: (-r["edge"], r["id"]))
    return out


def validation_id(train_id: str) -> str:
    return f"{train_id}-validation"


def already_asked(ledger: Path, done_dir: Path, train_id: str) -> bool:
    """True when this train experiment's validation query is answered or logged (never ask twice)."""
    vid = validation_id(train_id)
    if (done_dir / vid / "holdout.json").exists():
        return True
    if ledger.exists() and ledger.stat().st_size:
        with open(ledger, newline="") as f:
            return any(str(r.get("query_id", "")).startswith(vid + "-") for r in csv.DictReader(f))
    return False


def experiment_yaml(row: dict, sides: list[str]) -> str:
    """One `split: validation` experiment in the format `engine.run_queue` reads."""
    tables = ", ".join(f"{row['horizon']}-{s}" for s in sides)
    return (
        f"# Validation query for the go-live provisional rule (SPEC.md section 10): {tables}.\n"
        f"# Staged by scripts/provisional_candidates.py from the scored train experiment below; the queue\n"
        f"# answers both sides through Thresholdout and logs them in ledger/holdout_queries.csv.\n"
        f"id: {validation_id(row['id'])}\n"
        f"strategy: {row['strategy']}\n"
        f"split: validation\n"
        f"horizon: {row['horizon']}\n"
        f"train_experiment: {row['id']}\n"
        f"dates:\n"
        f"  start: {VALIDATION['start']}\n"
        f"  end: {VALIDATION['end']}\n"
    )


def stage(table_rows: dict, out_dir: Path, ledger: Path, done_dir: Path) -> list[Path]:
    """Write one validation experiment per eligible train experiment not yet asked. Returns the files."""
    by_id: dict[str, tuple[dict, list[str]]] = {}
    for rows in table_rows.values():
        for r in rows:
            by_id.setdefault(r["id"], (r, []))[1].append(r["side"])
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for train_id, (row, sides) in sorted(by_id.items()):
        if already_asked(ledger, done_dir, train_id):
            continue
        path = out_dir / f"{validation_id(train_id)}.yml"
        path.write_text(experiment_yaml(row, sides))
        written.append(path)
    return written


def render(table_rows: dict) -> str:
    lines = ["# Provisional-rule candidates (train half of SPEC.md section 10)", "",
             f"`top` selection; at least {MIN_PICKS} train picks, positive edge and positive directional move "
             "after costs. Best train edge first. The validation edge released by the holdout decides.", ""]
    for horizon, side in TABLES:
        rows = table_rows[(horizon, side)]
        lines.append(f"## {horizon} / {side}")
        lines.append("")
        if not rows:
            lines += ["None eligible: the table falls back to champion v1.", ""]
            continue
        lines += ["| Experiment | Picks | Edge (pts) | t | Dir. move |", "|---|---|---|---|---|"]
        for r in rows:
            t = "" if r["edge_t"] is None else f"{r['edge_t']:.2f}"
            lines.append(f"| {r['id']} | {r['n_picks']} | {100 * r['edge']:+.2f} | {t} | {100 * r['directional_move']:+.3f}% |")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--done", default="experiments/done")
    ap.add_argument("--ledger", default="ledger/holdout_queries.csv")
    ap.add_argument("--stage", help="directory to write validation experiments into (not experiments/pending)")
    ap.add_argument("--out", help="write the markdown table here instead of stdout")
    a = ap.parse_args(argv)
    done = Path(a.done)
    rows = eligible(done)
    md = render(rows)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(md + "\n")
    else:
        print(md)
    if a.stage:
        for p in stage(rows, Path(a.stage), Path(a.ledger), done):
            print(f"staged {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
