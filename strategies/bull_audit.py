"""Causality check for the BULL_V1 rules (`strategies/bull_core.py`, SPEC.md section 5), in the style of
`strategies/guru_audit.py`, on `strategies/g_gates_audit.py`'s synthetic panel with option OI and a futures
expiry column added.

1. Future rows are invisible: for several pick dates near the end of the panel, every rule's score on
   `engine.replay.truncate(panel, date)` equals its score on the same truncation of a panel whose rows on and
   after that date were replaced by wild values, and on a panel that simply ends before that date.
2. Cross-symbol causality: scaling every price and OI of `S01` (and giving it wild later rows) must not move
   any other symbol's score; the rules read only the symbol's own rows.
3. Every score is finite and strictly positive (bullish only).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from engine.replay import truncate
from strategies import bull_core as C
from strategies.g_gates_audit import _poison_from, synthetic_panel


def panel(n_symbols: int = 10, n_rows: int = 330, seed: int = 11) -> pd.DataFrame:
    """The g_gates synthetic panel plus option OI (random walks, each symbol its own stream), a futures OI change
    with fat tails so B4B and B5 fire, and a monthly near-month expiry."""
    p = synthetic_panel(n_symbols=n_symbols, n_rows=n_rows, seed=seed)
    parts = []
    for k, (sym, g) in enumerate(p.groupby("symbol", sort=True)):
        rng = np.random.default_rng(1000 + seed + k)
        g = g.copy()
        n = len(g)
        g["oi_ce_optstk"] = 50_000.0 * np.exp(np.cumsum(rng.normal(0, 0.08, n)))
        g["oi_pe_optstk"] = 40_000.0 * np.exp(np.cumsum(rng.normal(0, 0.08, n)))
        g["oi_chg_futstk"] = rng.standard_t(3, n) * 3_000.0
        month = pd.to_datetime(g["date"]).dt.to_period("M")
        g["expiry_futstk"] = month.dt.end_time.dt.strftime("%Y-%m-%d")
        parts.append(g)
    return pd.concat(parts, ignore_index=True)


def poison(p: pd.DataFrame, date: str) -> pd.DataFrame:
    out = _poison_from(p, date)
    late = out["date"] >= date
    out.loc[late, ["oi_ce_optstk", "oi_pe_optstk"]] = [1.0, 9e9]
    out.loc[late, "expiry_futstk"] = "2099-12-31"
    return out


def _dates(p: pd.DataFrame, n_dates: int) -> list[str]:
    return sorted(p["date"].unique())[-n_dates:]


def _same(a: pd.Series, b: pd.Series) -> bool:
    return a.sort_index().equals(b.sort_index())


def check_future_rows_invisible(n_dates: int = 6) -> dict:
    p = panel()
    failures, compared = [], 0
    for d in _dates(p, n_dates):
        clean = truncate(p, d)
        views = {"poisoned": truncate(poison(p, d), d), "cut": truncate(p[p["date"] < d].copy(), d)}
        for name in C.RULES:
            base = C.rule_score(name, clean)
            compared += 1
            for k, v in views.items():
                if not _same(base, C.rule_score(name, v)):
                    failures.append(f"{name} ({k}) on {d}")
    return {"passed": not failures and compared > 0, "failures": failures, "compared": compared}


def check_cross_symbol_causality(n_dates: int = 6) -> dict:
    p = panel()
    other = p.copy()
    m = other["symbol"] == "S01"
    for col in ("open", "high", "low", "close", "prevclose", "oi_ce_optstk", "oi_pe_optstk", "oi_chg_futstk"):
        other.loc[m, col] = other.loc[m, col] * 3.7
    failures, compared = [], 0
    for d in _dates(p, n_dates):
        for name in C.RULES:
            a = C.rule_score(name, truncate(p, d)).drop("S01", errors="ignore")
            b = C.rule_score(name, truncate(other, d)).drop("S01", errors="ignore")
            compared += 1
            if not _same(a, b):
                failures.append(f"{name} on {d}")
    return {"passed": not failures and compared > 0, "failures": failures, "compared": compared}


def check_strength_positive(n_dates: int = 80) -> dict:
    p = panel()
    failures, picks = [], {name: 0 for name in C.RULES}
    for d in _dates(p, n_dates):
        h = truncate(p, d)
        for name in C.RULES:
            for s, v in C.rule_score(name, h).items():
                picks[name] += 1
                if not (np.isfinite(v) and v > 0):
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
