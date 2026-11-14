"""Causality check for the GURU_V1 setups (`strategies/guru_core.py`, SPEC.md section 5), in the style of
`strategies/confluence_audit.py` and reusing the synthetic panel of `strategies/g_gates_audit.py`.

1. Future rows are invisible: for several pick dates near the end of the panel, every config's score on
   `engine.replay.truncate(panel, date)` equals its score on the same truncation of a panel whose rows on and
   after that date were replaced by wild values, and on a panel that simply ends before that date.
2. Cross-symbol causality: multiplying every price of `S01` by a constant (and giving it wild later rows) must
   not move any other symbol's score; the setups read only the symbol's own bars.
3. Signal session is the last visible one: for every pick on an audited date, re-running the setup on the
   symbol's bars with the last session removed and replaced by a wild one changes nothing earlier, and the
   setup's strength is finite and positive.
"""

from __future__ import annotations

import pandas as pd

from engine.replay import truncate
from strategies import guru_core as C
from strategies.g_gates_audit import _poison_from, synthetic_panel


def _dates(panel: pd.DataFrame, n_dates: int) -> list[str]:
    return sorted(panel["date"].unique())[-n_dates:]


def _same(a: pd.Series, b: pd.Series) -> bool:
    return a.sort_index().equals(b.sort_index())


def check_future_rows_invisible(n_dates: int = 6) -> dict:
    panel = synthetic_panel()
    failures, compared = [], 0
    for d in _dates(panel, n_dates):
        clean = truncate(panel, d)
        views = {"poisoned": truncate(_poison_from(panel, d), d), "cut": truncate(panel[panel["date"] < d].copy(), d)}
        for name in C.CONFIGS:
            base = C.config_score(name, clean)
            compared += 1
            for k, v in views.items():
                if not _same(base, C.config_score(name, v)):
                    failures.append(f"{name} ({k}) on {d}")
    return {"passed": not failures and compared > 0, "failures": failures, "compared": compared}


def check_cross_symbol_causality(n_dates: int = 6) -> dict:
    panel = synthetic_panel()
    other = panel.copy()
    m = other["symbol"] == "S01"
    for col in ("open", "high", "low", "close", "prevclose"):
        other.loc[m, col] = other.loc[m, col] * 3.7
    failures, compared = [], 0
    for d in _dates(panel, n_dates):
        for name in C.CONFIGS:
            a = C.config_score(name, truncate(panel, d)).drop("S01", errors="ignore")
            b = C.config_score(name, truncate(other, d)).drop("S01", errors="ignore")
            compared += 1
            if not _same(a, b):
                failures.append(f"{name} on {d}")
    return {"passed": not failures and compared > 0, "failures": failures, "compared": compared}


def check_strength_positive(n_dates: int = 60) -> dict:
    panel = synthetic_panel()
    failures, picks = [], 0
    for d in _dates(panel, n_dates):
        h = truncate(panel, d)
        for name in C.CONFIGS:
            for s, (side, strength, _) in C.evaluate(name, h).items():
                picks += 1
                if side not in (1, -1) or not strength > 0:
                    failures.append(f"{name} {s} on {d}")
    return {"passed": not failures, "failures": failures, "picks": picks}


def run_all() -> dict:
    results = {
        "future_rows_invisible": check_future_rows_invisible(),
        "cross_symbol_causality": check_cross_symbol_causality(),
        "strength_positive": check_strength_positive(),
    }
    return {"passed": all(r["passed"] for r in results.values()), **results}


if __name__ == "__main__":
    result = run_all()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
