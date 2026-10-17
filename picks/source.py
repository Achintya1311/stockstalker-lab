"""Reads `config/live_source.json` (B9's "Source" step, `state/queue.md`).

Contract: `{"chosen_on": "YYYY-MM-DD", "tables": {"day_bullish": {"strategy":
"<id>@vN", "label": "provisional"|"gated", "why": "..."}, "day_bearish": ...,
"week_bullish": ..., "week_bearish": ...}}`.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

LIVE_SOURCE_PATH = Path(__file__).resolve().parent.parent / "config" / "live_source.json"

TABLE_KEYS = ("day_bullish", "day_bearish", "week_bullish", "week_bearish")

# Only champion v1 exists as a strategy so far (B7). A strategy id is
# `<module under strategies/>@v<N>`; this registry is the one place that
# resolves an id to the module `score`/`rules_fired` actually live in, so
# a future strategy only needs one new line here, not a change to `run.py`.
_REGISTRY = {
    "champion_v1@v1": "strategies.champion_v1",
}

# The provisional fallback this contract names when no source file exists
# yet (dry mode only; `state/queue.md` B9's acceptance and SPEC.md section
# 10's "if none qualifies, champion v1").
DEFAULT_SOURCE = {
    "chosen_on": None,
    "tables": {
        key: {
            "strategy": "champion_v1@v1",
            "label": "provisional",
            "why": "no config/live_source.json yet; defaulting to champion v1 per its contract",
        }
        for key in TABLE_KEYS
    },
}


def resolve_strategy(strategy_id: str):
    module_path = _REGISTRY.get(strategy_id)
    if module_path is None:
        raise ValueError(f"unknown strategy id {strategy_id!r}; add it to picks.source._REGISTRY")
    return importlib.import_module(module_path)


def load_live_source(mode: str, path: Path = LIVE_SOURCE_PATH) -> dict | None:
    """Returns the parsed source config, or `None` meaning "do nothing" (live
    mode only, when the file does not exist yet - `run.py` must exit 0, not
    write anything). Dry mode never returns `None`: it falls back to
    `DEFAULT_SOURCE` so the code path can be exercised on real data before
    the real file is committed (`state/queue.md`'s B9 acceptance: "A push to
    `picks/` gives a green Live dry run").
    """
    if path.exists():
        return json.loads(path.read_text())
    if mode == "dry":
        return DEFAULT_SOURCE
    return None
