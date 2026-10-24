"""O02: order-block retest confirmed by D01's OI build-up (`cards/O02.yml`, `docs/orderblock_hypotheses.md`).

Tests whether OI build-up adds anything on top of a bare order-block retest: O01's side is kept only
when the symbol's last visible session was specifically a *build-up* (`oi_chg_futstk > 0`, not
unwinding or covering) whose own direction agrees with O01's side - the catalog's literal wording
("long build-up for bullish, short build-up for bearish"), not a looser "D01 agrees in sign" reading
that would also keep the two OI-down quadrants. Abstains in every other case, including wherever O01
or D01 itself abstains.

Imports `strategies.o01_order_block_retest` and `strategies.d01_oi_buildup` as libraries (not copied):
this card's whole point is comparing OB+OI against each ingredient alone, so it must stay bit-for-bit
consistent with the already-queued O01 and D01 train replays.

Day horizon only (`cards/O02.yml`'s red_flags): D01 gives no week-horizon reading to gate on.
"""

from __future__ import annotations

import pandas as pd

from strategies import d01_oi_buildup, o01_order_block_retest


def _last_rows(history: pd.DataFrame) -> dict[str, pd.Series]:
    if history.empty:
        return {}
    return {symbol: g.sort_values("date").iloc[-1] for symbol, g in history.groupby("symbol", sort=False)}


def _confirmed_scores(history: pd.DataFrame) -> dict[str, float]:
    ob_scores = o01_order_block_retest.score(history)
    if ob_scores.empty:
        return {}
    oi_scores = d01_oi_buildup.score(history)
    if oi_scores.empty:
        return {}
    last_rows = _last_rows(history[history["symbol"].isin(ob_scores.index)])

    out: dict[str, float] = {}
    for symbol, ob_score in ob_scores.items():
        oi_score = oi_scores.get(symbol)
        if oi_score is None:
            continue
        last = last_rows.get(symbol)
        oi_chg = None if last is None else last.get("oi_chg_futstk")
        if oi_chg is None or pd.isna(oi_chg) or not (oi_chg > 0):
            continue  # not a build-up session (unwinding, covering, or missing OI change): abstain
        ob_side = 1.0 if ob_score > 0 else -1.0
        oi_side = 1.0 if oi_score > 0 else -1.0
        if ob_side == oi_side:
            out[symbol] = ob_score
    return out


def score(history: pd.DataFrame) -> pd.Series:
    return pd.Series(_confirmed_scores(history), dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol]
    hit = _confirmed_scores(sub).get(symbol)
    if hit is None:
        ob = o01_order_block_retest.score(sub)
        if symbol not in ob.index:
            return "O02: O01 has no valid zone at price, abstain"
        return "O02: O01 has a zone but the last session was not a build-up agreeing with its side, abstain"
    side = "bullish" if hit > 0 else "bearish"
    return f"O02: {side} order block retest confirmed by D01 build-up, score {hit:+.2f}"
