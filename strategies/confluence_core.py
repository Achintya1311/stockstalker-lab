"""CONFLUENCE_V1: the discretionary "confluence" method as the trigger itself (`cards/CONFLUENCE_V1.yml`).

Attribution: a generic practitioner method ("smart money concepts" style chart reading: order blocks,
liquidity sweeps, support and resistance, candlestick patterns, moving averages, positioning and the
market backdrop studied together). No single source; no published record. Requested by AB on 14 Nov 2026
as one pre-declared train test. Earlier lab work (`strategies/g_gates.py`, `strategies/composite_v2.py`)
used such conditions only as filters on a bounce-back trigger; here the agreement of several conditions IS
the trigger. Nothing here is assumed to work (SPEC.md section 5).

Seven components, each a pure function of the truncated history, True / False / None (no verdict) per
symbol and side, defined for the bullish side and mirrored exactly for the bearish side. Every price is the
split/bonus adjusted series on the last `g_gates.TAIL_DATES` market dates (`g_gates._adjusted_tail`, the
same tail the C1 gates use); daily bars for both horizons (the week replay's history ends at Friday's close).
"range20" is the last 20 sessions' highest high minus lowest low (the last session included).

1. ob      order block (location): `ob_core.detect` on the last 60 bars (G6's window). Bullish True when the
           zone it returns is a demand zone and the last close is inside it or no further from it than
           0.10 x range20 (the distance `picks/tech.py` reports as `ob_dist`); bearish: supply zone.
           No zone, or a zone on the other side: False. Fewer than 60 rows: None.
2. sr      support / resistance (location): `picks.chart.swing_levels` on the last 45 bars (the chart's
           window, swing = 3 bars either side). Bullish True when the nearest swing low below the last close
           is no more than 0.10 x range20 below it; bearish: nearest swing high above, no more than
           0.10 x range20 above. No such swing: False. Fewer than 45 rows: None.
3. sweep   liquidity sweep (event): bullish True when the last session's low is below the lowest low of the
           10 sessions before it and the last close is above that low; bearish: high above the prior
           10-session highest high and close below it. Strength = sweep depth / range20. Fewer than 11 rows:
           None.
4. candle  candle (event): bullish engulfing (prior bar down, last bar up, last open <= prior close, last
           close >= prior open, last body strictly larger than the prior body) or hammer (lower wick >= 2 x
           body and close in the top third of the bar's range, range > 0); bearish: bearish engulfing or
           shooting star (upper wick >= 2 x body, close in the bottom third). Strength = engulfing body /
           range or hammer wick / range, the larger if both. Fewer than 2 rows: None.
5. ema     moving averages: bullish True when the last close is above its 50-session EMA and the 20-session
           EMA is above the 50-session EMA; bearish: below and below (`champion_v1._ema`, span form,
           adjust=False, over the symbol's rows in the tail). Fewer than 100 rows: None.
6. oi      open interest: G7's agreement (`g_gates.g7`, D01C's faded price-and-OI reading of the last
           session has the side's sign). D01C abstaining (no futures OI, zero move): None.
7. market  market backdrop, a stand-in for the volatility index and the overall market built from the lab's
           own universe (the dataset holds no volatility index and no overseas index series): bullish True
           when G10's equal-weight universe index is above its 200-date average AND G5's universe 20-day
           volatility is NOT above its 250-day median (calm); bearish True when the index is below its
           average AND volatility is above the median (stressed). Either reading missing: None.

A setup exists for a symbol and side only when at least one location (ob, sr) AND at least one event (sweep,
candle) is True. Its count is the number of True components. A symbol with a setup on both sides the same
day abstains. Score = side x (count + tie-break), tie-break = the largest, over the fired events, of that
event's mid-rank percentile ((rank - 0.5) / n, average ties) of its strength among the day's setups where
it fired, so it lies in (0, 1). A config keeps setups whose count >= its minimum. An ablation ignores one
component completely: it is not counted and cannot satisfy the location / event requirement.

Only symbols with a row on the last visible date, flagged `has_future` there (when the column exists), are
judged. All components are computed once per `history` (memoised on the object, so `rules_fired` after
`score` on the same slice costs nothing); every config is derived from that one table. No price level is
ever printed.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from picks import chart
from strategies import champion_v1, ob_core
from strategies import g_gates as G

COMPONENTS: tuple[str, ...] = ("ob", "sr", "sweep", "candle", "ema", "oi", "market")
LOCATIONS: tuple[str, ...] = ("ob", "sr")
EVENTS: tuple[str, ...] = ("sweep", "candle")
SIDES = (1, -1)

COMPONENT_NAMES = {
    "ob": "order block (close at or near an agreeing zone)",
    "sr": "support / resistance (close near the nearest swing level)",
    "sweep": "liquidity sweep (prior 10-session extreme taken and closed back inside)",
    "candle": "candle (engulfing bar or long rejection wick)",
    "ema": "moving averages (close and 20-session EMA on the side of the 50-session EMA)",
    "oi": "open interest (D01C positioning reading agrees)",
    "market": "market backdrop stand-in (universe trend and universe volatility; no volatility index in the data)",
}

RANGE_N = 20
NEAR = 0.10                 # share of range20
OB_ROWS = G.OB_ROWS         # 60, G6's window
SR_BARS = chart.BARS        # 45, the chart's window
SWEEP_N = 10
WICK_MULT = 2.0
EMA_FAST, EMA_SLOW = 20, 50
EMA_MIN_ROWS = 2 * EMA_SLOW


# ---------------------------------------------------------------- per-symbol components (arrays, oldest first)


def range20(h: np.ndarray, l: np.ndarray) -> float:
    return float(h[-RANGE_N:].max() - l[-RANGE_N:].min())


def order_block(o, h, l, c, side: int) -> bool | None:
    if len(c) < OB_ROWS:
        return None
    w = slice(len(c) - OB_ROWS, len(c))
    zone = ob_core.detect(o[w], h[w], l[w], c[w])
    if zone is None or zone["side"] != side:
        return False
    last = float(c[-1])
    gap = max(zone["zone_low"] - last, last - zone["zone_high"], 0.0)
    return bool(gap <= NEAR * range20(h, l))


def support_resistance(o, h, l, c, side: int) -> bool | None:
    if len(c) < SR_BARS:
        return None
    bars = np.column_stack([o[-SR_BARS:], h[-SR_BARS:], l[-SR_BARS:], c[-SR_BARS:]]).tolist()
    kind = "s" if side > 0 else "r"
    levels = [lv for lv in chart.swing_levels(bars) if lv["k"] == kind]
    if not levels:
        return False
    nearest = levels[0]["at"]  # swing_levels sorts by distance to the last close, nearest first
    dist = (float(c[-1]) - nearest) if side > 0 else (nearest - float(c[-1]))
    return bool(dist <= NEAR * range20(h, l))


def liquidity_sweep(h, l, c, side: int) -> tuple[bool | None, float]:
    if len(c) < SWEEP_N + 1:
        return None, 0.0
    if side > 0:
        ref = float(l[-(SWEEP_N + 1):-1].min())
        hit = l[-1] < ref and c[-1] > ref
        depth = ref - float(l[-1])
    else:
        ref = float(h[-(SWEEP_N + 1):-1].max())
        hit = h[-1] > ref and c[-1] < ref
        depth = float(h[-1]) - ref
    if not hit:
        return False, 0.0
    rng = range20(h, l)
    return True, float(depth / rng) if rng > 0 else 0.0


def candle(o, h, l, c, side: int) -> tuple[bool | None, float]:
    if len(c) < 2:
        return None, 0.0
    o0, c0, o1, h1, l1, c1 = (float(x) for x in (o[-2], c[-2], o[-1], h[-1], l[-1], c[-1]))
    rng = h1 - l1
    body0, body1 = abs(c0 - o0), abs(c1 - o1)
    strengths = []
    if side > 0:
        engulf = c0 < o0 and c1 > o1 and o1 <= c0 and c1 >= o0 and body1 > body0
        wick = min(o1, c1) - l1
        pin = rng > 0 and wick >= WICK_MULT * body1 and 3.0 * (c1 - l1) >= 2.0 * rng
    else:
        engulf = c0 > o0 and c1 < o1 and o1 >= c0 and c1 <= o0 and body1 > body0
        wick = h1 - max(o1, c1)
        pin = rng > 0 and wick >= WICK_MULT * body1 and 3.0 * (h1 - c1) >= 2.0 * rng
    if engulf:
        strengths.append(body1 / rng if rng > 0 else 0.0)
    if pin:
        strengths.append(wick / rng)
    if not strengths:
        return False, 0.0
    return True, float(max(strengths))


def ema_reading(c) -> tuple[float, float, float] | None:
    """(last close, 20-session EMA, 50-session EMA), or None with fewer than 100 rows."""
    if len(c) < EMA_MIN_ROWS:
        return None
    s = pd.Series(c, dtype=float)
    return float(c[-1]), float(champion_v1._ema(s, EMA_FAST).iloc[-1]), float(champion_v1._ema(s, EMA_SLOW).iloc[-1])


def ema_trend(c, side: int, reading: tuple | None = None) -> bool | None:
    r = ema_reading(c) if reading is None else reading
    if r is None:
        return None
    last, fast, slow = r
    return bool(last > slow and fast > slow) if side > 0 else bool(last < slow and fast < slow)


def symbol_components(o, h, l, c) -> dict:
    """{(component, side): verdict} and {(event, side): strength} for one symbol's adjusted bars."""
    out, strength = {}, {}
    ema = ema_reading(c)
    for side in SIDES:
        out[("ob", side)] = order_block(o, h, l, c, side)
        out[("sr", side)] = support_resistance(o, h, l, c, side)
        out[("sweep", side)], strength[("sweep", side)] = liquidity_sweep(h, l, c, side)
        out[("candle", side)], strength[("candle", side)] = candle(o, h, l, c, side)
        out[("ema", side)] = ema_trend(c, side, ema) if ema is not None else None
    return {"verdicts": out, "strength": strength}


# ---------------------------------------------------------------- universe-level components


def market_backdrop(adj: pd.DataFrame) -> dict[int, bool | None]:
    """{+1: calm uptrend, -1: stressed downtrend} from G10's and G5's readings on the universe tail."""
    trend, stress = G.market_trend_reading(adj), G.stress_reading(adj)
    if trend is None or stress is None:
        return {1: None, -1: None}
    (last, sma), (vol, median) = trend, stress
    stressed = vol > median
    return {1: bool(last > sma and not stressed), -1: bool(last < sma and stressed)}


def oi_agreement(history: pd.DataFrame, symbols: list[str], last_date) -> dict[int, dict[str, bool]]:
    """G7's verdict per side. D01C reads only each symbol's last visible row, so the rows on the last date
    are passed (identical result for symbols with a row on that date, without regrouping the whole history).
    G7 judges only a non-zero D01C score, so its bearish verdict is exactly the negation of its bullish one;
    it is asked once."""
    last_rows = history[history["date"] == last_date]
    bull = G.g7(last_rows, {s: 1 for s in symbols})
    return {1: bull, -1: {s: not v for s, v in bull.items()}}


# ---------------------------------------------------------------- the component table, once per history

_CACHE: list = []  # [(history object, shape, table)], one entry


def _universe_symbols(adj: pd.DataFrame, last_date) -> list[str]:
    last = adj[adj["date"] == last_date]
    if "has_future" in last.columns:
        last = last[last["has_future"].fillna(False).astype(bool)]
    return sorted(last["symbol"].unique())


def components(history: pd.DataFrame) -> pd.DataFrame:
    """One row per judged symbol; columns `<component>_bull`, `<component>_bear` (True / False / None) and
    `<event>_bull_strength`, `<event>_bear_strength`. Memoised on the `history` object (one entry)."""
    if _CACHE and _CACHE[0][0] is history and _CACHE[0][1] == history.shape:
        return _CACHE[0][2]
    table = _components_uncached(history)
    _CACHE[:] = [(history, history.shape, table)]
    return table


def _col(comp: str, side: int) -> str:
    return f"{comp}_{'bull' if side > 0 else 'bear'}"


def _components_uncached(history: pd.DataFrame) -> pd.DataFrame:
    cols = [_col(c, s) for c in COMPONENTS for s in SIDES] + [f"{_col(e, s)}_strength" for e in EVENTS for s in SIDES]
    if history.empty:
        return pd.DataFrame(columns=cols, dtype=object)
    adj = G._adjusted_tail(history)
    if adj.empty:
        return pd.DataFrame(columns=cols, dtype=object)
    last_date = adj["date"].max()
    symbols = _universe_symbols(adj, last_date)
    if not symbols:
        return pd.DataFrame(columns=cols, dtype=object)
    market = market_backdrop(adj)
    oi = oi_agreement(history, symbols, last_date)
    wanted = set(symbols)
    rows = {}
    sub = adj[adj["symbol"].isin(wanted)]
    for s, g in sub.groupby("symbol", sort=True):
        o, h, l, c = (g[f"adj_{k}"].to_numpy(float) for k in ("open", "high", "low", "close"))
        comp = symbol_components(o, h, l, c)
        row = {}
        for side in SIDES:
            for name in ("ob", "sr", "sweep", "candle", "ema"):
                row[_col(name, side)] = comp["verdicts"][(name, side)]
            row[_col("oi", side)] = oi[side].get(s)
            row[_col("market", side)] = market[side]
            for e in EVENTS:
                row[f"{_col(e, side)}_strength"] = comp["strength"][(e, side)]
        rows[s] = row
    return pd.DataFrame.from_dict(rows, orient="index", columns=cols)


# ---------------------------------------------------------------- setups and configs


@dataclass(frozen=True)
class Config:
    name: str
    min_count: int
    drop: str | None = None

    @property
    def active(self) -> tuple[str, ...]:
        return tuple(c for c in COMPONENTS if c != self.drop)

    @property
    def config_id(self) -> str:
        return self.name.upper()

    def describe(self) -> str:
        n = len(self.active)
        base = f"setup (a location AND an event) with at least {self.min_count} of {n} components True"
        return base + (f", {self.drop} ignored" if self.drop else "")


MIN_COUNTS = (3, 4, 5)
ABLATION_MIN = 4
CONFIGS: dict[str, Config] = {
    **{f"confluence_min{k}": Config(f"confluence_min{k}", k) for k in MIN_COUNTS},
    **{f"confluence_min{ABLATION_MIN}_no_{c}": Config(f"confluence_min{ABLATION_MIN}_no_{c}", ABLATION_MIN, c) for c in COMPONENTS},
}
MAIN = tuple(f"confluence_min{k}" for k in MIN_COUNTS)
ABLATIONS = tuple(f"confluence_min{ABLATION_MIN}_no_{c}" for c in COMPONENTS)


def _true(v) -> bool:
    return v is True or (isinstance(v, (bool, np.bool_)) and bool(v))


def setups(table: pd.DataFrame, active: tuple[str, ...] = COMPONENTS) -> pd.DataFrame:
    """Columns side, count, tiebreak, components (True names) for every symbol with a setup on exactly one
    side, using only the `active` components. Symbols with setups on both sides are left out."""
    locs = [c for c in LOCATIONS if c in active]
    evts = [c for c in EVENTS if c in active]
    found = {}
    for s, row in table.iterrows():
        sides = []
        for side in SIDES:
            if any(_true(row[_col(c, side)]) for c in locs) and any(_true(row[_col(c, side)]) for c in evts):
                sides.append(side)
        if len(sides) != 1:
            continue
        side = sides[0]
        true = [c for c in active if _true(row[_col(c, side)])]
        strength = {e: float(row[f"{_col(e, side)}_strength"]) for e in evts if _true(row[_col(e, side)])}
        found[s] = {"side": side, "count": len(true), "components": true, "strength": strength}
    out = pd.DataFrame.from_dict(found, orient="index", columns=["side", "count", "components", "strength"])
    if out.empty:
        return out.assign(tiebreak=pd.Series(dtype=float))
    tb = pd.Series(0.0, index=out.index)
    for e in evts:
        vals = pd.Series({s: d[e] for s, d in out["strength"].items() if e in d}, dtype=float)
        if vals.empty:
            continue
        pct = (vals.round(12).rank(method="average") - 0.5) / len(vals)
        tb.loc[pct.index] = np.maximum(tb.loc[pct.index].to_numpy(), pct.to_numpy())
    return out.assign(tiebreak=tb)


def config_setups(name: str, history: pd.DataFrame) -> pd.DataFrame:
    cfg = CONFIGS[name]
    st = setups(components(history), cfg.active)
    return st[st["count"] >= cfg.min_count] if not st.empty else st


def config_score(name: str, history: pd.DataFrame) -> pd.Series:
    st = config_setups(name, history)
    if st.empty:
        return pd.Series(dtype=float)
    return (st["side"].astype(float) * (st["count"].astype(float) + st["tiebreak"].astype(float))).astype(float)


def config(name: str):
    """`(score, rules_fired)` for one config."""
    if name not in CONFIGS:
        raise ValueError(f"no CONFLUENCE_V1 config {name!r}")
    cfg = CONFIGS[name]

    def score(history: pd.DataFrame) -> pd.Series:
        return config_score(name, history)

    def fired(history: pd.DataFrame, symbol: str) -> str:
        # Full history: the tie-break ranks across the day's setups and two components read the universe.
        st = config_setups(name, history)
        if symbol not in st.index:
            return (f"{cfg.config_id}: no single-side setup (a location AND an event) with at least "
                    f"{cfg.min_count} of {len(cfg.active)} components, abstain")
        r = st.loc[symbol]
        word = "bullish" if r["side"] > 0 else "bearish"
        held = "; ".join(COMPONENT_NAMES[c] for c in r["components"])
        return (f"{cfg.config_id}: {word} setup, {int(r['count'])} of {len(cfg.active)} components agree: {held}. "
                f"Event strength percentile {100 * float(r['tiebreak']):.0f}% of the day's setups.")

    score.__doc__ = f"{cfg.config_id}: {cfg.describe()}, both sides."
    return score, fired
