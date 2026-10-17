"""Replay engine: truncated slices, split authorisation, hashed pick logs.

Per SPEC.md section 4:

"It steps through dates. A strategy receives only data up to the previous
close (Friday's close for week picks), as a truncated slice. Picks are
appended to a log and hashed before outcomes are loaded. Any strategy
parameter that is learned is re-learned walk-forward, from past data only.
The engine refuses dates outside the split a job is authorised for."

A strategy is anything exposing `score(history: pd.DataFrame) -> pd.Series`
(SPEC.md section 5): one score per symbol, NaN meaning abstain. This module
only produces picks; scoring picks against outcomes (hits, market line,
edge, directional move, random baseline) is a separate concern (B5).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import yaml

SPLITS_PATH = Path(__file__).resolve().parent.parent / "config" / "splits.yml"


class SplitViolation(ValueError):
    """A date fell outside the split a run is authorised for."""


def load_splits(path: Path = SPLITS_PATH) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def authorize(date: str, split: str, splits: dict | None = None) -> None:
    """Raise SplitViolation unless `date` falls inside `split`'s bounds.

    `splits` defaults to the fixed, protected `config/splits.yml`; tests pass
    a literal dict instead of exercising the real file. Bounds load as
    `datetime.date` (or the literal string "go-live" for the open-ended exam
    split); both compare fine against an ISO `YYYY-MM-DD` string once
    stringified, since `str(date.date)` is also `YYYY-MM-DD`.
    """
    splits = load_splits() if splits is None else splits
    if split not in splits:
        raise SplitViolation(f"unknown split {split!r}; must be one of {sorted(splits)}")
    bounds = splits[split]
    start, end = str(bounds["start"]), bounds.get("end")
    date = str(date)
    if date < start:
        raise SplitViolation(f"{date} is before split {split!r} starts ({start})")
    if end not in (None, "go-live") and date > str(end):
        raise SplitViolation(f"{date} is after split {split!r} ends ({end})")


def truncate(history: pd.DataFrame, as_of: str) -> pd.DataFrame:
    """Rows strictly before `as_of`: all a strategy picking on `as_of` may see.

    Withholding `as_of`'s own row covers both horizons uniformly: for a day
    pick the strategy must not see today's own open/high/low/close, and for
    a week pick (made at Monday's open) the row immediately before Monday in
    the trading calendar already *is* the previous Friday's close, so no
    separate week-only truncation is needed.
    """
    return history[history["date"] < as_of].reset_index(drop=True)


def hash_picks(picks: pd.DataFrame) -> str:
    """SHA-256 of the pick log, in a row/column-order-independent canonical form.

    Call this immediately after a strategy produces its picks and before any
    outcome (close price, hit/miss) is joined in, so the hash is proof the
    picks were fixed before the result of the bet was known.
    """
    sort_cols = [c for c in ("date", "symbol") if c in picks.columns]
    canonical = picks.sort_values(sort_cols) if sort_cols else picks
    canonical = canonical.reindex(sorted(canonical.columns), axis=1).reset_index(drop=True)
    # A score column round-tripped through JSON (committed pick logs are
    # JSON, not parquet - see run_queue.py) can come back int64 instead of
    # float64 when every value happens to be a whole number; without this,
    # a verifier re-hashing the committed file would get a different digest
    # than the one actually computed pre-serialisation, for data that is
    # otherwise identical.
    for col in canonical.columns:
        if pd.api.types.is_numeric_dtype(canonical[col]):
            canonical[col] = canonical[col].astype("float64")
    payload = canonical.to_csv(index=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_pick_log(path) -> pd.DataFrame:
    """Read a committed `picks.json` back with the dtypes `hash_picks` expects.

    Plain `pd.read_json` infers types from the JSON itself: a `date` column
    of ISO strings becomes `datetime64` (changing how `to_csv` renders it)
    and a `score` column that happens to be all whole numbers becomes
    `int64`. Both silently change `hash_picks`' output on an otherwise
    unchanged pick log. This restores `date` to plain ISO strings so the
    digest a verifier recomputes matches the one in the pick log's own
    `manifest.json` (the numeric-dtype side of this is already handled
    inside `hash_picks` itself).
    """
    df = pd.read_json(path, convert_dates=False)
    if "date" in df.columns:
        df["date"] = df["date"].astype(str)
    return df


def pick_date(history: pd.DataFrame, strategy, date: str, split: str, splits: dict | None = None) -> pd.DataFrame:
    """One date's picks from `strategy`, after checking authorisation and truncating.

    Returns a `date, symbol, score` frame, one row per non-abstaining symbol.
    """
    authorize(date, split, splits)
    visible = truncate(history, date)
    scores = strategy.score(visible).dropna()
    return pd.DataFrame({"date": date, "symbol": scores.index, "score": scores.to_numpy()})


def run_dates(history: pd.DataFrame, strategy, dates, split: str, splits: dict | None = None) -> pd.DataFrame:
    """Picks for every date in `dates`, concatenated into one pick log.

    Every date is authorised and truncated independently via `pick_date`;
    a single unauthorised date raises and no picks are returned for any of
    them, so a bad queue entry can never partially leak into the log.
    """
    frames = [pick_date(history, strategy, d, split, splits) for d in dates]
    if not frames:
        return pd.DataFrame(columns=["date", "symbol", "score"])
    return pd.concat(frames, ignore_index=True)
