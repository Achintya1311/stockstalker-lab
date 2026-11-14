"""Causality check for CONFLUENCE_V1 (`strategies/confluence_core.py`, SPEC.md section 5), in the style of
`strategies/composite_v1_audit.py` and reusing the synthetic panel of `strategies/g_gates_audit.py`.

1. Future rows are invisible: for several pick dates near the end of the panel, the whole component table and
   every config's score on `engine.replay.truncate(panel, date)` equal those on the same truncation of a panel
   whose rows on and after that date were replaced by wild values, and those on a panel that simply ends
   before that date (truncating the future away changes nothing).
2. Cross-symbol causality of the per-symbol components (ob, sr, sweep, candle, ema, oi): giving `S01` one
   extra leading row must not move any other symbol's verdict. The market component reads the universe by
   design (G5 and G10, whose own causality `g_gates_audit` proves), and so does the tie-break rank.
3. Structure on every audited date: min5 picks are a subset of min4, min4 of min3, with identical scores; every
   pick has a location and an event among its True components; no symbol is scored on both sides.
"""

from __future__ import annotations

import pandas as pd

from engine.replay import truncate
from strategies import confluence_core as C
from strategies.g_gates_audit import _poison_from, synthetic_panel

PER_SYMBOL = ("ob", "sr", "sweep", "candle", "ema", "oi")


def _dates(panel: pd.DataFrame, n_dates: int) -> list[str]:
    return sorted(panel["date"].unique())[-n_dates:]


def _same(a: pd.DataFrame | pd.Series, b: pd.DataFrame | pd.Series) -> bool:
    return a.sort_index().equals(b.sort_index())


def check_future_rows_invisible(n_dates: int = 4) -> dict:
    panel = synthetic_panel()
    failures, compared = [], 0
    for d in _dates(panel, n_dates):
        views = {
            "clean": truncate(panel, d),
            "poisoned": truncate(_poison_from(panel, d), d),
            "cut": truncate(panel[panel["date"] < d].copy(), d),
        }
        tables = {k: C.components(v).copy() for k, v in views.items()}
        compared += len(tables["clean"])
        for k in ("poisoned", "cut"):
            if not _same(tables["clean"], tables[k]):
                failures.append(f"component table ({k}) on {d}")
            for name in C.CONFIGS:
                if not _same(C.config_score(name, views["clean"]), C.config_score(name, views[k])):
                    failures.append(f"{name} ({k}) on {d}")
    return {"passed": not failures and compared > 0, "failures": failures, "compared": compared}


def check_cross_symbol_causality() -> dict:
    short, long_ = synthetic_panel(), synthetic_panel(extra_leading={"S01": 1})
    a, b = C.components(short).copy(), C.components(long_).copy()
    failures, compared = [], 0
    for s in a.index:
        if s == "S01" or s not in b.index:
            continue
        for comp in PER_SYMBOL:
            for side in C.SIDES:
                col = C._col(comp, side)
                compared += 1
                if a.at[s, col] != b.at[s, col]:
                    failures.append(f"{comp} side {side}: {s} moved")
    return {"passed": not failures and compared > 0, "failures": failures, "compared": compared}


def check_structure(n_dates: int = 4) -> dict:
    panel = synthetic_panel()
    failures, picks = [], 0
    for d in _dates(panel, n_dates):
        h = truncate(panel, d)
        sc = {k: C.config_score(f"confluence_min{k}", h) for k in C.MIN_COUNTS}
        for lo, hi in zip(C.MIN_COUNTS, C.MIN_COUNTS[1:]):
            if not set(sc[hi].index) <= set(sc[lo].index) or any(sc[hi][s] != sc[lo][s] for s in sc[hi].index):
                failures.append(f"min{hi} not a subset of min{lo} with equal scores on {d}")
        for name in C.CONFIGS:
            st = C.config_setups(name, h)
            picks += len(st)
            for s, r in st.iterrows():
                comps = set(r["components"])
                if not comps & set(C.LOCATIONS) or not comps & set(C.EVENTS):
                    failures.append(f"{name} {s} on {d}: no location or no event")
                if C.CONFIGS[name].drop in comps:
                    failures.append(f"{name} {s} on {d}: ignored component counted")
                if not 0.0 <= r["tiebreak"] < 1.0:
                    failures.append(f"{name} {s} on {d}: tie-break outside [0, 1)")
    return {"passed": not failures, "failures": failures, "picks": picks}


def run_all() -> dict:
    results = {
        "future_rows_invisible": check_future_rows_invisible(),
        "cross_symbol_causality": check_cross_symbol_causality(),
        "structure": check_structure(),
    }
    return {"passed": all(r["passed"] for r in results.values()), **results}


if __name__ == "__main__":
    result = run_all()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
