# Journal

One entry per run: date, lane, hypothesis, result, next.

## 2026-10-16T18:16Z — build lane

Hypothesis: B2 (parse old CM/FO CSV and UDiFF bhavcopy formats into one table)
can be written and fully unit-tested against synthetic fixtures in the exact
NSE column layouts, without waiting on the real backfill.

What I did: a manual `backfill.yml` dispatch was already queued when this run
started (run 38944581180, triggered by Achintya1311) but had not concluded, so
per SPEC I moved on to B2 rather than blocking on it. Wrote
`scripts/build_dataset.py`: detects old-era (`TOTTRDQTY` / `INSTRUMENT`) vs
UDiFF (`FinInstrmTp`) bhavcopy by column names (not filename/date, since both
eras can land in the same raw tree during the transition), keeps only EQ
series for the equity table, keeps only FUTSTK/STF rows to flag `has_future`
per (date, symbol), and merges incrementally with any existing
`data/dataset.parquet` (new rows overwrite old ones for the same key, so the
daily `dataset.yml` update doesn't need to re-parse the full history). Writes
`state/data_manifest.json` with row/symbol counts, date range and a sha256 of
the parquet.

Result: 8 new unit tests in `tests/test_build_dataset.py` (old CM, old FO,
UDiFF CM, UDiFF FO parsing; cross-era merge with `has_future`; directory-shape
independence; incremental merge semantics; bad-schema rejection), all green.
Also ran the CLI end-to-end against a synthetic raw tree to check the
`dataset.yml` invocation shape (`--raw --out --manifest`) produces a real
parquet + manifest. `requirements.txt` added (pandas, pyarrow, numpy, pytest)
so `ci.yml` and `dataset.yml` can install dependencies; `conftest.py` added so
`tests/` can import `scripts/`.

Next: check whether the queued backfill run (started 18:04:56Z, 12-year
matrix, 240 min timeout) has concluded; if `success`, tick B1 and claim the
`build` lane for B3 (adjustment factors from PREVCLOSE / prior CLOSE, checked
against known splits/bonuses). If it failed, log why in
`state/engine-issues.md` first. If it's still running, the next run can start
B3/B4/B5 on synthetic data the same way B2 was done here, or re-dispatch
backfill for any years that failed.

## 2026-10-16T18:37Z — build lane

Hypothesis: B3 (adjustment factors from PREVCLOSE / previous CLOSE, checked
against known splits and bonuses) does not need the full backfill either —
like B2, its logic can be written and unit-tested against synthetic
corporate-action fixtures, independent of whether the real dataset is ready.

What I did: checked the queued backfill run (38944581180, dispatched
18:04:56Z) — still `in_progress`, 9 of 12 year-matrix jobs green, 3 running
(2024/2025/2026). Not concluded, so B1 stays unticked and B2 stays gated on
its manifest condition (current manifest: `trading_days: 1490`,
`max_gap_days: 2105` — nowhere near the `>=2850`/`<=7` bar, confirming the
queue note that a manifest from a partial backfill looks plausible but hides
missing years). Moved to B3 instead of waiting idle.

Wrote `scripts/adjustments.py`: `compute_adjustment_factors(df)` turns the
SPEC's rule (adjustment factor = PREVCLOSE(t) / CLOSE(t-1), snapped to 1.0
within 0.5% to absorb ordinary rounding noise) into a per-symbol, per-date
*cumulative* factor, computed as a reverse cumulative product so that
`adj_price(d) = raw_price(d) * cum_factor(d)` and the most recent date for
each symbol is always unadjusted (factor 1.0) relative to itself. Open,
high, low and close are all scaled by the same factor; volume and turnover
are left alone (SPEC only calls for price-series adjustment). Added
`detect_corporate_actions(df)`, the companion that lists every (date,
symbol, ratio) where a non-noise ratio was found — the mechanism for
"check against known splits and bonuses": it surfaces candidates now, and
cross-checking them against a real, independently sourced list of NSE
corporate actions (not against memory — nothing here is assumed true until
tested, per SPEC section 5) is a job for once the full dataset lands.

Result: 10 new unit tests in `tests/test_adjustments.py` — rounding-noise
snapping, a bare 2:1 split (verified the adjusted series removes the ~50%
jump across the split date and stays continuous), a 1:1 bonus compounding
with a later split, multi-symbol independence, first-row handling (no prior
day, so no action is knowable), OHLC all scaled consistently, and the
detector finding exactly the one synthetic event and nothing else. All 18
tests in the suite green (`python3.11 -m pytest -q`). Ticked B3 — its
acceptance (write + test the adjustment logic) has no explicit
full-dataset gate in `queue.md`, unlike B2.

Next: check the backfill run again; once it concludes `success`, re-run
`dataset.yml` (or let its weekday schedule do it) and verify the manifest
clears the `trading_days>=2850`/`max_gap_days<=7` bar to tick B1 and B2.
Until then, the next run can start B4 (replay engine: truncated slices,
hashed pick log, split authorisation) against synthetic fixtures the same
way, or run `detect_corporate_actions` against whatever partial real data
exists once a `dataset.parquet` is available, as a sanity spot-check ahead
of the full cross-reference.
