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

A table whose live strategy is a COMPOSITE_V1 table rule (`strategies.composite_v1_<table>`, e.g. the
day-bearish E2A AND G2 rule AB approved on 14 Nov 2026) gets the checks of its trigger, minus the gates the
composite already selects with: a pick can never fail a gate that chose it, so showing it would be noise.

When the table's strategy is not one of the four triggers or a composite of one (champion fallback, any other strategy), or the
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


def _name(strategy) -> str | None:
    return strategy if isinstance(strategy, str) else getattr(strategy, "__name__", None)


def _composite_table(name: str | None) -> str | None:
    """The COMPOSITE_V1 table whose keep-rule module is `name`, else None (complements never qualify)."""
    from strategies import composite_v1 as C1

    prefix = "strategies.composite_v1_"
    if not name or not name.startswith(prefix):
        return None
    table = name[len(prefix):]
    return table if table in C1.COMPOSITES else None


def trigger_of(strategy) -> str | None:
    """The `G.TRIGGERS` key whose module is `strategy` (a module or its dotted name), or the trigger of a
    COMPOSITE_V1 table rule, else None."""
    name = _name(strategy)
    for key, t in G.TRIGGERS.items():
        if t.module == name:
            return key
    table = _composite_table(name)
    if table is not None:
        from strategies import composite_v1 as C1

        return C1.COMPOSITES[table][0]
    return None


def selecting_gates(strategy) -> tuple[str, ...]:
    """Gates the strategy itself selects with (a COMPOSITE_V1 table rule's gates), else ()."""
    table = _composite_table(_name(strategy))
    if table is None:
        return ()
    from strategies import composite_v1 as C1

    return C1.COMPOSITES[table][1]


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
    used = selecting_gates(strategy)
    gates = tuple(g for g in candidates_for(trigger) if g not in used)
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
