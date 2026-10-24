"""Shared picks-file payload shape (B9's picks file contract, `state/queue.md`).

Split out from `picks/run.py` so `picks/exam.py` can build the same shape
without importing `run.py` (which imports `exam.py` to invoke the backfill -
importing back the other way would be circular).
"""

from __future__ import annotations

from picks.select import pick_table
from picks.source import resolve_strategy

# SPEC.md section 10, word for word.
BASE_DISCLAIMER = (
    "Model output in testing. Not investment advice or a recommendation. "
    "Not a SEBI-registered research analyst. Every pick is shown, including misses."
)
PROVISIONAL_DISCLAIMER = "Provisional strategy: it has not passed the lab's tests. No proven edge yet."


def table_label(labels: set[str]) -> str:
    """"provisional" or "gated" when both tables in this file agree, else
    "mixed" - `config/live_source.json` picks a bullish and a bearish
    strategy independently per horizon, so one can be gated while the
    other is still provisional.
    """
    if labels == {"gated"}:
        return "gated"
    if labels == {"provisional"}:
        return "provisional"
    return "mixed"


def disclaimer_for(labels: set[str]) -> str:
    text = BASE_DISCLAIMER
    if "provisional" in labels or "mixed" in labels:
        text += " " + PROVISIONAL_DISCLAIMER
    return text


def build_tables(dataset, source: dict, horizon: str, session: str, asof: str) -> tuple[dict, set[str]]:
    """`{"bullish": [...], "bearish": [...]}` for `horizon`, plus the set of
    labels (`{"provisional"}`, `{"gated"}`, or both) the two sides carry.
    """
    bullish_cfg = source["tables"][f"{horizon}_bullish"]
    bearish_cfg = source["tables"][f"{horizon}_bearish"]
    bullish = pick_table(
        dataset, resolve_strategy(bullish_cfg["strategy"]), bullish_cfg["strategy"], session, 1, asof
    )
    bearish = pick_table(
        dataset, resolve_strategy(bearish_cfg["strategy"]), bearish_cfg["strategy"], session, -1, asof
    )
    return {"bullish": bullish, "bearish": bearish}, {bullish_cfg["label"], bearish_cfg["label"]}


def make_payload(horizon: str, session: str, asof: str, generated_at: str, labels: set[str], tables: dict, xray: dict | None = None) -> dict:
    payload = {
        "session": session,
        "horizon": horizon,
        "asof": asof,
        "generated_at": generated_at,
        "label": table_label(labels),
        "disclaimer": disclaimer_for(labels),
        "tables": tables,
    }
    if xray is not None:
        payload["xray"] = xray
    return payload
