"""Not a strategy candidate - exercises the replay engine against real cached data.

B4's acceptance needs `replay.yml` to actually run `engine.run_queue` on the
train split in GitHub Actions, not just succeed with an empty queue. This
module scores every symbol bullish every day (no signal, no claim), purely
so `experiments/pending/engine-smoketest-day.yml` has something real to run
against `data/dataset.parquet`. It is never added to `cards/catalog.csv`,
never evaluated against a gate, and never a roster candidate.
"""

from __future__ import annotations

import pandas as pd


def score(history: pd.DataFrame) -> pd.Series:
    symbols = history["symbol"].unique() if not history.empty else []
    return pd.Series([1.0] * len(symbols), index=symbols)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    return "engine smoketest: always bullish"
