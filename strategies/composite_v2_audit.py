"""Causality check for COMPOSITE_V2 (`strategies/composite_v2.py`, SPEC.md section 5), in the style of
`strategies/composite_v1_audit.py` and reusing the synthetic panel of `strategies/g_gates_audit.py`.

The configs read nothing of their own: each is the trigger's side scores filtered (families A, C) or
re-weighted (family B) by gates from `strategies/g_gates.py`, whose causality `g_gates_audit` proves gate by
gate. This audit checks the combinations and the new keyword thresholds:

1. Future rows are invisible: for several pick dates near the end of a synthetic panel, every config's score
   on `engine.replay.truncate(panel, date)` is identical to the one on the same truncation of a panel whose
   rows on and after that date were replaced by wild values.
2. Structure on every audited date: vote and threshold picks are a subset of the trigger's side picks with
   the trigger's scores unchanged; a boost keeps every trigger pick, never flips a sign and never shrinks a
   magnitude; the shared-tail cache changes no gate verdict.
3. Each threshold gate at its C1 value through the new keyword gives the C1 cell's scores exactly.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from engine.replay import truncate
from strategies import composite_v2 as C
from strategies import g_gates as G
from strategies.g_gates_audit import _poison_from, synthetic_panel

C1_VALUES = {"leader_top": G.LEADER_TOP, "leader_bottom": G.LEADER_BOTTOM, "stress_quantile": 0.5,
             "volume_multiple": G.VOLUME_MULTIPLE, "near_high": G.PULLBACK_NEAR_HIGH}


def _dates(panel: pd.DataFrame, n_dates: int) -> list[str]:
    return sorted(panel["date"].unique())[-n_dates:]


def check_future_rows_invisible(n_dates: int = 3) -> dict:
    panel = synthetic_panel()
    failures = []
    for d in _dates(panel, n_dates):
        clean, poisoned = truncate(panel, d), truncate(_poison_from(panel, d), d)
        for table, key in C.CONFIGS:
            a, b = C.config_score(table, key, clean), C.config_score(table, key, poisoned)
            if not a.sort_index().equals(b.sort_index()):
                failures.append(f"{C.config_id(table, key)} on {d}")
    return {"passed": not failures, "failures": failures}


def check_structure(n_dates: int = 3) -> dict:
    panel = synthetic_panel()
    failures, picks = [], 0
    for d in _dates(panel, n_dates):
        h = truncate(panel, d)
        for table, key in C.CONFIGS:
            s = C.CONFIGS[(table, key)]
            base = G.trigger_side_scores(C.TABLES[table], h)
            got = C.config_score(table, key, h)
            picks += len(got)
            if s.family == "boost":
                if set(got.index) != set(base.index):
                    failures.append(f"{table} {key} on {d}: boost dropped or added a pick")
                elif any(np.sign(got[x]) != np.sign(base[x]) or abs(got[x]) < abs(base[x]) for x in base.index):
                    failures.append(f"{table} {key} on {d}: boost flipped a sign or shrank a score")
            elif not set(got.index) <= set(base.index) or any(got[x] != base[x] for x in got.index):
                failures.append(f"{table} {key} on {d}: not a subset of the trigger with unchanged scores")
        for table in C.TABLES:
            trig = C.TABLES[table]
            base = G.trigger_side_scores(trig, h)
            sides = {x: G.TRIGGERS[trig].side for x in base.index}
            for g in C.CANDIDATES[table]:
                plain = G.GATES[g](h, sides, trig)
                with G.shared_tail():
                    G.GATES[g](h, sides, trig)
                    cached = G.GATES[g](h, sides, trig)
                if plain != cached:
                    failures.append(f"{table} {g} on {d}: shared_tail changed a verdict")
    return {"passed": not failures, "failures": failures, "picks": picks}


def check_thresholds_at_c1_value_match_cells(n_dates: int = 2) -> dict:
    panel = synthetic_panel()
    failures = []
    for d in _dates(panel, n_dates):
        h = truncate(panel, d)
        for (table, key), s in C.CONFIGS.items():
            if s.family != "threshold":
                continue
            trig = C.TABLES[table]
            base = G.trigger_side_scores(trig, h)
            sides = {x: G.TRIGGERS[trig].side for x in base.index}
            kw = {k: C1_VALUES[k] for k in C.gate_kwargs(table, s)}
            if G.GATES[s.gate](h, sides, trig, **kw) != G.GATES[s.gate](h, sides, trig):
                failures.append(f"{table} {s.gate} at its C1 value on {d}")
    return {"passed": not failures, "failures": failures}


def run_all() -> dict:
    results = {
        "future_rows_invisible": check_future_rows_invisible(),
        "structure": check_structure(),
        "thresholds_at_c1_value_match_cells": check_thresholds_at_c1_value_match_cells(),
    }
    return {"passed": all(r["passed"] for r in results.values()), **results}


if __name__ == "__main__":
    result = run_all()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
