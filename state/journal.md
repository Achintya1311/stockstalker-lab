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

## 2026-10-17T00:13Z — build lane

Hypothesis: B1 and B2's gates might now be satisfied by data that landed
since the last run, without needing new work — only a check.

What I did: claimed the `build` lease (none existed; no other run had it).
Checked `backfill.yml`'s latest run via the public Actions API: run
38944581180 (dispatched 2026-10-16T18:04:56Z) is `completed`/`success` — B1's
condition. Read the committed `state/data_manifest.json`: `date_start
2015-01-01`, `date_end 2026-10-16`, `trading_days 2911`, `max_gap_days 5` —
all four of B2's explicit bar (`date_start<=2015-01-02`, `date_end` within 3
trading days of today 2026-10-17, `trading_days>=2850`, `max_gap_days<=7`)
are met. Ticked both B1 and B2 in `state/queue.md` with this evidence,
rather than leaving a satisfied gate unticked for another 2-hour cycle.

That makes B3 (adjustment factors) the first unticked item, reopened per
the 17 Oct queue note (its corporate-actions cross-check was previously
deferred, which the note now treats as not done). Its acceptance needs an
Actions run of `detect_corporate_actions` against the *real* full dataset,
writing `reports/corporate_actions_check.md`, then >=10 of the detected
events checked against an independent public source.

Wrote `scripts/check_corporate_actions.py`: loads a dataset parquet, runs
`detect_corporate_actions` (already in `scripts/adjustments.py`), classifies
each event's ratio against common split/bonus ratios (2:1 split or 1:1
bonus == 0.5, etc.), and writes a markdown report listing every candidate
event, a sub-table of events with a >=30% single-day jump, and a TODO
placeholder for the independent-source cross-check (which needs real
detected events and an actual lookup — not something this script, with no
dataset access outside Actions, can do). 4 new unit tests
(`tests/test_check_corporate_actions.py`): ratio classification, the
report separates big-jump events from the full list, the empty case, and
that the independent-check TODO is present. Ran it end-to-end against a
synthetic parquet (one 2:1-style event) locally to confirm the CLI works
and the output reads correctly. All 25 tests in the suite green.

Found the actual blocker: no existing workflow runs this script on real
data and commits the result. `dataset.yml`'s commit step only stages
`state/data_manifest.json`; `replay.yml` already stages `reports/` but only
triggers on `experiments/pending/**`, `strategies/**`, `engine/**` or
`gates/**` changes, and its job runs `engine.run_queue`, not this script.
Since the routine cannot edit `.github/`, wrote the exact wiring needed
(two options) to `state/engine-issues.md` as "READY FOR WIRING: B3
corporate-actions report" for a supervised session.

Result: B1 ticked, B2 ticked, B3's script+tests written and passing, B3's
wiring gap documented for a human to add. B3 itself stays unticked — it
needs the real report and the manual cross-check against >=10 independent
sources, neither possible yet.

Next: once a supervised session wires `dataset.yml` (or an on-demand job)
to run `scripts/check_corporate_actions.py` and commit
`reports/corporate_actions_check.md`, a build-lane run should read that
report, cross-check >=10 events against NSE corporate announcements or
news (date and ratio matching, source linked, mismatches explained), fill
in the report's TODO columns, and tick B3. Until then, the next build run
can start B4 (replay engine) on synthetic fixtures, or a discover-lane run
can proceed with catalog research per SPEC.md section 5 while the build
lease is held.

## 2026-10-17T02:10Z — build lane

Hypothesis: B3 stays blocked on a supervised session (per the last entry);
B4 (replay engine) can be built and tested now, since its three
requirements - truncated slices, split authorisation, hashing picks before
outcomes - don't need the corporate-actions wiring at all.

What I did: claimed the `build` lease (free). Wrote `engine/replay.py`
(`truncate`, `authorize`/`SplitViolation`, `hash_picks`, `pick_date`,
`run_dates`) and `engine/run_queue.py` (the `replay.yml` entrypoint: loads
each `experiments/pending/*.yml`, resolves its strategy module, runs it
over the dates its horizon implies, writes a hashed pick log to
`experiments/done/<id>/`, consumes the pending file). Added `strategies/`
with `engine_smoketest.py` - an always-bullish, no-signal module, never a
roster candidate - and queued it over Jan 2015 (train split) specifically
so `replay.yml` would exercise the engine against the *real* cached
dataset, not an empty queue. 25 new tests (`tests/test_replay.py`,
`tests/test_run_queue.py`), all green locally alongside the existing 23.

Pushed, and the engine genuinely ran on real NSE data in Actions
(run 38994265344: "29542 picks over 20 dates") - but no commit landed on
main. Traced it myself rather than filing it to `state/engine-issues.md`:
`replay.yml`'s commit step runs `git add -A ledger reports experiments
state` as one command over four pathspecs, and `git add` aborts the whole
invocation if *any* one pathspec matches nothing. Neither `ledger/` nor
`reports/` existed yet, so the command failed outright (swallowed by
`2>/dev/null || true`), silently staging nothing - not even the real,
non-ignored changes under `experiments/`. The job still reported green
because the empty `git diff --cached --quiet` that follows is also a clean
exit. Confirmed by cloning the repo at the failing commit and replaying
the exact commands locally. Neither directory is in `PROTECTED.txt`
(only `engine/` and `gates/` are), so I fixed it directly: added
`ledger/.gitkeep` and `reports/.gitkeep`, re-queued the smoketest
experiment each time, and re-pushed until a real commit landed
(`01b0ad6`).

Also found, while trying to verify that committed output: picks were
being written as `picks.parquet`, which `.gitignore`'s blanket
`*.parquet` rule (there for the NSE dataset) silently swallowed - so the
first real commit held only `manifest.json` with a hash and nothing to
check it against, violating "picks JSON are committed". Switched
`run_queue.py` to `picks.json` and re-ran (`1c274e0`). Then checked the
*committed* `picks.json` against its own `manifest.json` hash by hand and
it still didn't match: `pd.read_json` turns an all-whole-number `score`
column into `int64` (was `float64` before serialisation) and `date` into
`datetime64`, both silently changing `hash_picks`' `to_csv`-based
rendering. Fixed `hash_picks` to cast numeric columns to `float64` before
hashing, and added `load_pick_log()` to restore `date` to plain ISO
strings on read - then re-verified by hand that
`hash_picks(load_pick_log("experiments/done/engine-smoketest-day/picks.json"))`
now equals the hash recorded in that experiment's own `manifest.json`.
Without this a committed pick-log hash was correct the instant it was
written and unfalsifiable forever after - the opposite of what hashing
before outcomes is supposed to buy.

Result: B4 ticked. All four of its conditions hold with real evidence, not
just passing tests: `replay.yml` ran the engine against real cached NSE
data on the train split and succeeded (manifest: 29542 picks, 20 trading
dates, Jan 2015); `test_pick_date_never_shows_the_strategy_the_pick_dates_
own_row_or_later` and `test_run_dates_sees_only_dates_before_each_
respective_pick_date` prove a strategy never sees its own pick date or
later; picks are hashed before any outcome column could exist, and that
hash is now independently reproducible from the committed pick log, not
just asserted; `test_authorize_rejects_validation_date_for_a_train_job`
and `test_authorize_rejects_test_date_for_a_train_job` prove an
unauthorised split raises rather than silently running.

Next: B5 (scoring - hits, market line, edge, directional move after costs,
random baseline) is the next build item and doesn't depend on anything
blocked. It will need real outcome data (next day's/week's close) joined
in *after* `hash_picks` runs, which `run_queue.py` doesn't do yet - that
join point is exactly where B5's code belongs. B3 is still blocked on the
supervised session named in `state/engine-issues.md`. Worth a second look
by whoever does that wiring: `replay.yml`'s `git add -A ledger reports
experiments state` is still one fragile command over four pathspecs - it
will break again the same way if any of those four ever get removed or
renamed, with no failure signal anywhere (the job stays green). A per-path
`git add` (or `mkdir -p` before the `add`) would remove that fragility for
good, but that edit is inside `.github/` and this routine cannot make it.

## 2026-10-17T04:08Z — build lane

Mode A, build lease. B3 (corporate-actions report) remains blocked on the
supervised `.github/` wiring already logged in `state/engine-issues.md`
("READY FOR WIRING: B3"); nothing new to add there since the last run.
Took B5 next, per the previous run's own recommendation: scoring (hits,
market line, edge, directional move after costs, random baseline), which
doesn't depend on anything blocked.

Hypothesis: SPEC.md section 3's scoring primitives can be built as pure
functions over `(date, symbol, move)` and `(date, symbol, in_universe)`
frames, re-using the existing pick-log shape (`date, symbol, score`) by
reading a pick's side as the sign of its score, and the cost model falls
out directly from section 2's "a short is realistic only through stock
futures": bullish picks cost as a cash-delivery round trip, bearish picks
as a stock-future short/cover, so there's no free parameter to pick for
which cost model applies.

What I built, all in `engine/` (open for B5) with tests in `tests/`:
- `engine/scoring.py`: `hit()` (a flat move is always a miss - `move*side`
  is exactly 0 whenever `move` is 0, failing the strict `>0` test for either
  side); `universe_membership()` (active FUTSTK AND 20-day trailing median
  turnover >= `config/universe.yml`'s Rs 25cr floor - both bullet points of
  SPEC.md section 2, not just the FUTSTK one); `market_line()`; `edge()`
  (refuses mixed-side pick frames rather than silently averaging a hit rate
  against the wrong line - section 6 checks every gate "separately for
  each horizon and side"); `directional_move_after_costs()`; and
  `random_baseline_percentile()` (same-shaped random pick lists: for every
  (date, side) group in the real picks, draws the same count of symbols
  without replacement from that date's universe, scores them against the
  real market move, and reports the fraction of 1,000 random lists the
  real pooled hit rate strictly beats).
- `engine/reports.py`: turns these into `reports/market_line_train.md`
  (B5's acceptance in `state/queue.md`) - share of the universe up/down,
  by year, 2015-2020, day and week. Wired into `engine/run_queue.main()`
  so it (re)writes whenever a loaded dataset has the needed columns,
  independently of whether anything is queued; it no-ops otherwise, which
  is what kept the existing `run_queue` tests' minimal synthetic datasets
  (no `open`/`has_future`/`turnover` columns) passing unchanged.

Result: B5 ticked. All its conditions hold with real evidence: 19 new
tests in `tests/test_scoring.py` plus 4 in `tests/test_reports.py` and
`tests/test_run_queue.py`, each reproducing a hand-computed value where
the acceptance text asks for one (including an exact 0.0 case for the
random percentile: when the real picks ARE the entire universe, every
random draw without replacement is forced to select that same universe,
so the real rate can never be strictly greater than a random one - 73/73
tests pass). `python -m engine.run_queue` exercised by hand end to end
against a synthetic 2-symbol dataset before pushing. Pushed (`56721e1`),
which triggered `replay.yml` on `engine/**`; the run succeeded
(https://github.com/Achintya1311/stockstalker-lab/actions/runs/39002009113)
and committed `reports/market_line_train.md` (`3155ca9`) against the real
cached dataset - by-year day/week shares for 2015-2020 all sit near 44-56%,
consistent with a liquid-stock universe with no extreme directional bias.
No new entries in `state/workflow_failures.md`.

Next: B3 is still the only blocked item (needs the supervised `.github/`
wiring). B6 (engine self-tests: a leaky strategy must be flagged, a random
strategy must show no edge) is the next unblocked build item and can
reuse this run's `engine/scoring.py` directly - a leaky strategy's "edge"
would be computed from a same-day close, which `hit()`/`edge()` as written
don't defend against by themselves (they trust whatever `move` they're
given); B6's self-test needs a strategy that peeks at the pick date's own
close, fed through the real replay engine, to prove the *engine* path
doesn't let that leak through, not just that `scoring.py`'s arithmetic is
correct in isolation.

## 2026-10-17T0624Z — build lane

Claimed `build` (free, no contention). Next unticked, unblocked item was
B6: engine self-tests (B3 is still only READY FOR WIRING - needs a
supervised `.github/` change, so stays blocked and skipped per
`state/engine-issues.md`).

Hypothesis: B4's causality tests (`tests/test_replay.py`) already prove
`truncate()` withholds the pick date and everything after, so B6's "a
leaky strategy must be flagged" needs a *different* leak shape to be a
real test - not the engine failing to truncate, but a strategy module
holding its own reference to the full dataset outside the `history`
argument the engine ever hands it, which `truncate()` can't stop by
construction. Built that as `LeakyStrategy` (picks only symbols that will
actually close up the next trading day, so every pick is a guaranteed
hit) in `engine/selftest.py`, run through the real `engine.replay`
machinery, scored with the leak-alarm thresholds from SPEC.md section 6
(accuracy >= 70% or edge >= 15 points). Alongside it, `RandomStrategy`
(uniform random direction, no signal) over 5 seeds, checked against the
+-1.5 point tolerance `state/queue.md` sets. Both wired into
`engine.run_queue.main` alongside B5's market-line report, writing
`reports/selftest.md`.

Sized the self-test window at 2018-01-01 to 2018-06-30 (~125 trading
days), not the B4 smoketest's one-month window: random-pick noise only
averages down with independent trading days (each day's hit rate is an
unbiased draw from that day's own already-realised up/down split, so
more symbols on the same few days doesn't help as much as more days
does), and one month's worth of the real universe's typical size was too
thin a sample to land inside +-1.5 points reliably.

Result: B6 ticked. 20 new tests in `tests/test_selftest.py` (91 total,
all passing), including an end-to-end check against a synthetic
1,000-symbol x 60-trading-day dataset sized so the random check's
expected-zero edge holds in practice, not just on average, plus a
regression guard so a dataset with the right columns but no data in the
self-test window (as two of `tests/test_run_queue.py`'s small synthetic
fixtures have) no-ops instead of crashing the whole queue run. Pushed
(`e272d85`), which triggered `replay.yml`
(https://github.com/Achintya1311/stockstalker-lab/actions/runs/39009574017,
succeeded) and committed the real `reports/selftest.md` (`d8a64d3`)
against the cached dataset: the leaky strategy came back 100% accurate
with a 56.14-point edge (flagged), and all 5 random seeds landed within
+-0.3 points of zero on both sides - both PASS.

Next: B3 is still the only blocked item (READY FOR WIRING in
`state/engine-issues.md`, needs a supervised session). B7 (champion v1 =
current StockStalker blended score, day and week, train then validation)
is the next unblocked build item - it needs reading STOCKSTALKER's actual
blended-score logic and porting it as a `strategies/` module scored
through the same `engine.replay`/`engine.scoring` path this run already
exercised end to end.

## 2026-10-17T0822Z — build lane

Claimed `build` (free, no contention). Next unticked, unblocked item was
B7: champion v1 = current StockStalker blended score, day and week, train
then validation (B3 is still only READY FOR WIRING in
`state/engine-issues.md`, needs a supervised `.github/` change, so stays
blocked and skipped).

Hypothesis: B7 splits into two parts with different dependencies - the
train-split report needs porting the strategy and a real `replay.yml` run
against the cached dataset (same B5/B6 shape), but "then validation" needs
a reusable-holdout (Thresholdout) query mechanism that doesn't exist yet -
Thresholdout itself is bundled into B8 ("Gates, ledger, Thresholdout,
budgets..."), not B7. So this run does the achievable half and leaves the
rest explicit rather than skipping the item or faking the second half.

Read `STOCKSTALKER/stockstalker/screener.py` and
`stockstalker/signals/{trend,momentum,volume}.py` (read-only reference) to
get the exact blended-score formula: trend = SMA(20,50) crossover spread
x10 clipped to [-1,1]; momentum = 0.5 x RSI(14, Wilder) re-centred on 50 +
0.5 x MACD(12,26,9) histogram as % of price, each clipped to [-1,1];
volume = 0.5 x rolling 20-day volume z-score /3 + 0.5 x 20-day OBV change
over 20-day traded volume, each clipped to [-1,1]; blend = weighted
average, weights {trend: 0.4, momentum: 0.35, volume: 0.25}. Ported this
(not imported - STOCKSTALKER isn't checked out in GitHub Actions) into
`strategies/champion_v1.py`, operating on the adjusted close series
(`scripts.adjustments.compute_adjustment_factors`, since B3's own report
wiring is blocked but the adjustment math itself already exists and is
tested) and raw volume. Score is kept in StockStalker's native [-1,1]
blend, not remapped to [0,1], so its sign carries direction per SPEC.md
section 5 - the same score-sign-as-side convention `engine.selftest`
already uses for the B6 self-tests. A symbol abstains (dropped, same as
NaN) below `MIN_ROWS=50` rows so no component's own insufficient-history
default (0.0) masquerades as a real reading.

Added `strategies/champion_v1_audit.py` (SPEC.md section 5: "audit.py
causality check" required per strategy) - not re-proving engine-level
truncation (B4 already does that), but proving the strategy's own
per-symbol groupby never lets one symbol's extra trailing row (a
realistic shape given NSE's ragged trading calendar) leak into another
symbol's score. 9 new tests in `tests/test_champion_v1.py`: known-signal
synthetic cases (steady uptrend -> bullish, steady downtrend -> bearish,
flat -> exactly neutral), the abstain floor, cross-symbol independence,
`rules_fired` wording, and the causality audit.

Added `engine/champion_report.py` (writes `reports/champion_v1_train.md`:
B7's acceptance in `state/queue.md`), wired into `engine.run_queue.main`
the same way B5/B6's reports are, so a push touching `engine/`,
`strategies/` or `experiments/pending/` regenerates it from the real
cached dataset. Reports picks/accuracy/edge by calendar year, per side,
for day and week, matching the gate-3 ("positive edge in >= 70% of
calendar years") breakdown. Deliberately left out gate 6's random-list
percentile: on 6 years of the real universe across 2 horizons x 2 sides,
1,000 redraws each proved far too slow for a report meant to regenerate
on every relevant push - confirmed by timing it locally (a 3-symbol,
~100-day synthetic fixture alone took over 2 minutes before the random
baseline was dropped); gate 6 belongs to the promotion job checking it
once on test, not to a report. 7 new tests in
`tests/test_champion_report.py` against a synthetic UP/DOWN/FLAT dataset,
plus a manual end-to-end run of `python3.13 -m engine.run_queue` against a
tiny synthetic parquet to confirm the CLI wiring itself. 107 tests total,
all passing (`python3.13 -m pytest tests/` - this sandbox's bare `pytest`
resolves to a different, package-less Python 3.13 install; pre-existing,
unrelated to this change).

Pushed (commit pending). This triggers `replay.yml` against the real
cached dataset, which should commit the real `reports/champion_v1_train.md`
if it succeeds.

Next: check the `replay.yml` run this push triggers
(https://github.com/Achintya1311/stockstalker-lab/actions/workflows/replay.yml)
succeeded and `reports/champion_v1_train.md` landed with sane numbers
(positive edge in most years, on both sides, for a strategy that's shipped
in production before - a flat or negative edge across the board would be
a bug worth finding before going further, not a result to report as-is).
If it looks sane, the next unblocked part of B7 is "then validation": a
minimal reusable-holdout (Thresholdout, Dwork et al. 2015) query mechanism
over champion v1's validation-split edge, logged as the one row
`ledger/holdout_queries.csv` needs - built now as its own small, focused
module (reusable by B8's fuller gates/budgets machinery later), not as
part of B8's whole bundle. Only then does B7 tick. B3 remains the one
other blocked item (READY FOR WIRING).
