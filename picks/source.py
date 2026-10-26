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

# A draft of the next `config/live_source.json`, read by dry mode only, so a
# choice can be exercised on real data before the roster window in which the
# real file may change (SPEC.md section 7). Live mode never reads it.
DRAFT_SOURCE_PATH = LIVE_SOURCE_PATH.with_name("live_source.draft.json")

TABLE_KEYS = ("day_bullish", "day_bearish", "week_bullish", "week_bearish")

# A strategy id is `<module under strategies/>@v<N>`; this registry is the
# one place that resolves an id to the module `score`/`rules_fired` actually
# live in, so a future strategy only needs one new line here, not a change
# to `run.py`. Besides champion v1 (B7), it lists every strategy the
# provisional rule (SPEC.md section 10) could choose on Fri 30 Oct
# (`research/notes/validation_answers_2026-10-26.md`), so the first live
# run cannot fail on an unknown id.
_REGISTRY = {
    "champion_v1@v1": "strategies.champion_v1",
    "e2a_a02_crowded@v1": "strategies.e2a_a02_crowded",
    "e2a_d01c_fallback@v1": "strategies.e2a_d01c_fallback",
    "d01c_oi_fade@v1": "strategies.d01c_oi_fade",
    "a01_weekly_reversal@v1": "strategies.a01_weekly_reversal",
    "t05c_upcross_fade@v1": "strategies.t05c_upcross_fade",
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


def load_live_source(mode: str, path: Path = LIVE_SOURCE_PATH, draft_path: Path = DRAFT_SOURCE_PATH) -> dict | None:
    """Returns the parsed source config, or `None` meaning "do nothing" (live
    mode only, when the file does not exist yet - `run.py` must exit 0, not
    write anything). Dry mode never returns `None`: it falls back to
    `DEFAULT_SOURCE` so the code path can be exercised on real data before
    the real file is committed (`state/queue.md`'s B9 acceptance: "A push to
    `picks/` gives a green Live dry run"). Before falling back, dry mode uses
    the draft (`DRAFT_SOURCE_PATH`) if one exists.
    """
    if path.exists():
        return json.loads(path.read_text())
    if mode == "dry":
        if draft_path.exists():
            return json.loads(draft_path.read_text())
        return DEFAULT_SOURCE
    return None
