"""The committed draft source (`config/live_source.draft.json`) runs end to end on synthetic data.

The Live dry run only writes a session that has no picks file yet, so it cannot exercise a new source
until a new session is due. This drives `picks.run.run` in dry mode with the committed draft copied
beside a temporary source path, on a synthetic dataset that carries the futures OI columns E2A reads, and
checks each table names the draft's strategy, carries the provisional disclaimer, and uses no forbidden
publishing words (SPEC.md section 10).
"""

import json
import shutil

import numpy as np
import pytest

from picks.run import run
from picks.source import DRAFT_SOURCE_PATH
from tests._picks_dataset import make_dataset

FORBIDDEN = ("buy", "sell", "target", "stop-loss", "stop loss", "entry price")


def _dataset_with_oi(dates):
    data = make_dataset({"UP": 0.01, "DOWN": -0.01, "FLAT": 0.0, "UP2": 0.02, "DOWN2": -0.02, "UP3": 0.005}, dates)
    rng = np.random.default_rng(0)
    data["oi_futstk"] = 10_000.0
    data["oi_chg_futstk"] = rng.normal(0, 500, len(data))
    return data


@pytest.mark.skipif(not DRAFT_SOURCE_PATH.exists(), reason="no draft committed")
def test_draft_source_runs_day_and_week_tables(tmp_path):
    from tests.test_picks_run import _dates_ending, _write_parquet

    source_dir = tmp_path / "config"
    source_dir.mkdir()
    shutil.copy(DRAFT_SOURCE_PATH, source_dir / "live_source.draft.json")
    draft = json.loads(DRAFT_SOURCE_PATH.read_text())["tables"]

    dates = _dates_ending("2026-10-16")  # Friday, so Monday 19 Oct gets a week table too
    data_path = _write_parquet(tmp_path, _dataset_with_oi(dates))
    out_dir = tmp_path / "out"
    run(data_path, out_dir, mode="dry", source_path=source_dir / "live_source.json")

    for horizon in ("day", "week"):
        payload = json.loads((out_dir / horizon / "2026-10-19.json").read_text())
        assert "Provisional strategy: it has not passed the lab's tests. No proven edge yet." in payload["disclaimer"]
        for side in ("bullish", "bearish"):
            expected = draft[f"{horizon}_{side}"]["strategy"]
            for pick in payload["tables"][side]:
                assert pick["strategy"] == expected
                text = pick.get("reasoning", "").lower()
                assert not any(word in text for word in FORBIDDEN), text
