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


def _noisy_dataset(dates, n_symbols=60, seed=2):
    """Random-walk symbols with daily ranges and varying volume, so pattern
    strategies (RSI(2) dips, narrow-range days, order blocks) get bars to fire on;
    the steady trends of `make_dataset` never give them one. Seed 2 makes every
    bullish candidate fire on both horizons (checked 26 Oct 2026)."""
    import pandas as pd

    from tests._picks_dataset import TURNOVER_WELL_ABOVE_FLOOR

    rng = np.random.default_rng(seed)
    frames = []
    for i in range(n_symbols):
        close = 100.0 * np.exp(np.cumsum(rng.normal(0.0005 * (i - n_symbols / 2), 0.02, len(dates))))
        prev = np.concatenate([[close[0]], close[:-1]])
        span = np.abs(rng.normal(0, 0.01, len(dates))) + 0.002
        frames.append(pd.DataFrame({
            "date": dates, "symbol": f"S{i:02d}", "open": prev,
            "high": np.maximum(prev, close) * (1 + span), "low": np.minimum(prev, close) * (1 - span),
            "close": close, "prevclose": prev, "volume": 1e6 * np.exp(rng.normal(0, 0.4, len(dates))),
            "turnover": TURNOVER_WELL_ABOVE_FLOOR, "has_future": True,
            "oi_futstk": 10_000.0, "oi_chg_futstk": rng.normal(0, 500, len(dates)),
        }))
    return pd.concat(frames, ignore_index=True)


BULLISH_CANDIDATES = [
    "t04_connors_rsi2@v1", "t10_nr7_narrow_range@v1", "t25_heikin_ashi@v1", "a05b_max_effect_ranked@v1",
    "a04_52_week_high@v1", "o05_order_block_weekly@v1", "i02_low_vol_level@v1",
]


@pytest.mark.skipif(not DRAFT_SOURCE_PATH.exists(), reason="no draft committed")
@pytest.mark.parametrize("candidate", BULLISH_CANDIDATES)
def test_each_bullish_candidate_runs_in_the_draft(tmp_path, candidate):
    """AB's edge-only batch (26 Oct 2026): whichever candidate wins validation can be
    dropped into both bullish tables of the draft and the run still completes, names
    it, and writes no forbidden publishing words."""
    import pandas as pd

    from tests.test_picks_run import _write_parquet

    source_dir = tmp_path / "config"
    source_dir.mkdir()
    draft = json.loads(DRAFT_SOURCE_PATH.read_text())
    for key in ("day_bullish", "week_bullish"):
        draft["tables"][key] = {"strategy": candidate, "label": "provisional", "why": "test"}
    (source_dir / "live_source.draft.json").write_text(json.dumps(draft))

    # 300 sessions, so the candidates that need a year of rows (I02, A04) can score.
    dates = list(pd.bdate_range(end="2026-10-16", periods=300).strftime("%Y-%m-%d"))
    data_path = _write_parquet(tmp_path, _noisy_dataset(dates))
    out_dir = tmp_path / "out"
    run(data_path, out_dir, mode="dry", source_path=source_dir / "live_source.json")

    for horizon in ("day", "week"):
        payload = json.loads((out_dir / horizon / "2026-10-19.json").read_text())
        assert payload["tables"]["bullish"], f"{candidate} wrote an empty {horizon} table"
        for pick in payload["tables"]["bullish"]:
            assert pick["strategy"] == candidate
            text = pick.get("reasoning", "").lower()
            assert not any(word in text for word in FORBIDDEN), text
