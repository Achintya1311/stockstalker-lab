"""The committed `config/live_source.json` (30 Oct 2026, SPEC.md section 10) runs end to end.

Copies the real file beside a temporary source path and drives `picks.run.run` on synthetic random-walk
data, so every table's strategy must resolve, fire and carry the provisional disclaimer before the first
live run writes the picks for 2 Nov.
"""

import json
import shutil

import pytest

from picks.run import run
from picks.source import LIVE_SOURCE_PATH, TABLE_KEYS
from tests.test_picks_draft_source import FORBIDDEN, _noisy_dataset

PROVISIONAL = "Provisional strategy: it has not passed the lab's tests. No proven edge yet."


@pytest.mark.skipif(not LIVE_SOURCE_PATH.exists(), reason="no live source committed")
def test_live_source_contract():
    source = json.loads(LIVE_SOURCE_PATH.read_text())
    assert source["chosen_on"] == "2026-10-30"
    assert set(source["tables"]) == set(TABLE_KEYS)
    for table in source["tables"].values():
        assert table["label"] in ("provisional", "gated")
        assert "@v" in table["strategy"]


@pytest.mark.skipif(not LIVE_SOURCE_PATH.exists(), reason="no live source committed")
def test_live_source_runs_day_and_week_tables(tmp_path):
    import pandas as pd

    from tests.test_picks_run import _write_parquet

    source_dir = tmp_path / "config"
    source_dir.mkdir()
    shutil.copy(LIVE_SOURCE_PATH, source_dir / "live_source.json")
    tables = json.loads(LIVE_SOURCE_PATH.read_text())["tables"]

    dates = list(pd.bdate_range(end="2026-10-16", periods=320).strftime("%Y-%m-%d"))  # ends on a Friday
    data_path = _write_parquet(tmp_path, _noisy_dataset(dates))
    out_dir = tmp_path / "out"
    run(data_path, out_dir, mode="dry", source_path=source_dir / "live_source.json")

    for horizon in ("day", "week"):
        payload = json.loads((out_dir / horizon / "2026-10-19.json").read_text())
        assert PROVISIONAL in payload["disclaimer"]
        for side in ("bullish", "bearish"):
            expected = tables[f"{horizon}_{side}"]["strategy"]
            assert payload["tables"][side], f"{horizon} {side} fired no picks"
            for pick in payload["tables"][side]:
                assert pick["strategy"] == expected
                assert not any(word in pick.get("reasoning", "").lower() for word in FORBIDDEN)
