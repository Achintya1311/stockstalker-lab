"""GURU_V1: well-known published daily-chart setups, coded literally with one fixed parameter set each
(`cards/R01.yml`, `cards/R02.yml`, `cards/R02B.yml`, `cards/R03.yml`, `cards/R04.yml`, `cards/P01.yml`,
`cards/P02.yml`).

Attribution (rules restated in the lab's own words; no text or code copied from any book or site):
  R01  Holy Grail            Linda Bradford Raschke and Laurence Connors, "Street Smarts" (1995).
  R02  Turtle Soup           Raschke and Connors, "Street Smarts" (1995).
  R02B Turtle Soup Plus One  Raschke and Connors, "Street Smarts" (1995).
  R03  Anti                  Linda Bradford Raschke (3-10 oscillator setup; also in "Street Smarts").
  R04  80-20                 Raschke and Connors, "Street Smarts" (1995).
  P01  Five-EMA              Subasish Pani (Power of Stocks), an intraday 5 / 15 minute method; here a
                             DAILY adaptation, which is not what the author published.
  P02  Bollinger 1.5         a practitioner variant of P01's alert-candle logic on John Bollinger's bands
                             (20 periods, 1.5 standard deviations).
Requested by the owner on 14 Nov 2026 to ask whether these setups are useful on NSE F&O stocks. Nothing here
is assumed to work (SPEC.md section 5) and nothing is tuned (SPEC.md section 8 is not applied: one literal
parameter set each, every ambiguity resolved in the card under `assumptions`).

Common machinery. Every symbol with a row on the last visible date (flagged `has_future` there, when the column
exists) and at least `MIN_ROWS` rows in the tail is judged. Prices are the split / bonus adjusted series
(`scripts.adjustments.compute_adjustment_factors`) on the last `TAIL_DATES` market dates; adjustment factors
depend only on later rows, so the tail's adjusted values equal the full history's. Recursive indicators (EMA,
Wilder smoothing) start at the tail's first row, so they are pure functions of the visible past. The signal
session S is always the LAST visible session (the previous close for a day pick, Friday's close for a week
pick): no setup reads anything after it. Indicators, oldest first, per symbol:
  ATR(14)   Wilder average of the true range (`_wilder`, seeded with the simple mean of the first 14 values).
  ADX(14)   Wilder's +DI, -DI and ADX (directional movement smoothed with `_wilder`, DX smoothed again).
  EMA(n)    exponential average, span form, adjust=False, first value = first close.
  SMA(n)    simple rolling mean; Bollinger standard deviation is the population form (ddof = 0).

A setup returns (side, strength) with strength > 0; score = side x strength, so the engine's `top` selection
takes the strongest readings on each side. A symbol whose bullish and bearish setups both fire abstains.
Reasoning text names conditions only, never a price level.

Setup rules (bullish; bearish is the exact mirror: highs for lows, +DI for -DI, above for below):

R01 Holy Grail. A "touch" session has low <= EMA20. T = the most recent touch among the `HG_WINDOW` sessions
    before S; every session after T and before S failed to trade above its prior session's high (so S is the
    first break since the touch); S's high > the prior session's high. The trend qualifies on Q, the session
    just before the first touch of the run of consecutive touch sessions ending at T: ADX(14) at Q > 30,
    ADX at Q > ADX `HG_RISING` sessions before Q, and +DI > -DI at Q. Strength = ADX(14) at S.
R02 Turtle Soup. Prior low = the lowest low of the 20 sessions before S, at its most recent occurrence P.
    Low at S < prior low, S - P >= 4, close at S > prior low. Strength = (prior low - low at S) / ATR at S.
R02B Turtle Soup Plus One. The same new-low test on session S-1 (prior low over the 20 sessions before S-1,
    made at least 4 sessions before S-1), S-1 closed at or below that prior low, and S closes above it.
    Strength = (prior low - the lower of the lows of S-1 and S) / ATR at S.
R03 Anti. fast = SMA3(close) - SMA10(close); slow = SMA16(fast). slow rose on each of the last 3 sessions
    (slow[S] > slow[S-1] > slow[S-2] > slow[S-3]); fast fell on the 2 sessions before S
    (fast[S-3] > fast[S-2] > fast[S-1]) and rose at S (fast[S] > fast[S-1]).
    Strength = (slow[S] - slow[S-3]) / 3 / ATR at S.
R04 80-20. Session S-1 has a range > 0, opened in its top 20% ((open - low) >= 0.8 x range) and closed in its
    bottom 20% ((close - low) <= 0.2 x range). S trades below S-1's low and closes above it.
    Strength = (low of S-1 - low of S) / ATR at S.
P01 Five-EMA. Alert candle A = S-1. Bullish: the whole of A is below its EMA5 (high < EMA5 at A) and S trades
    above A's high. Bearish: low of A > EMA5 at A and S trades below A's low.
    Strength = |EMA5 at A - nearer extreme of A| / ATR at A.
P02 Bollinger 1.5. Bands at A = S-1: SMA20 of close +/- 1.5 population standard deviations. Bullish: high of A
    < lower band at A and S trades above A's high. Bearish: low of A > upper band at A and S trades below A's
    low. Strength = distance of A's nearer extreme from the band it cleared / ATR at A.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

TAIL_DATES = 250
MIN_ROWS = 60
ATR_N = 14
ADX_N = 14

HG_ADX_MIN = 30.0
HG_RISING = 3       # ADX higher than this many sessions earlier
HG_EMA = 20
HG_WINDOW = 3       # the touch must be within this many sessions before the signal session

TS_N = 20
TS_GAP = 4          # previous 20-session low made at least this many sessions earlier

ANTI_FAST, ANTI_SLOW, ANTI_SIGNAL = 3, 10, 16
ANTI_RISE = 3       # slow line rising for this many sessions
ANTI_PULLBACK = 2   # fast line falling for this many sessions before turning up

ET_TOP = 0.8        # 80-20: open in the top 20%, close in the bottom 20% of the range
ET_BOTTOM = 0.2

FIVE_EMA = 5
BB_N, BB_K = 20, 1.5

Setup = Callable[[np.ndarray, np.ndarray, np.ndarray, np.ndarray], "tuple[int, float, str] | None"]


# ---------------------------------------------------------------- indicators (numpy, oldest first)


def _wilder(values: np.ndarray, n: int, start: int = 0) -> np.ndarray:
    """Wilder's recursion over values[start:], seeded with the mean of its first n values; NaN before."""
    out = np.full(len(values), np.nan)
    v = values[start:]
    if len(v) < n:
        return out
    acc = float(np.mean(v[:n]))
    out[start + n - 1] = acc
    for i in range(n, len(v)):
        acc = acc + (float(v[i]) - acc) / n
        out[start + i] = acc
    return out


def true_range(h: np.ndarray, l: np.ndarray, c: np.ndarray) -> np.ndarray:
    pc = np.r_[c[0], c[:-1]]
    return np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))


def atr(h, l, c, n: int = ATR_N) -> np.ndarray:
    return _wilder(true_range(h, l, c), n)


def adx(h, l, c, n: int = ADX_N) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(+DI, -DI, ADX), NaN until defined. Directional movement starts at the second row."""
    up = np.r_[0.0, h[1:] - h[:-1]]
    dn = np.r_[0.0, l[:-1] - l[1:]]
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = true_range(h, l, c)
    s_tr, s_p, s_m = (_wilder(x, n, start=1) for x in (tr, pdm, mdm))
    with np.errstate(invalid="ignore", divide="ignore"):
        pdi = np.where(s_tr > 0, 100.0 * s_p / s_tr, np.nan)
        mdi = np.where(s_tr > 0, 100.0 * s_m / s_tr, np.nan)
        tot = pdi + mdi
        dx = np.where(tot > 0, 100.0 * np.abs(pdi - mdi) / tot, 0.0)
    dx = np.where(np.isnan(pdi), np.nan, dx)
    first = int(np.argmax(~np.isnan(dx))) if (~np.isnan(dx)).any() else len(dx)
    a = _wilder(np.nan_to_num(dx), n, start=first) if first < len(dx) else np.full(len(dx), np.nan)
    return pdi, mdi, a


def ema(c: np.ndarray, span: int) -> np.ndarray:
    return pd.Series(c, dtype=float).ewm(span=span, adjust=False).mean().to_numpy()


def sma(x: np.ndarray, n: int) -> np.ndarray:
    return pd.Series(x, dtype=float).rolling(n, min_periods=n).mean().to_numpy()


def flip(o, h, l, c, level: float = 0.0):
    """Mirror bars about `level` (bullish <-> bearish); used by the tests and the audit."""
    return 2 * level - o, 2 * level - l, 2 * level - h, 2 * level - c


def _ok(x: float) -> bool:
    return x is not None and np.isfinite(x)


# ---------------------------------------------------------------- setups: (o, h, l, c) -> (side, strength, note) | None


def holy_grail(o, h, l, c):
    n = len(c)
    if n < MIN_ROWS:
        return None
    e = ema(c, HG_EMA)
    pdi, mdi, a = adx(h, l, c)
    s = n - 1
    hits = []
    for side in (1, -1):
        touch = (l <= e) if side > 0 else (h >= e)
        broke = (h[1:] > h[:-1]) if side > 0 else (l[1:] < l[:-1])  # broke[i-1]: session i broke session i-1
        if not broke[s - 1]:
            continue
        t = None
        for j in range(s - 1, s - 1 - HG_WINDOW, -1):
            if touch[j]:
                t = j
                break
            if broke[j - 1]:     # an earlier break since the touch: S is not the first
                break
        if t is None:
            continue
        t0 = t
        while t0 - 1 >= 0 and touch[t0 - 1]:
            t0 -= 1
        q = t0 - 1
        if q - HG_RISING < 0 or not (_ok(a[q]) and _ok(a[q - HG_RISING]) and _ok(pdi[q]) and _ok(mdi[q])):
            continue
        di_ok = pdi[q] > mdi[q] if side > 0 else mdi[q] > pdi[q]
        if a[q] > HG_ADX_MIN and a[q] > a[q - HG_RISING] and di_ok and _ok(a[s]) and a[s] > 0:
            hits.append((side, float(a[s]), f"ADX {a[q]:.1f} rising before a pullback to EMA{HG_EMA} "
                                            f"{s - t} session(s) ago, then a break of the prior session's "
                                            f"{'high' if side > 0 else 'low'}; ADX now {a[s]:.1f}"))
    return _one(hits)


def _prior_extreme(h, l, end: int, side: int) -> tuple[float, int] | None:
    """Lowest low (side +1) / highest high (side -1) over the TS_N sessions before `end`, most recent index."""
    if end - TS_N < 0:
        return None
    w = l[end - TS_N:end] if side > 0 else h[end - TS_N:end]
    val = float(w.min() if side > 0 else w.max())
    idx = end - TS_N + int(np.flatnonzero(w == val)[-1])
    return val, idx


def turtle_soup(o, h, l, c):
    n = len(c)
    if n < MIN_ROWS:
        return None
    s = n - 1
    r = atr(h, l, c)[s]
    if not (_ok(r) and r > 0):
        return None
    hits = []
    for side in (1, -1):
        pe = _prior_extreme(h, l, s, side)
        if pe is None:
            continue
        ref, p = pe
        if s - p < TS_GAP:
            continue
        if side > 0 and l[s] < ref and c[s] > ref:
            depth = ref - l[s]
        elif side < 0 and h[s] > ref and c[s] < ref:
            depth = h[s] - ref
        else:
            continue
        hits.append((side, float(depth / r), f"new 20-session {'low' if side > 0 else 'high'} beyond one made "
                                             f"{s - p} sessions earlier, closed back inside; depth "
                                             f"{depth / r:.2f} ATR"))
    return _one(hits)


def turtle_soup_plus_one(o, h, l, c):
    n = len(c)
    if n < MIN_ROWS:
        return None
    s, d = n - 1, n - 2
    r = atr(h, l, c)[s]
    if not (_ok(r) and r > 0):
        return None
    hits = []
    for side in (1, -1):
        pe = _prior_extreme(h, l, d, side)
        if pe is None:
            continue
        ref, p = pe
        if d - p < TS_GAP:
            continue
        if side > 0 and l[d] < ref and c[d] <= ref and c[s] > ref:
            depth = ref - min(l[d], l[s])
        elif side < 0 and h[d] > ref and c[d] >= ref and c[s] < ref:
            depth = max(h[d], h[s]) - ref
        else:
            continue
        hits.append((side, float(depth / r), f"new 20-session {'low' if side > 0 else 'high'} one session ago "
                                             f"closed beyond the earlier one, reclaimed today; depth "
                                             f"{depth / r:.2f} ATR"))
    return _one(hits)


def anti(o, h, l, c):
    n = len(c)
    if n < MIN_ROWS:
        return None
    s = n - 1
    fast = sma(c, ANTI_FAST) - sma(c, ANTI_SLOW)
    slow = sma(fast, ANTI_SIGNAL)
    r = atr(h, l, c)[s]
    win = slice(s - max(ANTI_RISE, ANTI_PULLBACK + 1), s + 1)
    if not (_ok(r) and r > 0) or np.isnan(slow[win]).any() or np.isnan(fast[win]).any():
        return None
    hits = []
    for side in (1, -1):
        f, sl = side * fast, side * slow
        rising = all(sl[s - i] > sl[s - i - 1] for i in range(ANTI_RISE))
        pulled = all(f[s - 1 - i] < f[s - 2 - i] for i in range(ANTI_PULLBACK))
        if rising and pulled and f[s] > f[s - 1]:
            slope = (sl[s] - sl[s - ANTI_RISE]) / ANTI_RISE / r
            hits.append((side, float(slope), f"3-10 slow line {'rising' if side > 0 else 'falling'} "
                                             f"{ANTI_RISE}+ sessions, fast line turned back after a "
                                             f"{ANTI_PULLBACK}-session pullback; slope {slope:.3f} ATR/session"))
    return _one(hits)


def eighty_twenty(o, h, l, c):
    n = len(c)
    if n < MIN_ROWS:
        return None
    s, d = n - 1, n - 2
    rng = h[d] - l[d]
    r = atr(h, l, c)[s]
    if rng <= 0 or not (_ok(r) and r > 0):
        return None
    hits = []
    op, cp = (o[d] - l[d]) / rng, (c[d] - l[d]) / rng
    if op >= ET_TOP and cp <= ET_BOTTOM and l[s] < l[d] and c[s] > l[d]:
        hits.append((1, float((l[d] - l[s]) / r), f"prior session opened in its top 20% and closed in its bottom "
                                                  f"20%; today undercut its low and closed back above "
                                                  f"({(l[d] - l[s]) / r:.2f} ATR)"))
    if op <= ET_BOTTOM and cp >= ET_TOP and h[s] > h[d] and c[s] < h[d]:
        hits.append((-1, float((h[s] - h[d]) / r), f"prior session opened in its bottom 20% and closed in its top "
                                                   f"20%; today exceeded its high and closed back below "
                                                   f"({(h[s] - h[d]) / r:.2f} ATR)"))
    return _one(hits)


def _alert_break(h, l, c, upper: np.ndarray, lower: np.ndarray, what: str):
    """Shared by P01 and P02: alert candle A = S-1 fully beyond a line; S breaks A's opposite extreme."""
    s, a = len(c) - 1, len(c) - 2
    r = atr(h, l, c)[a]
    if not (_ok(r) and r > 0 and _ok(upper[a]) and _ok(lower[a])):
        return None
    hits = []
    if h[a] < lower[a] and h[s] > h[a]:
        dist = (lower[a] - h[a]) / r
        hits.append((1, float(dist), f"prior candle wholly below {what} ({dist:.2f} ATR clear); today broke its high"))
    if l[a] > upper[a] and l[s] < l[a]:
        dist = (l[a] - upper[a]) / r
        hits.append((-1, float(dist), f"prior candle wholly above {what} ({dist:.2f} ATR clear); today broke its low"))
    return _one(hits)


def five_ema(o, h, l, c):
    if len(c) < MIN_ROWS:
        return None
    e = ema(c, FIVE_EMA)
    return _alert_break(h, l, c, e, e, f"EMA{FIVE_EMA}")


def bollinger_1p5(o, h, l, c):
    if len(c) < MIN_ROWS:
        return None
    s = pd.Series(c, dtype=float)
    mid = s.rolling(BB_N, min_periods=BB_N).mean().to_numpy()
    sd = s.rolling(BB_N, min_periods=BB_N).std(ddof=0).to_numpy()
    return _alert_break(h, l, c, mid + BB_K * sd, mid - BB_K * sd, f"its {BB_K} sd band")


def _one(hits: list):
    if len(hits) != 1:
        return None   # nothing, or both sides at once: abstain
    side, strength, note = hits[0]
    if not (_ok(strength) and strength > 0):
        return None
    return side, strength, note


# ---------------------------------------------------------------- configs and the panel


@dataclass(frozen=True)
class Config:
    config_id: str
    module: str
    label: str
    setup: Setup


CONFIGS: dict[str, Config] = {
    "r01_holy_grail": Config("R01", "r01_holy_grail", "Holy Grail (ADX trend pullback to EMA20)", holy_grail),
    "r02_turtle_soup": Config("R02", "r02_turtle_soup", "Turtle Soup (failed 20-session breakout)", turtle_soup),
    "r02b_turtle_soup_plus_one": Config("R02B", "r02b_turtle_soup_plus_one", "Turtle Soup Plus One",
                                        turtle_soup_plus_one),
    "r03_anti": Config("R03", "r03_anti", "Anti (3-10 oscillator pullback)", anti),
    "r04_eighty_twenty": Config("R04", "r04_eighty_twenty", "80-20 (reversal of an extreme bar)", eighty_twenty),
    "p01_five_ema": Config("P01", "p01_five_ema", "Five-EMA alert candle (daily adaptation)", five_ema),
    "p02_bollinger_1p5": Config("P02", "p02_bollinger_1p5", "Bollinger 1.5 sd alert candle", bollinger_1p5),
}


def _flag(s: pd.Series) -> pd.Series:
    return s.fillna(False).astype(bool)


_MEMO: list = []   # one entry: (history object, its adjusted tail); `rules_fired` after `score` reuses it


def tail(history: pd.DataFrame) -> pd.DataFrame:
    """Adjusted rows of the judged symbols on the last TAIL_DATES market dates, sorted by symbol then date."""
    if _MEMO and _MEMO[0][0] is history and _MEMO[0][1] == len(history):
        return _MEMO[0][2]
    out = _tail_uncached(history)
    _MEMO[:] = [(history, len(history), out)]
    return out


def _tail_uncached(history: pd.DataFrame) -> pd.DataFrame:
    if history.empty:
        return history.iloc[0:0]
    last = history["date"].max()
    on_last = history[history["date"] == last]
    if "has_future" in on_last.columns:
        on_last = on_last[_flag(on_last["has_future"])]
    syms = set(on_last["symbol"])
    if not syms:
        return history.iloc[0:0]
    dates = np.sort(history["date"].unique())
    h = history[(history["date"] >= dates[max(len(dates) - TAIL_DATES, 0)]) & history["symbol"].isin(syms)]
    return compute_adjustment_factors(h).sort_values(["symbol", "date"])


def _bars(g: pd.DataFrame):
    return tuple(g[k].to_numpy(dtype=float) for k in ("adj_open", "adj_high", "adj_low", "adj_close"))


def evaluate(name: str, history: pd.DataFrame, symbol: str | None = None) -> dict[str, tuple[int, float, str]]:
    setup = CONFIGS[name].setup
    out = {}
    adj = tail(history)
    if symbol is not None:
        adj = adj[adj["symbol"] == symbol]
    for sym, g in adj.groupby("symbol", sort=False):
        if len(g) < MIN_ROWS:
            continue
        hit = setup(*_bars(g))
        if hit is not None:
            out[sym] = hit
    return out


def config_score(name: str, history: pd.DataFrame) -> pd.Series:
    hits = evaluate(name, history)
    return pd.Series({s: side * strength for s, (side, strength, _) in hits.items()}, dtype=float)


def config(name: str):
    cfg = CONFIGS[name]
    tag = name.upper()

    def _score(history: pd.DataFrame) -> pd.Series:
        return config_score(name, history)

    def _rules_fired(history: pd.DataFrame, symbol: str) -> str:
        if (tail(history)["symbol"] == symbol).sum() < MIN_ROWS:
            return f"{tag} {cfg.label}: insufficient history or not judged on the last date, abstain"
        hit = evaluate(name, history, symbol).get(symbol)
        if hit is None:
            return f"{tag} {cfg.label}: setup not present, abstain"
        side, strength, note = hit
        word = "bullish pick" if side > 0 else "bearish pick"
        return f"{tag} {cfg.label}: {note} -> score {side * strength:+.4f} ({word})"

    return _score, _rules_fired
