"""Causality check for the C1 gates and every trigger x gate cell (`strategies/g_gates.py`, SPEC.md section 5).

One audit covers all 68 cell modules (batch 1, G1-G8, and batch 2, G9-G10), since each is a one-line call into `g_gates.cell`. Three properties:

1. Future rows are invisible: for several pick dates near the end of a synthetic panel, every gate's verdict
   and every cell's score computed on `engine.replay.truncate(panel, date)` is identical to the one
   computed on the same truncation of a panel whose rows on and after that date were replaced by wild
   values. (The engine already guarantees the truncation; this proves no gate re-reads anything else.)
2. Cross-symbol causality for the per-symbol gates (G1, G4, G6, G7, G8): giving `S01` one extra leading row
   must not move any other symbol's verdict, the same shape as `strategies/consensus_db_v1_audit.py`.
   G2, G3, G5, G9 and G10 read the universe by design (a rank, a market return, a market volatility, a rank,
   a market index), like A05B.
3. The universe series those three use are causal: the equal-weight return and its 20-day volatility on
   every past date are the same whether computed from the panel up to that date or from the whole panel
   (no centred window, no back-fill), the 63-day leader percentile on a date uses only rows up to it
   (G2, G9), and G10's index-over-its-200-date-average ratio on every past date is the same from either
   panel (the index restarts at a different date, but the ratio does not depend on where it starts).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from engine.replay import truncate
from strategies import g_gates as G

PER_SYMBOL_GATES = ("g1", "g4", "g6", "g7", "g8")


def synthetic_panel(n_symbols: int = 10, n_rows: int = 330, seed: int = 11, extra_leading: dict | None = None) -> pd.DataFrame:
    """Deterministic random-walk OHLCV panel with futures OI, one row per business day per symbol.

    Each symbol draws from its own seeded stream, so adding a leading row to one symbol (`extra_leading`
    maps symbol -> rows) leaves every other symbol's values unchanged.
    """
    dates = pd.bdate_range("2015-01-01", periods=n_rows + max((extra_leading or {}).values(), default=0))
    frames = []
    for k in range(n_symbols):
        sym = f"S{k:02d}"
        rng = np.random.default_rng(seed + k)
        n = n_rows + (extra_leading or {}).get(sym, 0)
        r = rng.normal(0.0004 * (k - n_symbols / 2), 0.02, n)
        close = 100.0 * np.exp(np.cumsum(r))
        prev = np.r_[close[0], close[:-1]]
        open_ = prev * np.exp(rng.normal(0, 0.006, n))
        frames.append(pd.DataFrame({
            "date": dates[-n:].strftime("%Y-%m-%d"),
            "symbol": sym,
            "open": open_,
            "high": np.maximum(open_, close) * 1.004,
            "low": np.minimum(open_, close) * 0.996,
            "close": close,
            "prevclose": prev,
            "volume": rng.lognormal(13.0, 0.6, n),
            "has_future": True,
            "oi_futstk": 100_000.0,
            "oi_chg_futstk": rng.normal(0, 2_000, n),
        }))
    return pd.concat(frames, ignore_index=True)


def _poison_from(panel: pd.DataFrame, date: str, inclusive: bool = True) -> pd.DataFrame:
    """Rows on (or, with `inclusive=False`, strictly after) `date` replaced by wild values."""
    out = panel.copy()
    late = out["date"] >= date if inclusive else out["date"] > date
    for col in ("open", "high", "low", "close", "prevclose"):
        out.loc[late, col] = out.loc[late, col] * 7.0
    out.loc[late, "volume"] = 1e12
    out.loc[late, "oi_chg_futstk"] = -9e9
    return out


def check_future_rows_invisible(n_dates: int = 4) -> dict:
    panel = synthetic_panel()
    dates = sorted(panel["date"].unique())[-n_dates:]
    failures = []
    for d in dates:
        clean, poisoned = truncate(panel, d), truncate(_poison_from(panel, d), d)
        symbols = sorted(clean["symbol"].unique())
        for trigger in G.TRIGGERS:
            sides = {s: G.TRIGGERS[trigger].side for s in symbols}
            for gate, fn in G.GATES.items():
                if fn(clean, sides, trigger) != fn(poisoned, sides, trigger):
                    failures.append(f"{gate} ({trigger}) on {d}")
        for trigger, gate in G.CELLS:
            for keep in (True, False):
                a, b = G.cell_score(trigger, gate, keep, clean), G.cell_score(trigger, gate, keep, poisoned)
                if not a.sort_index().equals(b.sort_index()):
                    failures.append(f"{G.cell_id(trigger, gate, keep)} on {d}")
    return {"passed": not failures, "failures": failures}


def check_cross_symbol_causality() -> dict:
    short, long_ = synthetic_panel(), synthetic_panel(extra_leading={"S01": 1})
    others = [s for s in sorted(short["symbol"].unique()) if s != "S01"]
    failures, compared = [], 0
    for gate in PER_SYMBOL_GATES:
        for side in (1, -1):
            sides = {s: side for s in sorted(short["symbol"].unique())}
            before, after = G.GATES[gate](short, sides), G.GATES[gate](long_, sides)
            for s in others:
                compared += s in before
                if before.get(s) != after.get(s):
                    failures.append(f"{gate} side {side}: {s} moved")
    return {"passed": not failures and compared > 0, "failures": failures, "compared": compared}


def _trend_ratio(universe_returns: pd.Series) -> pd.Series:
    """G10's reading on every date: the index over its trailing 200-date simple average."""
    index = (1.0 + universe_returns).cumprod()
    return index / index.rolling(G.MARKET_TREND_WINDOW).mean()


def check_universe_series_causal() -> dict:
    panel = synthetic_panel(n_rows=400)
    full = G._adjusted_tail(panel)
    ret_full = G.universe_returns(full)
    vol_full = ret_full.rolling(G.STRESS_VOL_WINDOW).std(ddof=0)
    failures = []
    for d in sorted(panel["date"].unique())[-40::10]:
        part = G._adjusted_tail(panel[panel["date"] <= d])
        ret_part = G.universe_returns(part)
        vol_part = ret_part.rolling(G.STRESS_VOL_WINDOW).std(ddof=0)
        common = ret_part.index.intersection(ret_full.index)[G.STRESS_VOL_WINDOW:]
        if not np.allclose(ret_part[common], ret_full[common], rtol=0, atol=1e-12):
            failures.append(f"universe return before {d}")
        if not np.allclose(vol_part[common], vol_full[common], rtol=0, atol=1e-12):
            failures.append(f"universe volatility before {d}")
        ratio_part = _trend_ratio(ret_part)
        ratio_full = _trend_ratio(ret_full)
        common_r = ratio_part.dropna().index.intersection(ratio_full.dropna().index)
        if common_r.empty or not np.allclose(ratio_part[common_r], ratio_full[common_r], rtol=1e-10, atol=0):
            failures.append(f"universe index trend ratio before {d}")
        pct_a = G.leader_percentiles(part)
        pct_b = G.leader_percentiles(G._adjusted_tail(_poison_from(panel, d, inclusive=False)[lambda f: f["date"] <= d]))
        if pct_a.empty or not pct_a.sort_index().round(12).equals(pct_b.sort_index().round(12)):
            failures.append(f"leader percentile on {d}")
    return {"passed": not failures, "failures": failures}


def run_all() -> dict:
    results = {
        "future_rows_invisible": check_future_rows_invisible(),
        "cross_symbol_causality": check_cross_symbol_causality(),
        "universe_series_causal": check_universe_series_causal(),
    }
    return {"passed": all(r["passed"] for r in results.values()), **results}


if __name__ == "__main__":
    result = run_all()
    print(result)
    raise SystemExit(0 if result["passed"] else 1)
