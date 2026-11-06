"""E2A_F11_FB: E2A's day-bearish picks when it has a likely-tradable one, F11's otherwise (`cards/E2A_F11_FB.yml`).

Lab-original (go-live track, `research/diagnostics/f11.md` and `research/diagnostics/e2a_d01c_fb.md`).
E2A (A02's extreme-day fade kept where futures OI rose) is the lab's strongest day-bearish train reading
(+7.46) but fires on only 64% of train dates. E2A_D01C_FB backed it with D01C and reached +5.97 on 94% of
dates; D01C was weak on exactly the quiet dates E2A skips. F11 (Alpha#38 range-top fade, +4.47 train, reads
every date) is a different kind of signal (a close at the top of its 10-session range on an up bar, not an
OI classification), so it may hold up better on those dates.

Two pre-declared changes from E2A_D01C_FB, both stated on the card:
1. Fallback member F11 instead of D01C.
2. The switch counts only E2A picks that were in the universe at the last close in the slice (an active
   stock future that session and a 20-session median turnover at or above `config/universe.yml`'s floor,
   on a row dated the slice's last date). E2A_D01C_FB switched on raw scores, so on about 80 train dates
   E2A's only bearish names were outside the universe, the engine dropped them and the table was empty.
   This uses the previous session's flags only; the engine still applies its own filter on the pick date.

Bullish scores of either member are dropped: a bearish table only. Each pick keeps its member's own magnitude.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from strategies import e2a_a02_crowded, f11_range_top_fade

TURNOVER_WINDOW = 20
_UNIVERSE = Path(__file__).resolve().parent.parent / "config" / "universe.yml"


def _floor_rupees() -> float:
    with open(_UNIVERSE) as f:
        return float(yaml.safe_load(f)["min_median_turnover_20d_cr"]) * 1e7


def _bearish(scores: pd.Series) -> pd.Series:
    return scores[scores < 0]


def tradable_at_last_close(history: pd.DataFrame) -> set[str]:
    """Symbols in the universe at the slice's last date: a row that date, an active future, enough turnover."""
    if history.empty or not {"has_future", "turnover"} <= set(history.columns):
        return set()
    last_date = history["date"].max()
    recent = history.sort_values("date").groupby("symbol", sort=False).tail(TURNOVER_WINDOW)
    stats = recent.groupby("symbol").agg(last=("date", "max"), n=("turnover", "size"), med=("turnover", "median"))
    last_rows = history[history["date"] == last_date].set_index("symbol")["has_future"]
    ok = (stats["last"] == last_date) & (stats["n"] >= TURNOVER_WINDOW) & (stats["med"] >= _floor_rupees())
    ok &= last_rows.reindex(stats.index).fillna(False).astype(bool)
    return set(stats.index[ok])


def chosen_member(history: pd.DataFrame) -> tuple[str, pd.Series]:
    """("e2a" or "f11", that member's bearish scores) for the date `history` ends on."""
    e2a = _bearish(e2a_a02_crowded.score(history))
    if not e2a.empty and e2a.index.isin(list(tradable_at_last_close(history))).any():
        return "e2a", e2a
    return "f11", _bearish(f11_range_top_fade.score(history))


def score(history: pd.DataFrame) -> pd.Series:
    if history.empty:
        return pd.Series(dtype=float)
    return chosen_member(history)[1]


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    member, scores = chosen_member(history)
    name = "E2A crowded fade" if member == "e2a" else "F11 range-top fade (E2A has no tradable bearish pick this date)"
    if symbol not in scores.index:
        return f"E2A_F11_FB: reading from {name}; no bearish score for this stock, abstain"
    return f"E2A_F11_FB: reading from {name} -> score {float(scores[symbol]):+.4f} (bearish)"
