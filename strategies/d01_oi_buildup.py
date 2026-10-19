"""D01: OI build-up classification (`cards/D01.yml`, `state/queue.md` port lane).

Ported from the standard Indian F&O desk convention: a session's own price
move alongside its own change in open interest classifies that session as
long build-up (price up, OI up - bullish, fresh conviction), short
build-up (price down, OI up - bearish, fresh conviction), long unwinding
(price down, OI down - bearish, but weaker: position-closing, not fresh
conviction) or short covering (price up, OI down - bullish, but weaker) -
not assumed true here (SPEC.md section 5) until a real train replay's edge
is in; `cards/D01.yml`'s `status` moves to `confirmed`/`refuted` then.

The catalog's own classification reads a session's own close/prevclose and
own OI change - information `engine/replay.py`'s `truncate()` correctly
withholds about the pick date itself (B4), the same wall A09's gap fade
hit. Ported as a one-day lag instead: `history`'s last visible row (the
session right before the pick date) is classified, and that classification
predicts the *next* session - a real "does yesterday's positioning pattern
carry forward" claim, not the literal same-session reading (`cards/D01.yml`'s
red flags).

`score = direction * abs(oi_pct_chg) * weight`: `direction` always follows
the price move's own sign (up bullish, down bearish, in every quadrant,
exactly as the catalog's four-way table says); `weight` is 1.0 for a
build-up (OI up) and `WEAK_WEIGHT` for unwinding/covering (OI down) - the
catalog's "treated as weaker" instruction, applied to magnitude only, never
to sign.
"""

from __future__ import annotations

import pandas as pd

WEAK_WEIGHT = 0.5


def _oi_buildup_score(row: pd.Series) -> float | None:
    """One row's (session's) build-up/unwind score, or `None` to abstain."""
    if not bool(row.get("has_future", False)):
        return None

    prevclose = row.get("prevclose")
    close = row.get("close")
    oi_chg = row.get("oi_chg_futstk")
    oi_level = row.get("oi_futstk")

    if pd.isna(prevclose) or pd.isna(close) or pd.isna(oi_chg) or pd.isna(oi_level):
        return None
    if prevclose == 0:
        return None

    price_move = (close - prevclose) / prevclose
    if price_move == 0:
        return None  # no clear direction, abstain

    prior_oi = oi_level - oi_chg
    if pd.isna(prior_oi) or prior_oi <= 0:
        return None

    oi_pct_chg = oi_chg / prior_oi
    direction = 1.0 if price_move > 0 else -1.0
    weight = 1.0 if oi_chg > 0 else WEAK_WEIGHT
    return direction * abs(oi_pct_chg) * weight


def score(history: pd.DataFrame) -> pd.Series:
    """One OI-build-up score per symbol, from each symbol's last visible row.

    A symbol with no history, no active future on its last visible row, a
    zero price move, or OI fields that make the arithmetic undefined,
    abstains (left out of the returned Series) rather than guessing.
    """
    if history.empty:
        return pd.Series(dtype=float)

    if "has_future" in history.columns:
        # Performance prefilter, not a correctness check (see
        # `strategies/champion_v1.py`'s identical prefilter): a symbol with
        # no F&O future anywhere in its visible history can never produce a
        # real score here (every row would fail the `has_future` check
        # inside `_oi_buildup_score` anyway), so skipping it here avoids
        # recomputing this over the full EQ series on every pick date.
        eligible = history.loc[history["has_future"], "symbol"].unique()
        history = history[history["symbol"].isin(eligible)]
        if history.empty:
            return pd.Series(dtype=float)

    out: dict[str, float] = {}
    for symbol, group in history.groupby("symbol", sort=False):
        last = group.sort_values("date").iloc[-1]
        s = _oi_buildup_score(last)
        if s is not None:
            out[symbol] = s
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    if sub.empty:
        return "D01 OI build-up: no history, abstain"

    last = sub.iloc[-1]
    s = _oi_buildup_score(last)
    if s is None:
        return "D01 OI build-up: no active future, zero move or undefined OI change on the last session, abstain"

    price_up = last["close"] > last["prevclose"]
    oi_up = last["oi_chg_futstk"] > 0
    label = (
        "long build-up" if price_up and oi_up else
        "short build-up" if not price_up and oi_up else
        "short covering" if price_up else
        "long unwinding"
    )
    direction = "bullish" if s > 0 else "bearish"
    return (
        f"D01 OI build-up classification: last session was {label} "
        f"(price {'up' if price_up else 'down'}, OI {'up' if oi_up else 'down'}) "
        f"-> score {s:+.4f} ({direction})"
    )
