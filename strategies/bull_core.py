"""BULL_V1: four bullish-only daily rules fixed in advance for the bullish-table trials B1, B4 and B5
(plan of 14 Nov 2026, "Bullish tables: plan for the next run"; cards `cards/B1.yml`, `cards/B4A.yml`,
`cards/B4B.yml`, `cards/B5.yml`).

Attribution (rules restated in the lab's own words; nothing copied):
  B1   20/50 average cross above the 200-day: a long-standing practitioner trend rule (moving-average
       crossovers with a long-average trend filter; no single author). Chosen because it was the one rule
       with a large average gain in the owner's outside tests on 12 Indian large caps (right about 4 in 10),
       so it is judged with an exit plan (`engine/exits.py`), by payoff rather than hit rate.
  B4A  Put writing on an up day: Indian derivatives-desk lore that rising put open interest on a rising
       stock means support is being written underneath. Lab hypothesis, no audited source.
  B4B  End of long liquidation: the exact mirror of the lab's own working bearish rule E2A
       (`strategies/e2a_a02_crowded.py`): an extreme DOWN day (A02's test) on which futures OI FELL.
  B5   Failed bearish setup: a stock that met E2A's bearish setup three sessions ago and has not fallen since;
       those positioned for the fall may have to cover. Lab hypothesis built on E2A.
Nothing here is assumed to work (SPEC.md section 5) and nothing is tuned (SPEC.md section 8 is not applied):
one fixed parameter set each, every ambiguity resolved in the card under `assumptions`.

All four are bullish only: score > 0 means a bullish pick, a symbol that does not qualify abstains (left out).
The signal session is always the LAST visible session S (the previous close for a day pick, Friday's close for
a week pick); nothing after it is read. B1 and B5 reuse `strategies/guru_core.py`'s judged-symbol tail (symbols
with `has_future` on the last visible date, split / bonus adjusted, last 250 market dates) and its indicators
(ATR(14) Wilder, EMA span form adjust=False seeded at the tail's first close, SMA simple mean).

B1  EMA20[S] > EMA50[S] and EMA20[S-1] <= EMA50[S-1] (the cross happened on S, not earlier) and close[S] >
    SMA200[S]. Needs 200 rows in the tail. Strength = (EMA20[S] - EMA50[S]) / ATR(14)[S].
B4A On S the adjusted close is above the previous session's adjusted close; both option OI series
    (`oi_ce_optstk`, `oi_pe_optstk`, near-month stock options summed across strikes) are present on S and
    present and > 0 on S-1 (the panel's previous market date, which the symbol must have a row on); the
    near-month futures expiry is the same on both sessions (no expiry roll, which resets near-month option OI);
    put OI % change > 0 and > call OI % change. Strength = put OI % change - call OI % change (in fractions).
B4B A02's score > 0 (S's close-to-close return at least 2 trailing sigmas DOWN; `strategies/a02_extreme_day_reversal.py`)
    and near-month futures OI change on S < 0 (`strategies/e_confluence_core.py`'s `last_oi_chg`, as E2A reads
    it). Strength = A02's score, exactly as E2A ranks with the sign mirrored. Imports A02 and the E2 helpers.
B5  T3 = the panel's market date 3 sessions before S. E2A (`strategies/e2a_a02_crowded.py`, imported) run on
    the history up to and including T3 gives the symbol a bearish (negative) score, with the symbol's own last
    row in that history dated T3; and the adjusted close on S >= the adjusted close on T3.
    Strength = (close[S] - close[T3]) / ATR(14)[S], floored at `B5_FLOOR` so an exactly equal close still
    counts as a bullish pick (ranked last). E2A is run on the last `B5_E2A_DATES` market dates up to T3, enough
    for A02's 22-row window; on the synthetic panel this gives the same scores as the full history.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import a02_extreme_day_reversal as a02
from strategies import e2_a02_oi as e2
from strategies import e2a_a02_crowded
from strategies import guru_core as G

B1_FAST, B1_SLOW, B1_TREND = 20, 50, 200
B1_MIN_ROWS = B1_TREND
B5_LAG = 3                 # E2A setup on session S-3
B5_E2A_DATES = 250         # market dates handed to E2A (it needs 22 rows per symbol)
B5_FLOOR = 1e-6
ATR_N = G.ATR_N

LABELS = {
    "b1_trend_cross": "20/50 EMA cross above the 200-day average",
    "b4_put_writing": "put writing on an up day (put OI up faster than call OI)",
    "b4_long_liquidation_end": "extreme down day with futures OI falling (mirror of E2A)",
    "b5_failed_bearish": "failed E2A bearish setup (no fall in 3 sessions)",
}


def _ok(x) -> bool:
    return x is not None and np.isfinite(x)


# ---------------------------------------------------------------- B1


def trend_cross(o, h, l, c):
    """(strength, note) or None, on one symbol's adjusted bars (oldest first, last = S)."""
    n = len(c)
    if n < B1_MIN_ROWS:
        return None
    fast, slow, trend = G.ema(c, B1_FAST), G.ema(c, B1_SLOW), G.sma(c, B1_TREND)
    r = G.atr(h, l, c)[-1]
    if not (_ok(r) and r > 0 and _ok(trend[-1])):
        return None
    if not (fast[-1] > slow[-1] and fast[-2] <= slow[-2] and c[-1] > trend[-1]):
        return None
    gap = float((fast[-1] - slow[-1]) / r)
    if not (_ok(gap) and gap > 0):
        return None
    return gap, (f"EMA{B1_FAST} crossed above EMA{B1_SLOW} on the last session, close above its SMA{B1_TREND}; "
                 f"gap {gap:.3f} ATR")


def _b1(history: pd.DataFrame, symbol: str | None = None) -> dict:
    adj = G.tail(history)
    if symbol is not None:
        adj = adj[adj["symbol"] == symbol]
    out = {}
    for sym, g in adj.groupby("symbol", sort=False):
        hit = trend_cross(*G._bars(g))
        if hit is not None:
            out[sym] = hit
    return out


# ---------------------------------------------------------------- B4A


def _pct(x: float, sign: bool = True) -> str:
    """A fractional change as a short percent; capped in the text so it never prints a five-digit number."""
    v = x * 100.0
    if abs(v) > 999:
        return (">" if v > 0 else "<-") + "999" + ("%" if sign else "")
    return f"{v:+.1f}%" if sign else f"{v:.1f}"


def _on_last(history: pd.DataFrame) -> pd.DataFrame:
    last = history["date"].max()
    rows = history[history["date"] == last]
    if "has_future" in rows.columns:
        rows = rows[G._flag(rows["has_future"])]
    return rows


def _b4a(history: pd.DataFrame, symbol: str | None = None) -> dict:
    need = {"oi_ce_optstk", "oi_pe_optstk", "close", "prevclose", "date", "symbol"}
    if history.empty or not need <= set(history.columns):
        return {}
    dates = np.sort(history["date"].unique())
    if len(dates) < 2:
        return {}
    s_date, p_date = dates[-1], dates[-2]
    cur = _on_last(history)
    prev = history[history["date"] == p_date]
    if symbol is not None:
        cur, prev = cur[cur["symbol"] == symbol], prev[prev["symbol"] == symbol]
    both = cur.merge(prev, on="symbol", suffixes=("", "_p"))
    out = {}
    for row in both.itertuples(index=False):
        ce, pe, ce_p, pe_p = row.oi_ce_optstk, row.oi_pe_optstk, row.oi_ce_optstk_p, row.oi_pe_optstk_p
        if not all(_ok(v) for v in (ce, pe, ce_p, pe_p)) or ce_p <= 0 or pe_p <= 0 or ce < 0 or pe < 0:
            continue
        if "expiry_futstk" in both.columns:
            e, e_p = row.expiry_futstk, row.expiry_futstk_p
            if pd.isna(e) or pd.isna(e_p) or e != e_p:
                continue
        # Up session on the adjusted series: S's own PREVCLOSE is the exchange's adjusted base for S-1's close.
        base = row.prevclose if _ok(row.prevclose) and row.prevclose > 0 else row.close_p
        if not (_ok(base) and base > 0 and row.close > base):
            continue
        pe_chg, ce_chg = pe / pe_p - 1.0, ce / ce_p - 1.0
        if not (pe_chg > 0 and pe_chg > ce_chg):
            continue
        out[row.symbol] = (float(pe_chg - ce_chg),
                           f"up session; put OI {_pct(pe_chg)} vs call OI {_pct(ce_chg)} "
                           f"(spread {_pct(pe_chg - ce_chg, sign=False)} points)")
    return out


# ---------------------------------------------------------------- B4B


def _b4b(history: pd.DataFrame, symbol: str | None = None) -> dict:
    if history.empty:
        return {}
    h = history if symbol is None else history[history["symbol"] == symbol]
    base = a02.score(h)
    chg = e2.core.last_oi_chg(h)
    out = {}
    for sym, sc in base.items():
        if sc > 0 and sym in chg and chg[sym] < 0:
            out[sym] = (float(sc), f"extreme down day ({-sc:+.2f} sigma) while futures OI fell "
                                   f"(long liquidation, not new shorts)")
    return out


# ---------------------------------------------------------------- B5


def e2a_bearish_on(history: pd.DataFrame, d: str) -> dict[str, float]:
    """E2A's bearish scores for setups whose signal session is exactly market date `d`."""
    dates = np.sort(history["date"].unique())
    dates = dates[dates <= d]
    if len(dates) == 0:
        return {}
    h = history[(history["date"] >= dates[max(len(dates) - B5_E2A_DATES, 0)]) & (history["date"] <= d)]
    sc = e2a_a02_crowded.score(h)
    sc = sc[sc < 0]
    if sc.empty:
        return {}
    last_date = h[h["symbol"].isin(sc.index)].groupby("symbol")["date"].max()
    return {s: float(v) for s, v in sc.items() if last_date.get(s) == d}


def _b5(history: pd.DataFrame, symbol: str | None = None) -> dict:
    if history.empty:
        return {}
    dates = np.sort(history["date"].unique())
    if len(dates) <= B5_LAG:
        return {}
    t3 = dates[-1 - B5_LAG]
    adj = G.tail(history)
    if symbol is not None:
        adj = adj[adj["symbol"] == symbol]
    if adj.empty:
        return {}
    setups = e2a_bearish_on(history if symbol is None else history[history["symbol"] == symbol], t3)
    out = {}
    for sym, g in adj[adj["symbol"].isin(setups)].groupby("symbol", sort=False):
        on_t3 = g[g["date"] == t3]
        if on_t3.empty or len(g) < ATR_N + 1:
            continue
        o, h, l, c = G._bars(g)
        r = G.atr(h, l, c)[-1]
        ref = float(on_t3["adj_close"].iloc[0])
        if not (_ok(r) and r > 0) or c[-1] < ref:
            continue
        dist = float((c[-1] - ref) / r)
        out[sym] = (max(dist, B5_FLOOR),
                    f"met E2A's bearish setup {B5_LAG} sessions ago (score {setups[sym]:+.2f}) and has not fallen "
                    f"since; close {dist:.2f} ATR above that session's close")
    return out


# ---------------------------------------------------------------- panel


RULES = {"b1_trend_cross": _b1, "b4_put_writing": _b4a, "b4_long_liquidation_end": _b4b, "b5_failed_bearish": _b5}


def evaluate(name: str, history: pd.DataFrame, symbol: str | None = None) -> dict[str, tuple[float, str]]:
    return RULES[name](history, symbol)


def rule_score(name: str, history: pd.DataFrame) -> pd.Series:
    return pd.Series({s: strength for s, (strength, _) in evaluate(name, history).items()}, dtype=float)


def config(name: str):
    tag, label = name.upper(), LABELS[name]

    def _score(history: pd.DataFrame) -> pd.Series:
        return rule_score(name, history)

    def _rules_fired(history: pd.DataFrame, symbol: str) -> str:
        hit = evaluate(name, history, symbol).get(symbol)
        if hit is None:
            return f"{tag} {label}: setup not present or data missing, abstain"
        strength, note = hit
        return f"{tag} {label}: {note} -> score {strength:+.4f} (bullish pick)"

    return _score, _rules_fired
