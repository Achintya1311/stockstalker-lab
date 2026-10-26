"""T04_Q06_FB: T04's day-bullish picks when it fires, Q06's on the dates it does not (`cards/T04_Q06_FB.yml`).

T04 (Connors RSI(2) inside a 200-day trend filter) is the day-bullish draft: train +3.37, released +4.36 on
validation, but bullish picks on only about 74% of train dates. Q06 (long lower wick on the last bar) is
weaker (+2.58, released +2.58) but reads every date, and the two pick almost disjoint stocks (about 1% top-5
overlap; `research/diagnostics/q06.md`). Same pre-declared shape as `strategies/e2a_d01c_fallback.py`:
not an average but a per-date fallback. If T04 scores any likely-in-universe stock bullish on the date, only
T04's bullish scores are returned; otherwise only Q06's. Bearish scores of either member are dropped, so this
is a bullish table only. Day horizon, like both members.

One change from E2A_D01C_FB, whose diagnosis found about 80 blank dates because its switch counted member
scores on stocks the engine's universe filter later drops: here the switch counts only stocks that look in
the universe on the last visible row (an active future, and a 20-session median turnover at or above the
floor in `config/universe.yml`). That is the closest the strategy can see to the pick date's universe.
"""

from __future__ import annotations

import pandas as pd

from engine.scoring import load_universe_config
from strategies import q06_wick_balance, t04_connors_rsi2

TURNOVER_WINDOW = 20


def _bullish(scores: pd.Series) -> pd.Series:
    return scores[scores > 0]


def likely_in_universe(history: pd.DataFrame) -> set[str]:
    """Symbols whose last visible row has an active future and a 20-session median turnover at the floor.
    A column the history lacks is not checked."""
    last = history.sort_values("date").groupby("symbol", sort=False)
    ok = pd.Series(True, index=last.size().index)
    if "has_future" in history.columns:
        ok &= last["has_future"].last().fillna(False).astype(bool)
    if "turnover" in history.columns:
        floor = float(load_universe_config()["min_median_turnover_20d_cr"]) * 1e7
        median = last["turnover"].apply(
            lambda s: s.tail(TURNOVER_WINDOW).median() if len(s) >= TURNOVER_WINDOW else float("nan")
        )
        ok &= median >= floor
    return set(ok[ok].index)


def chosen_member(history: pd.DataFrame) -> tuple[str, pd.Series]:
    """("t04" or "q06", that member's bullish scores) for the date `history` ends on."""
    t04 = _bullish(t04_connors_rsi2.score(history))
    if t04.index.isin(list(likely_in_universe(history))).any():
        return "t04", t04
    return "q06", _bullish(q06_wick_balance.score(history))


def score(history: pd.DataFrame) -> pd.Series:
    if history.empty:
        return pd.Series(dtype=float)
    return chosen_member(history)[1]


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    member, scores = chosen_member(history)
    name = "T04 Connors RSI(2)" if member == "t04" else "Q06 lower wick (T04 has no bullish pick this date)"
    if symbol not in scores.index:
        return f"T04_Q06_FB: reading from {name}; no bullish score for this stock, abstain"
    return f"T04_Q06_FB: reading from {name} -> score {float(scores[symbol]):+.4f} (bullish)"
