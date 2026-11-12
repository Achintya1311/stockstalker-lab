"""COMPOSITE_V1: one combined rule per live table, the trigger AND every C1 gate that qualified (`cards/COMPOSITE_V1.yml`).

The selection was fixed from the C1 table (`research/diagnostics/composite_ingredients.md`, 34 cells, 7
qualify) before any composite was replayed. Each table's composite is its live trigger plus every qualifying
gate for that trigger, nothing added, dropped or re-thresholded:

    day bearish   E2A  AND G2
    day bullish   T04  AND G3 AND G4 AND G7 AND G9
    week bullish  A05B AND G5
    week bearish  A01  AND G8

The trigger, its side restriction and every gate are imported from `strategies.g_gates` and never copied, so
a composite's picks are always a subset of the trigger's side picks, scored with the trigger's own unchanged
values (the engine's `top` selection then ranks the survivors by those values, as for a single C1 cell).

Verdicts. Every listed gate is asked about every trigger pick. A pick for which ANY gate gives no verdict
abstains in both the composite and its complement (the single-cell convention, applied gate by gate). Among
picks where every gate has a verdict:

    composite  (keep=True)   kept only if EVERY gate returns True
    complement (keep=False)  kept only if AT LEAST ONE gate returns False

so the two partition the fully judged picks and a composite that only shrinks the sample cannot pass for an
edge. Both sides of every pick are bullish or bearish readings only; nothing here names a price level.
"""

from __future__ import annotations

import pandas as pd

from strategies import e_confluence_core as core
from strategies import g_gates as G

# table -> (trigger, gates). Fixed from the C1 table; do not edit without a new card version.
COMPOSITES: dict[str, tuple[str, tuple[str, ...]]] = {
    "day_bearish": ("e2a", ("g2",)),
    "day_bullish": ("t04", ("g3", "g4", "g7", "g9")),
    "week_bullish": ("a05b", ("g5",)),
    "week_bearish": ("a01", ("g8",)),
}

def _check_table() -> None:
    for table, (trigger, gates) in COMPOSITES.items():
        for gate in gates:
            if (trigger, gate) not in G.CELLS:
                raise ValueError(f"composite {table}: {trigger} x {gate} is not a C1 cell")
        t = G.TRIGGERS[trigger]
        if table != f"{t.horizon}_{t.side_word}":
            raise ValueError(f"composite {table}: trigger {trigger} sits on the {t.horizon} {t.side_word} table")


_check_table()


def composite_id(table: str, keep: bool = True) -> str:
    return f"COMPOSITE_V1_{table.upper()}" + ("" if keep else "_NOT")


def _gate_list(gates: tuple[str, ...]) -> str:
    return " AND ".join(g.upper() for g in gates)


def verdicts(table: str, history: pd.DataFrame) -> tuple[pd.Series, dict[str, bool]]:
    """The trigger's side scores and, for each pick every gate judged, whether all gates hold."""
    trigger, gates = COMPOSITES[table]
    base = G.trigger_side_scores(trigger, history)
    if base.empty:
        return base, {}
    side = G.TRIGGERS[trigger].side
    sides = {s: side for s in base.index}
    per_gate = [{s: bool(x) for s, x in G.GATES[g](history, sides, trigger).items()} for g in gates]
    out = {}
    for s in base.index:
        if all(s in v for v in per_gate):
            out[s] = all(v[s] for v in per_gate)
    return base, out


def composite_score(table: str, keep: bool, history: pd.DataFrame) -> pd.Series:
    base, v = verdicts(table, history)
    return core.keep_if(base, v if keep else {s: not x for s, x in v.items()})


def composite(table: str, keep: bool = True):
    """`(score, rules_fired)` for one table's composite (keep=True) or its complement (keep=False)."""
    if table not in COMPOSITES:
        raise ValueError(f"no composite for table {table!r}")
    trigger, gates = COMPOSITES[table]
    t, cid = G.TRIGGERS[trigger], composite_id(table, keep)
    held = f"all of {_gate_list(gates)} hold" if keep else f"not all of {_gate_list(gates)} hold"

    def score(history: pd.DataFrame) -> pd.Series:
        return composite_score(table, keep, history)

    def fired(history: pd.DataFrame, symbol: str) -> str:
        # Full history, not the symbol's own rows: G2, G3, G5 and G9 read the universe.
        if symbol in composite_score(table, keep, history).index:
            return f"{cid}: {t.label} {t.side_word} pick where {held}. " + t.mod.rules_fired(history, symbol)
        return f"{cid}: no {t.label} {t.side_word} pick, or a gate of {_gate_list(gates)} gave no verdict or the other verdict, abstain"

    score.__doc__ = f"{cid}: {t.label} {t.side_word} scores kept where {held}."
    return score, fired
