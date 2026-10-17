"""Writes `reports/champion_v1_train.md`: B7's acceptance report (`state/queue.md`).

Champion v1 (`strategies/champion_v1.py`, the current StockStalker blended
score) run through the real replay engine on the train split, day and week,
split into bullish (score > 0) and bearish (score < 0) picks - the same
score-sign-as-side convention `engine.selftest` already establishes for the
leak/random self-tests (B6); B8's gates will formalise the same read.
Reported by calendar year, per side and horizon, so a few bad years can't
hide inside one whole-split average: SPEC.md section 6 gate 3 ("positive
edge in at least 70% of calendar years") is checked against exactly this
breakdown. Invoked from `engine.run_queue.main` whenever a dataset with the
needed columns is available, so a push that triggers `replay.yml`
regenerates it from the real cached dataset.

Deliberately leaves out `random_baseline_percentile` (gate 6, "beats at
least 95% of random lists"): it redraws 1,000 random pick lists per side,
and on six years of the real universe (this report's whole point) that
cost multiplies by every side and horizon here. B7's acceptance
(`state/queue.md`) asks for picks/accuracy/edge by year and side, not the
random baseline - gate 6 belongs to the promotion job that checks it once,
on test, not to a report regenerated on every push that touches `engine/`,
`strategies/` or `experiments/pending/`.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from engine.replay import load_splits, run_dates
from engine.scoring import (
    directional_move_after_costs,
    edge,
    hit,
    moves_for_horizon,
    universe_membership,
)
from strategies import champion_v1

TRAIN_START, TRAIN_END = "2015-01-01", "2020-12-31"
REQUIRED_COLUMNS = {
    "date", "symbol", "open", "high", "low", "close", "prevclose", "volume", "turnover", "has_future",
}
HORIZONS = ("day", "week")
SIDES = (1, -1)
SIDE_NAME = {1: "Bullish", -1: "Bearish"}


def _pick_dates_for_horizon(available_dates: list[str], start: str, end: str, horizon: str) -> list[str]:
    """Trading dates in `[start, end]` to generate picks for.

    Mirrors `engine.run_queue.pick_dates_for_horizon` exactly (not imported
    from it: `engine.run_queue` imports this module to wire the report in,
    and `engine.selftest` keeps its own equivalent copy for the same reason -
    importing back from `run_queue` would be circular)."""
    dates = sorted(d for d in available_dates if start <= d <= end)
    if horizon == "day":
        return dates
    if horizon == "week":
        weekly, seen_weeks = [], set()
        for d in dates:
            key = pd.Timestamp(d).isocalendar()[:2]
            if key not in seen_weeks:
                seen_weeks.add(key)
                weekly.append(d)
        return weekly
    raise ValueError(f"unknown horizon {horizon!r}; must be 'day' or 'week'")


def _side_picks(picks: pd.DataFrame, side: int) -> pd.DataFrame:
    """`date, symbol, side` rows for one side, derived from a raw `score` pick
    log (same convention as `engine.selftest._side_picks`)."""
    mask = picks["score"] > 0 if side > 0 else picks["score"] < 0
    out = picks.loc[mask, ["date", "symbol"]].copy()
    out["side"] = side
    return out


def _restrict_to_universe(picks: pd.DataFrame, universe: pd.DataFrame) -> pd.DataFrame:
    in_universe = universe.loc[universe["in_universe"], ["date", "symbol"]]
    return picks.merge(in_universe, on=["date", "symbol"], how="inner")


def _yearly_table(picks: pd.DataFrame, moves: pd.DataFrame, universe: pd.DataFrame) -> list[dict]:
    years = sorted(pd.to_datetime(picks["date"]).dt.year.unique())
    rows = []
    for year in years:
        year_picks = picks[pd.to_datetime(picks["date"]).dt.year == year]
        joined = year_picks.merge(moves, on=["date", "symbol"], how="inner")
        if joined.empty:
            continue
        rows.append(
            {
                "year": int(year),
                "n_picks": int(len(year_picks)),
                "accuracy": float(hit(joined["move"], joined["side"]).mean()),
                "edge": edge(year_picks, moves, universe),
            }
        )
    return rows


def side_results(
    picks: pd.DataFrame, side: int, moves: pd.DataFrame, universe: pd.DataFrame
) -> dict:
    side_picks = _restrict_to_universe(_side_picks(picks, side), universe)
    if side_picks.empty:
        return {"n_picks": 0, "by_year": [], "accuracy": None, "edge": None, "directional_move": None}

    joined = side_picks.merge(moves, on=["date", "symbol"], how="inner")
    return {
        "n_picks": int(len(side_picks)),
        "by_year": _yearly_table(side_picks, moves, universe),
        "accuracy": float(hit(joined["move"], joined["side"]).mean()),
        "edge": edge(side_picks, moves, universe),
        "directional_move": directional_move_after_costs(side_picks, moves),
    }


def horizon_results(
    dataset: pd.DataFrame, horizon: str, start: str = TRAIN_START, end: str = TRAIN_END, split: str = "train"
) -> dict:
    """`split` authorises `start`/`end` with `engine.replay.run_dates` (SPEC.md
    section 4): it must match whichever split `[start, end]` actually falls
    inside, or the engine raises `SplitViolation` - e.g. `engine.holdout_report`
    reuses this same function for the validation split by passing both."""
    splits = load_splits()
    available = sorted(dataset["date"].unique())
    dates = _pick_dates_for_horizon(available, start, end, horizon)
    picks = run_dates(dataset, champion_v1, dates, split, splits)
    moves = moves_for_horizon(dataset, horizon)
    universe = universe_membership(dataset)
    return {side: side_results(picks, side, moves, universe) for side in SIDES}


def _pts(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.2f}"


def _render_side(horizon: str, side: int, result: dict) -> list[str]:
    lines = [f"### {horizon.title()} - {SIDE_NAME[side]}", ""]
    if result["n_picks"] == 0:
        lines += ["No in-universe picks on this side.", ""]
        return lines
    lines += [
        f"Whole split: {result['n_picks']} picks, accuracy {_pts(result['accuracy'])}%, "
        f"edge {_pts(result['edge'])} points, directional move after costs "
        f"{_pts(result['directional_move'])} points.",
        "",
        "| Year | Picks | Accuracy | Edge (points) |",
        "|---|---|---|---|",
    ]
    for row in result["by_year"]:
        lines.append(f"| {row['year']} | {row['n_picks']} | {_pts(row['accuracy'])}% | {_pts(row['edge'])} |")
    lines.append("")
    return lines


def render(results: dict) -> str:
    lines = [
        "# Champion v1 train results (B7, `state/queue.md`)",
        "",
        "`strategies/champion_v1.py` - the current StockStalker blended score "
        "(trend 0.4 / momentum 0.35 / volume 0.25) - run through the real replay "
        f"engine on the train split ({TRAIN_START} to {TRAIN_END}), day and week, "
        "split into bullish (score > 0) and bearish (score < 0) picks. Definitions "
        "per SPEC.md section 3; gates per SPEC.md section 6 are checked on test, "
        "not here - this is the train-split baseline before any validation look.",
        "",
    ]
    for horizon in HORIZONS:
        lines.append(f"## {horizon.title()}")
        lines.append("")
        for side in SIDES:
            lines += _render_side(horizon, side, results[horizon][side])
    return "\n".join(lines)


def write_champion_report(dataset: pd.DataFrame, out_path: Path) -> None:
    results = {horizon: horizon_results(dataset, horizon) for horizon in HORIZONS}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render(results))


def maybe_write_champion_report(dataset: pd.DataFrame, out_path: Path, start: str = TRAIN_START, end: str = TRAIN_END) -> bool:
    """Write the report iff `dataset` carries every column it needs and
    actually covers the train split; otherwise no-op - mirrors
    `engine.reports.maybe_write_market_line_report` / `engine.selftest.maybe_write_selftest_report`
    so `run_queue.main` can call this unconditionally once a dataset is loaded."""
    if not REQUIRED_COLUMNS.issubset(dataset.columns):
        return False
    if not ((dataset["date"] >= start) & (dataset["date"] <= end)).any():
        return False
    write_champion_report(dataset, out_path)
    return True
