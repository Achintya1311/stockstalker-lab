"""Writes `reports/market_line_train.md`: B5's acceptance report (`state/queue.md`).

Share of the universe that moved up or down, open to close (day) or Monday's
open to Friday's close (week), by calendar year, on the train split only
(SPEC.md section 4). Invoked from `engine.run_queue.main` whenever a dataset
with the needed columns is available, so a push that triggers `replay.yml`
regenerates it from the real cached dataset.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from engine.scoring import moves_for_horizon, universe_membership

TRAIN_START, TRAIN_END = "2015-01-01", "2020-12-31"
REQUIRED_COLUMNS = {"date", "symbol", "open", "close", "has_future", "turnover"}


def yearly_market_line(dataset: pd.DataFrame, horizon: str) -> pd.DataFrame:
    """One row per calendar year in the train split: observation count, share up, share down."""
    universe = universe_membership(dataset)
    moves = moves_for_horizon(dataset, horizon)
    moves = moves[(moves["date"] >= TRAIN_START) & (moves["date"] <= TRAIN_END)]

    in_universe = universe.loc[universe["in_universe"], ["date", "symbol"]]
    merged = moves.merge(in_universe, on=["date", "symbol"], how="inner")
    merged["year"] = pd.to_datetime(merged["date"]).dt.year
    merged["up"] = merged["move"] > 0
    merged["down"] = merged["move"] < 0

    by_year = merged.groupby("year").agg(
        n_obs=("move", "size"),
        share_up=("up", "mean"),
        share_down=("down", "mean"),
    )
    return by_year.reset_index()


def _render_table(table: pd.DataFrame) -> list[str]:
    lines = ["| Year | Observations | Share up | Share down |", "|---|---|---|---|"]
    for _, row in table.iterrows():
        lines.append(
            f"| {int(row['year'])} | {int(row['n_obs'])} | {row['share_up']:.4f} | {row['share_down']:.4f} |"
        )
    return lines


def render(day_table: pd.DataFrame, week_table: pd.DataFrame) -> str:
    lines = [
        "# Market line, train split (2015-2020)",
        "",
        "Share of the universe (active FUTSTK, 20-day median turnover >= Rs 25cr,",
        "`config/universe.yml`) that moved up or down, open to close (day) or",
        "Monday's open to Friday's close (week). B5 acceptance (`state/queue.md`);",
        "definitions per SPEC.md section 3.",
        "",
        "## Day",
        "",
        *_render_table(day_table),
        "",
        "## Week",
        "",
        *_render_table(week_table),
        "",
    ]
    return "\n".join(lines)


def write_market_line_report(dataset: pd.DataFrame, out_path: Path) -> None:
    day_table = yearly_market_line(dataset, "day")
    week_table = yearly_market_line(dataset, "week")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render(day_table, week_table))


def maybe_write_market_line_report(dataset: pd.DataFrame, out_path: Path) -> bool:
    """Write the report iff `dataset` carries every column it needs; otherwise no-op.

    Lets `engine.run_queue.main` call this unconditionally once a dataset is
    loaded, including under tests that pass a minimal synthetic dataset with
    only the columns their own experiment needs.
    """
    if not REQUIRED_COLUMNS.issubset(dataset.columns):
        return False
    write_market_line_report(dataset, out_path)
    return True
