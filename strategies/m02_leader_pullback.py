"""M02: pullback in a leader, bullish only, for the month horizon (`cards/M02.yml`).

A stock that has led the universe over the last quarter, is in an uptrend and
sits near its one-year high, but closed lower on the last session, is a
bullish pick: strength that persists over about a month, bought on a down day.
Nothing is ever scored bearish.

Every condition reuses `strategies/g_gates.py` (imported, never copied):

- 63-day adjusted return in the top 30% of the universe on the last date:
  `g_gates.leader_percentiles` (mid-rank percentile) above `g_gates.LEADER_TOP`
  (0.70);
- adjusted close above its 200-day simple average: `g_gates._sma_side` == +1
  (T04's average, as gate G1);
- the last session's adjusted daily return below zero: `g_gates._daily_returns`;
- last adjusted close at least `g_gates.PULLBACK_NEAR_HIGH` (0.85) x the
  highest adjusted close of the last `g_gates.PULLBACK_HIGH_WINDOW` (252) rows,
  i.e. within 15% of the 252-day high (gate G9's test).

Score = the 63-day percentile (between 0.70 and 1), so `top` keeps the five
strongest leaders that qualify. Every other symbol abstains. Prices are split
and bonus adjusted on `g_gates._adjusted_tail` (the last 300 market dates).
"""

from __future__ import annotations

import pandas as pd

from strategies import g_gates as G


def _readings(history: pd.DataFrame) -> pd.DataFrame:
    adj = G._adjusted_tail(history)
    pct = G.leader_percentiles(adj)
    if pct.empty:
        return pd.DataFrame(columns=["pct", "trend", "last_ret", "near_high", "ok"])
    adj = adj.assign(_ret=G._daily_returns(adj))
    rows = {}
    for s, g in adj.groupby("symbol", sort=False):
        if s not in pct.index:
            continue
        close = g["adj_close"].to_numpy(float)
        if len(close) < G.PULLBACK_HIGH_WINDOW:
            continue
        trend = G._sma_side(g["adj_close"])
        last_ret = g["_ret"].iloc[-1]
        near = close[-1] / close[-G.PULLBACK_HIGH_WINDOW:].max()
        ok = bool(pct[s] > G.LEADER_TOP and trend == 1 and pd.notna(last_ret) and last_ret < 0
                  and near >= G.PULLBACK_NEAR_HIGH)
        rows[s] = {"pct": float(pct[s]), "trend": trend, "last_ret": last_ret, "near_high": near, "ok": ok}
    return pd.DataFrame.from_dict(rows, orient="index")


def score(history: pd.DataFrame) -> pd.Series:
    """The 63-day percentile for qualifying leaders (bullish); every other symbol abstains."""
    if history.empty:
        return pd.Series(dtype=float)
    r = _readings(history)
    if r.empty:
        return pd.Series(dtype=float)
    return r.loc[r["ok"].astype(bool), "pct"].astype(float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    r = _readings(history)
    if symbol not in r.index:
        return "M02 leader pullback: no reading, abstain"
    x = r.loc[symbol]
    verdict = "bullish" if x["ok"] else "abstain"
    return (f"M02 leader pullback: 63-day return percentile {x['pct']:.2f} (needs above {G.LEADER_TOP:.2f}), "
            f"{'above' if x['trend'] == 1 else 'not above'} the 200-day average, last session "
            f"{'lower' if x['last_ret'] < 0 else 'not lower'}, {x['near_high']:.0%} of the 252-day high "
            f"(needs at least {G.PULLBACK_NEAR_HIGH:.0%}) -> {verdict}")
