# Build queue (supervised build first; the autonomous loop starts after B8)

| # | Item | Done |
|---|------|------|
| B1 | Fetch NSE bhavcopy history 2015 to date (`scripts/fetch_bhavcopy.py`) | [ ] |
| B2 | Parse old and UDiFF formats into one table: date, symbol, open, high, low, close, prevclose, volume, turnover; plus the daily FUTSTK universe | [ ] |
| B3 | Adjustment factors from PREVCLOSE / previous CLOSE; check against known splits and bonuses | [ ] |
| B4 | Replay engine: truncated slices, pick log hashed before outcomes, split authorisation | [ ] |
| B5 | Scoring: hits, market line, edge, directional move after costs, random baseline | [ ] |
| B6 | Engine self-tests: a leaky strategy must be caught, a random strategy must show no edge | [ ] |
| B7 | Champion v1 = current StockStalker blended score; day and week; train, then validation | [ ] |
| B8 | Gates, ledger, Thresholdout, budgets, guard check, CI, branch protection, auto-merge | [ ] |
| B9 | Live picks JSON plus GitHub Actions (evening and morning runs); exam backfill | [ ] |
| B10 | Start the 2-hourly lab routine with lanes | [ ] |
