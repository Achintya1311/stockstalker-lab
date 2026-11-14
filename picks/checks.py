"""A pick's checks (AB, 14 Nov 2026): the C1 gates of its table's trigger, shown as plain context.

The gates G1-G10 (`strategies/g_gates.py`) did not reliably raise the hit rate on unseen data, so they do
not choose picks. Each published pick only carries their verdicts, like `picks/tech.py`: they describe the
pick, not why it was picked.

For a table whose live strategy is one of the four triggers in `strategies.g_gates.TRIGGERS`, every pick
gets the candidate gates `strategies.composite_v2.CANDIDATES` lists for that trigger's table, each asked
through `strategies.g_gates.GATES` (imported, never copied) on the same truncated history the pick was
made from, with the pick's side and the trigger:

- `checks`: `[{"k": "g3", "label": "stock-specific move", "ok": true | false | null}, ...]`, in the
  candidate order; `null` means the gate gave no verdict for this stock.
- `checks_agree`: how many are true; `checks_total`: how many are not null.

When the table's strategy is not one of the four triggers (champion fallback, any other strategy), or the
trigger's own side differs from the table's, there are no checks and the keys are left out.

Picks files are write-once, so the keys appear from the next file written; nothing existing is rewritten.
"""

from __future__ import annotations

import pandas as pd

from strategies import composite_v2 as V2
from strategies import g_gates as G

# Plain words, at most four each.
LABELS: dict[str, str] = {
    "g1": "trend on its side",
    "g2": "not fading a leader",
    "g3": "stock-specific move",
    "g4": "no gap",
    "g5": "market stress",
    "g6": "at an order block",
    "g7": "open interest agrees",
    "g8": "volume surge",
    "g9": "pullback in a leader",
    "g10": "market trend agrees",
}


def trigger_of(strategy) -> str | None:
    """The `G.TRIGGERS` key whose module is `strategy` (a module or its dotted name), else None."""
    name = strategy if isinstance(strategy, str) else getattr(strategy, "__name__", None)
    for key, t in G.TRIGGERS.items():
        if t.module == name:
            return key
    return None


def candidates_for(trigger: str) -> tuple[str, ...]:
    """The candidate gates of the composite table this trigger sits on."""
    for table, trig in V2.TABLES.items():
        if trig == trigger:
            return V2.CANDIDATES[table]
    return ()


def checks_for(history: pd.DataFrame, strategy, side: int, symbols) -> dict[str, dict]:
    """`{symbol: {"checks", "checks_agree", "checks_total"}}` for the picks of one table, or `{}`.

    `history` is the truncated slice the picks were made from; `side` is +1 (bullish) or -1 (bearish).
    """
    symbols = list(symbols)
    trigger = trigger_of(strategy)
    if trigger is None or not symbols or G.TRIGGERS[trigger].side != side:
        return {}
    gates = candidates_for(trigger)
    sides = {s: side for s in symbols}
    with G.shared_tail():
        verdicts = {g: G.GATES[g](history, sides, trigger) for g in gates}
    out = {}
    for s in symbols:
        rows = [{"k": g, "label": LABELS[g], "ok": (bool(verdicts[g][s]) if s in verdicts[g] else None)} for g in gates]
        out[s] = {
            "checks": rows,
            "checks_agree": sum(r["ok"] is True for r in rows),
            "checks_total": sum(r["ok"] is not None for r in rows),
        }
    return out
