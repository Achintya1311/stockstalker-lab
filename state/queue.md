# Build queue (supervised build first; the autonomous loop starts after B8)

Rules for build items (added 16 Oct after the first run):
1. Unresolved entries in `state/workflow_failures.md` come first. Fix the cause, then add `RESOLVED <commit>` under that entry.
2. Never write NSE column names or codes from memory. Use `docs/nse_formats.md`, which is copied from real files.
3. An item that needs the full dataset is ticked only after its GitHub Actions run succeeds. B2 is done when `state/data_manifest.json`, written by `dataset.yml`, has `date_start` on or before 2015-01-02 and `date_end` within 3 trading days of the run date, **and** `trading_days` is at least 2,850 with `max_gap_days` at most 7. A manifest built before the backfill finished can show the right start and end dates while missing whole years in between; this condition catches that.

| # | Item | Done |
|---|------|------|
| B1 | Fetch NSE bhavcopy history 2015 to date: `backfill.yml` in GitHub Actions, zips kept in the Actions cache only (never committed or published) | [x] |
| B2 | Parse old and UDiFF formats into one table: date, symbol, open, high, low, close, prevclose, volume, turnover; plus the daily FUTSTK universe | [x] |
| B3 | Adjustment factors from PREVCLOSE / previous CLOSE; check against known splits and bonuses | [ ] |
| B4 | Replay engine: truncated slices, pick log hashed before outcomes, split authorisation | [x] |
| B5 | Scoring: hits, market line, edge, directional move after costs, random baseline | [x] |
| B6 | Engine self-tests: a leaky strategy must be caught, a random strategy must show no edge | [x] |
| B7 | Champion v1 = current StockStalker blended score; day and week; train, then validation | [x] |
| B8 | Gates, ledger, Thresholdout, budgets, guard check, CI, branch protection, auto-merge | [ ] |
| B9 | Live picks JSON plus GitHub Actions (evening and morning runs); exam backfill | [ ] |
| B10 | Start the 2-hourly lab routine with lanes | [ ] |

## After the build (Mode B, discover and port lanes)

- **D1:** extend the dataset with near-month stock-futures and options open interest from the F&O files already cached. This unlocks catalog rows D01–D02.
- **D2:** add a fetcher for NSE's security-wise delivery file. This unlocks D03.
- Work through `cards/catalog.csv` in the testing order SPEC.md §5 gives.

## Acceptance per item (a tick needs all of it; "the logic is written" is not enough)

- **B3:** once B2 is done, run `detect_corporate_actions` on the full dataset in Actions and write `reports/corporate_actions_check.md`. At least 10 detected events must be checked against an independent public source (NSE corporate announcements or news), with date and ratio matching and the source linked. Every mismatch is explained. Events where the adjusted close jumps more than 30% in one day are listed and explained.
- **B4:** the replay runs on the train split in Actions (`replay.yml` succeeds). A test proves that a strategy only ever sees dates before the pick date. The pick log for each date is hashed before outcomes load. Asking for validation or test dates without authorisation raises an error.
- **B5:** unit tests reproduce a small hand-computed example for hit, market line, edge, directional move after costs and random percentile. An Actions run writes `reports/market_line_train.md`: the share of the universe up open-to-close, by year for 2015–2020, for day and week.
- **B6:** an Actions run writes `reports/selftest.md`. A leaky strategy (same-day close) is flagged, and a random strategy's train edge is within ±1.5 points over 5 seeds.
- **B7:** champion v1 train results for day and week, by year and side, in `reports/champion_v1_train.md`. One validation query goes through the holdout, logged in `ledger/holdout_queries.csv`.
- **B8 and B9:** the routine cannot edit `.github/`. Write the code (`scripts/guard_check.py`, gates, budgets, picks generator) with tests, then add a line "READY FOR WIRING: <item>" to `state/engine-issues.md`. A supervised session adds the workflows and branch protection and ticks the item.
