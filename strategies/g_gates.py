"""C1 ingredient gates G1-G8 and the trigger x gate cell builder (`cards/COMPOSITE_INGREDIENTS.yml`).

The closed ingredient list is fixed in the combined-strategy research note (finance-portfolio-hub
`projects/combined-strategy/RESEARCH.md`, sections 4 and 5; 12 Nov 2026, before any number was read).
Each gate is a keep-only filter on one live trigger's own picks. Following the E-series pattern
(`strategies/e_confluence_core.py`), the trigger and every reused condition are imported as libraries,
never copied, so a cell's picks are always a subset of the already-scored trigger replay. For every cell
the complement (trigger AND NOT gate) is a separate module, so a gate that only shrinks the sample cannot
pass for an edge.

Triggers and the one table side each is tested on (`config/live_source.json`):

    e2a   strategies.e2a_a02_crowded        day   bearish
    t04   strategies.t04_connors_rsi2       day   bullish
    a05b  strategies.a05b_max_effect_ranked week  bullish
    a01   strategies.a01_weekly_reversal    week  bearish

A cell keeps only the trigger's scores on that side (other-side scores are dropped), unchanged in value, so
the engine's own `top` (5 largest |score| per date among in-universe stocks) and `all` selections apply to
the gated set exactly as they apply to the trigger. For the continuous triggers (A01, A05B) this means the
`top` selection of a cell is the strongest trigger readings that pass the gate, not "the trigger's top 5,
then gated"; the `all` selection is the trigger's full side, gated.

Gate interface: `gate(history, sides, trigger) -> {symbol: bool}`. `history` is the truncated slice the
engine hands a strategy (last row = the last close before the pick); `sides` maps each pick to +1
(bullish) or -1 (bearish). A symbol absent from the result has no verdict and abstains in BOTH the keep
and the complement cell. Prices are split/bonus adjusted (`scripts.adjustments.compute_adjustment_factors`),
volume is raw (A07's convention). Every gate reads only rows of `history`. Gates compute on the last
`TAIL_DATES` market dates only (enough for the longest window, G5's 20 + 250 days); adjustment factors
depend only on later rows, so the adjusted values on that tail are the same as on the full history.

"Trigger day" means the last visible session for all four triggers, including the two weekly ones (the
Friday close before a Monday pick). For every one of the four triggers the move being faded points against
the pick side (E2A: an up day for a bearish pick; T04: a fall to RSI(2) < 10 for a bullish pick; A01: last
week's gain for a bearish pick), so "the direction of the move" is `-side` throughout.

Exactly what each gate implements:

G1 trend side: bullish keep if adjusted close > its 200-day simple average, bearish keep if close < it
   (T04's own `_sma`/`TREND_WINDOW`). Fewer than 200 rows: no verdict. T04 x G1 is skipped (identity).
G2 not fading a leader: 63-day adjusted return (64 closes) ranked across the universe on the last date
   (universe = symbols whose last row is on the last date with `has_future` true; mid-rank percentile
   `(rank - 0.5) / n`, average ties, as A05B). Bearish pick dropped if percentile > 0.70 AND close > 200-day
   average; bullish pick dropped if percentile < 0.30 AND close < 200-day average; kept otherwise. No
   63-day reading: no verdict; rank condition met but under 200 rows: no verdict.
   T04 x G2 is skipped: T04 only picks bullish above the same 200-day average, so G2 can never drop a T04
   pick (keep = T04, complement empty), the same kind of identity as T04 x G1.
G3 stock-specific move: the trigger's move is recomputed on the market-adjusted return, where the market is
   the equal-weight mean over the universe (rows with `has_future` true; every row if the column is absent)
   for the same window and the same date.
   - E2A: A02's z = last-day return / A02's own 20-day sigma (A02's `_move_day_z`). Residual z = (last-day
     return - universe mean last-day return) / the same sigma. Keep if residual z has the same sign as z and
     |residual z| >= 1.0 (half of A02's 2.0 threshold).
   - T04: last day's return minus the universe mean last-day return must be negative for a bullish pick
     (positive for a bearish pick).
   - A01: A01's 5-day return minus the universe mean 5-day return (A01's `_trailing_return` for every
     universe symbol on the same last date) must keep the 5-day return's sign.
   - A05B: not applicable (a cross-sectional rank of the trailing-max day has no single "move" to adjust);
     the cell is not built.
G4 no-news proxy: A09's gap z for the trigger day (adjusted open / prior adjusted close - 1, over the
   population sigma of the 20 gaps before it; A09's `_yesterdays_gap_z`). Dropped if the gap z in the
   direction of the move exceeds 1.0 (`gap_z * -side > 1.0`), kept otherwise. For A05B (no move) the same
   rule reads "dropped if the trigger day gapped more than 1 sigma against the pick side". Undefined gap
   z: no verdict.
G5 market stress: equal-weight universe daily return (as G3); its 20-day realised volatility (population
   std of the last 20 universe returns) on the last date must be above the median of the trailing 250
   values of that same 20-day series (the current value included). One verdict per date for every pick;
   fewer than 270 universe-return dates: no verdict.
G6 order-block location: `strategies.ob_core.detect` as it stands, on the last 60 adjusted daily bars
   (O01's `MIN_ROWS`, the way O01 calls it). `detect` returns the single most recent unmitigated zone with
   an impulse at most 20 bars old (its own freshness rule). Bullish keep if that zone is a demand zone and
   the last close is at or above its low; bearish keep if it is a supply zone and the last close is at or
   below its high. Because `detect` returns one zone, "not inside a supply zone" holds whenever the
   returned zone is a demand zone. No zone, or a zone on the other side: False (the complement keeps it).
   Fewer than 60 rows: no verdict.
G7 OI state: D01C's score (`strategies.d01c_oi_fade`, the last session's price move and futures OI change,
   faded) must have the pick's sign. D01C abstaining: no verdict. E2A x G7 is skipped (identity).
G8 volume surge: trigger-day raw volume > 1.5 x the mean raw volume of the 20 sessions before it (the
   window being judged is excluded from its own yardstick, A07's boundary convention). Fewer than 21 rows
   or a zero baseline: no verdict.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors
from strategies import (
    a01_weekly_reversal,
    a02_extreme_day_reversal,
    a09_gap_fade,
    d01c_oi_fade,
    e_confluence_core as core,
    o01_order_block_retest,
    ob_core,
    t04_connors_rsi2,
)

TAIL_DATES = 300

TREND_WINDOW = t04_connors_rsi2.TREND_WINDOW  # 200
LEADER_WINDOW = 63
LEADER_TOP, LEADER_BOTTOM = 0.70, 0.30
RESIDUAL_Z_SHARE = 0.5  # half of A02's threshold
GAP_SIGMA = 1.0
STRESS_VOL_WINDOW, STRESS_MEDIAN_WINDOW = 20, 250
OB_ROWS = o01_order_block_retest.MIN_ROWS  # 60
VOLUME_WINDOW, VOLUME_MULTIPLE = 20, 1.5


@dataclass(frozen=True)
class Trigger:
    label: str
    module: str
    side: int
    horizon: str

    @property
    def mod(self):
        return importlib.import_module(self.module)

    @property
    def side_word(self) -> str:
        return "bullish" if self.side > 0 else "bearish"


TRIGGERS: dict[str, Trigger] = {
    "e2a": Trigger("E2A", "strategies.e2a_a02_crowded", -1, "day"),
    "t04": Trigger("T04", "strategies.t04_connors_rsi2", +1, "day"),
    "a05b": Trigger("A05B", "strategies.a05b_max_effect_ranked", +1, "week"),
    "a01": Trigger("A01", "strategies.a01_weekly_reversal", -1, "week"),
}

GATE_NAMES = {
    "g1": "trend side (200-day average)",
    "g2": "not fading a leader (63-day rank and 200-day average)",
    "g3": "stock-specific move (market-adjusted trigger move)",
    "g4": "no-news proxy (no trigger-day gap over 1 sigma in the move's direction)",
    "g5": "market stress (universe 20-day volatility above its 250-day median)",
    "g6": "order-block location (agreeing fresh zone at price)",
    "g7": "OI state (D01C agrees)",
    "g8": "volume surge (trigger-day volume over 1.5x its 20-day average)",
}

SKIPPED: dict[tuple[str, str], str] = {
    ("e2a", "g7"): "identity: E2A already contains the OI condition (RESEARCH.md section 4)",
    ("t04", "g1"): "identity: T04 already requires close above the 200-day average (RESEARCH.md section 4)",
    ("t04", "g2"): "identity: G2 only drops a bullish pick below its 200-day average, where T04 never picks",
    ("a05b", "g3"): "not applicable: A05B is a cross-sectional rank with no single move to market-adjust",
}

CELLS: list[tuple[str, str]] = [(t, g) for t in TRIGGERS for g in GATE_NAMES if (t, g) not in SKIPPED]


# ---------------------------------------------------------------- shared preparation


def _flag(col: pd.Series) -> pd.Series:
    return col.fillna(False).astype(bool)


def _eligible(history: pd.DataFrame) -> pd.DataFrame:
    """The triggers' own `has_future` prefilter: symbols with a future anywhere in the visible slice."""
    if "has_future" in history.columns:
        history = history[history["symbol"].isin(history.loc[_flag(history["has_future"]), "symbol"].unique())]
    return history


def _adjusted_tail(history: pd.DataFrame, symbols=None) -> pd.DataFrame:
    """Adjusted rows on the last `TAIL_DATES` market dates, sorted by symbol then date."""
    if history.empty:
        return history.iloc[0:0]
    history = _eligible(history)
    if symbols is not None:
        history = history[history["symbol"].isin(list(symbols))]
    if history.empty:
        return history.iloc[0:0]
    dates = np.sort(history["date"].unique())
    history = history[history["date"] >= dates[max(len(dates) - TAIL_DATES, 0)]]
    return compute_adjustment_factors(history)


def _daily_returns(adj: pd.DataFrame) -> pd.Series:
    prior = adj.groupby("symbol", sort=False)["adj_close"].shift(1)
    ret = adj["adj_close"] / prior - 1.0
    return ret.where(prior.notna() & (prior != 0) & ~adj["series_gap"].astype(bool))


def _universe_mask(adj: pd.DataFrame) -> pd.Series:
    if "has_future" in adj.columns:
        return _flag(adj["has_future"])
    return pd.Series(True, index=adj.index)


def universe_returns(adj: pd.DataFrame) -> pd.Series:
    """Equal-weight mean daily return of the universe, by date (G3, G5)."""
    if adj.empty:
        return pd.Series(dtype=float)
    ret = _daily_returns(adj)
    mask = _universe_mask(adj) & ret.notna()
    return ret[mask].groupby(adj.loc[mask, "date"]).mean().sort_index()


def _last_rows(adj: pd.DataFrame) -> pd.DataFrame:
    return adj.groupby("symbol", sort=False).tail(1).set_index("symbol")


def _sma_side(close: pd.Series) -> int | None:
    """+1 above the 200-day average, -1 below, 0 at it, None with too little history."""
    if len(close) < TREND_WINDOW:
        return None
    last, sma = float(close.iloc[-1]), t04_connors_rsi2._sma(close, TREND_WINDOW)
    return int(np.sign(last - sma))


# ---------------------------------------------------------------- the eight gates


def g1(history: pd.DataFrame, sides: dict[str, int], trigger: str | None = None) -> dict[str, bool]:
    adj = _adjusted_tail(history, sides)
    out = {}
    for s, g in adj.groupby("symbol", sort=False):
        trend = _sma_side(g["adj_close"])
        if trend is not None and s in sides:
            out[s] = trend == sides[s]
    return out


def leader_percentiles(adj: pd.DataFrame) -> pd.Series:
    """Mid-rank percentile of the 63-day adjusted return across the universe on the last date (G2)."""
    if adj.empty:
        return pd.Series(dtype=float)
    last_date = adj["date"].max()
    rets = {}
    for s, g in adj.groupby("symbol", sort=False):
        if g["date"].iloc[-1] != last_date or len(g) < LEADER_WINDOW + 1:
            continue
        if "has_future" in g.columns and not _flag(g["has_future"]).iloc[-1]:
            continue
        close = g["adj_close"].to_numpy(float)
        prior = close[-(LEADER_WINDOW + 1)]
        if prior > 0:
            rets[s] = close[-1] / prior - 1.0
    r = pd.Series(rets, dtype=float)
    if r.empty:
        return r
    return (r.round(10).rank(method="average") - 0.5) / len(r)


def g2(history: pd.DataFrame, sides: dict[str, int], trigger: str | None = None) -> dict[str, bool]:
    adj = _adjusted_tail(history)
    pct = leader_percentiles(adj)
    out = {}
    for s, side in sides.items():
        if s not in pct.index:
            continue
        extreme = pct[s] > LEADER_TOP if side < 0 else pct[s] < LEADER_BOTTOM
        if not extreme:
            out[s] = True
            continue
        trend = _sma_side(adj.loc[adj["symbol"] == s, "adj_close"])
        if trend is not None:
            out[s] = not (trend == -side)  # leader = strong rank AND trend against the pick
    return out


def g3(history: pd.DataFrame, sides: dict[str, int], trigger: str | None = None) -> dict[str, bool]:
    if trigger not in ("e2a", "t04", "a01"):
        return {}
    adj = _adjusted_tail(history)
    if adj.empty:
        return {}
    out = {}
    if trigger in ("e2a", "t04"):
        mkt = universe_returns(adj)
        for s, g in adj[adj["symbol"].isin(list(sides))].groupby("symbol", sort=False):
            d = g["date"].iloc[-1]
            if d not in mkt.index or len(g) < 2:
                continue
            closes = g["adj_close"].to_numpy(float)
            if closes[-2] == 0:
                continue
            r = closes[-1] / closes[-2] - 1.0
            resid = r - float(mkt[d])
            if trigger == "t04":
                out[s] = bool(resid * sides[s] < 0)
                continue
            if len(g) < a02_extreme_day_reversal.MIN_ROWS:
                continue
            z = a02_extreme_day_reversal._move_day_z(g["adj_close"])
            if z is None or r == 0:
                continue
            sigma = r / z
            resid_z = resid / sigma
            out[s] = bool(np.sign(resid_z) == np.sign(z) and abs(resid_z) >= RESIDUAL_Z_SHARE * a02_extreme_day_reversal.Z_THRESHOLD)
        return out
    # a01: 5-day return minus the universe mean 5-day return on the same date
    rets, dates, in_univ = {}, {}, {}
    for s, g in adj.groupby("symbol", sort=False):
        if len(g) < a01_weekly_reversal.MIN_ROWS:
            continue
        rets[s] = a01_weekly_reversal._trailing_return(g["adj_close"])
        dates[s] = g["date"].iloc[-1]
        in_univ[s] = bool(_flag(g["has_future"]).iloc[-1]) if "has_future" in g.columns else True
    for s, side in sides.items():
        if s not in rets:
            continue
        peers = [rets[p] for p in rets if in_univ[p] and dates[p] == dates[s]]
        if not peers:
            continue
        resid = rets[s] - float(np.mean(peers))
        out[s] = bool(rets[s] != 0 and np.sign(resid) == np.sign(rets[s]))
    return out


def g4(history: pd.DataFrame, sides: dict[str, int], trigger: str | None = None) -> dict[str, bool]:
    adj = _adjusted_tail(history, sides)
    out = {}
    for s, g in adj.groupby("symbol", sort=False):
        if len(g) < a09_gap_fade.MIN_ROWS:
            continue
        z = a09_gap_fade._yesterdays_gap_z(g["adj_open"], g["adj_close"])
        if z is None:
            continue
        out[s] = not (z * -sides[s] > GAP_SIGMA)
    return out


def stress_reading(adj: pd.DataFrame) -> tuple[float, float] | None:
    """(20-day universe volatility on the last date, median of its trailing 250 values), or None (G5)."""
    mkt = universe_returns(adj)
    if len(mkt) < STRESS_VOL_WINDOW + STRESS_MEDIAN_WINDOW - 1:
        return None
    vol = mkt.rolling(STRESS_VOL_WINDOW).std(ddof=0).dropna()
    if len(vol) < STRESS_MEDIAN_WINDOW:
        return None
    return float(vol.iloc[-1]), float(vol.iloc[-STRESS_MEDIAN_WINDOW:].median())


def g5(history: pd.DataFrame, sides: dict[str, int], trigger: str | None = None) -> dict[str, bool]:
    if not sides:
        return {}
    reading = stress_reading(_adjusted_tail(history))
    if reading is None:
        return {}
    return {s: reading[0] > reading[1] for s in sides}


def g6(history: pd.DataFrame, sides: dict[str, int], trigger: str | None = None) -> dict[str, bool]:
    adj = _adjusted_tail(history, sides)
    out = {}
    for s, g in adj.groupby("symbol", sort=False):
        if len(g) < OB_ROWS:
            continue
        g = g.tail(OB_ROWS)
        zone = ob_core.detect(g["adj_open"].to_numpy(float), g["adj_high"].to_numpy(float), g["adj_low"].to_numpy(float), g["adj_close"].to_numpy(float))
        last = float(g["adj_close"].iloc[-1])
        side = sides[s]
        if zone is None or zone["side"] != side:
            out[s] = False
        else:
            out[s] = last >= zone["zone_low"] if side > 0 else last <= zone["zone_high"]
    return out


def g7(history: pd.DataFrame, sides: dict[str, int], trigger: str | None = None) -> dict[str, bool]:
    if history.empty or not sides:
        return {}
    d = d01c_oi_fade.score(history[history["symbol"].isin(list(sides))])
    return {s: bool(np.sign(d[s]) == sides[s]) for s in sides if s in d.index and d[s] != 0}


def g8(history: pd.DataFrame, sides: dict[str, int], trigger: str | None = None) -> dict[str, bool]:
    if history.empty or not sides or "volume" not in history.columns:
        return {}
    sub = _eligible(history)
    sub = sub[sub["symbol"].isin(list(sides))].sort_values(["symbol", "date"])
    out = {}
    for s, g in sub.groupby("symbol", sort=False):
        v = g["volume"].to_numpy(float)
        if len(v) < VOLUME_WINDOW + 1:
            continue
        base = v[-(VOLUME_WINDOW + 1) : -1].mean()
        if not np.isfinite(base) or base <= 0 or not np.isfinite(v[-1]):
            continue
        out[s] = bool(v[-1] > VOLUME_MULTIPLE * base)
    return out


GATES: dict[str, Callable[..., dict[str, bool]]] = {"g1": g1, "g2": g2, "g3": g3, "g4": g4, "g5": g5, "g6": g6, "g7": g7, "g8": g8}


# ---------------------------------------------------------------- cells


def cell_id(trigger: str, gate: str, keep: bool = True) -> str:
    return f"G_{trigger.upper()}_{gate.upper()}" + ("" if keep else "_NOT")


def trigger_side_scores(trigger: str, history: pd.DataFrame) -> pd.Series:
    """The trigger's own scores, restricted to its table side."""
    t = TRIGGERS[trigger]
    base = t.mod.score(history)
    return base[base * t.side > 0].astype(float)


def verdicts(trigger: str, gate: str, history: pd.DataFrame) -> tuple[pd.Series, dict[str, bool]]:
    base = trigger_side_scores(trigger, history)
    if base.empty:
        return base, {}
    side = TRIGGERS[trigger].side
    v = GATES[gate](history, {s: side for s in base.index}, trigger)
    return base, {s: bool(x) for s, x in v.items()}


def cell_score(trigger: str, gate: str, keep: bool, history: pd.DataFrame) -> pd.Series:
    base, v = verdicts(trigger, gate, history)
    return core.keep_if(base, v if keep else {s: not x for s, x in v.items()})


def cell(trigger: str, gate: str, keep: bool = True):
    """`(score, rules_fired)` for one cell; refuses a skipped or unknown cell."""
    if (trigger, gate) not in CELLS:
        raise ValueError(f"no cell {trigger} x {gate}: {SKIPPED.get((trigger, gate), 'unknown')}")
    t, cid = TRIGGERS[trigger], cell_id(trigger, gate, keep)
    held = "holds" if keep else "does not hold"

    def score(history: pd.DataFrame) -> pd.Series:
        return cell_score(trigger, gate, keep, history)

    def fired(history: pd.DataFrame, symbol: str) -> str:
        # Full history, not the symbol's own rows: G2, G3 and G5 read the universe.
        if symbol in cell_score(trigger, gate, keep, history).index:
            return f"{cid}: {t.label} {t.side_word} pick where {gate.upper()} {GATE_NAMES[gate]} {held}. " + t.mod.rules_fired(history, symbol)
        return f"{cid}: no {t.label} {t.side_word} pick, or {gate.upper()} {GATE_NAMES[gate]} gave no verdict or the other verdict, abstain"

    score.__doc__ = f"{cid}: {t.label} {t.side_word} scores kept where {gate.upper()} {held}."
    return score, fired
