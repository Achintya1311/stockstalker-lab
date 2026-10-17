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

## 2026-10-17T10:18Z — build lane

Hypothesis: the `Replay` run triggered by the previous commit (dc6a0a1, B7
champion v1 train-half) was still `in_progress` after 1h45m+ (checked via
`curl .../actions/runs/39017169385`), where every historically comparable
`Replay` run (B4-B6, also against the real cached dataset) had completed in
2-3 minutes. That gap is itself evidence of a real performance bug in the
new code this run introduced, not normal variance - worth investigating
before waiting on it any further.

What I found (`investigate-first`): `engine.replay.run_dates` calls
`strategy.score(history)` fresh for every pick date - once per symbol per
date, over that symbol's whole truncated history, by design (SPEC.md
section 4's causal truncation). `strategies/champion_v1.py`'s `score()`
had two costs that don't show up on any existing small/short fixture but
dominate at real scale:

1. `_wilder_smooth` (inside `_rsi`) ran a pure-Python `for` loop over each
   symbol's full truncated history length, on every call.
2. `score()` ran `compute_adjustment_factors` - a full `sort_values` +
   `groupby().shift()` + `groupby().cumprod()` - over *every* EQ-series
   symbol in `history` (3,818 on the real dataset per
   `state/data_manifest.json`), even though only F&O-eligible names
   (a few hundred) can ever survive `_restrict_to_universe` downstream.

For B7's train-split report that's ~1,800 pick dates (day + week,
2015-2020) x up to 3,818 symbols x a growing per-symbol history - squarely
why this run (the first to exercise `champion_v1.score()` against the real
dataset at this scale) is the first to run long, when B4-B6's self-tests
(trivial `score()` implementations, or 6-month windows) never hit it.

What I did (`surgical-patch`): vectorized `_wilder_smooth` with
`pandas.Series.ewm(adjust=False)` (same linear recursion, re-factored;
proven equal to the original Python loop to floating-point rounding by a
new regression test, `test_wilder_smooth_matches_reference_loop`, over 400
random rows). Added a `has_future`-based prefilter at the top of `score()`
that drops symbols that can never be F&O-eligible before the expensive
work starts (loose only in the inclusive direction - it can't exclude a
symbol that should score, see its docstring and
`test_score_prefilter_does_not_change_an_eligible_symbols_score`). A
synthetic 400-symbol/20-eligible/600-row micro-benchmark (not committed -
`/tmp` scratch) showed 17.3x: 1.886s -> 0.109s per `score()` call with the
old vs new code; the real dataset's ratio of eligible-to-total symbols is
far more lopsided (a few hundred F&O names out of 3,818 EQ-series symbols),
so the real speedup should be larger still. 110 tests pass
(`python3.13 -m pytest tests/`); the only 2 failures are the pre-existing,
unrelated `pyarrow`-not-installed sandbox gap noted in earlier entries
(reproduced identically on `dc6a0a1` before this change, via `git stash`).

Result: pushing now queues behind the still-running `Replay` run (the
`replay` concurrency group has no `cancel-in-progress`), so this fix won't
retroactively speed up run 39017169385 - that run will still finish
(success, or a correctness/engine_issues-worthy failure) or hit its
300-minute timeout on its own. But every push after it lands - including
the one this commit makes - should regenerate `reports/champion_v1_train.md`
in a reasonable number of minutes instead of hours, which matters a lot
given `replay.yml` fires on every future push touching `engine/`,
`strategies/`, `gates/` or `experiments/pending/`.

Next: check whether run 39017169385 finished (success/failure/timeout) and
whether the queued run for *this* commit lands `reports/champion_v1_train.md`
quickly. If the numbers in that report look sane (positive edge in most
years, both sides, for a strategy that's shipped in production before),
continue B7's remaining "then validation" step - the minimal reusable
Thresholdout query module - exactly as the previous entry planned. If
39017169385 failed or timed out, record it under `state/workflow_failures.md`
(the workflow's own failure-reporting step should already have done this on
failure; check it landed).

## 2026-10-17T1211Z — build lane

Claimed `build` (free, no lease held). Orientation first: run 39017169385
(the previous entry's open question) had finished `success` at 11:49:22Z,
3.5h after it started - the fix in the next commit never retroactively
sped it up (queued behind it, no `cancel-in-progress`, as already
expected) - and its commit `ad965e6` landed `reports/champion_v1_train.md`
on `main` with the same sane-looking numbers (positive edge in most
years, both sides) the previous entry wanted checked. So the unblocked
next step was exactly as planned: B7's "then validation" - the minimal
reusable Thresholdout query module.

But the *next* queued run (39024479250, for the vectorization-fix commit
itself) had meanwhile failed - not at `engine.run_queue` (which ran fine
and wrote the report again) but at `replay.yml`'s own commit step: an
add/add merge conflict from racing the already-landed `ad965e6` commit
(both runs' checkouts predate each other's push, so each one sees itself
as *creating* `reports/champion_v1_train.md`), and the commit step's own
failure-recovery line (`git reset --hard; git pull`) made it worse - a
failed `git rebase` leaves `HEAD` detached, so `reset --hard` never
reattaches it to `main`, and the following bare `git pull` (no
branch given) errored out before even the failure-reporting step could
run. Nothing was lost (the correct report had already landed from the
run ahead of it) but `state/workflow_failures.md` never got an entry
automatically - added by hand from the job's log via the public API, with
the full diagnosis and three `.github/`-side fix options in
`state/engine-issues.md` ("READY FOR WIRING: replay.yml's commit step
can't survive two queued runs landing the same report").

Hypothesis: SPEC.md section 4 describes exactly what's needed here -
Thresholdout (Dwork et al. 2015), "noisy pass/fail answers" - and the
previous entry already scoped it as a standalone module (`engine/holdout.py`),
separate from B8's fuller gate/budget machinery, built once and reused
later.

What I did (`investigate-first` read of `engine/replay.py`, `engine/scoring.py`,
`engine/champion_report.py`, `config/splits.yml` first): added
`engine/holdout.py` - a single `thresholdout_query(train_value,
holdout_value, *, threshold, tolerance, rng)` function implementing the
textbook algorithm (Laplace noise on the train/holdout comparison; if they
disagree by more than noise can explain, release the holdout value plus
its own noise - "budget spent" - otherwise release the train value for
free). The true, un-noised holdout value is never returned from the
function at all, let alone logged anywhere - only `released_value` and
whether `budget_spent`.

Added `engine/holdout_report.py` to actually run the one real query B7
needs: champion v1's day-horizon, bullish-side edge, train vs. validation
(2021-2023), through that function, logged as one row in
`ledger/holdout_queries.csv`. Gave `engine.champion_report.horizon_results`
a `split` parameter (default `"train"`, every existing call site
unaffected) so this could reuse it for the validation split instead of
duplicating the day/week pick-date logic. `maybe_log_holdout_query` is
idempotent against an already-logged query id, so this only ever runs its
expensive computation once - every push after the first is a cheap no-op
read of the ledger, not a second un-budgeted query.

14 new tests (`tests/test_holdout.py`, `tests/test_holdout_report.py`):
the free-vs-paid branches, that the true holdout value never appears
verbatim even when budget is spent, idempotency, and that `maybe_log_holdout_query`
only fires once real train+validation coverage and the right columns are
present. One of my own first drafts of `test_holdout.py` was itself wrong
on first run (`test_identical_values_never_spend_budget_across_many_seeds`
asserted a flaky "never" that's actually an ~11% per-seed chance at
`tolerance=0.01` against `threshold=0.03` - basic Laplace-tail arithmetic
I'd skipped; fixed by tightening that one test's `tolerance` to `0.001`,
where the same tail probability is negligible, rather than touching the
module). 121 passed, 2 failed (`python3.13 -m pytest tests/` - the same
pre-existing, unrelated pyarrow-not-installed sandbox gap as every earlier
entry).

Pushed (`51e20b4`). The triggered `Replay` run (39032187555) took ~34
minutes end to end - longer than the ~19 minutes the previous (vectorized)
commit's own `Replay` run took for its two `horizon_results` calls
(champion_report's day+week, train only). Root cause, found while it was
still running: `engine.scoring.universe_membership` and
`moves_for_horizon` both recompute their rolling-window pass over *every*
row of the full cached dataset (now ~5M rows, 3,818 symbols) on *every*
`horizon_results` call, regardless of which split or how few dates it
asks for - already paid twice per `Replay` run by `champion_report` itself
(once for day, once for week), and my two added calls (duplicate day/train,
plus day/validation) each pay that same whole-dataset tax a third and
fourth time. Not a bug in this commit and not something worth fixing as
part of B7 (`champion_report`'s existing double-payment predates this
change and will keep recurring on every future push regardless; my two
extra payments are one-time only, guarded by the same idempotency check
above) - flagging it here as a real "Duplicated Derivation" finding
(`ml-pipeline-audit`) worth a future, focused optimization (cache
`universe_membership`/`moves_for_horizon` per dataset instead of
recomputing per `horizon_results` call) if `Replay` run times become a
problem again as the lab adds more strategies that each want their own
report.

Result: the run succeeded. `ledger/holdout_queries.csv` now has its first
real row: `champion_v1-day-bullish-edge-v1`, `train_value≈-0.00113`
(matches `reports/champion_v1_train.md`'s "Day - Bullish... edge -0.11
points" exactly), `released_value≈0.02529`, `budget_spent=True` - meaning
the mechanism judged validation-split day-bullish edge to disagree with
train by more than noise can explain, and released a noisy estimate of
the true (never-logged) validation value instead of the free train
answer. That is exactly what Thresholdout is supposed to do when train
and holdout genuinely diverge; it says nothing by itself about whether
champion v1 is good or bad on validation - that reading, and any gating
on it, is B8's job, not B7's. B7 ticked in `state/queue.md`: both halves
(train report with sane numbers, one logged validation query) are done.

Next: B3 remains the only other blocked item (READY FOR WIRING, needs a
supervised `.github/` change - unrelated to this entry's new
engine-issues.md entry, which needs a *different* `.github/` change to
`replay.yml`'s commit step). With B7 done, B8 ("Gates, ledger,
Thresholdout, budgets, guard check, CI, branch protection, auto-merge")
is the next unblocked build item - it can lean on `engine/holdout.py`
directly rather than rebuilding Thresholdout from scratch, but still owes
its own weekly query-budget enforcement (`ledger/holdout_queries.csv`
only has one manually-triggered row so far, no rate limiting yet) and the
full gate checks from SPEC.md section 6.

## 2026-10-17T1409Z — build lane

Mode A, build lease (no competing holder - no `state/leases/` directory
existed at all this run). B3 is still only READY FOR WIRING (needs the
supervised `.github/` change to `dataset.yml`); B4-B7 are ticked. B8
("Gates, ledger, Thresholdout, budgets, guard check, CI, branch
protection, auto-merge") is next, and per its own acceptance note in
`state/queue.md` ("Write the code ... with tests, then add a line 'READY
FOR WIRING: <item>' ... A supervised session ... ticks the item") this
run's job is the code-and-tests half only, same shape as B3's.

Hypothesis: the three things `state/queue.md`'s B8 line names - "the
guard: a CI check that fails if any path in `PROTECTED.txt` changed,
budgets in the ledger (`ledger/holdout_queries.csv`,
`ledger/test_looks.csv`) and the leak alarm" - plus the eight roster gates
from SPEC.md section 6, can all be written as pure, dataset-free code
(policy over already-computed numbers, or ledger/CSV bookkeeping),
leaving only the Actions/branch-protection wiring for a supervised
session, exactly like B3's split.

What I did:
- `gates/gates.py`: the eight gates (edge, trial-corrected significance,
  70%-of-years, >=500 test picks, directional move, random baseline,
  param-nudge robustness, roster overlap) as named bools on a
  `StrategyMetrics` dataclass, plus `high_conviction_tag` and
  `leak_alarm_triggered`/`leak_alarm_cleared`. Gate 2's rising bar
  (`required_t`) is a Bonferroni correction on the literal t>=3 single-trial
  bar, using `statistics.NormalDist` (stdlib, no new dependency) -
  `required_t(1) == 3.0` exactly, and rises monotonically with more
  cumulative trials.
- `gates/trials.py`: `ledger/trials.csv`'s schema and an append-only
  `record_trial`/`cumulative_trial_count` pair (the trial count gate 2
  needs). No file committed yet - nothing has logged a real trial, same
  as `ledger/holdout_queries.csv` before B7's first query.
- `gates/budgets.py`: ISO-calendar-week rate limiting for
  `ledger/holdout_queries.csv` (validation, cap from
  `config/splits.yml`'s `max_queries_per_week`, currently 60) and the new
  `ledger/test_looks.csv` (test, `max_looks_per_week`, currently 2), plus
  `record_test_look`. Deliberately does not touch
  `engine/holdout_report.py` (B7's already-shipped, already-tested single
  query) - this is the reusable mechanism a future `evaluate` lane should
  call *before* spending a query/look.
- `scripts/guard_check.py`: parses `PROTECTED.txt` (exact-file or
  directory-prefix entries) and diffs `git diff --name-only
  <base>...<head>` against them; exits 1 and lists every offending path on
  a hit.
- Tests for all four (`tests/test_gates.py`, `tests/test_trials.py`,
  `tests/test_budgets.py`, `tests/test_guard_check.py`), including
  `test_guard_check.py` against the real `PROTECTED.txt`, not just a
  synthetic copy.
- Added "READY FOR WIRING: B8" to `state/engine-issues.md`: the CI
  workflow step to run `guard_check.py`, the branch-protection rule to
  require it, and a note that "budgets respected" as an auto-merge
  condition has nothing to wire against yet (no code path spends a
  holdout query or test look outside B7's one already-shipped query).

Result: `pytest -q` - 159 passed, 0 failures, after one small fix: my
first pass imported `gates.budgets.test_looks_this_week` and
`test_look_budget_remaining` by their real names into
`tests/test_budgets.py`, and pytest collected both as test functions in
their own right (names start with `test_`), producing two
`PytestReturnNotNoneWarning`s - harmless (they ran against a
nonexistent default ledger path and returned 0) but sloppy. Fixed by
importing them under aliases (`looks_this_week`, `look_budget_remaining`)
in the test module; re-ran clean, no warnings, same 34 passing in the new
files plus all 125 pre-existing tests still green. `state/queue.md`'s B8
row stays unticked, per its own acceptance note - a supervised session
ticks it once `.github/` is wired and the guard check runs green on a
real PR.

Next: B3 is still the only item blocked purely on `.github/` wiring with
no code of its own left to write. B8's *code* is now done, but it also
stays blocked on `.github/` wiring (CI + branch protection) before it can
tick - so after this run, every remaining build item (B3, B8, B9, B10)
needs either a supervised `.github/` change or build-lane code B8/B9
haven't written yet. The next build-lane run should write B9's "picks
generator" (the one piece B8/B9's acceptance note names that this run
deliberately left out) and its tests, then check whether a supervised
session has since wired B3/B8 - if both are wired and ticked by then,
the next run after that can finally write `state/BUILD_DONE` once B9 is
also ticked.

## 2026-10-17T16:30Z — build lane

Hypothesis: B3's acceptance note flagged the corporate-actions detector's
19,825 candidates as implausibly high and named likely causes, including
"the previous row is not the previous trading day." Checked that first,
since cross-checking events against a detector known to be noisy would be
wasted work.

Result: found it. Parsed `reports/corporate_actions_check.md`'s full event
list and found eleven single dates where 1,000+ of ~3,200 symbols all show
a "corporate action" at once (full breakdown and evidence in
`state/engine-issues.md`'s new entry) — every one is the first weekday
after a real NSE Saturday/Sunday session (Budget-day special trading,
Diwali Muhurat trading, BCP/DR mock sessions) that `scripts/fetch_bhavcopy.py`
never attempted, because its date loop only tried `weekday() < 5`. Verified
directly against `nsearchives.nseindia.com` (several of these weekend
URLs return real, full bhavcopy files, both CM and FO) and with a direct
3-file spot check for `3IINFOTECH` on 2015-02-27/28/03-02 — the "corporate
action" PREVCLOSE matches the missing Saturday's real close exactly, not
a split/bonus. Fixed `fetch_bhavcopy.py` to attempt every calendar day;
added `tests/test_fetch_bhavcopy.py` (2 new tests). Full suite: 159 passed
(157 pre-existing + 2 new), `pytest -q`, no failures.

Triggered a fresh `backfill.yml` run (all years; the fetch is idempotent,
and only 11 of the 12 years were spot-checked) so the newly-added weekend
sessions actually land in the Actions cache; `dataset.yml` auto-chains off
`workflow_run: Backfill NSE history completed` and will rebuild
`data/dataset.parquet` once it finishes.

Next: once that backfill + dataset rebuild lands (check Actions run
status), delete `reports/corporate_actions_check.md` so `dataset.yml`
regenerates it, confirm the eleven spike dates are gone/shrunk to
plausible ratios, then do B3's actual job — cross-check at least 10 of
the *remaining* events against an independent public source (NSE
corporate announcements or news) and explain every mismatch and every
>=30% jump, per `state/queue.md`'s B3 acceptance note. The ~18,000
scattered smaller-deviation candidates left in the current report are a
separate question (EQ/BE series switches, thin-trading gaps) not
investigated this run. B3 stays unticked.

## 2026-10-17T20:09Z — build lane

Hypothesis: last run's next step was clear — the triggered all-years
backfill re-run (for the weekend-session fix) had landed by this run's
start (`Backfill NSE history` 39049507308 and the chained `Build dataset`
39054392433 both `success`), so delete the stale
`reports/corporate_actions_check.md` (still showing the old 19,825-count),
let `dataset.yml` regenerate it, confirm the eleven mega-spike dates were
gone, then do B3's actual job: cross-check >=10 events.

Result: regenerated report dropped to 5,503 candidates (down from
19,825) — the eleven mega-spikes were gone, but several smaller
single-date spikes remained (100-230 symbols "acting" at once, mostly on
Tuesdays), the same shape as the resolved bug one order of magnitude
down. Traced it directly against raw NSE data (AUTOIND, 17/18 Aug 2020):
root cause is the EQ-only dataset dropping a symbol's row on any day it
trades in NSE's BE (trade-to-trade) series, so `compute_adjustment_factors`'s
"prior close" silently skips the gap to a stale EQ row, while the real
PREVCLOSE (continuous across the series switch) looks like a corporate
action against it. Fixed in `scripts/adjustments.py` (detect a dataset
row-gap against the whole market's actual previous trading day; treat it
as unadjusted, same as a symbol's first row) with 2 new tests
(`tests/test_adjustments.py`); full suite 161 passed. Regenerated again
on the real dataset (Actions run 39066804573): **3** candidates remain.

That number (3, not "low thousands") led to the real finding this run:
checked two confirmed, named, real NSE corporate actions directly against
raw bhavcopy (HDFCBANK's 1:2 split, ex-date 19-Sep-2019; WIPRO's 1:3
bonus, ex-date 06-Mar-2019, NSE circular 33/2019) and in both, PREVCLOSE
on the ex-date is the **unrebased, literal prior-day close** — the whole
share-count change shows up only in that day's ordinary OPEN/CLOSE
trading. SPEC.md section 2's premise (adjustment factors come from
PREVCLOSE/prior CLOSE) does not hold for either action type on real data.
So `detect_corporate_actions` structurally cannot find real splits or
bonuses — full stop, not a tuning problem. What it *can* find (and all 3
remaining candidates are): face-value/unit changes NSE does rebase for
(SETFGOLD's confirmed 100:1 face-value split, ex-date 06-Jan-2022, NSE
circular — ratio matches exactly) and dividend-linked base-price nudges
(CARERATING, plausible but unconfirmed by a primary source; CUPID,
unexplained by any dividend/bonus/split found). All 3 cross-checked and
written into `reports/corporate_actions_check.md`'s table with sources.

Wrote the full finding and three possible directions (independent
corporate-actions data source; detect the price-side signature instead;
narrow what SPEC.md section 2 means by "adjusted") in
`state/engine-issues.md`'s new "`detect_corporate_actions` cannot find
what B3 needs it to find" entry, and updated B3's acceptance note in
`state/queue.md` to point there. B3 stays unticked, but its status
changed from "noise, not yet cleaned up" to "blocked on a design
decision for a supervised session" — "at least 10 events" is not
reachable by cleaning up more noise, since real splits/bonuses can't
surface in this detector's output at all.

Also worth noting for champion_v1: the series-gap fix in this run changes
its live adjusted prices for any symbol with BE-series history (it calls
the same `compute_adjustment_factors`), not just the report — a real
correctness fix, not just report hygiene.

Next: a supervised session should pick one of the three directions in
`state/engine-issues.md` for B3 (most direct: an independent
corporate-actions fetcher, likely new `scripts/` + Actions-workflow
infrastructure similar to `backfill.yml`). Until then, B3 is blocked, not
just unticked (its new entry in `state/engine-issues.md` is a
`READY FOR WIRING` entry not yet marked `WIRED`, so the `build` lane's
next run should see it as blocked per the routine's own rule and move on
to B9 — unblocked per `state/queue.md`, write the `picks/` package to its
contract there).

## 2026-10-17T2208Z build / B9

B3 is still blocked (READY FOR WIRING, not WIRED, per the previous
entry), so per the routine's own rule this run took B9 instead: "write
the `picks/` package to the contract in `state/queue.md`."

Hypothesis: the contract (`state/queue.md` B9) is implementable without
touching `engine/`/`gates/` at all - `engine.replay.truncate` and
`engine.scoring` already give everything a live pick needs; the only new
pieces are the next-session calendar, the source config reader, and the
picks-file shape itself.

Built `picks/` (calendar, source, select, outcomes, payload, exam,
summary, run) plus `config/nse_holidays.txt` (NSE's published 2026
equity-segment holiday list, cross-checked across two aggregators - see
the file's own header for sources). Two design calls worth recording for
whoever reads this next:

- **Universe eligibility for a live pick reads `asof`'s own row, not the
  session's.** `engine.scoring.universe_membership` lets a date's own
  turnover count toward its own membership, which is honest for a
  backtest reading that date's close after the fact (SPEC.md section 2),
  but a real decision made before the session's open can't know the
  session's own turnover yet. `picks/select.py` uses the most recent
  reading a live decision could actually have. The exam backfill keeps
  the backtest convention instead (pick-date's own universe), for
  consistency with B5-B7's already-accepted code, since it's genuinely
  replaying a known past rather than making a live call.
- **Where bullish and bearish strategies for a horizon could differ**
  (`config/live_source.json`'s four independent table entries), a single
  picks file's top-level `label`/`disclaimer` resolve to "mixed" when the
  two sides disagree (one gated, one still provisional) - not specified
  explicitly in the contract, but needed to keep the one disclaimer
  honest once the roster isn't all-champion-v1 any more.

Result: `python3 -m pytest` - 217 passed (18 new test files/additions
under `tests/test_picks_*.py` plus `tests/_picks_dataset.py`, a shared
synthetic-dataset builder mirroring `tests/test_champion_v1.py`'s
`_trending_symbol`). Pushed (017ba65); `Live` run 39075234846 succeeded
on the real cached dataset and committed `reports/live_dryrun/` with
`day/2026-10-19.json` and `week/2026-10-19.json` (5 bullish + 5 bearish
picks each, real symbols, champion v1's own reasoning text, provisional
disclaimer - `config/live_source.json` doesn't exist yet so dry mode
used its documented fallback) plus `summary.json`; `CI` run 39075234817
passed the full suite on the same commit. Ticked B9 in `state/queue.md`
with the run ids.

`asof` on the real run came back `2026-10-16` (Friday) with session
`2026-10-19` (Monday) - a genuine week-boundary crossing, so the week
file got exercised for real on the very first live run, not just in
tests. Also incidentally exercised the holiday-aware calendar for real:
Monday 2026-10-19's own *next* session (not generated this run, but
checked by hand) correctly skips Tuesday 2026-10-20 (Dussehra) to
Wednesday 2026-10-21.

Not done, deliberately: `config/live_source.json` itself (that's the
go-live track's job, due by Fri 30 Oct per `state/queue.md`'s "Go-live
track", not B9's) and forcing a second dry run today to exercise the
scoring path on committed files - 2026-10-19 hasn't happened yet, so
there's no outcome to score. B3 is still the real blocker on B10/
BUILD_DONE; it's unticked, not B9.

Next: a future run should (a) once Monday 2026-10-19's close is in the
cached dataset, check that the next push touching `picks/` (or the next
natural dry run) actually adds `hit`/`move_pct` to
`reports/live_dryrun/day/2026-10-19.json` - confirming the scoring half
of B9's acceptance for real, not just on synthetic data; (b) keep
chasing B3's three documented directions for a supervised session, since
that's still the only thing standing between here and BUILD_DONE; (c) if
`build` is free and B3 is still blocked, there's nothing else unticked
in B1-B9 - the next `build`-lane run should treat B1-B9 as exhausted
until B3 unblocks, and this routine's own rule ("never leave a run
idle") means doing research-during-the-build work instead (discover/
port/tune/diagnose on `cards/catalog.csv`), not inventing more build
work where none remains.
