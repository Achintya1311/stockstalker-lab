"""Causality check for COMPOSITE_V1 (`strategies/composite_v1.py`, SPEC.md section 5), in the style of
`strategies/g_gates_audit.py` and reusing its synthetic panel.

The composites read nothing of their own: each is the trigger's side scores filtered by gates from
`strategies/g_gates.py`, whose causality `g_gates_audit` already proves gate by gate. This audit checks the
combination itself:

1. Future rows are invisible: for several pick dates near the end of a synthetic panel, every composite's and
   every complement's score on `engine.replay.truncate(panel, date)` is identical to the one on the same
   truncation of a panel whose rows on and after that date were replaced by wild values.
2. Structure on every audited date: composite and complement are disjoint, both are subsets of the trigger's
   side picks with the trigger's scores unchanged, and their union is exactly the picks every gate judged.
3. A one-gate composite (day bearish, week bullish, week bearish) gives the same scores as its C1 cell
   (`g_gates.cell_score`), keep and complement alike.
"""

from __future__ import annotations

import pandas as pd

from engine.replay import truncate
from strategies import composite_v1 as C
from strategies import g_gates as G
from strategies.g_gates_audit import _poison_from, synthetic_panel


def _dates(panel: pd.DataFrame, n_dates: int) -> list[str]:
    return sorted(panel["date"].unique())[-n_dates:]


def check_future_rows_invisible(n_dates: int = 4) -> dict:
    panel = synthetic_panel()
    failures = []
    for d in _dates(panel, n_dates):
        clean, poisoned = truncate(panel, d), truncate(_poison_from(panel, d), d)
        for table in C.COMPOSITES:
            for keep in (True, False):
                a, b = C.composite_score(table, keep, clean), C.composite_score(table, keep, poisoned)
                if not a.sort_index().equals(b.sort_index()):
                    failures.append(f"{C.composite_id(table, keep)} on {d}")
    return {"passed": not failures, "failures": failures}


def check_structure(n_dates: int = 4) -> dict:
    panel = synthetic_panel()
    failures, judged_total = [], 0
    for d in _dates(panel, n_dates):
        h = truncate(panel, d)
        for table in C.COMPOSITES:
            base, v = C.verdicts(table, h)
            keep, comp = C.composite_score(table, True, h), C.composite_score(table, False, h)
            judged_total += len(v)
            if set(keep.index) & set(comp.index):
                failures.append(f"{table} on {d}: composite and complement overlap")
            if set(keep.index) | set(comp.index) != set(v):
                failures.append(f"{table} on {d}: union is not the judged picks")
            for part in (keep, comp):
                if not set(part.index) <= set(base.index) or any(part[s] != base[s] for s in part.index):
                    failures.append(f"{table} on {d}: not a subset of the trigger with unchanged scores")
    return {"passed": not failures, "failures": failures, "judged": judged_total}


def check_single_gate_matches_cell(n_dates: int = 3) -> dict:
    panel = synthetic_panel()
    failures = []
    for d in _dates(panel, n_dates):
        h = truncate(panel, d)
        for table, (trigger, gates) in C.COMPOSITES.items():
            if len(gates) != 1:
                continue
            for keep in (True, False):
                a = C.composite_score(table, keep, h).sort_index()
                b = G.cell_score(trigger, gates[0], keep, h).sort_index()
                if not a.equals(b):
                    failures.append(f"{C.composite_id(table, keep)} vs {G.cell_id(trigger, gates[0], keep)} on {d}")
    return {"passed": not failures, "failures": failures}


def run_all() -> dict:
    results = {
        "future_rows_invisible": check_future_rows_invisible(),
        "structure": check_structure(),
        "single_gate_matches_cell": check_single_gate_matches_cell(),
    }
    return {"passed": all(r["passed"] for r in results.values()), **results}


if __name__ == "__main__":
    result = run_all()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
