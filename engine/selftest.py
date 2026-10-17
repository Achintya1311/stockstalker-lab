"""Engine self-tests (B6, `state/queue.md`): writes `reports/selftest.md`.

B4 (`tests/test_replay.py`) already proves `truncate()` never shows a
strategy its own pick date or anything after. B6 is a different claim: that
if a strategy leaked tomorrow's close some *other* way - not through
`history`, but through a reference of its own to the full, untruncated
dataset, which is the realistic way a strategy module could leak in
practice - the leak alarm (SPEC.md section 6: accuracy >= 70% or edge >= 15
points) would actually catch it. Run alongside a strategy with no real
signal (uniform random direction), whose edge must stay within noise of
zero, so the self-test also proves scoring isn't structurally biased to
manufacture edge out of nothing.

Both strategies here are self-test fixtures only: never added to
`cards/catalog.csv`, never a roster candidate.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from engine.replay import load_splits, run_dates
from engine.scoring import day_moves, edge, hit, universe_membership

REQUIRED_COLUMNS = {"date", "symbol", "open", "close", "has_future", "turnover"}

# The first half of 2018: years past the dataset's own first 20 trading
# days (the 20-day trailing turnover window needs that much history before
# `in_universe` can ever be True - see `engine.scoring.universe_membership`),
# so the universe is real and stable throughout, without replaying the whole
# train split. ~125 trading days, not one month: the random check's edge
# only has noise to average down because each trading day is an independent
# draw from that day's own real up/down split (sampling without replacement
# from a finite, already-realised population - unbiased regardless of any
# cross-sectional correlation in that day's actual returns); at a typical
# day's universe size one month is not enough days for that averaging to
# keep the random strategy's edge reliably inside +-1.5 points on real data.
SELFTEST_START, SELFTEST_END = "2018-01-01", "2018-06-30"

RANDOM_SEEDS = (0, 1, 2, 3, 4)
LEAK_ACCURACY_THRESHOLD = 0.70  # SPEC.md section 6, "leak alarm"
LEAK_EDGE_THRESHOLD = 0.15      # SPEC.md section 6, "leak alarm" (15 points)
RANDOM_EDGE_TOLERANCE = 0.015   # B6 acceptance, state/queue.md (+-1.5 points)


class LeakyStrategy:
    """Scores every symbol bullish that will, in fact, close up the next
    trading day - learned from a reference to the *full* dataset held at
    construction time, never from the `history` the engine hands `score()`.
    Abstains on everything else, so every pick it makes is a guaranteed hit:
    exactly the shape of leak the alarm in SPEC.md section 6 exists to catch.
    """

    def __init__(self, full_moves: pd.DataFrame):
        self._moves = full_moves.set_index(["date", "symbol"])["move"]
        dates = sorted(full_moves["date"].unique())
        self._next_date = {d: dates[i + 1] for i, d in enumerate(dates[:-1])}

    def score(self, history: pd.DataFrame) -> pd.Series:
        if history.empty:
            return pd.Series(dtype=float)
        today = self._next_date.get(history["date"].max())
        if today is None:
            return pd.Series(dtype=float)
        symbols = pd.Index(history["symbol"].unique())
        try:
            today_moves = self._moves.xs(today, level="date")
        except KeyError:
            return pd.Series(dtype=float)
        up = today_moves.reindex(symbols).dropna()
        up = up[up > 0]
        return pd.Series(1.0, index=up.index)

    def rules_fired(self, history: pd.DataFrame, symbol: str) -> str:
        return "self-test only: reads the next trading day's already-realised close"


class RandomStrategy:
    """Uniform random +1/-1 per symbol per date. No signal, by construction."""

    def __init__(self, seed: int):
        self._rng = np.random.default_rng(seed)

    def score(self, history: pd.DataFrame) -> pd.Series:
        symbols = history["symbol"].unique() if not history.empty else np.array([])
        if len(symbols) == 0:
            return pd.Series(dtype=float)
        signs = self._rng.choice([1.0, -1.0], size=len(symbols))
        return pd.Series(signs, index=symbols)

    def rules_fired(self, history: pd.DataFrame, symbol: str) -> str:
        return "self-test only: uniform random direction"


def _pick_dates(dataset: pd.DataFrame, start: str, end: str) -> list[str]:
    return sorted(d for d in dataset["date"].unique() if start <= d <= end)


def _restrict_to_universe(picks: pd.DataFrame, universe: pd.DataFrame) -> pd.DataFrame:
    """Drop picks on a symbol/date outside the universe (SPEC.md section 2).

    Keeps both checks' picks comparable to `market_line`, which is itself
    computed over the universe only - otherwise an illiquid or no-future
    symbol the strategy was merely shown (but that a real roster evaluation
    would never count) could skew a check that has nothing to do with it.
    """
    in_universe = universe.loc[universe["in_universe"], ["date", "symbol"]]
    return picks.merge(in_universe, on=["date", "symbol"], how="inner")


def _side_picks(picks: pd.DataFrame, side: int) -> pd.DataFrame:
    """`date, symbol, side` rows for one side, derived from a raw `score` pick log."""
    mask = picks["score"] > 0 if side > 0 else picks["score"] < 0
    out = picks.loc[mask, ["date", "symbol"]].copy()
    out["side"] = side
    return out


def _is_leak_flagged(accuracy: float, strategy_edge: float) -> bool:
    return accuracy >= LEAK_ACCURACY_THRESHOLD or strategy_edge >= LEAK_EDGE_THRESHOLD


def check_leak(
    dataset: pd.DataFrame, moves: pd.DataFrame, universe: pd.DataFrame, splits: dict, start: str, end: str
) -> dict:
    strategy = LeakyStrategy(moves)
    dates = _pick_dates(dataset, start, end)
    picks = run_dates(dataset, strategy, dates, "train", splits)
    bull = _restrict_to_universe(_side_picks(picks, 1), universe)
    if bull.empty:
        raise ValueError("leaky strategy produced no in-universe picks in the self-test window")
    joined = bull.merge(moves, on=["date", "symbol"], how="inner")
    accuracy = float(hit(joined["move"], 1).mean())
    strategy_edge = edge(bull, moves, universe)
    return {
        "n_picks": int(len(bull)),
        "accuracy": accuracy,
        "edge": strategy_edge,
        "flagged": _is_leak_flagged(accuracy, strategy_edge),
    }


def check_random(
    dataset: pd.DataFrame,
    moves: pd.DataFrame,
    universe: pd.DataFrame,
    splits: dict,
    start: str,
    end: str,
    seeds=RANDOM_SEEDS,
) -> list[dict]:
    dates = _pick_dates(dataset, start, end)
    results = []
    for seed in seeds:
        strategy = RandomStrategy(seed)
        picks = run_dates(dataset, strategy, dates, "train", splits)
        bull = _restrict_to_universe(_side_picks(picks, 1), universe)
        bear = _restrict_to_universe(_side_picks(picks, -1), universe)
        if bull.empty or bear.empty:
            raise ValueError(f"random strategy (seed={seed}) produced no in-universe picks on one side")
        bull_edge = edge(bull, moves, universe)
        bear_edge = edge(bear, moves, universe)
        results.append({
            "seed": seed,
            "bull_edge": bull_edge,
            "bear_edge": bear_edge,
            "within_tolerance": abs(bull_edge) <= RANDOM_EDGE_TOLERANCE and abs(bear_edge) <= RANDOM_EDGE_TOLERANCE,
        })
    return results


def selftest_passed(leak_result: dict, random_results: list[dict]) -> bool:
    return bool(leak_result["flagged"]) and all(r["within_tolerance"] for r in random_results)


def _pts(x: float) -> str:
    return f"{x * 100:.2f}"


def render(leak_result: dict, random_results: list[dict], start: str, end: str) -> str:
    leak_pass = bool(leak_result["flagged"])
    random_pass = all(r["within_tolerance"] for r in random_results)
    lines = [
        "# Engine self-test (B6, `state/queue.md`)",
        "",
        f"Train-split window {start} to {end} - far enough past the dataset's own",
        "first 20 trading days for the 20-day turnover window to have a real",
        "universe throughout, without replaying the whole split. Thresholds per",
        "SPEC.md section 6 (leak alarm) and this item's acceptance (`state/queue.md`).",
        "",
        "## Leak check",
        "",
        "A strategy that reads the next trading day's already-realised close - not",
        "through `history` (`truncate()` already proves that path withholds it; see",
        "`tests/test_replay.py`), but through its own reference to the full dataset,",
        "the realistic way a strategy module could leak - must trip the leak alarm",
        f"(accuracy >= {_pts(LEAK_ACCURACY_THRESHOLD)}% or edge >= {_pts(LEAK_EDGE_THRESHOLD)} points).",
        "",
        "| Picks | Accuracy | Edge (points) | Flagged |",
        "|---|---|---|---|",
        f"| {leak_result['n_picks']} | {_pts(leak_result['accuracy'])}% | {_pts(leak_result['edge'])} | "
        f"{'YES' if leak_result['flagged'] else 'NO'} |",
        "",
        f"Result: **{'PASS' if leak_pass else 'FAIL'}** - "
        + (
            "the leak alarm catches it."
            if leak_pass
            else "not caught; the leak alarm thresholds or this check need attention before the gates ship."
        ),
        "",
        "## Random check",
        "",
        "A strategy with no real signal - uniform random direction, independent of",
        f"the actual move - run over {len(random_results)} seeds; its edge on each side",
        f"must stay within +-{_pts(RANDOM_EDGE_TOLERANCE)} points of zero.",
        "",
        "| Seed | Bull edge | Bear edge | Within tolerance |",
        "|---|---|---|---|",
    ]
    for r in random_results:
        lines.append(
            f"| {r['seed']} | {_pts(r['bull_edge'])} | {_pts(r['bear_edge'])} | "
            f"{'YES' if r['within_tolerance'] else 'NO'} |"
        )
    lines += [
        "",
        f"Result: **{'PASS' if random_pass else 'FAIL'}**",
        "",
    ]
    return "\n".join(lines)


def write_selftest_report(
    dataset: pd.DataFrame, out_path: Path, start: str = SELFTEST_START, end: str = SELFTEST_END
) -> None:
    moves = day_moves(dataset)
    universe = universe_membership(dataset)
    splits = load_splits()
    leak_result = check_leak(dataset, moves, universe, splits, start, end)
    random_results = check_random(dataset, moves, universe, splits, start, end)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render(leak_result, random_results, start, end))


def maybe_write_selftest_report(
    dataset: pd.DataFrame, out_path: Path, start: str = SELFTEST_START, end: str = SELFTEST_END
) -> bool:
    """Write the report iff `dataset` has every column it needs and actually
    covers the self-test window; otherwise no-op.

    Mirrors `engine.reports.maybe_write_market_line_report` so `run_queue.main`
    can call this unconditionally once a dataset is loaded, including under
    tests that pass a minimal synthetic dataset missing these columns or
    spanning only a handful of dates outside this fixed window - neither
    should take down the rest of the queue run.
    """
    if not REQUIRED_COLUMNS.issubset(dataset.columns):
        return False
    if not ((dataset["date"] >= start) & (dataset["date"] <= end)).any():
        return False
    write_selftest_report(dataset, out_path, start, end)
    return True
