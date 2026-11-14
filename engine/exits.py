"""Exit-plan (payoff) scoring: an opt-in `exit:` block on a train experiment (owner-approved, 14 Nov 2026).

Hit rate says whether a pick's direction was right; it says nothing about what a rule pays once an exit
plan decides when a position ends. This module simulates one exit plan for every scored pick
(`date, symbol, side`) and reports the payoff in R multiples and in percent, after the engine's own cost
model (`engine.scoring.DELIVERY_COST` for a bullish pick, `FUTURES_COST` for a bearish one, SPEC.md
section 3), next to the same plan applied to every universe stock on the same dates.

Nothing here runs unless an experiment's yml carries an `exit:` block. Without one, `engine/run_queue.py`
and `engine/experiment_report.py` take exactly the code path they took before (proven byte-identical by
`tests/test_exits.py`). Train only: this is observation, not a gate (see `state/engine-issues.md`).

Conventions (bullish; bearish is the exact mirror, prices negated):

- Entry: the pick date's open, the same entry the day / week / month moves already use (the strategy saw
  data up to the previous close, `engine.replay.truncate`). Session 1 of the hold is the pick date itself.
- Risk unit R = `stop_atr` x ATR(14). ATR is Wilder's (true range, first value the simple mean of the
  first 14 true ranges, then the 1/14 recursion) on split/bonus-adjusted prices
  (`scripts.adjustments`), taken from the symbol's last session strictly before the pick date, so it
  uses no price from the pick date or later. It is held fixed for the whole hold.
- `fixed`: stop 1R against the entry, target `target_r` x R in favour, time exit at the close of session
  `max_sessions`. On session 2 onward an open beyond the stop (or target) fills at that open. If one
  session's range touches both the stop and the target, the stop counts (conservative).
- `trail`: no target. The stop sits `stop_atr` x ATR below the best close since entry (the entry price
  before the first close), and never moves down: chandelier style. A gap through it fills at the open.
  Plus the time exit.
- `time`: no stop, no target; exit at the close of session `max_sessions`. `stop_atr` (default 2) then
  only sets the R unit, so R figures stay comparable with a `fixed` plan of the same `stop_atr`.
- A session on which the symbol has no row is skipped (nothing can trigger); the time exit then uses
  the last close inside the window. A pick whose `max_sessions` window would run past the split's end
  date (or past the data) is dropped before scoring, so no train result sees a validation price.
- Outcome: favourable fractional move from entry to exit minus the side's round-trip cost, in percent;
  divided by R / entry it is the outcome in R.

The simulation is vectorised: every pick's forward window is gathered from price matrices
(calendar date x symbol) into `[picks, max_sessions]` arrays and resolved with numpy, in chunks.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from engine.scoring import DELIVERY_COST, FUTURES_COST, MONTH_BLOCK, block_bootstrap_interval, block_t

KINDS = ("fixed", "trail", "time")
SIDE_NAMES = {1: "bullish", -1: "bearish"}
SIDE_CODES = {v: k for k, v in SIDE_NAMES.items()}
ATR_PERIOD = 14
TIME_STOP_ATR_DEFAULT = 2.0
BOOTSTRAP_REPS = 2000
STOP, TARGET, TIME = 0, 1, 2
_CHUNK = 50_000
_ALLOWED = {"fixed": {"kind", "stop_atr", "target_r", "max_sessions", "sides"},
            "trail": {"kind", "stop_atr", "max_sessions", "sides"},
            "time": {"kind", "stop_atr", "max_sessions", "sides"}}
COST_NOTE = (f"engine cost model (SPEC.md section 3): bullish = delivery round trip {DELIVERY_COST * 100:.3f}%, "
             f"bearish = futures round trip {FUTURES_COST * 100:.3f}%, charged once per pick")


def parse_exit_plan(block) -> dict:
    """Validate an experiment's `exit:` block and return it normalised. Raises ValueError when invalid.

    Schema:
        exit:
          kind: fixed | trail | time
          stop_atr: number > 0       # required for fixed and trail; time: optional (default 2), sets R only
          target_r: number > 0       # fixed only, required
          max_sessions: integer >= 1 # required: time exit at the close of this session (entry session = 1)
          sides: [bullish, bearish]  # optional: which sides of the `top` selection to simulate (default both)
    """
    if not isinstance(block, dict):
        raise ValueError("exit: must be a mapping")
    kind = block.get("kind")
    if kind not in KINDS:
        raise ValueError(f"exit.kind must be one of {list(KINDS)}, got {kind!r}")
    unknown = set(block) - _ALLOWED[kind]
    if unknown:
        raise ValueError(f"exit ({kind}) does not take {sorted(unknown)}")

    def number(key, required, default=None):
        v = block.get(key, default)
        if v is None:
            if required:
                raise ValueError(f"exit ({kind}) needs {key}")
            return None
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
            raise ValueError(f"exit.{key} must be a positive number, got {v!r}")
        return float(v)

    ms = block.get("max_sessions")
    if isinstance(ms, bool) or not isinstance(ms, int) or ms < 1:
        raise ValueError(f"exit.max_sessions must be an integer >= 1, got {ms!r}")
    sides = block.get("sides", ["bullish", "bearish"])
    if (not isinstance(sides, list) or not sides or len(set(sides)) != len(sides)
            or not set(sides) <= set(SIDE_CODES)):
        raise ValueError(f"exit.sides must be a non-empty list drawn from {list(SIDE_CODES)}, got {sides!r}")
    plan = {"kind": kind,
            "stop_atr": number("stop_atr", kind != "time", TIME_STOP_ATR_DEFAULT if kind == "time" else None)}
    if kind == "fixed":
        plan["target_r"] = number("target_r", True)
    plan["max_sessions"] = ms
    plan["sides"] = [s for s in ("bullish", "bearish") if s in sides]
    return plan


def time_control(plan: dict) -> dict:
    """The plain time-only plan with the same hold and the same R unit: what the exit plan is compared with."""
    return {"kind": "time", "stop_atr": plan["stop_atr"], "max_sessions": plan["max_sessions"], "sides": plan["sides"]}


def plan_label(plan: dict) -> str:
    if plan["kind"] == "fixed":
        return (f"fixed: stop {plan['stop_atr']:g} ATR (= 1R), target {plan['target_r']:g}R, "
                f"time exit after {plan['max_sessions']} sessions")
    if plan["kind"] == "trail":
        return f"trail: stop {plan['stop_atr']:g} ATR from the best close (1R = {plan['stop_atr']:g} ATR), " \
               f"time exit after {plan['max_sessions']} sessions"
    return f"time: exit at the close of session {plan['max_sessions']} (1R = {plan['stop_atr']:g} ATR, no stop)"


def wilder_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = ATR_PERIOD) -> np.ndarray:
    """Wilder ATR over one symbol's rows in date order. NaN until `period` true ranges exist.
    Row 0's true range is high - low (no previous close)."""
    prev = np.r_[np.nan, close[:-1]]
    tr = np.fmax(high - low, np.fmax(np.abs(high - prev), np.abs(low - prev)))
    out = np.full(len(tr), np.nan)
    if len(tr) < period:
        return out
    out[period - 1] = tr[:period].mean()
    for i in range(period, len(tr)):
        out[i] = out[i - 1] + (tr[i] - out[i - 1]) / period
    return out


def _grouped_wilder_atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> np.ndarray:
    """`wilder_atr` for every symbol at once (df sorted by symbol, date), via pandas' ewm recursion."""
    prev = df.groupby("symbol", sort=False)["c"].shift(1).to_numpy()
    h, l = df["h"].to_numpy(), df["l"].to_numpy()
    tr = np.fmax(h - l, np.fmax(np.abs(h - prev), np.abs(l - prev)))
    pos = df.groupby("symbol", sort=False).cumcount().to_numpy()
    seed = pd.Series(tr).groupby(df["symbol"].to_numpy()).transform(
        lambda s: s.rolling(period, min_periods=period).mean()).to_numpy()
    x = np.where(pos == period - 1, seed, np.where(pos >= period, tr, np.nan))
    # ewm(adjust=False) starts its recursion at each group's first non-NaN value: the seed.
    atr = pd.Series(x).groupby(df["symbol"].to_numpy()).transform(
        lambda s: s.ewm(alpha=1.0 / period, adjust=False, ignore_na=True).mean()).to_numpy()
    return np.where(pos >= period - 1, atr, np.nan)


class ExitData:
    """Adjusted open/high/low/close and the pre-pick ATR as (calendar date x symbol) matrices."""

    def __init__(self, dataset: pd.DataFrame):
        cols = ["date", "symbol", "open", "high", "low", "close"]
        df = dataset[cols + (["prevclose"] if "prevclose" in dataset.columns else [])].copy()
        df["date"] = df["date"].astype(str)
        if "prevclose" in df.columns and df["prevclose"].notna().all():
            from scripts.adjustments import compute_adjustment_factors

            adj = compute_adjustment_factors(df)
            df = adj[["date", "symbol"]].assign(o=adj["adj_open"], h=adj["adj_high"], l=adj["adj_low"],
                                                c=adj["adj_close"])
        else:  # no PREVCLOSE to derive split factors from: raw prices
            df = df.rename(columns={"open": "o", "high": "h", "low": "l", "close": "c"})
        df = df.sort_values(["symbol", "date"]).reset_index(drop=True)
        self.dates = np.array(sorted(df["date"].unique()))
        self.symbols = np.array(sorted(df["symbol"].unique()))
        self._di = pd.Index(self.dates)
        self._si = pd.Index(self.symbols)
        di, si = self._di.get_indexer(df["date"]), self._si.get_indexer(df["symbol"])
        shape = (len(self.dates), len(self.symbols))
        self.O, self.H, self.L, self.C = (np.full(shape, np.nan) for _ in range(4))
        for mat, col in ((self.O, "o"), (self.H, "h"), (self.L, "l"), (self.C, "c")):
            mat[di, si] = df[col].to_numpy(dtype=float)
        atr = np.full(shape, np.nan)
        atr[di, si] = _grouped_wilder_atr(df)
        # ATR known before date d = the symbol's latest ATR on a calendar date strictly before d.
        self.ATR = pd.DataFrame(atr).ffill().shift(1).to_numpy()

    def last_index(self, split_end=None) -> int:
        """Index of the last calendar date a window may use: the split's end date (inclusive) or the data end."""
        if split_end in (None, "go-live"):
            return len(self.dates) - 1
        return int(np.searchsorted(self.dates, str(split_end), side="right")) - 1

    def simulate(self, plan: dict, side: int, dates, symbols, split_end=None) -> dict:
        """Outcomes for one side's picks. Returns arrays aligned with the input (NaN / -1 when dropped):
        `r`, `pct` (fractions, net of cost), `hold` (sessions), `reason` (STOP / TARGET / TIME)."""
        di = self._di.get_indexer(pd.Index(np.asarray(dates).astype(str)))
        si = self._si.get_indexer(pd.Index(np.asarray(symbols).astype(str)))
        n, N = len(di), int(plan["max_sessions"])
        r, pct = np.full(n, np.nan), np.full(n, np.nan)
        hold, reason = np.full(n, -1), np.full(n, -1)
        ok = (di >= 0) & (si >= 0) & (di + N - 1 <= self.last_index(split_end))
        safe_di, safe_si = np.where(ok, di, 0), np.where(ok, si, 0)
        entry, atr = self.O[safe_di, safe_si], self.ATR[safe_di, safe_si]
        ok &= np.isfinite(entry) & (entry > 0) & np.isfinite(atr) & (atr > 0)
        cost = DELIVERY_COST if side > 0 else FUTURES_COST
        steps = np.arange(N)
        for start in range(0, int(ok.sum()), _CHUNK):
            idx = np.flatnonzero(ok)[start:start + _CHUNK]
            rows, cols = di[idx, None] + steps, si[idx, None]
            o, h, l, c = self.O[rows, cols], self.H[rows, cols], self.L[rows, cols], self.C[rows, cols]
            if side < 0:  # mirror: a bearish hold is a bullish hold on negated prices
                o, h, l, c = -o, -l, -h, -c
            e = entry[idx]
            fe = side * e
            risk = plan["stop_atr"] * atr[idx]
            px, why, hold_i = _resolve(plan, o, h, l, c, fe, risk)
            move = (px - fe) / e - cost
            pct[idx], r[idx] = move, move * e / risk
            hold[idx], reason[idx] = hold_i, why
        return {"r": r, "pct": pct, "hold": hold, "reason": reason}


def _resolve(plan, o, h, l, c, fe, risk):
    """Exit price (mirrored space), reason and holding sessions for a chunk of `[picks, N]` windows."""
    n, N = o.shape
    later = np.arange(N)[None, :] > 0  # a gap fill needs an open after the entry open
    if plan["kind"] == "fixed":
        stop = (fe - risk)[:, None]
        tgt = (fe + plan["target_r"] * risk)[:, None]
        gap_s, gap_t = later & (o <= stop), later & (o >= tgt)
        hit_s, hit_t = l <= stop, h >= tgt
        event = gap_s | gap_t | hit_s | hit_t
        price = np.where(gap_s | gap_t, o, np.where(hit_s, stop, tgt))
        why = np.where(gap_s | (~gap_t & hit_s), STOP, TARGET)
    elif plan["kind"] == "trail":
        best = np.fmax.accumulate(np.column_stack([fe, c[:, :-1]]), axis=1)  # best close known before each open
        stop = best - risk[:, None]
        gap_s, hit_s = later & (o <= stop), l <= stop
        event = gap_s | hit_s
        price = np.where(gap_s, o, stop)
        why = np.full((n, N), STOP)
    else:
        event = np.zeros((n, N), dtype=bool)
        price = why = None
    rows = np.arange(n)
    valid = np.isfinite(c)
    last = N - 1 - np.argmax(valid[:, ::-1], axis=1)  # last session with a close (session 1 always has one)
    px, out_why, held = c[rows, last], np.full(n, TIME), last + 1
    has = event.any(axis=1)
    if has.any():
        j = np.argmax(event, axis=1)
        px = np.where(has, price[rows, j], px)
        out_why = np.where(has, why[rows, j], out_why)
        held = np.where(has, j + 1, held)
    return px, out_why, held


def worst_losing_run(r_in_order) -> int:
    """Longest run of consecutive picks that were not right (outcome <= 0), in (date, symbol) order."""
    lose = np.asarray(r_in_order) <= 0
    if not lose.any():
        return 0
    edges = np.diff(np.r_[0, lose.astype(int), 0])
    return int((np.flatnonzero(edges == -1) - np.flatnonzero(edges == 1)).max())


def payoff_summary(r, pct, hold, reason) -> dict:
    """Metrics of one set of outcomes (already in (date, symbol) order, dropped rows removed)."""
    r, pct = np.asarray(r, float), np.asarray(pct, float)
    gains, losses = r[r > 0].sum(), -r[r < 0].sum()
    return {
        "n_picks": int(len(r)),
        "share_right": float((r > 0).mean()),
        "avg_r": float(r.mean()),
        "median_r": float(np.median(r)),
        "profit_factor": float(gains / losses) if losses > 0 else None,
        "avg_pct": float(pct.mean()),
        "median_pct": float(np.median(pct)),
        "avg_holding_sessions": float(np.mean(hold)),
        "share_stop": float(np.mean(np.asarray(reason) == STOP)),
        "share_target": float(np.mean(np.asarray(reason) == TARGET)),
        "share_time": float(np.mean(np.asarray(reason) == TIME)),
        "worst_losing_run": worst_losing_run(r),
    }


def block_length(plan: dict, horizon: str) -> int:
    """Pick dates per block for t and the bootstrap: at least one whole hold of overlap, and at least 8.
    Day picks are one session apart; week and month picks about five."""
    spacing = 1 if horizon == "day" else 5
    return max(MONTH_BLOCK, -(-int(plan["max_sessions"]) // spacing))


def interval_method(block: int) -> str:
    return (f"holds overlap across pick dates, so dates are not independent. t = mean / standard error of the "
            f"means of non-overlapping blocks of {block} consecutive pick dates; 95% interval = moving-block "
            f"bootstrap, block length {block} pick dates, {BOOTSTRAP_REPS} resamples, seed 0, percentile method")


def _side_payoff(xd: ExitData, plan: dict, side: int, side_picks: pd.DataFrame, universe: pd.DataFrame,
                 horizon: str, split_end) -> dict:
    picks = side_picks.sort_values(["date", "symbol"]).reset_index(drop=True)
    sim = xd.simulate(plan, side, picks["date"], picks["symbol"], split_end)
    keep = np.isfinite(sim["r"])
    out_of_window = int((~keep).sum())
    if not keep.any():
        return {"n_picks": 0, "n_dropped": out_of_window}
    res = payoff_summary(sim["r"][keep], sim["pct"][keep], sim["hold"][keep], sim["reason"][keep])
    res["n_dropped"] = out_of_window
    p = picks[keep].assign(r=sim["r"][keep])

    dates = p["date"].unique()
    uni = universe[universe["date"].isin(dates)].sort_values(["date", "symbol"]).reset_index(drop=True)
    usim = xd.simulate(plan, side, uni["date"], uni["symbol"], split_end)
    uni = uni.assign(r=usim["r"]).dropna(subset=["r"])
    per_date = p.groupby("date")["r"].mean().to_frame("pick_r").join(
        uni.groupby("date")["r"].mean().rename("universe_r"), how="inner").sort_index()
    diff = (per_date["pick_r"] - per_date["universe_r"]).to_numpy()
    block = block_length(plan, horizon)
    iv = block_bootstrap_interval(diff, block=block, reps=BOOTSTRAP_REPS, seed=0)
    res.update({
        "n_dates": int(len(per_date)),
        "baseline_avg_r": float(per_date["universe_r"].mean()) if len(per_date) else None,
        "avg_r_above_baseline": float(diff.mean()) if len(diff) else None,
        "t": block_t(diff, block=block),
        "interval": list(iv) if iv is not None else None,
        "interval_method": interval_method(block),
    })
    years = pd.to_datetime(p["date"]).dt.year
    dyear = pd.to_datetime(per_date.index).year
    by_year = []
    for y, g in p.groupby(years):
        d = diff[dyear == y]
        by_year.append({"year": int(y), "n_picks": int(len(g)), "share_right": float((g["r"] > 0).mean()),
                        "avg_r": float(g["r"].mean()),
                        "avg_r_above_baseline": float(d.mean()) if len(d) else None})
    res["by_year"] = by_year
    res["positive_year_share"] = float(np.mean([y["avg_r_above_baseline"] > 0 for y in by_year
                                                if y["avg_r_above_baseline"] is not None])) if by_year else None
    return res


def score_exit(side_picks: dict, plan: dict, xd: ExitData, universe: pd.DataFrame, horizon: str,
               split_end=None) -> dict:
    """Payoff of `plan` (and its time-only control) for each side in `plan['sides']`.

    `side_picks` maps a side name to that side's `date, symbol` picks (the `top` selection, in universe);
    `universe` is the in-universe `date, symbol` frame. Returns the block written to results.json."""
    out = {"plan": plan, "plan_label": plan_label(plan), "selection": "top", "cost": COST_NOTE,
           "control": None if plan["kind"] == "time" else time_control(plan), "sides": {}}
    for name in plan["sides"]:
        side = SIDE_CODES[name]
        picks = side_picks.get(name)
        if picks is None or picks.empty:
            out["sides"][name] = {"n_picks": 0}
            continue
        res = _side_payoff(xd, plan, side, picks, universe, horizon, split_end)
        if plan["kind"] != "time" and res.get("n_picks"):
            res["control"] = _side_payoff(xd, time_control(plan), side, picks, universe, horizon, split_end)
        out["sides"][name] = res
    return out


def _f(x, pct=False, digits=2) -> str:
    if x is None:
        return "n/a"
    return f"{x * 100:.{digits}f}%" if pct else f"{x:.{digits}f}"


def render_exit(block: dict, horizon: str) -> str:
    """Markdown section appended to results.md for an experiment with an `exit:` block."""
    lines = ["## Exit plan payoff (train-only observation)", "",
             f"Exit plan parameters: {block['plan_label']}. Selection: `{block['selection']}`. "
             f"Entry convention: the pick date's open; R = stop_atr x ATR(14) known before the pick date. "
             f"Outcomes in R multiples and percent, net of the {block['cost']}. "
             "Baseline: the same exit plan applied to every universe stock on the same dates; the headline is "
             "average R above that baseline. Not a gate and not a roster input: SPEC.md has no payoff wording "
             "yet (`state/engine-issues.md`).", ""]
    head = ("| Plan | Side | Picks | Right | Avg R | Median R | Profit factor | Avg % | Avg hold | Stop | Target "
            "| Time | Worst losing run | Baseline avg R | Avg R above baseline | t | 95% interval |")
    lines += [head, "|" + "---|" * 17]
    for name, res in block["sides"].items():
        rows = [("exit plan", res)]
        if res.get("control"):
            rows.append(("time-only control", res["control"]))
        for label, m in rows:
            if not m.get("n_picks"):
                lines.append(f"| {label} | {name} | 0 | | | | | | | | | | | | | | |")
                continue
            iv = m.get("interval")
            iv_text = "n/a" if iv is None else f"{iv[0]:.3f} to {iv[1]:.3f}"
            lines.append(
                f"| {label} | {name} | {m['n_picks']} | {_f(m['share_right'], True, 1)} | {_f(m['avg_r'], digits=3)} "
                f"| {_f(m['median_r'], digits=3)} | {_f(m['profit_factor'])} | {_f(m['avg_pct'], True)} "
                f"| {_f(m['avg_holding_sessions'], digits=1)} | {_f(m['share_stop'], True, 0)} "
                f"| {_f(m['share_target'], True, 0)} | {_f(m['share_time'], True, 0)} | {m['worst_losing_run']} "
                f"| {_f(m['baseline_avg_r'], digits=3)} | {_f(m['avg_r_above_baseline'], digits=3)} "
                f"| {_f(m['t'])} | {iv_text} |")
    lines.append("")
    for name, res in block["sides"].items():
        if not res.get("n_picks"):
            continue
        lines += [f"### {name}: by year (exit plan)", "", "| Year | Picks | Right | Avg R | Avg R above baseline |",
                  "|---|---|---|---|---|"]
        lines += [f"| {y['year']} | {y['n_picks']} | {_f(y['share_right'], True, 1)} | {_f(y['avg_r'], digits=3)} "
                  f"| {_f(y['avg_r_above_baseline'], digits=3)} |" for y in res["by_year"]]
        lines += ["", f"Dropped (window past the split end or no ATR yet): {res['n_dropped']}. "
                      f"Intervals: {res['interval_method']}.", ""]
    return "\n".join(lines)
