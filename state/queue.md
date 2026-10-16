# Build queue (supervised build first; the autonomous loop starts after B8)

Rules for build items (added 16 Oct after the first run):
1. Unresolved entries in `state/workflow_failures.md` come first. Fix the cause, then add `RESOLVED <commit>` under that entry.
2. Never write NSE column names or codes from memory. Use `docs/nse_formats.md`, which is copied from real files.
3. An item that needs the full dataset is ticked only after its GitHub Actions run succeeds. B2 is done when `state/data_manifest.json`, written by `dataset.yml`, has `date_start` on or before 2015-01-02 and `date_end` within 3 trading days of the run date, **and** `trading_days` is at least 2,850 with `max_gap_days` at most 7. A manifest built before the backfill finished can show the right start and end dates while missing whole years in between; this condition catches that.

| # | Item | Done |
|---|------|------|
| B1 | Fetch NSE bhavcopy history 2015 to date: `backfill.yml` in GitHub Actions, zips kept in the Actions cache only (never committed or published) | [ ] |
| B2 | Parse old and UDiFF formats into one table: date, symbol, open, high, low, close, prevclose, volume, turnover; plus the daily FUTSTK universe | [ ] |
| B3 | Adjustment factors from PREVCLOSE / previous CLOSE; check against known splits and bonuses | [x] |
| B4 | Replay engine: truncated slices, pick log hashed before outcomes, split authorisation | [ ] |
| B5 | Scoring: hits, market line, edge, directional move after costs, random baseline | [ ] |
| B6 | Engine self-tests: a leaky strategy must be caught, a random strategy must show no edge | [ ] |
| B7 | Champion v1 = current StockStalker blended score; day and week; train, then validation | [ ] |
| B8 | Gates, ledger, Thresholdout, budgets, guard check, CI, branch protection, auto-merge | [ ] |
| B9 | Live picks JSON plus GitHub Actions (evening and morning runs); exam backfill | [ ] |
| B10 | Start the 2-hourly lab routine with lanes | [ ] |
