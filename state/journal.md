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
