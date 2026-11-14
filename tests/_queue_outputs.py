"""Run `engine.run_queue.main` end to end on the synthetic horizon dataset and fingerprint every output.

No `test_` prefix, so pytest does not collect it. Used by `tests/test_exits.py` to prove that, with no
`exit:` block in any experiment, the queue writes exactly what the engine wrote before exit scoring was
added: the fingerprints in `tests/golden/no_exit_golden.json` were produced by `fingerprint` on the
engine as it stood before that change (commit 1af656e).
"""

from __future__ import annotations

import csv
import hashlib
import sys
from pathlib import Path

import yaml

from tests._horizon_dataset import make_dataset

SPLITS = {"train": {"start": "2015-01-01", "end": "2016-03-31"},
          "validation": {"start": "2016-04-01", "end": "2016-06-30", "max_queries_per_week": 60}}

STRATEGY = (
    "import numpy as np, pandas as pd\n\ndef score(history):\n"
    "    last = history[history['date'] == history['date'].max()].set_index('symbol')\n"
    "    r = last['close'] / last['open'] - 1.0\n"
    "    return pd.Series(-r.to_numpy() * 100, index=last.index)\n"
)

EXPERIMENTS = {
    "q-day": {"horizon": "day", "dates": {"start": "2015-02-02", "end": "2015-09-30"}},
    "q-week": {"horizon": "week", "dates": {"start": "2015-02-02", "end": "2016-03-31"}},
    "q-month": {"horizon": "month", "dates": {"start": "2015-02-02", "end": "2016-03-31"}},
}


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def run(tmp_path: Path, monkeypatch, extra: dict | None = None) -> Path:
    """Write the strategy, dataset and ymls under `tmp_path`, run the queue, return the done dir.
    `extra` maps an experiment id to keys merged into its yml (e.g. an `exit:` block)."""
    monkeypatch.syspath_prepend(str(tmp_path))
    (tmp_path / "q_signal.py").write_text(STRATEGY)
    data = tmp_path / "dataset.parquet"
    make_dataset().to_parquet(data, index=False)
    pending, done = tmp_path / "pending", tmp_path / "done"
    pending.mkdir()
    for exp_id, exp in EXPERIMENTS.items():
        body = {"id": exp_id, "strategy": "q_signal", "split": "train", **exp, **(extra or {}).get(exp_id, {})}
        (pending / f"{exp_id}.yml").write_text(yaml.dump(body))
    monkeypatch.setattr("engine.run_queue.load_splits", lambda *a, **k: SPLITS)
    monkeypatch.setattr("engine.experiment_report.load_splits", lambda *a, **k: SPLITS)
    monkeypatch.setattr("engine.run_queue.maybe_write_champion_report", lambda *a, **k: False)
    monkeypatch.setattr("engine.run_queue.maybe_write_selftest_report", lambda *a, **k: False)
    monkeypatch.setattr("engine.run_queue.maybe_log_holdout_query", lambda *a, **k: False)
    monkeypatch.setattr(sys, "argv", ["run_queue.py", "--data", str(data), "--pending", str(pending),
                                      "--done", str(done), "--leaderboard", str(tmp_path / "board.md"),
                                      "--trials-ledger", str(tmp_path / "trials.csv"),
                                      "--market-line-report", str(tmp_path / "ml.md"),
                                      "--holdout-ledger", str(tmp_path / "holdout.csv")])
    from engine.run_queue import main
    main()
    return done


def fingerprint(tmp_path: Path) -> dict:
    """SHA-256 of every file the queue wrote (the trials ledger without its wall-clock timestamp column)."""
    out = {}
    for f in sorted((tmp_path / "done").rglob("*")):
        if f.is_file():
            out[str(f.relative_to(tmp_path))] = _sha(f.read_bytes())
    for name in ("board.md", "ml.md"):
        if (tmp_path / name).exists():
            out[name] = _sha((tmp_path / name).read_bytes())
    with open(tmp_path / "trials.csv", newline="") as f:
        rows = [{k: v for k, v in r.items() if k != "timestamp"} for r in csv.DictReader(f)]
    out["trials.csv (no timestamp)"] = _sha(repr(rows).encode())
    return out
