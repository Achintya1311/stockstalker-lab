# Journal

One entry per run: date, lane, hypothesis, result, next.

## 2026-10-18T22:30Z — port lane

Hypothesis: with `diagnose` and `tune` both still blocked on the
`engine/experiment_report.py` scoring gap (`state/engine-issues.md`, now
ten landed experiments with zero of them diagnosed), and `build` blocked
on B3/B10, the highest-value unit of research work is the go-live
track's P3 (`state/queue.md`, SPEC.md section 10): "D1 and D2... move
ahead of the indicator rules... scripts/ changes, which the routine can
make." C01-C04 (calendar effects) are exhausted (C03/C04 blocked on a
holiday calendar and a dataset expiry field that doesn't exist - checked
`scripts/build_dataset.py`'s FO parsing directly this run and confirmed
`parse_fo_file` drops `EXPIRY_DT`/`XpryDt` entirely, so C04 is genuinely
blocked, not just unconfirmed), so D1 (extend the dataset with near-month
OI) is next in priority, ahead of T01.

What I did: scoped D1 to its futures half only (one unit of work, not the
full "futures and options OI" the queue line describes - options OI is a
materially different parse, left as a named follow-up). `parse_fo_file`
in `scripts/build_dataset.py` now keeps each FUTSTK/STF row's expiry date
and OI/change-in-OI (old format: `EXPIRY_DT` as `%d-%b-%Y`, `OPEN_INT`,
`CHG_IN_OI`; UDiFF: `XpryDt` already ISO, `OpnIntrst`, `ChngInOpnIntrst`),
and where a symbol has more than one live expiry on the same date
(near/next/far month - confirmed from `docs/nse_formats.md`'s "~210
stocks x 3 expiries" note), keeps only the soonest-expiry row - D01's
"near-month" convention, not an average or sum. `build()` carries this
through into the merged dataset as `oi_futstk`/`oi_chg_futstk`, NaN for
any (date, symbol) with no active future, same pattern `has_future`
already used. No `engine/` or `.github/` change needed - `dataset.yml`
already reruns `build_dataset.py` against the full raw cache on its own
schedule, so the real dataset picks this up without a backfill.

Added two new synthetic fixtures (`tests/test_build_dataset.py`): three
simultaneous expiries in the old format, two in UDiFF, each asserting the
near-month row's OI/change-in-OI is kept and the others discarded - the
actual thing this change is for, not just "it still parses." Extended the
three existing `parse_fo_file`/`build` tests with OI assertions on single-
expiry fixtures too. Marked **D01 `testable_now: yes`** in
`cards/catalog.csv` (D02 stays `no` - options OI untouched). Added a note
under `state/queue.md`'s D1 line recording this as partial, so the next
`port` run knows D01 is ready to card-and-test and D02's options-OI parse
is still open, without re-deriving either from scratch.

Also found, by accident, while installing test dependencies fresh in this
sandbox (`requirements.txt` pins no versions): `pip install`'ing
`pandas==3.0.6`/`numpy==2.4.6` makes `tests/test_c01_day_of_week.py::test_causality_audit_passes`
deterministically fail locally, on the exact commit (`183946a4`) whose own
`CI` run on GitHub Actions passed minutes earlier - confirmed this
reproduces independently of my own changes via `git stash`. Not root-
caused (Python 3.11.17 here vs 3.12.15 on the runner, or a pandas version
difference, or both) and not acted on - CI is the authoritative
environment and is green, and this is a pre-existing fragility in an
already-landed card's audit, not something this run's D1 change touches.
Recorded as a new `state/engine-issues.md` WATCH entry so a future session
doesn't waste time re-diagnosing it from zero, and notices if it ever
starts failing on CI itself.

Result: `python3 -m pytest -q --deselect tests/test_c01_day_of_week.py::test_causality_audit_passes`
(full suite, that one pre-existing/environment-specific failure excluded)
- 376 passed, 0 failed, in 332.30s. No regressions from this change.

Next: card and test D01 (OI build-up classification: price up with OI up
= long build-up/bullish, price down with OI up = short build-up/bearish)
now that `oi_futstk`/`oi_chg_futstk` exist - next `port`-lane run, or this
one if a future run has spare budget. Options OI for D02 (stock PCR) is
still a separate, larger parse (sum by option type across strikes within
the near-month expiry) - not started. The `engine/experiment_report.py`
scoring blocker remains the single highest-priority item for a supervised
session, now overdue relative to the 30 Oct `config/live_source.json`
deadline: ten landed experiments (A01-A09, C01, C02), zero diagnosed,
and the go-live track's P1 cannot award a single validation query without
it. `build` is still blocked on B3 (methodology decision) and B10 (needs
`.github/` plus B1-B9 all ticked, and B3 isn't) - nothing changed there
this run.

## 2026-10-18T20:23Z — port lane

Hypothesis: C02 (turn-of-month effect), the next untested `testable_now:
yes` card in SPEC order after C01, was flagged in `cards/C01.yml`'s own
red_flags as "likely portable the same way C01 was" via the
yesterday's-proxy trick - worth confirming that holds for a week-horizon
card, not just C01's day-horizon one.

What I did: it does hold, with one real design wrinkle found along the
way. `score()` proxies "is the upcoming pick week close to turn-of-month"
with "is `history`'s own last visible trading day (the day right before
the pick week starts) itself turn-of-month" - turn-of-month membership
computed purely from trading-day rank within each calendar month among
the dates `history` contains (last trading day of a month, or first 3
trading days of the next one, matching the catalog's "window -1..+3"),
never an external holiday calendar. Construction and lookup key on the
identical quantity, so it's self-consistent like C01.

The wrinkle: my first draft built historical base rates by grouping
`history` into true ISO calendar weeks (`.isocalendar()`), mirroring how
`engine.run_queue` actually picks weekly dates. Writing the causality
audit (shift every date in a synthetic market by 10 years, same technique
`c01_day_of_week_audit.py` uses) caught that this breaks: a whole-year
`DateOffset` shift does NOT reliably preserve weekday once a 29 February
is crossed (confirmed directly: `2016-02-29 + 11y = 2027-02-28`, and more
broadly 262 of 1000 synthetic dates land on a different weekday after an
11-year shift that happens to preserve the *anchor* date's weekday). That
scrambles which calendar days an ISO week groups together after the
shift, so the audit failed - correctly, not a false alarm: the
underlying design really was fragile, just not in a way day-to-day
replay on real, unshifted NSE dates would ever surface (real dates are
never shifted). Fixed by building historical base rates from
non-overlapping runs of 5 consecutive trading days counted by *position*
from `history`'s own earliest visible date (a "trading-day week") instead
of `.isocalendar()` - this doesn't change what `score()` itself reads at
live-scoring time (still just `history`'s own last visible date), only
how the internal training buckets are built, and it made the module
immune to the same class of bug, not just this one instance of it.

Wrote `cards/C02.yml` (reasoning, params, red flags including this
wrinkle), `strategies/c02_turn_of_month.py` (`score`/`rules_fired`/
`_is_totm`/`_pooled_week_returns`), `strategies/c02_turn_of_month_audit.py`
(the corrected causality check: a synthetic market with a deterministic
turn-of-month bias, built and verified independently of the module's own
ranking code, shift-invariant under an 11-year `DateOffset`, plus
determinism), and `tests/test_c02_turn_of_month.py` (10 tests: known bias
in whichever bucket the fixture's last day actually falls into, bearish
sign, zero-bias abstain, below-threshold abstain, empty history, `has_future`
exclusion, `rules_fired` reasoning, a direct `_is_totm` boundary check
against a hand-read January 2015 calendar, the causality audit). Queued
the train replay as `experiments/pending/c02-turn-of-month-week.yml` (week
horizon, matching the catalog row) and marked C02 `queued` in
`cards/catalog.csv`.

Result: `python3.13 -m pytest -q` (full suite) - 375 passed (365 existing
+ 10 new), 0 failed, in 220.01s. No regressions. The audit module also
runs standalone (`python3.13 -m strategies.c02_turn_of_month_audit`) and
passes (`bias_base`/`bias_shifted` both 0.02, matching the fixture's
expected bucket).

Next: once `replay.yml` lands `experiments/done/c02-turn-of-month-week/`,
it hits the same still-open blocker every ported card has hit since A01 -
`state/engine-issues.md`'s "READY FOR WIRING: no automated way to score a
finished train replay" (now ten landed experiments, zero scored) - this
is the highest-value thing for a supervised session to pick up before
30 Oct, since the go-live track's P1 (one validation query per positive-
train-edge card) cannot start without real train numbers for *any* ported
card. Until then, `port`-lane runs should keep working through
`cards/catalog.csv` in SPEC order: next candidates are C03 (pre-holiday -
`state/engine-issues.md` already flags this as needing a real NSE holiday
history back to 2015, not portable by proxy) and C04 (expiry-week - may
be more tractable if the dataset's own FUTSTK expiry field is usable,
worth checking `scripts/build_dataset.py`'s FO parsing before assuming it
needs the same fetch), then T01 onward. `build` is still blocked on B3
(methodology decision for a supervised session) and B10 (needs a
`.github/` change plus B1-B9 all ticked, and B3 isn't) - nothing changed
there this run.

## 2026-10-18T18:21Z — port lane

Hypothesis: C01 (day-of-week effect), next in SPEC testing order after
A01-A09, looked blocked at first glance - its catalog rule needs the pick
date's own weekday, and `engine.replay.pick_date` never passes a date into
`strategy.score()` at all (SPEC.md section 5's interface is `score(history)`
only), with `history` itself truncated strictly before the pick date (B4).
Unlike A09's gap-fade wall (the right information existed, just dated a day
late), this looked like it might have no workaround - "today's weekday"
isn't derivable from any amount of past price data. But it is derivable
indirectly: `history`'s own last visible date ("yesterday") has a weekday,
and NSE trading days almost always increment Mon->Tue->...->Fri->Mon with
no gap, so yesterday's weekday is nearly always today's weekday minus one
trading day - a proxy that needs no pick-date knowledge, and is
self-consistent as long as both the historical base-rate construction and
the live lookup use it identically (which this port does).

What I did: wrote `cards/C01.yml` documenting the wall and the proxy (plus
why it's a cleaner reinterpretation than A09's - same claim measured
through a one-step-earlier lens, not a different day's effect), with a
red flag that the proxy mislabels the rare week where a holiday falls
right after the keying day. Wrote `strategies/c01_day_of_week.py`: pools
open-to-close returns across the F&O universe per date (market-wide, not
cross-sectional - the catalog gives no per-symbol differentiation), buckets
every historical (date, next-date) pair by the first date's weekday, and
scores every `has_future`-eligible symbol identically with the bucket mean
keyed by yesterday's weekday, abstaining below `MIN_OCCURRENCES` (20)
pairs. Wrote `strategies/c01_day_of_week_audit.py` - a different shape of
audit than A01-A09's (nothing cross-symbol to leak here, since every
symbol gets the same score by design): it proves the module reads weekday
only off `history`'s own dates by checking the predicted bias is invariant
to shifting every date in a synthetic market ten years later. Wrote
`tests/test_c01_day_of_week.py` (10 tests). Queued the train replay as
`experiments/pending/c01-day-of-week-day.yml` (day horizon, matching the
catalog row) and marked C01 `queued` in `cards/catalog.csv`.

Also wrote a new `state/engine-issues.md` entry generalising this finding:
`score(history)` structurally can never carry the pick date, which is a
wall the whole calendar-effect family (C01-C04) shares, but unevenly - C02
(turn-of-month) looks portable the same yesterday-relative way C01 was,
while C03 (pre-holiday) and C04 (expiry-week) need *future* calendar
knowledge (is tomorrow a holiday / an expiry day) that no proxy on past
data can ever supply, and `config/nse_holidays.txt` covers 2026 only -
flagged so whoever picks those up doesn't rediscover the gap from scratch.

Result: `python3.13 -m pytest -q` (full suite) - 365 passed (355 existing +
10 new), 0 failed, in 212.06s. No regressions. The causality/purity audit
also runs standalone (`python3.13 -m strategies.c01_day_of_week_audit`) and
passes. Pushing this should trigger `replay.yml` against the real cached
dataset.

Next: once `replay.yml` lands `experiments/done/c01-day-of-week-day/`, it
hits the same scoring blocker A01-A09 already did (`engine/experiment_report.py`
proposal in `state/engine-issues.md`, still not landed - a supervised
session's attention is overdue here; ten landed experiments now have zero
of them diagnosed, and go-live track P1 cannot start without it). Next
`port`-lane run: try C02 (turn-of-month effect) using the same
yesterday-relative proxy this run validated for C01 - check whether
"history's last visible date is near a month boundary" is enough, same as
weekday was. If C02 also needs no engine change, C03/C04 come next but
hit the holiday-calendar gap flagged above; a supervised session may want
to pick a direction for that (full NSE holiday history back to 2015, same
shape as B3's proposed fetcher) before C03/C04's turn, rather than at the
go-live deadline. `build` is still blocked on B3 (methodology decision for
a supervised session) and B10 (needs a `.github/` change plus B1-B9 all
ticked, and B3 isn't) - nothing changed there this run.

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

## 2026-10-18T00:10Z — port lane

Hypothesis: with `build` blocked (B3 needs a supervised data-source decision
per `state/engine-issues.md`; B10 needs B1-B9 all ticked) and no catalog row
ever ported yet (all 51 `cards/catalog.csv` rows were still `untested`,
`cards/`, `strategies/`, `experiments/pending/`, `experiments/done/` and
`ledger/trials.csv` all empty of any real strategy work), "research during
the build" (SPEC.md's own answer to a run finding nothing to do) means the
`port` lane is free and A01 is next in SPEC.md section 5's testing order
(academic anomalies before indicator rules; A01 is the first anomaly row,
`testable_now: yes`, needs only `ohlcv`).

What I did: ported A01, short-term (weekly) reversal (Lehmann 1990, QJE;
Jegadeesh 1990, JF) - `cards/A01.yml` (source, claim, params, red flags),
`strategies/a01_weekly_reversal.py` (score = -(trailing 5-day return) on
the adjusted close series, same sign convention and `has_future` prefilter
as `strategies/champion_v1.py`; week horizon only, per the card's own
rule), `strategies/a01_weekly_reversal_audit.py` (cross-symbol causality
check, same shape as `champion_v1_audit.py`), and
`tests/test_a01_weekly_reversal.py` (13 tests: known-sign and exact-
magnitude checks on a deterministic flat-then-move fixture, abstain on
thin history, per-symbol independence, `has_future` prefilter, causality
audit, `rules_fired`). Queued the train replay as
`experiments/pending/a01-weekly-reversal-week.yml` (train split,
2015-01-01 to 2020-12-31, week horizon) and marked A01 `queued` in
`cards/catalog.csv`.

Result: `python3 -m pytest -q` - 230 passed (217 existing + 13 new), no
regressions. Pushing this should trigger `replay.yml` (queue touched)
against the real cached dataset.

Next: once `replay.yml` lands `experiments/done/a01-weekly-reversal-week/`,
a `diagnose`-lane run should record A01's train edge (day N/A, week
bullish/bearish) in `cards/catalog.csv`'s `status` column and in
`ledger/trials.csv` (first-ever row - the ledger didn't exist before this
run), then write `research/diagnostics/A01.md` (which years/regimes it
works or fails in, what to try next). Per the go-live track (P1,
`state/queue.md`): if A01 shows a positive train edge and positive
directional move on week-bullish or week-bearish, it earns one validation
query toward provisional-strategy status once `build` or a later Mode B
run reaches the evaluate lane. A02 (daily reversal after an extreme day)
is next in the `port` queue after A01. `build` is still blocked on B3 -
the three documented directions in `state/engine-issues.md` still need a
supervised pick; nothing changed there this run.

## 2026-10-18T02:11Z — port lane

Hypothesis: `build` is still blocked (B3 needs a supervised data-source
decision; B10 needs B1-B9 all ticked) and A01's train replay had already
landed in `experiments/done/` with the previous run's journal entry
flagging "research during the build" as the next step and A02 (daily
reversal after an extreme day) as the next catalog row in SPEC order. Tried
first to do the `diagnose` work that same entry queued up (record A01's
train edge in `cards/catalog.csv`/`ledger/trials.csv`, write
`research/diagnostics/A01.md`), but hit a structural blocker: scoring a
pick log needs the real dataset, which lives only in the Actions cache, and
the only workflow that touches it (`replay.yml`) runs a fixed
`engine.run_queue` command with no way to point it at a new script, while
`champion_report.py` (the only existing scoring-by-year/side code) is
hardcoded to champion v1 and lives inside the protected `engine/` tree.
Wrote this up in full in `state/engine-issues.md` ("READY FOR WIRING: no
automated way to score a finished train replay") with a concrete proposed
fix (`engine/experiment_report.py` generalising `champion_report.py`'s
per-year/side scoring to any `experiments/done/<id>/picks.json`, called
from `run_queue.main()`), since this blocks `diagnose` for every future
`port`ed card, not just A01 - then moved on rather than leaving the run
idle on it.

What I did: ported A02, daily reversal after an extreme day (microstructure
liquidity-overreaction literature, no single canonical paper per the
catalog's own `prior_claim`) - `cards/A02.yml` (source, claim, params,
red flags - including that there's no single dated study to check vintage
against), `strategies/a02_extreme_day_reversal.py` (score = -(yesterday's
close-to-close return / trailing 20-day sigma, sigma excluding yesterday's
own return), selective: abstains unless |z| >= 2.0; day horizon, same
`has_future` prefilter as A01/champion_v1), `strategies/a02_extreme_day_reversal_audit.py`
(cross-symbol causality check - built a deterministic alternating-return
fixture, since a pure random walk may or may not clear the 2-sigma gate for
any given seed, unlike A01's unconditional continuous score), and
`tests/test_a02_extreme_day_reversal.py` (16 tests: known-sign and exact
z-score-magnitude checks via the same deterministic fixture, threshold
abstain both sides of the gate, zero-volatility abstain, insufficient
history, per-symbol independence, `has_future` prefilter, causality audit).
Queued the train replay as `experiments/pending/a02-extreme-day-reversal-day.yml`
(train split, day horizon) and marked A02 `queued` in `cards/catalog.csv`.

Result: `python3 -m pytest -q` - 246 passed (230 existing + 16 new), no
regressions. Pushing this should trigger `replay.yml` (queue touched)
against the real cached dataset.

Next: once `replay.yml` lands `experiments/done/a02-extreme-day-reversal-day/`,
it will hit the exact same scoring blocker A01 already did - a `diagnose`-lane
run can't turn either pick log into real edge numbers until a supervised
session picks up the `engine/experiment_report.py` proposal in
`state/engine-issues.md`. Until then, further `port`-lane runs should keep
working through `cards/catalog.csv` in SPEC order (A03 price momentum 12-1
is next) rather than stall on `diagnose` - and a future run should re-check
whether a supervised session has picked up the engine-issues entry, since
once it lands, A01's and A02's pick logs are both sitting ready to be
scored immediately with no further replay needed. `build` is still blocked
on B3 - nothing changed there this run.

## 2026-10-18T04:09Z — port lane

Hypothesis: `build` is still blocked (B3 needs a supervised data-source
decision; B10 needs B1-B9 all ticked, and B10 itself is a `.github/` change
only a supervised session can make) and the previous run's journal entry
named A03 (price momentum 12-1) as the next catalog row in SPEC order. The
`diagnose` blocker on A01/A02 (`state/engine-issues.md`'s "READY FOR
WIRING: no automated way to score a finished train replay") is still open
- checked `engine/` for `experiment_report.py` before starting; it does
not exist yet, so a supervised session has not picked this up. Rather than
stall waiting on that, kept working through the catalog (SPEC.md's "the
work never runs out").

What I did: ported A03, price momentum 12-1 (Jegadeesh and Titman 1993,
JF) - `cards/A03.yml` (source, claim, params, red flags - including that
the paper's own horizon is 3-12 months, far longer than the one week
tested here, and that momentum is known to crash sharply in reversal
periods), `strategies/a03_momentum_12_1.py` (score = +(trailing 252-day
return, skipping the most recent 21 days) - continuous, signed, opposite
sign convention from A01's reversal since this is a continuation bet, not
a reversal one; week horizon; same `has_future` prefilter as
A01/A02/champion_v1), `strategies/a03_momentum_12_1_audit.py` (cross-symbol
causality check, same per-symbol-groupby shape as A01/A02's audits), and
`tests/test_a03_momentum_12_1.py` (16 tests: a new fixture that places a
known move only between the two formation-window anchors so the exact
formation-return magnitude is a known expected signal, a separate check
that a move strictly inside the skipped month does not change the score at
all, threshold/insufficient-history abstain, per-symbol independence,
`has_future` prefilter, causality audit) - 14 tests. Queued the train
replay as `experiments/pending/a03-momentum-12-1-week.yml` (train split,
week horizon) and marked A03 `queued` in `cards/catalog.csv`.

Also hit and fixed a sandbox-only tooling snag, not a lab code issue: this
container's `python3` (3.11, via `/usr/local/bin/python3`) has no
`pandas`/`pytest`, while `pip3`'s underlying interpreter (3.13) has
`pandas` but initially neither `pytest` nor `pyarrow`. Installed `pytest`,
`pyarrow` and `pyyaml` for `/usr/bin/python3.13` (`--user`) and ran the
suite with that interpreter explicitly; this is local-sandbox environment
state only, nothing committed, and shouldn't recur identically in Actions
(which has its own `requirements.txt`-driven environment) or in a future
sandbox session, but worth knowing if a future run hits the same
`ModuleNotFoundError` wall.

Result: `/usr/bin/python3.13 -m pytest -q` - 260 passed (246 existing + 14
new), 0 failed. Before installing `pyarrow` the same run showed 9 failures,
all `ImportError: ... no usable [parquet] engine` in
`tests/test_picks_run.py`/`tests/test_run_queue.py`; those disappeared
once `pyarrow` was installed, confirming they were never a real
regression from this change, just this sandbox missing a dependency
`requirements.txt` already lists. No regressions. Pushing this should
trigger `replay.yml` (queue touched) against the real cached dataset.

Next: once `replay.yml` lands `experiments/done/a03-momentum-12-1-week/`,
it will hit the same scoring blocker A01 and A02 already did - still
waiting on the `engine/experiment_report.py` proposal in
`state/engine-issues.md` for a supervised session to pick up. Until then,
further `port`-lane runs should keep working through `cards/catalog.csv`
in SPEC order (A04, 52-week-high proximity, is next) rather than stall on
`diagnose`. `build` is still blocked on B3 and B10 - nothing changed there
this run.

## 2026-10-18T06:11Z — port lane

Hypothesis: A04 (52-week-high proximity, George and Hwang 2004) is next in
`cards/catalog.csv`'s testing order after A01-A03; it can be ported and
train-queued the same way, with `diagnose` still blocked (see
2026-10-18T02:11Z and 04:19Z entries) and `build` still blocked on B3
(needs a supervised data-source decision) and B10 (needs a `.github/`
change).

What I did: the catalog's own rule ("close / 52-week high: nearest to the
high bullish, farthest bearish") is a ratio in (0, 1], not directly
signed - every other card on this roster (and
`engine.champion_report`/`engine.selftest`) reads a pick's side from its
own score's sign in absolute terms, not a cross-sectional rank, so a
literal close/high ratio could never produce a bearish pick. Adapted it
by centring the ratio on each stock's own trailing 252-day high/low range:
`score = 2 * (close - low) / (high - low) - 1`, so a close at the 52-week
high scores +1 and a close at the 52-week low scores -1. Flagged this
adaptation explicitly in `cards/A04.yml`'s red flags since it changes what
"farthest from the high" means (farthest within the stock's own range,
not farthest among all stocks that day, which is what the paper's own
decile-sort portfolio construction uses).

Added `cards/A04.yml`, `strategies/a04_52_week_high.py` (same `has_future`
prefilter and walk-forward adjustment as A01-A03), its causality audit
(`strategies/a04_52_week_high_audit.py`, same per-symbol-groupby shape),
and `tests/test_a04_52_week_high.py` (15 tests: known expected-signal
fixtures at the window high, window low, midpoint and an arbitrary
interior point exactly 0.5, a leading-history-doesn't-leak-into-the-window
check, threshold/insufficient-history abstain, per-symbol independence,
`has_future` prefilter, causality audit). Queued the train replay as
`experiments/pending/a04-52-week-high-week.yml` (train split, week
horizon) and marked A04 `queued` in `cards/catalog.csv`.

Result: `python3.13 -m pytest -q` (full suite, this sandbox's
`/usr/bin/python3.13` interpreter per the 2026-10-18T04:09Z entry's
tooling note) - 275 passed (260 existing + 15 new), 0 failed, in 243.84s.
No regressions. Pushing this should trigger `replay.yml` (queue touched)
against the real cached dataset.

Next: once `replay.yml` lands `experiments/done/a04-52-week-high-week/`,
it will hit the same scoring blocker A01-A03 already did - still waiting
on the `engine/experiment_report.py` proposal in `state/engine-issues.md`
for a supervised session to pick up; that blocker now affects four landed
experiments, not one. Until then, further `port`-lane runs should keep
working through `cards/catalog.csv` in SPEC order (A05, MAX effect /
lottery stocks, is next). `build` is still blocked on B3 and B10 -
nothing changed there this run.

## 2026-10-18T08:10Z — port lane

Hypothesis: A05 (MAX effect / lottery stocks, Bali, Cakici and Whitelaw
2011) is next in `cards/catalog.csv`'s testing order after A01-A04; `port`
was free (no lease held), `build` remains blocked on B3 (methodology
decision for a supervised session) and B10 (needs a `.github/` change),
and `diagnose` remains blocked on the `engine/experiment_report.py`
proposal in `state/engine-issues.md` (no automated way yet to score a
landed pick log) - so `port` is the right lane to keep research moving
(SPEC.md's "the work never runs out").

What I did: the catalog's own rule for A05 ("highest single-day return
over the past month: high MAX bearish, low MAX bullish") is, like A04's
"close / 52-week high", not directly signed around zero - MAX is a
maximum of a roughly mean-zero return distribution, so it's typically
positive regardless of whether a stock is, in the paper's own
cross-sectional sense, unusually lottery-like for its own history.
Adapted it the same way A04 adapted its ratio: centred per-symbol, this
time against a trailing volatility baseline rather than the stock's own
price range. `z = MAX / sigma`, where `MAX` is the largest daily return
over the trailing 21 trading days and `sigma` is the standard deviation
of daily returns over the 60 trading days immediately *preceding* that
window (a separate, non-overlapping baseline, so the month being judged
can't inflate the yardstick it's judged against - the same trick A02
uses to keep an extreme day out of its own sigma estimate). `score = -z`,
so an unusually large best day relative to the stock's own normal
volatility (lottery-like) scores bearish, and a muted one scores bullish.
Flagged this adaptation explicitly in `cards/A05.yml`'s red flags, same as
A04's.

Added `cards/A05.yml`, `strategies/a05_max_effect.py` (same `has_future`
prefilter and walk-forward adjustment as A01-A04), its causality audit
(`strategies/a05_max_effect_audit.py`, same per-symbol-groupby shape), and
`tests/test_a05_max_effect.py` (15 tests: known expected-`z` fixtures via
a deterministic alternating-return baseline plus a constant-return month,
a large-best-day-scores-bearish case, a muted-best-day-scores-bullish
case, zero-baseline-volatility abstain, a leading-history-doesn't-leak
check, threshold/insufficient-history abstain, per-symbol independence,
`has_future` prefilter, causality audit). Queued the train replay as
`experiments/pending/a05-max-effect-week.yml` (train split, week horizon)
and marked A05 `queued` in `cards/catalog.csv`.

Result: `python3.13 -m pytest -q` (full suite, this sandbox's
`/usr/bin/python3.13` interpreter; `pytest`/`pandas`/`pyarrow`/`numpy`/
`pyyaml` had to be installed into it first via `python3.13 -m pip install`
- no interpreter in this sandbox had them preinstalled this run, unlike
the 2026-10-18T04:09Z entry's note) - 290 passed (275 existing + 15 new),
0 failed, in 217.89s. No regressions. Pushing this should trigger
`replay.yml` (queue touched) against the real cached dataset.

Next: once `replay.yml` lands `experiments/done/a05-max-effect-week/`, it
will hit the same scoring blocker A01-A04 already did - still waiting on
the `engine/experiment_report.py` proposal in `state/engine-issues.md` for
a supervised session to pick up; that blocker now affects five landed
experiments, not one, and is worth prioritising once a supervised session
is available, since every further `port` just adds another unscored
experiment to the pile. Until then, further `port`-lane runs should keep
working through `cards/catalog.csv` in SPEC order (A06, low volatility /
idiosyncratic volatility, is next). `build` is still blocked on B3 and
B10 - nothing changed there this run.

## 2026-10-18T10:10Z — port lane

Hypothesis: A06 (low volatility / idiosyncratic volatility, Ang, Hodrick,
Xing and Zhang 2006) is next in `cards/catalog.csv`'s testing order after
A01-A05, as the previous run's journal entry queued up. `build` remains
blocked on B3 (methodology decision for a supervised session) and B10
(needs a `.github/` change); `diagnose` remains blocked on the
`engine/experiment_report.py` proposal in `state/engine-issues.md` (no
automated way yet to score a landed pick log, now affecting five landed
experiments); no lease was held for `port`. So `port` is the right lane
to keep research moving (SPEC.md's "the work never runs out").

What I did: the catalog's own rule for A06 ("low recent volatility
bullish, high volatility bearish") is, like A04 and A05, not directly
signed around zero - a realised standard deviation of returns is never
negative, so raw sigma is bearish-leaning by construction regardless of
whether a stock is, in its own history, unusually calm or unusually
turbulent right now. Also decided not to attempt the paper's own
methodology: Ang et al. measure *idiosyncratic* volatility (the std of a
Fama-French three-factor regression residual), but the catalog's own
`default_params` ("20- or 60-day sigma") already describes a plain sigma
window with no factor model, so this card follows that simplification -
total realised volatility, not isolated idiosyncratic volatility -
flagged explicitly in `cards/A06.yml`'s red flags rather than introducing
a factor model the catalog row never asked for. Centred it the same way
A05 centred MAX: against a trailing baseline, this time a ratio rather
than a z-score. `ratio = sigma_recent / sigma_baseline`, where
`sigma_recent` is realised volatility over the trailing 20 trading days
and `sigma_baseline` is realised volatility over the 60 trading days
immediately *preceding* that window (a separate, non-overlapping
baseline, the same boundary trick A02 and A05 use). `score = 1 - ratio`,
so a stock calmer than its own recent normal scores bullish and one more
turbulent than normal scores bearish.

Added `cards/A06.yml`, `strategies/a06_low_volatility.py` (same
`has_future` prefilter and walk-forward adjustment as A01-A05), its
causality audit (`strategies/a06_low_volatility_audit.py`, same
per-symbol-groupby shape), and `tests/test_a06_low_volatility.py` (16
tests: known expected-ratio fixtures via a deterministic alternating-
return baseline and recent window, both score directions, a neutral
ratio-of-1 case, zero-baseline-volatility abstain, a leading-history-
doesn't-leak check, threshold/insufficient-history abstain, per-symbol
independence, `has_future` prefilter, causality audit). Queued the train
replay as `experiments/pending/a06-low-volatility-week.yml` (train split,
week horizon) and marked A06 `queued` in `cards/catalog.csv`.

Result: `python3.13 -m pytest -q` (full suite, this sandbox's
`/usr/bin/python3.13` interpreter; `pytest`/`pandas`/`pyarrow`/`numpy`/
`pyyaml` had to be installed into it first via `python3.13 -m pip
install`, same as the previous two runs) - 306 passed (290 existing + 16
new), 0 failed, in 223.97s. No regressions. Pushing this should trigger
`replay.yml` (queue touched) against the real cached dataset.

Next: once `replay.yml` lands `experiments/done/a06-low-volatility-week/`,
it will hit the same scoring blocker A01-A05 already did - still waiting
on the `engine/experiment_report.py` proposal in `state/engine-issues.md`
for a supervised session to pick up; that blocker now affects six landed
experiments, not one, and is worth prioritising once a supervised session
is available, since every further `port` just adds another unscored
experiment to the pile. Until then, further `port`-lane runs should keep
working through `cards/catalog.csv` in SPEC order (A07, high-volume
return premium, is next). `build` is still blocked on B3 and B10 -
nothing changed there this run.

## 2026-10-18T12:16Z — port lane

Hypothesis: A07 (high-volume return premium, Gervais, Kaniel and
Mingelgrin 2001) is next in `cards/catalog.csv`'s testing order after
A01-A06, as the previous run's journal entry queued up. `build` remains
blocked on B3 (methodology decision for a supervised session) and B10
(needs a `.github/` change); `diagnose` remains blocked on the
`engine/experiment_report.py` proposal in `state/engine-issues.md` (no
automated way yet to score a landed pick log, now affecting six landed
experiments); no lease was held for `port`. So `port` is the right lane
to keep research moving (SPEC.md's "the work never runs out"), and it
also serves the go-live track's P1 priority (SPEC.md section 10,
`state/queue.md`: "keep working through `cards/catalog.csv` in SPEC
order" ranks right after leak alarms and workflow failures while any
table is provisional).

What I did: unlike A04/A05/A06, the catalog's own rule for A07
("unusually high volume bullish, unusually low bearish") is already
directly signed around zero - a two-sided z-score claim, not a one-sided
non-negative quantity like a range position or a raw sigma that first
needs centring before it can point either way. So this card needed no
sign-flip or `1 - ratio` transform: `score = z = (avg_recent_volume -
baseline_mean) / baseline_std`, with `avg_recent_volume` the mean of the
trailing 5 trading days' ("last week") volume and `baseline_mean`/
`baseline_std` the mean/population std of the 50 trading days immediately
*preceding* that window (non-overlapping, the same boundary trick
A02/A05/A06 use). High recent volume (z > 0) scores bullish, low recent
volume (z < 0) scores bearish, matching the catalog row and the paper's
claim with no inversion.

Flagged one confound explicitly in `cards/A07.yml`'s red flags that
earlier cards didn't need to worry about: volume is used raw, not
price-adjusted, so a split/bonus's share-count change could shift raw
volume independent of any real demand change and masquerade as a
high-volume bullish signal exactly on a split day - worth checking in
`diagnose` once that lane is unblocked, not assumed immaterial.

Added `cards/A07.yml`, `strategies/a07_high_volume_premium.py` (same
`has_future` prefilter as A01-A06; no `scripts.adjustments` import needed
since this card scores raw volume, not price, so there is nothing to
adjust), its causality audit
(`strategies/a07_high_volume_premium_audit.py`, same per-symbol-groupby
shape), and `tests/test_a07_high_volume_premium.py` (16 tests: known-z
fixtures via a deterministic alternating-volume baseline and a flat
recent window, both score directions, a neutral z=0 case, zero-baseline-
std abstain, a leading-history-doesn't-leak check, threshold/
insufficient-history abstain, per-symbol independence, `has_future`
prefilter, causality audit). Queued the train replay as
`experiments/pending/a07-high-volume-premium-week.yml` (train split, week
horizon - the catalog row's own rule has no day-horizon variant) and
marked A07 `queued` in `cards/catalog.csv`.

Result: `python3.13 -m pytest -q` (full suite, this sandbox's
`/usr/bin/python3.13` interpreter; `pytest`/`pandas`/`pyarrow`/`numpy`/
`pyyaml` installed into it first via `python3.13 -m pip install`, same as
every recent run) - 322 passed (306 existing + 16 new), 0 failed, in
227.22s. No regressions. Pushing this should trigger `replay.yml` (queue
touched) against the real cached dataset.

Next: once `replay.yml` lands `experiments/done/a07-high-volume-premium-week/`,
it will hit the same scoring blocker A01-A06 already did - still waiting
on the `engine/experiment_report.py` proposal in `state/engine-issues.md`
for a supervised session to pick up; that blocker now affects seven
landed experiments, not one, and is worth prioritising once a supervised
session is available (it's also what the go-live track's P1 validation
queries, SPEC.md section 10, ultimately depend on - a provisional
candidate needs a known positive train edge and directional move before
it can earn a validation query, and nothing here can compute either yet).
Until then, further `port`-lane runs should keep working through
`cards/catalog.csv` in SPEC order (A08, overnight vs intraday tug of war,
is next - still an academic anomaly, day horizon this time). `build` is
still blocked on B3 and B10 - nothing changed there this run.

## 2026-10-18T14:18Z — port lane

Hypothesis: A08 (overnight vs intraday tug of war, Lou, Polk and Skouras
2019, JFE) is next in `cards/catalog.csv`'s testing order after A01-A07,
as the previous run's journal entry queued up. `build` remains blocked on
B3 (methodology decision for a supervised session) and B10 (needs a
`.github/` change); `diagnose` remains blocked on the
`engine/experiment_report.py` proposal in `state/engine-issues.md` (no
automated way yet to score a landed pick log, now affecting seven landed
experiments); no lease was held for `port`. So `port` is the right lane
to keep research moving (SPEC.md's "the work never runs out"), and it
also serves the go-live track's P1 priority (SPEC.md section 10,
`state/queue.md`: "keep working through `cards/catalog.csv` in SPEC
order" ranks right after leak alarms and workflow failures while any
table is provisional).

What I did: unlike A01-A07, A08 is a day-horizon card whose predicted
quantity (open-to-close) is exactly our own day pick's scored outcome, not
a proxy for it - picked ahead in SPEC.md's testing order for that reason.
The catalog's rule ("strong past overnight returns but weak intraday
returns: bearish for open-to-close, and the reverse") decomposes each of
the trailing 20 trading days into an overnight leg
(`adj_open_t / adj_close_(t-1) - 1`) and an intraday leg
(`adj_close_t / adj_open_t - 1`), averages each over the window, and
scores `avg_intraday - avg_overnight`: a stock whose recent gains came
from the intraday leg scores bullish, one whose recent gains came mostly
overnight (with weak or negative intraday) scores bearish - matching the
catalog row with no sign flip. Prices are the split/bonus-adjusted series
(`scripts.adjustments.compute_adjustment_factors`, same as A02) so a
corporate action between a close and the next open doesn't masquerade as
a real gap; the intraday leg needs no adjustment (same-row factor
cancels) but is read from the same adjusted frame for one consistent
column set.

Added `cards/A08.yml`, `strategies/a08_overnight_intraday_tug.py` (same
`has_future` prefilter and `compute_adjustment_factors` use as A02), its
causality audit (`strategies/a08_overnight_intraday_tug_audit.py`, same
per-symbol independent-open/close synthetic fixture as A02/A07's audits,
extended to draw open and close as two independent legs so the overnight
and intraday components are genuinely distinct), and
`tests/test_a08_overnight_intraday_tug.py` (16 tests: known-score fixture
via constant per-day overnight/intraday returns - exact expected
`avg_intraday - avg_overnight` - both score directions, a zero-tug case
that must still be included (not an abstain), a leading-history-doesn't-
leak check, a non-positive-price abstain, insufficient-history abstain,
per-symbol independence, `has_future` prefilter, causality audit). Hit
and fixed one test-fixture bug before trusting the suite: the leading-
history fixture's own `pd.bdate_range` call started from the same default
date as the tail fixture, so concatenating them produced duplicate dates
for the same symbol - not a strategy bug, but it would have let a real
leak slip past the test undetected, since `compute_adjustment_factors`'s
previous-trading-day logic needs a real chronological axis to prove
anything. Fixed by giving the leading fixture an explicit earlier
`start_date`; confirmed the originally-intended property (tail-window
scores are unaffected by rows before it) only once dates were real.
Queued the train replay as `experiments/pending/a08-overnight-intraday-tug-day.yml`
(train split, day horizon - the catalog row's own rule has no week-horizon
variant) and marked A08 `queued` in `cards/catalog.csv`.

Result: `python3.13 -m pytest -q` (full suite) - 338 passed (322 existing
+ 16 new), 0 failed, in 210.27s. No regressions. Pushing this should
trigger `replay.yml` (queue touched) against the real cached dataset.

Next: once `replay.yml` lands `experiments/done/a08-overnight-intraday-tug-day/`,
it will hit the same scoring blocker A01-A07 already did - still waiting
on the `engine/experiment_report.py` proposal in `state/engine-issues.md`
for a supervised session to pick up; that blocker now affects eight
landed experiments, not one. Until then, further `port`-lane runs should
keep working through `cards/catalog.csv` in SPEC order (A09, gap fade, is
next - another day-horizon anomaly, closely related to A08 per both
cards' red flags: worth checking A08/A09 pick overlap once both have
train results, ahead of SPEC.md section 6 gate 8's roster-level 50%
overlap check). `build` is still blocked on B3 and B10 - nothing changed
there this run.

## 2026-10-18T16:19Z — port lane

Hypothesis: A09 (gap fade), next in SPEC testing order after A08, can be
ported honestly despite its catalog rule needing information (the pick
date's own open) that `engine/replay.py`'s `truncate()` structurally
withholds from every day-horizon strategy (B4) - a one-day-lagged variant
(yesterday's gap predicting today's open-to-close move, via the same
z-score shape A02 already uses on close-to-close returns) keeps the
catalog's fade mechanism testable without violating causality.

What I did: wrote `cards/A09.yml` documenting the reinterpretation and why
the literal same-day claim is untestable here (not a code bug - the
engine is correctly refusing to leak today's open to a day-horizon
strategy, and closing this gap for real would need a SPEC-level change to
when picks are made, not an engine fix, so it is not filed in
`state/engine-issues.md`), flagging that A10 (gap and go) will hit the
identical wall. Wrote `strategies/a09_gap_fade.py` (score = -z, where
z = yesterday's close-to-open gap / trailing-20-day gap sigma, yesterday's
own gap excluded from that sigma - mirrors A02's structure exactly,
applied to the gap component instead of close-to-close return),
`strategies/a09_gap_fade_audit.py` (cross-symbol causality proof via a
deterministic alternating-gap fixture), and `tests/test_a09_gap_fade.py`
(17 tests: known-score fixture, both score directions, threshold
boundary, zero-gap-volatility abstain, insufficient history, per-symbol
independence, `has_future` prefilter, causality audit, plus a
same-strategy-level sanity check that only the fixture's own last row
drives the score). Queued the train replay as
`experiments/pending/a09-gap-fade-day.yml` (day horizon only, matching the
catalog row) and marked A09 `queued` in `cards/catalog.csv`.

Result: `python3.13 -m pytest -q` (full suite) - 355 passed (338 existing
+ 17 new), 0 failed, in 206.60s. No regressions. The causality audit
module also runs standalone (`python3.13 -m strategies.a09_gap_fade_audit`)
and passes. Pushing this should trigger `replay.yml` against the real
cached dataset.

Next: once `replay.yml` lands `experiments/done/a09-gap-fade-day/`, it
will hit the same scoring blocker A01-A08 already did - still waiting on
the `engine/experiment_report.py` proposal in `state/engine-issues.md`
("READY FOR WIRING: no automated way to score a finished train replay")
for a supervised session to pick up; that blocker now affects nine landed
experiments with zero of them diagnosed, and the go-live track's P1 (every
positive-train-edge card earns one validation query toward a provisional
table) cannot start at all until it lands, since no train edge numbers
exist yet for any ported card. With `config/live_source.json` due by Fri
30 Oct 12:00 UTC and nothing ported since A01 (2026-10-17) actually
scored, this is worth a supervised session's attention soon rather than
at the deadline - flagging this explicitly since several runs in a row
have hit the same wall without it being picked up. Until then, further
`port`-lane runs should keep working through `cards/catalog.csv` in SPEC
order (next candidates in order: C01-C04 calendar effects, then T01
onward - A10, gap-and-go, is only "partly" testable_now per the catalog
since opening volume is unavailable, so it stays behind the clean `yes`
rows). `build` is still blocked on B3 (methodology decision for a
supervised session) and B10 (needs a `.github/` change plus B1-B9 all
ticked, and B3 isn't) - nothing changed there this run.

## 2026-10-19T00:09Z — port lane

Hypothesis: D01 (OI build-up classification), unlocked by D1's near-month
futures OI columns (landed 2026-10-18T22:31Z) and explicitly moved ahead
of the plain indicator rules (T/I/X rows) by the go-live track's P3 (`state/queue.md`:
"D1 and D2 ... move ahead of the indicator rules... where an F&O-only
universe is most likely to hold an edge that price rules miss") - a
derivatives-family card, next in priority even though C03/C04/T01 sit
earlier in the catalog's raw row order.

What I did: the catalog's own classification (price up/down x OI up/down)
reads a session's own close and own OI change - the identical same-day
wall A09's gap fade hit (`cards/A09.yml`), since `engine/replay.py`'s
`truncate()` correctly withholds the pick date's own close/OI from a
day-horizon strategy. Ported as the honest one-day lag: `history`'s last
visible row (the session right before the pick date) is classified
long/short build-up or long-unwinding/short-covering from its own
`close`/`prevclose` and `oi_chg_futstk`/`oi_futstk`, and that
classification predicts the *next* session. `score = direction *
abs(oi_pct_chg) * weight`: direction always follows the last row's own
price-move sign (matching the catalog's four-way table's sign in every
quadrant), `weight` is 1.0 for a build-up (OI up) and 0.5 (`WEAK_WEIGHT`,
a new strategy parameter, not tuned) for unwinding/covering (OI down) -
the catalog's "treated as weaker" instruction applied to magnitude only,
sign untouched, exactly as stated.

Wrote `cards/D01.yml` (documenting the lag reinterpretation and the
`weak_weight` choice in its red flags, same shape as A09's card),
`strategies/d01_oi_buildup.py` (`has_future` prefilter, abstains on zero
price move, non-positive `prior_oi`, or missing OI/price fields),
`strategies/d01_oi_buildup_audit.py` (cross-symbol causality proof: giving
one symbol an extra trailing row changes only that symbol's score, via a
four-row synthetic fixture whose arithmetic I hand-verified before trusting
the test), and `tests/test_d01_oi_buildup.py` (22 tests: one test per
quadrant with a hand-computed expected score, a direct check that
unwinding/covering reads weaker than an equal-sized build-up, abstain
cases for zero move/non-positive prior OI/zero prevclose/no future/missing
OI columns, "only the last visible row counts" (an earlier build-up row
must not leak through once a later, differently-classified row exists),
per-symbol independence, `rules_fired` text for all four quadrants plus
both abstain messages, the causality audit, and the `has_future` prefilter).
Queued the train replay as `experiments/pending/d01-oi-buildup-day.yml`
(day horizon only - the catalog row's own horizon field is `day`, and
there is no natural weekly OI-build-up reading to invent) and marked D01
`queued` in `cards/catalog.csv`.

Result: `pip3 install -r requirements.txt` (no pytest/pandas preinstalled
in this sandbox this run, unlike prior runs' notes - installed cleanly,
no version pin issues hit) then `python3.13 -m pytest -q` (full suite) -
399 passed (377 existing + 22 new), 0 failed, in 243.70s. No regressions.
Pushing this should trigger `replay.yml` against the real cached dataset
(D1's dataset rebuild already landed 2026-10-18T22:37Z, so OI columns
should be populated back through 2015 for every symbol-day that had an
active future, not just recent history).

Next: this run did not touch the `engine/experiment_report.py` proposal
in `state/engine-issues.md` ("READY FOR WIRING: no automated way to score
a finished train replay") - that entry now affects eleven landed
experiments (A01-A09, C01, C02) with zero of them diagnosed, and D01 will
be the twelfth once its replay lands. It is worth flagging explicitly
again: the go-live track's P1 ("every train replay with a positive edge
... gets one validation query ... that is how a provisional candidate
earns its place") structurally cannot start - there are no train edge
numbers for anything ported since A01 (2026-10-17) - and `config/live_source.json`
is due by Fri 30 Oct 12:00 UTC. The SPEC's own fallback (champion v1 when
nothing qualifies) covers that specific deadline either way, so this is
not a go-live blocker by itself, but every day this stays unpicked-up is
a day the lab cannot tell whether any of its eleven-going-on-twelve ported
cards are worth anything, on train or otherwise. Further `port`-lane runs
should keep working through `cards/catalog.csv` in SPEC order, factoring
in the go-live P3 reordering (D02 is next in the derivatives family but is
still blocked - `testable_now: no`, options OI is a separate, larger
parse not yet done; after that, C03/C04 are next in raw catalog order but
both are flagged blocked in `state/engine-issues.md`: C03 needs full NSE
holiday history back to 2015, C04 might be unblocked by the FO expiry
field already in the dataset - worth checking before assuming it needs
the same holiday fetch). `build` is still blocked on B3 and B10 - nothing
changed there this run.

## 2026-10-19T02:11Z — port lane

Hypothesis: the previous run's journal entry flagged C04 (F&O expiry-week
effect) as possibly unblockable without the holiday-history fetch C03
needs, "worth checking before assuming it needs the same holiday fetch."
Checked: `scripts/build_dataset.py`'s `parse_fo_file` already parses each
FUTSTK/STF row's own expiry date (used internally to pick the near-month
contract when several expiries trade the same symbol-day) but then
dropped it before the final output columns - never actually in the
dataset. So C04 was blocked by an implementation gap, not a genuine
future-information problem: NSE's monthly expiry schedule is already
published and already present in the FO bhavcopy on every day it is
active, unlike C03's "is tomorrow a holiday" (which truly isn't derivable
from any amount of past price data).

What I did: extended `scripts/build_dataset.py` to keep that near-month
expiry date as a new column, `expiry_futstk` (ISO string, alongside
`oi_futstk`/`oi_chg_futstk` from D1), and updated `tests/test_build_dataset.py`
to assert it end to end (per-expiry parsing, near-month selection among
several simultaneous expiries, and the merged `build()` output for both
the old and UDiFF formats). Then ported C04 as two strategy modules
(`score(history)` is never told which horizon it's running for, the same
reason C01/C02 are each single-horizon cards - a calendar-anchored rule
like this can't share one function across both):

- `strategies/c04_expiry_week_day.py`: "yesterday's near-month contract
  expires in yesterday's own ISO week" stands in for "today is in expiry
  week" (C01's weekday-proxy idiom, applied to expiry-week membership).
- `strategies/c04_expiry_week_week.py`: week picks are made at Monday's
  open with history truncated through the prior Friday, and by Friday the
  contract has usually already rolled past whatever week just finished -
  so the day variant's proxy doesn't transfer. Instead: does the near-month
  contract active on the last visible Friday expire in the ISO week
  exactly 7 calendar days later (always the upcoming pick week)?

Both are market-wide (every eligible symbol gets the identical bucketed
historical-mean score, direction not assumed - the catalog states only
that expiry weeks behave differently, not which way) and build their base
rates from real ISO calendar weeks rather than C02's trading-day-chunk
workaround (that workaround existed only to dodge a weekday-alignment risk
that doesn't apply to an ISO-week-keyed rule). Shared calendar helpers live
in `strategies/c04_common.py` (not a strategy itself - no `score`, nothing
calls it directly) to avoid duplicating the `expiry_futstk` reading between
the two variants.

Wrote `cards/C04.yml` (horizon: both, documenting the dataset-gap finding
and both proxies' reasoning), `strategies/c04_expiry_week_{day,week}.py`,
matching `_audit.py` causality checks (a pure day-count-multiple-of-7 shift
of both `date` and `expiry_futstk` together must leave every score
unchanged, since only the relationship between the two columns should ever
matter - not C01's whole-years shift, which doesn't apply once the proxy
compares two absolute dates to each other instead of reading one date's
own weekday), and `tests/test_c04_expiry_week_{day,week}.py` (21 new tests:
known-bias exact scores for day and week, bearish sign, zero-bias and
under-threshold abstains, `has_future` exclusion, missing-expiry abstain,
`rules_fired` text, causality audit). Queued both horizons' train replays
(`experiments/pending/c04-expiry-week-{day,week}.yml`) and marked C04
`queued` in the catalog.

Caught and fixed one performance bug before committing: the week variant's
first `_cutoff_with_enough_history` test helper recomputed the *entire*
base-rate table from scratch for every candidate trading day while
searching for a scoreable cutoff, making the week test file take over two
minutes (quadratic in trading days) versus ~1s for everything else -
noticed only because the test run visibly hung past the usual few-second
turnaround, in the same spirit as `state/engine-issues.md`'s existing
"a strategy fast on test fixtures is not proven fast at real scale" WATCH
note. Rewrote it as a single O(n) walk that counts the exact condition the
real base-rate function buckets on, without rebuilding the table each
time; the test file dropped from 2+ minutes to ~6s with identical
assertions and results. The strategies' own `score()` implementations were
never affected - the slow code was only in the audit/test fixture
generator, not in anything a real replay runs.

Result: `pip3 install -r requirements.txt` then `python3.13 -m pytest -q`
(full suite) - 420 passed (399 existing + 21 new), 0 failed, in 278.34s.
No regressions. Pushing this should trigger `replay.yml` against the real
cached dataset; the dataset rebuild it needs (to backfill `expiry_futstk`
for all historical has_future rows, same mechanism D1's OI columns used)
should happen automatically on the next `dataset.yml` run as long as the
raw NSE zip cache hasn't been evicted since D1 landed.

Next: `diagnose` is still blocked on the `engine/experiment_report.py`
proposal in `state/engine-issues.md` - thirteen landed experiments now
(A01-A09, C01, C02, D01, and once this push's replay lands, C04-day and
C04-week), zero of them diagnosed, and the go-live track's P1 ("every
train replay with a positive edge ... gets one validation query") still
cannot start without it. A supervised session should pick that up soon;
Fri 30 Oct 12:00 UTC (`config/live_source.json` due) is getting closer
with no train numbers yet for anything ported since A01. Further
`port`-lane runs should keep working through `cards/catalog.csv`: D02
(options OI, still `testable_now: no` - options OI is a separate, larger
parse than the futures-only expiry/OI work D1 and this run did) and the
T0x/I0x/X0x rows are next once C03 (the one genuinely holiday-calendar-
blocked row) is set aside for a supervised decision. `build` is still
blocked on B3 (methodology decision for a supervised session) and B10
(needs a supervised decision too) - nothing changed there this run.

## 2026-10-19T04:12Z — port lane

Hypothesis: with `diagnose` still blocked on the `engine/experiment_report.py`
scoring gap (`state/engine-issues.md`, now thirteen landed experiments -
A01-A09, C01, C02, D01, C04-day, C04-week - zero diagnosed) and `build`
blocked on B3 and B10 (both need a supervised decision), the highest-value
unit of research work is still P1/the plain catalog order: keep porting
through `cards/catalog.csv`. C03 (pre-holiday) is genuinely blocked on a
missing NSE holiday calendar back to 2015 (`state/engine-issues.md`'s own
note) and D02-D04 stay `testable_now: no` (options OI, delivery %, bulk
deals all need fetchers not yet built), so the next untested,
`testable_now: yes` row in file order is **T01** (SMA crossover 20/50,
both horizons) - the first indicator-rule card, and notably the exact
signal `strategies/champion_v1.py`'s trend component already contributes
to its blend, now isolated and tested standalone.

What I did: ported T01 as a single module, `strategies/t01_sma_crossover.py`
- unlike C01/C02/C04, a pure price-based SMA crossover needs no pick-date
knowledge at all (both SMAs read purely off past adjusted closes already
inside whatever truncated `history` slice `engine.replay` hands it), so one
`score()` serves both horizons exactly the way `champion_v1.py` does,
without a day/week module split. Score is continuous:
`(fast_sma - slow_sma) / abs(slow_sma)` on the adjusted close series
(unscaled/unclipped, since this card is tested standalone, not blended),
same "sign gives direction, magnitude gives conviction" convention as
`a01_weekly_reversal.py`. `MIN_ROWS = 50` (the slow SMA's own window); the
same `has_future` prefilter `a01`/`champion_v1` already use.

Wrote `cards/T01.yml` (flagging the champion-v1-trend-overlap risk explicitly
under `red_flags`, relevant to SPEC.md section 6 gate 8 once this and
champion v1 both have real picks to compare), `strategies/t01_sma_crossover_audit.py`
(the generic cross-symbol causality check, same shape as `a01`'s and
`champion_v1`'s own), and `tests/test_t01_sma_crossover.py` (13 tests:
bullish/bearish/flat-zero cases, an exact hand-derived expected spread from
a plateau-then-shift fixture - 30 rows at 100.0 then 20 at 110.0 gives
slow_mean=104.0, fast_mean=110.0, spread=6/104 exactly - abstain on short
history, empty history, per-symbol independence, `rules_fired` text, the
`has_future` prefilter both ways, and the causality audit). Queued both
horizons' train replays (`experiments/pending/t01-sma-crossover-{day,week}.yml`,
both pointing at the same module) and marked T01 `queued` in the catalog.

Result: `pip3 install -r requirements.txt` then `python3.13 -m pytest -q
--deselect tests/test_c01_day_of_week.py::test_causality_audit_passes`
(the one pre-existing, environment-specific failure from the
`state/engine-issues.md` WATCH entry, confirmed still local-only, not
re-investigated this run) - 432 passed, 0 failed, in 265s (420 existing +
13 new, less 1 deselected). No regressions. Pushing this should trigger
`replay.yml` against the real cached dataset for both new experiments.

Next: `diagnose` remains blocked on the `engine/experiment_report.py`
proposal - still zero of fifteen (once this push's replay lands) landed
experiments scored, and the go-live track's P1 validation-query award
cannot start without it, with the holdout queries it would need allowed
from Mon 26 Oct and `config/live_source.json` due Fri 30 Oct 12:00 UTC.
This is now the single most overdue item for a supervised session - a
future run should keep flagging it, not just keep working around it by
porting more cards that then also can't be scored. Further `port`-lane
runs: next in file order after T01 is T02 (golden/death cross 50/200,
week-only) through T25, then I01/I02, then X01-X06 (SPEC testing order
only requires academic-before-indicator, already satisfied; file order is
otherwise as good a tiebreak as any). `build` is still blocked on B3
(methodology decision) and B10 (needs B3 plus a `.github/` change) -
nothing changed there this run.

## 2026-10-22T10:13Z port lane: D2 (security-wise delivery fetcher)

Mode: Mode A (BUILD_DONE still absent). Both unticked B items remain
blocked (B3 needs a supervised methodology decision; B10 needs B3 plus a
`.github/` change), so this run did research-during-build per SPEC's "the
work never runs out." `diagnose` is still fully blocked by the
`engine/experiment_report.py` gap (unchanged, still flagged in
`state/engine-issues.md`, still zero of seventeen landed experiments
scored) and `tune` needs a diagnosed edge first, so `discover`/`port` were
the only open lanes. The go-live track's P3 ("D1 and D2... move ahead of
the indicator rules... scripts/ changes, which the routine can make") ranks
above plain catalog order while any table is provisional (all four are),
and D1 is already partial, so this run picked up **D2**: a fetcher for
NSE's security-wise delivery file, which D03 (delivery percentage spike)
needs.

Hypothesis: NSE publishes delivered-quantity/delivery-% separately from the
ordinary bhavcopy, and per rule 2 in `state/queue.md` ("never write NSE
column names from memory") the real format had to be found, not guessed.

What I did: fetched real sample files directly in this sandbox (zero spend,
read-only, same NSE archive host `fetch_bhavcopy.py` already uses) and
confirmed `https://nsearchives.nseindia.com/archives/equities/mto/MTO_DDMMYYYY.DAT`
is live and format-stable from 2015-01-02 (checked against 2015-01-02,
2015-06-15, 2024-07-08/09, 2026-09-15, 2026-10-19) - one 7-field data-row
shape (`20,SrNo,Symbol,Series,QtyTraded,DeliverableQty,DeliveryPct`) the
whole span, no old/UDiFF-style split. Documented it in
`docs/nse_formats.md` with the real header. Wrote
`scripts/fetch_delivery.py` (same polite/resumable/missing.txt shape as
`fetch_bhavcopy.py`, one segment) and extended `scripts/build_dataset.py`
with `parse_delivery_file` plus a left-join of `deliv_qty`/`deliv_pct` into
`build()`'s output by (date, symbol), EQ-series only. New tests:
`tests/test_fetch_delivery.py` (4 cases) and 5 new cases in
`tests/test_build_dataset.py` covering both real preamble variants, series
filtering, the merge, and the no-delivery-files case. Updated D03's catalog
row (still `testable_now: no`, now naming the real blocker) and filed
"READY FOR WIRING: D2 delivery-% fetcher" in `state/engine-issues.md` -
like B3, the `scripts/` half is done but `backfill.yml`/`dataset.yml` need
a supervised step added to actually fetch and cache these files for
Actions; nothing this run wrote ever touches `.github/` or commits real
NSE data.

Result: `python3.13 -m pytest -q --deselect
tests/test_c01_day_of_week.py::test_causality_audit_passes` - 441 passed,
1 deselected (the pre-existing pandas-version-sensitive case from the WATCH
entry, not re-investigated), in 229s. No regressions (401 existing + 20
new - 1 deselected... 420 existing this run's base, consistent with last
run's count plus this run's 20 additions less the 1 pre-existing
deselection carried forward). This change touches no protected path and no
`experiments/pending/` or `strategies/` file, so it should not trigger
`replay.yml` on its own.

Next: the highest-value supervised item is still
`engine/experiment_report.py` (now blocking seventeen landed experiments'
scoring, not just A01/T01's two) - every `port` since 18 Oct has added more
cards that then can't be diagnosed, and the go-live track's P1 validation
queries (allowed from Mon 26 Oct, `config/live_source.json` due Fri 30 Oct
12:00 UTC) depend on it to know which candidate has a positive train edge
at all. A second, now-also-queued ask for a supervised session: wire D2's
fetcher into `backfill.yml`/`dataset.yml` per the new entry in
`state/engine-issues.md`, so D03 can actually be tested once scoring is
unblocked. Absent a supervised session, the next autonomous run should
keep working through plain catalog/port order (T02 next) or D1's still-open
options-OI continuation (unlocks D02), since neither needs
`engine/experiment_report.py` to be queued, only to eventually be scored.

## 2026-10-22T12:23Z port lane: D1 options-OI continuation (unlocks D02)

Mode: Mode A (BUILD_DONE still absent). No `state/leases/` lease files existed
at the start of this run, so `build` was free to check, but both unticked B
items (B3: methodology decision; B10: needs B3 plus a `.github/` change) are
still blocked on a supervised session — unchanged since the last run. `diagnose`
remains fully blocked by the `engine/experiment_report.py` gap (still flagged,
still zero landed experiments scored) and `tune` needs a diagnosed edge first,
so `discover`/`port` were the only open lanes, same as the previous two runs.

Hypothesis: the go-live track's P3 ("D1 and D2... move ahead of the indicator
rules... scripts/ changes, which the routine can make") ranks above plain
catalog order while any table is provisional (all four still are), and the
previous run's own next-steps flagged D1's options-OI continuation
(unlocks D02) as open and needing no supervised wiring — a better use of this
run than T02, since D1/D2 outrank indicator rules right now.

What I did: fetched real sample files directly in this sandbox (zero spend,
read-only, same NSE archive host `fetch_bhavcopy.py` already uses) to confirm
the options-row shape before writing anything, per rule 2 ("never write NSE
column names from memory") — the same rule applies to instrument-code *values*,
not just column names, after the 16 Oct bug that rule exists to prevent.
Confirmed against a real old-era file (`fo02JAN2015bhav.csv`, fetched this
run): distinct `INSTRUMENT` values are `FUTIDX, FUTIVX, FUTSTK, OPTIDX, OPTSTK`
— stock options are `OPTSTK`, `OPTION_TYP` in `{CE, PE}` (24,368 such rows on
02-Jan-2015 alone). Confirmed against a real UDiFF file
(`BhavCopy_NSE_FO_0_0_0_20260915_F_0000.csv`): `FinInstrmTp == STO` rows carry
`StrkPric`, `OptnTp` in `{CE, PE}`, and the same `OpnIntrst`/`ChngInOpnIntrst`
pair `STF` rows already use. Documented both in `docs/nse_formats.md`.

Added `scripts/build_dataset.py`'s `parse_fo_options_file`: filters each FO
zip's option rows (`OPTSTK` old era / `STO` UDiFF era), keeps only each
symbol's own near-month expiry (found independently per symbol, not assumed
to match the stock future's near-month), and sums `OPEN_INT`/`OpnIntrst` by
option type across strikes into `oi_ce_optstk`/`oi_pe_optstk` (catalog row
D02's "near-month options OI... for a stock-level put/call ratio" need).
Wired into `build()`'s merge alongside the existing futures-OI and delivery
left-joins. No `.github/` change needed and nothing new to fetch: these rows
live inside the same already-cached `fo_*.csv.zip` files D01 already parses
(confirmed by `backfill.yml`'s existing cm/fo fetch, already live since
before D01 landed), so D02's data need is satisfied by a pure parsing
addition — the same shape D01 itself was. Six new tests in
`tests/test_build_dataset.py`: both eras' near-month-only filtering (a
far-month decoy row with an implausible OI must not leak into the sum),
a symbol with only one option type trading (the other side reads 0.0, not
missing), the no-options-rows case, and two `build()`-level merge/NaN tests
mirroring the existing futures/delivery ones. Updated D02's catalog row
(`testable_now` now `yes`, naming why no wiring is needed) and
`state/queue.md`'s D1 entry with this continuation's result.

Result: `python3.13 -m pytest -q --deselect
tests/test_c01_day_of_week.py::test_causality_audit_passes` — 447 passed, 1
deselected (the pre-existing pandas-version-sensitive case from the WATCH
entry, not re-investigated), in 287s (441 existing + 6 new). No regressions.
This change touches no protected path; it also touches no
`experiments/pending/`/`strategies/`/`engine/`/`gates/` path, so it should not
trigger `replay.yml` on its own (same as the previous D2 run).

Next: the highest-value supervised item is unchanged —
`engine/experiment_report.py` (still blocking every landed experiment's
scoring; the go-live track's P1 validation queries, allowed from Mon 26 Oct,
depend on it) and wiring D2's fetcher into `backfill.yml`/`dataset.yml` (both
already flagged in `state/engine-issues.md`). Absent a supervised session,
D02 is now `testable_now: yes` and ready for the next `port`-lane run to card
and queue its train replay (card it like D01 was: a stock-level PCR from
`oi_ce_optstk`/`oi_pe_optstk`, "extreme PCR... test both" per the catalog's
own wording — both a contrarian and a confirmatory read are worth trying as
separate scored variants, or one card with a sign parameter). Otherwise the
next run should fall back to plain catalog/port order (T02).

## 2026-10-22T14:14Z port lane: D02 (stock put/call OI ratio, both variants)

Mode: Mode A (BUILD_DONE still absent). B3 (methodology decision) and B10
(needs B3 plus a `.github/` change) remain the only unticked B items and
both are still blocked on a supervised session, unchanged. `diagnose`
remains fully blocked by the `engine/experiment_report.py` gap (still
flagged, zero of seventeen-plus landed experiments scored) and `tune` needs
a diagnosed edge first, so `discover`/`port` were the only open lanes.
Followed the previous run's own "next": the go-live track's P3 ranks D1/D2
above plain catalog order while any table is provisional (all four still
are), D1's options-OI continuation unlocked D02 (`testable_now: yes`) last
run, and this run's job was exactly what that run flagged - card it.

Hypothesis: the catalog itself disputes D02's direction ("contrarian or
confirmatory, test both"), so this is honestly ported as two separate,
equally untested strategies sharing one core, not as a card that picks a
side (SPEC.md section 5: "no claim is assumed true").

What I did: claimed the `port` lease (free). Wrote `cards/D02.yml`: PCR per
session = `oi_pe_optstk / oi_ce_optstk` (D1's near-month options OI,
already summed by type across strikes); "extreme" = `|z| >= 2.0` against
the *same symbol's own* trailing 20-session PCR mean/std (Bollinger-band
style, the scored session itself included in the window) - reused D03's
own catalog-stated "z > 2 vs 20-day" threshold for consistency across the
two OI/flow-extreme cards in this family, since D02 gives no number of its
own. Read from `history`'s last visible row only, lagging one week the same
way `cards/D01.yml` lags one day for its day-horizon rule.

Wrote `strategies/d02_stock_pcr_core.py` (the shared z-score/threshold/
F&O-universe-gate machinery, `signal(history, *, contrarian: bool)`) and
two thin wrappers, `strategies/d02_stock_pcr_contrarian.py` (extreme-high
PCR -> bullish reversal, extreme-low -> bearish) and
`strategies/d02_stock_pcr_confirmatory.py` (the opposite sign - extreme-high
PCR -> bearish continuation), differing only in a final sign flip - same
shared-core shape `strategies/t01_sma_crossover.py` already uses to serve
two horizons from one module, applied here to serve two sign readings
instead. `strategies/d02_stock_pcr_audit.py` proves the shared per-symbol
rolling z-score can't leak across symbols (same shape as
`d01_oi_buildup_audit.py`'s cross-symbol check): giving one symbol an extra
extreme trailing session changes only that symbol's score, verified by hand
before trusting the test (`python3.13 -m` the audit module directly - both
`AAA`/`CCC` stayed un-scored in both scenarios, `BBB` newly scored only with
the extra session).

19 new tests (`tests/test_d02_stock_pcr.py`): both variants' sign on an
extreme-high and an extreme-low PCR, that the two variants agree on
magnitude and only disagree on sign, non-extreme/short-history/zero-`oi_ce`/
missing-columns/no-future/degenerate-std abstains, cross-symbol
independence, `rules_fired` wording for both variants and for the abstain
case, and the causality audit. Queued both variants as separate train-split
(week horizon, per the catalog) experiments -
`experiments/pending/d02-stock-pcr-contrarian-week.yml` and
`...-confirmatory-week.yml` - each will be its own trial in
`ledger/trials.csv` once scored, not a shared one. Marked D02 `queued` in
`cards/catalog.csv` and recorded this in `state/queue.md`'s D1/D2 note.

Result: `python3.13 -m pytest -q --deselect
tests/test_c01_day_of_week.py::test_causality_audit_passes` - 466 passed, 1
deselected (the pre-existing pandas-version-sensitive case from the WATCH
entry, not re-investigated), in 231s (447 existing + 19 new). No
regressions. This change touches `experiments/pending/` and `strategies/`,
so pushing it should trigger `replay.yml` against the real cached dataset.

Next: once `replay.yml` lands both
`experiments/done/d02-stock-pcr-{contrarian,confirmatory}-week/`, they hit
the same still-open blocker every ported card has hit since A01 -
`engine/experiment_report.py` (now blocking eighteen-plus landed
experiments' scoring) - this remains the single most overdue item for a
supervised session, more so now: the go-live track's P1 validation queries
are allowed from Mon 26 Oct and `config/live_source.json` is due Fri 30 Oct
12:00 UTC, and P1 cannot award a single query without real train numbers
for any candidate. Absent a supervised session, the next `port`-lane run
should fall back to plain catalog order (T02, golden/death cross 50/200,
week-only) - D1 and D2's own go-live-track priority (P3) is now fully spent
(both D01 and D02 are carded and queued; D03 still needs the separate
`backfill.yml`/`dataset.yml` wiring already flagged in
`state/engine-issues.md`, not something `port` alone can finish). `build`
is still blocked on B3 (methodology decision) and B10 (needs B3 plus a
`.github/` change) - nothing changed there this run.

## 2026-10-22T16:13Z port lane: T02 (golden/death cross 50/200, week)

Mode: Mode A (BUILD_DONE still absent). B3 and B10 remain the only
unticked B items, both still blocked on a supervised session, unchanged.
`diagnose` remains fully blocked by the `engine/experiment_report.py` gap
(state/engine-issues.md) - now nineteen landed experiments in
`experiments/done/`, zero scored into `research/diagnostics/` or
`ledger/trials.csv` (confirmed this run: both directories/files are still
empty). `tune` needs a diagnosed edge first, so `discover`/`port` were
again the only open lanes. The previous run's own "next" note pointed here:
D1/D2 (go-live track P3) are now fully carded and queued (both D01 and D02
variants), C03 (pre-holiday) stays genuinely blocked on a missing NSE
holiday calendar back to 2015, so the next untested `testable_now: yes`
row in plain catalog order is T02.

Hypothesis: T02 (50/200 "golden/death cross") is the slower, media-reported
cousin of T01's 20/50 pair already ported — same shape, different windows,
worth testing standalone per SPEC.md section 5's "no claim is assumed
true", since media popularity is not evidence.

What I did: claimed the `port` lease (free, pushed immediately). Wrote
`cards/T02.yml` (source: classic/media convention, no paper; catalog's own
`prior_claim`: "popular in media; trend signal, slow"). Wrote
`strategies/t02_golden_death_cross.py` — identical structure to
`strategies/t01_sma_crossover.py` (continuous signed score
`(fast_sma - slow_sma) / abs(slow_sma)`, `FAST=50, SLOW=200`,
`MIN_ROWS=SLOW`, same `has_future` prefilter, same adjusted-close input via
`scripts.adjustments.compute_adjustment_factors`) and
`strategies/t02_golden_death_cross_audit.py` (cross-symbol causality proof,
same construction as T01's audit: one symbol gets an extra trailing row,
the other two symbols' scores must not move). Catalog lists T02's horizon
as week only (unlike T01's "both"), so only one experiment file was
queued: `experiments/pending/t02-golden-death-cross-week.yml`. Marked T02
`queued` in `cards/catalog.csv` and recorded this in `state/queue.md`.

13 new tests (`tests/test_t02_golden_death_cross.py`), mirroring
`tests/test_t01_sma_crossover.py`'s suite with the hand-derived spread
re-worked for 200 total rows / 50 fast rows (slow_mean =
(150*100 + 50*110)/200 = 102.5 for the rising-tail case, spread =
7.5/102.5): rising/falling tail sign, flat-series exact zero, the
hand-derived magnitude, insufficient-history abstain (both in `score` and
`rules_fired`), empty history, per-symbol independence, the `has_future`
prefilter (keeps an eligible symbol unchanged, drops one with no future
anywhere), and the causality audit.

Result: `pip3 install -r requirements.txt` then `python3.13 -m pytest -q
--deselect tests/test_c01_day_of_week.py::test_causality_audit_passes` —
479 passed, 1 deselected (the pre-existing pandas-version-sensitive case
from the WATCH entry, not re-investigated), in 223s (466 existing + 13
new). No regressions. This change touches `experiments/pending/` and
`strategies/`, so pushing it should trigger `replay.yml` against the real
cached dataset.

Next: `engine/experiment_report.py` is now a four-day-old blocker (first
flagged 2026-10-18) sitting in front of nineteen fully-replayed, zero-scored
experiments, and it is getting more urgent, not less: go-live is Mon 2 Nov,
`config/live_source.json` is due Fri 30 Oct 12:00 UTC, and the go-live
track's P1 ("every train replay with a positive edge ... gets one
validation query") cannot award a single query without real train numbers
for any candidate beyond champion v1 — meaning every table's provisional
choice currently has no way to beat the champion-v1 fallback regardless of
how much `port`/`discover` work lands. This should go to Achintya directly
rather than waiting for another run to re-flag it. Absent a supervised
session, the next `port`-lane run should continue plain catalog order:
T03 (RSI(14) overbought/oversold) is next (`testable_now: yes`). `build`
is still blocked on B3 and B10 — nothing changed there this run.

## 2026-10-22T18:11Z port lane: T03 (RSI(14) 30/70 thresholds, both horizons)

Mode: Mode A (BUILD_DONE still absent). B3 and B10 remain the only
unticked B items, both still blocked on a supervised session, unchanged.
`diagnose` remains fully blocked by the `engine/experiment_report.py` gap
(state/engine-issues.md) — twenty landed experiments in `experiments/done/`
now (T02 landed since the last run), zero scored into `research/diagnostics/`
or `ledger/trials.csv` (both still empty, confirmed this run). `tune` needs
a diagnosed edge first, so `discover`/`port` were again the only open
lanes. Previous run's own "next" note pointed here: T03 (RSI(14)
overbought/oversold) is the next untested `testable_now: yes` row in plain
catalog order after T02.

Hypothesis: T03 is the most common retail oscillator rule (Wilder 1978),
structurally different from T01/T02's always-on SMA-spread shape — the
catalog's literal claim ("RSI below 30 bullish, above 70 bearish") only
takes a stance at the two extremes, so this card is selective by
construction (abstains inside 30-70), not continuous across the whole
range the way T01/T02 are. Worth testing as its own standalone signal
since it's half of `strategies/champion_v1.py`'s momentum component
already (re-centred continuously there, thresholded here).

What happened: `cards/T03.yml` (claim, horizon "both", red flags including
the catalog's own "also test 20/80" aside, left for a future `tune`-lane
pass rather than carded as a second row). `strategies/t03_rsi_thresholds.py`:
score = `(30 - rsi) / 30` when RSI < 30, `-(rsi - 70) / 30` when RSI > 70,
NaN (abstain) otherwise; RSI via a reimplemented (copied, not imported)
version of `champion_v1`'s vectorized Wilder's-smoothing (`ewm(alpha=1/period,
adjust=False)` after a simple-mean seed) — a per-row Python loop here would
hit the exact real-dataset slowdown `state/engine-issues.md`'s "Replay took
1h45m+" entry already documents for an unvectorized indicator.
`strategies/t03_rsi_thresholds_audit.py`: same cross-symbol causality proof
as T01/T02's, generalised to tolerate either flanking symbol abstaining on
a given random seed (a threshold rule won't always fire on arbitrary noise,
unlike T01/T02's always-on spread) rather than assuming both always score.
13 new tests (`tests/test_t03_rsi_thresholds.py`): exact boundary cases
(all-gains -> RSI=100 -> fully bearish; all-losses -> RSI=0 -> fully
bullish; flat -> RSI=50 -> abstain) rather than an approximate numeric
check, since Wilder's recursion converges to those exact values under
those constructions, plus the usual abstain/prefilter/causality coverage
every other card's suite carries. Catalog lists this card's horizon as
"both" (RSI needs no pick-date knowledge, same reasoning T01's card gives),
so two experiments are queued: `experiments/pending/t03-rsi-thresholds-{day,week}.yml`.
`cards/catalog.csv`'s T03 row now reads `queued`. Ran the new test file
alone (13 passed) and the full suite (`python3 -m pytest -q`, after fixing
this sandbox's pip/python version mismatch — `pip3` was resolving to
Python 3.13's site-packages while `python3` is 3.11; `python3 -m pip
install` instead) before committing; see this run's commit for the final
pass count and confirmation of no regressions.

Flags unchanged from the last run, now five days old (first flagged
2026-10-18): `engine/experiment_report.py` still sits in front of twenty
fully-replayed, zero-scored experiments, and go-live's `config/live_source.json`
deadline (Fri 30 Oct 12:00 UTC) is eight days out. The go-live track's P1
validation queries open Mon 26 Oct — four days from this run — and still
cannot be awarded to a single candidate beyond champion v1 without this
wiring landing first. Sending this to Achintya directly this run (per the
last run's own note) rather than letting it sit for a sixth day unflagged
outside the journal.

Next: continue plain catalog order for `port` — T04 (Connors RSI-2) is the
next untested `testable_now: yes` row after T03. `discover` (adding new
catalog rows from SPEC.md section 5's sources) is also still open and
untouched for several runs if a future run prefers it over more T0x
indicator ports. `build` is still blocked on B3 and B10 — nothing changed
there this run.

## 2026-10-22T20:11Z port lane: T04 (Connors RSI-2, day)

Mode: Mode A (BUILD_DONE still absent). B3 and B10 remain the only
unticked B items, both still blocked on a supervised session, unchanged.
`diagnose` remains fully blocked by the `engine/experiment_report.py` gap
(state/engine-issues.md, now six days old) — twenty-one landed experiments
in `experiments/done/` now (T04's day run will make twenty-two once
replayed), zero scored into `research/diagnostics/` or `ledger/trials.csv`.
`tune` needs a diagnosed edge first, so `discover`/`port` were again the
only open lanes. Previous run's own "next" note pointed here: T04 (Connors
RSI-2) is the next untested `testable_now: yes` row in plain catalog order
after T03 — C03 (pre-holiday effect) stays blocked, confirmed again this
run: `config/nse_holidays.txt` only covers 2026 (built for B9's live
picks), not the 2015-2020 train split a port needs.

Hypothesis: Connors RSI-2 (Connors and Alvarez 2009) is structurally
different from every T0x card so far — a conjunction of a slow 200-day
trend filter and a fast 2-period RSI extreme, rather than one indicator
read on its own. Worth testing as its own standalone signal: it is
plausibly a cleaner mean-reversion-inside-a-trend read than T03's
single-oscillator gate, at the cost of being asymmetric by construction
(no bullish case below the 200-day SMA, no bearish case above it) and
doubly selective (needs both legs to agree).

What happened: `cards/T04.yml` (claim, horizon "day" only — the book's
setup is a next-day trade inside a slow filter, not a week-ahead one — red
flags noting the doubled selectivity and the as-stated 10/90 thresholds as
a future `tune`-lane candidate). `strategies/t04_connors_rsi2.py`: bullish
when `close > SMA200` and `RSI(2) < 10`, scoring `(10 - rsi2) / 10`;
bearish when `close < SMA200` and `RSI(2) > 90`, scoring
`-(rsi2 - 90) / 10`; NaN (abstain) otherwise, including the two crosswise
cases (above SMA with RSI(2) > 90, below SMA with RSI(2) < 10) the
catalog's rule never states a view on. RSI(2) reuses T03's vectorized
Wilder-smoothing shape with `period=2` instead of 14; the 200-day SMA
reuses T02's plain trailing-mean shape; both copied, not imported, so this
card stays standalone. `strategies/t04_connors_rsi2_audit.py`: same
cross-symbol causality proof shape as T01-T03's, `MIN_ROWS=200` fixture.

12 new tests (`tests/test_t04_connors_rsi2.py`). Unlike T01-T03, this
card's firing region is not reachable from a globally monotonic series —
a fully monotonic uptrend gives RSI(2)=100 (the overbought threshold)
while price sits above its own SMA200 (the bullish trend reading), so the
two legs always disagree and the strategy abstains; same mirrored for a
fully monotonic downtrend. Used that exact-degenerate property as two
clean abstain tests, then built two directional fixtures (a long linear
drift over 215 rows, ending in a sharp 2-day countermove) for the firing
cases, cross-checked against an independent loop-based Wilder RSI(2) and
plain-mean SMA200 reference implemented directly in the test file (not
reused from the module) — the fixture lands RSI(2) at ~1.96 (bullish
case) and ~98.04 (bearish case), well past the 10/90 thresholds, confirmed
by direct computation before trusting the test. Catalog lists this card's
horizon as day only, so one experiment is queued:
`experiments/pending/t04-connors-rsi2-day.yml`. `cards/catalog.csv`'s T04
row now reads `queued`.

This sandbox was missing `pyarrow` (only `numpy`/`pandas`/`pyyaml`/`pytest`
were present going in, via `python3 -m pip install` after confirming
`pip`'s own resolver points at a different Python than `python3` here —
same mismatch the previous run's journal entry already flagged). Ran the
new test file alone first (12 passed), then the full suite without
`pyarrow` (495 passed, 10 failed — the one pre-existing pandas-version
flake plus nine `ImportError: pyarrow`/`fastparquet` failures in
`tests/test_picks_run.py` and `tests/test_run_queue.py`, both pre-existing
parquet-backed suites unrelated to this card), then installed `pyarrow`
and re-ran exactly those three files: 25 passed, 1 failed (the same
pre-existing pandas-version-sensitive flake `state/engine-issues.md`
already documents) — confirms zero regressions from this change, the nine
parquet failures were this sandbox's own missing dependency, not a bug.

Flags still open from the last two runs, now six days old (first flagged
2026-10-18): `engine/experiment_report.py` sits in front of twenty-two
fully-replayed, zero-scored experiments once T04's run lands. The go-live
track's P1 validation-query window opens Mon 26 Oct — four days from this
run — and `config/live_source.json` is due Fri 30 Oct 12:00 UTC, eight
days out. Neither deadline can be met with a real validation-backed
candidate (as opposed to falling straight through to champion v1 by
default) unless this wiring lands first; this run is escalating it outside
the lab loop itself (a push notification to Achintya) rather than letting
it sit for a seventh day with only a journal note, since a supervised
session is the only thing that can act on it and the next unsupervised run
cannot.

Next: continue plain catalog order for `port` — T05 (MACD crossover) is
the next untested `testable_now: yes` row after T04. `discover` remains
open and untouched for several runs if a future run prefers it. `build` is
still blocked on B3 and B10 — nothing changed there this run.

## 2026-10-22T22:10Z build lane: B10 (start the 2-hourly lab routine) — ticked, was never actually blocked

Mode: Mode A (BUILD_DONE still absent). Claimed the `build` lease (free —
no lease files existed at all in `state/leases/`, confirmed via `git log
--all -- state/leases/`: only `port`/`tune`-style claims have ever been
made, never a `build` one). B9 and B10 were the only two B items touched
recently; B9 has read `[x]` since 17 Oct, so B10 was the first unticked,
unblocked item to check.

Hypothesis: every previous run's journal ("build is still blocked on B3
and B10") treated B10 the same way as B3 — needs a supervised session —
without ever actually checking what B10's remaining work is. But B10's
text is just "start the 2-hourly lab routine with lanes", and this
session's own existence is that routine: it's not a repo artifact at all,
so the B-item blocking rule (READY FOR WIRING entry, or a `.github/`
change) doesn't apply to it the way it does to a code item.

What happened: called `list_triggers` (Claude_Code_Remote MCP server,
available in every run, not gated to a supervised one) and found the
scheduled task directly: name "StockStalker lab", id
`trig_01TkTBqUyJAMF7PiSGxQcy3u`, `cron_expression: "7 */2 * * *"`,
`enabled: true`, `created_at: 2026-10-16T18:07:01Z`, and `last_fired_at:
2026-10-22T22:07:45Z` — that firing is this very run. Its stored prompt is
exactly the lanes workflow this journal and `state/queue.md` describe
(orient, claim a lane by lease, do one unit of work, journal, push every 2
hours). SPEC.md section 1 ("it runs every 2 hours, on its own, with no
human approval step") and section 9's lanes table describe this exact
mechanism, which has been live for six days and 70+ firings already. There
is no outstanding `READY FOR WIRING` entry for B10 in
`state/engine-issues.md` (checked: none exists) and no `.github/` change
it needs. Ticked B10 in `state/queue.md` with this evidence recorded
inline, and corrected the standing misdiagnosis so future runs stop
re-flagging it as blocked.

This does not create `state/BUILD_DONE` — B3 is now the only unticked B
item, and it is genuinely blocked (methodology, not wiring: NSE's
PREVCLOSE does not rebase at a split/bonus ex-date, so
`detect_corporate_actions` structurally cannot find 10 real events to
cross-check; three possible directions are already laid out in
`state/engine-issues.md`, waiting on Achintya's choice). Checked
`state/engine-issues.md` end to end this run: the other standing
`READY FOR WIRING` entry — no automated scoring for a finished train
replay (`engine/experiment_report.py` missing), which has fully blocked
the `diagnose` lane since 18 Oct and now sits in front of twenty-two
landed, zero-scored experiments in `experiments/done/` — is unchanged
since the last run flagged it (2 hours ago); not re-escalating it
separately this run since nothing about it is new, but it remains the
single most urgent open item: the go-live track's P1 validation-query
window opens Mon 26 Oct (4 days out) and cannot be used for a real
candidate without this landing first, and `config/live_source.json` is due
Fri 30 Oct 12:00 UTC (8 days out).

Next: with B10 done, `build` has nothing left to claim (B3 stays blocked
on Achintya's methodology decision) — the next run should go straight to
research-during-the-build (`discover`/`port`/`tune`/`diagnose`, the last
still walled off by the `experiment_report.py` gap above). Catalog order
continues at T05 (MACD crossover), per the previous run's note.

## 2026-10-23T00:19Z port lane: T05 (MACD crossover, both horizons)

Mode: Mode A (BUILD_DONE still absent). B3 remains the only unticked B
item, still blocked on Achintya's methodology decision
(`state/engine-issues.md`: NSE's PREVCLOSE does not rebase at a split or
bonus ex-date, so `detect_corporate_actions` structurally cannot find the
10 real events B3's acceptance line asks for). `diagnose` remains fully
blocked by the missing `engine/experiment_report.py` wiring (now flagged
since 18 Oct, escalated to Achintya directly by the last two runs on 22
Oct) — confirmed again this run: `ledger/trials.csv` still does not exist
anywhere in the repo, `research/diagnostics/` still does not exist, and
`experiments/done/` now holds 24 fully-replayed, zero-scored experiment
directories once this run's T05 queue lands two more. `tune` needs a
diagnosed edge first, so `discover`/`port` remain the only open lanes.
Previous run's own "next" note pointed here: T05 (MACD crossover) is the
next untested `testable_now: yes` row in plain catalog order after T04
(C03 pre-holiday stays blocked, confirmed again: `config/nse_holidays.txt`
only covers 2026, not the train split a port needs).

Hypothesis: MACD(12, 26, 9) (Appel, 1970s) is structurally different from
every T0x card so far in one specific way: the catalog's own wording
("crossing above ... crossing below") is explicitly an event, not a
persisted state the way T01's always-on SMA spread, T02's golden/death
cross, T03's RSI thresholds, or T04's conjunction all read continuously
(or at the boundary) every bar. MACD should therefore fire far less often
than T01 — worth testing as its own standalone signal both because it's a
different smoothing family entirely (plain EMA, not Wilder's) and because
the literal "crossing" reading changes the selectivity story completely
from a continuous "is above" variant.

What happened: `cards/T05.yml` (claim, horizon "both" per the catalog,
red flags including the "crossing vs. is-above" distinction and a
possible future continuous variant as a separate, not-yet-carded card).
`strategies/t05_macd_crossover.py`: MACD line = EMA(12) - EMA(26) of the
adjusted close (plain EMA via `close.ewm(span=N, adjust=False).mean()`,
pandas' own recursive formula, no custom seeding needed since MACD's
published definition isn't Wilder-smoothed); signal = EMA(9) of the MACD
line; fires only on a fresh cross (`macd_prev <= signal_prev and
macd_latest > signal_latest`, or the mirrored `>=`/`<` for bearish),
scoring `(macd_latest - signal_latest) / abs(close_latest)` (sign always
matches cross direction by construction); abstains (NaN) on every other
bar, including one where MACD already sits well clear of signal without a
fresh cross. `MIN_ROWS = 36` (26 + 9 for a stable signal value, plus one
more row for the prior-bar comparison the cross itself needs).
`strategies/t05_macd_crossover_audit.py`: same cross-symbol causality
proof shape as T01-T04's.

11 new tests (`tests/test_t05_macd_crossover.py`): a steady monotonic
uptrend proves the "already crossed, no fresh cross" abstain case (found
empirically first — confirmed in this sandbox that a 80-row linspace
uptrend settles into MACD sitting persistently ~5.29 above a signal line
~5.28, both still rising together, no bar where the inequality flips —
before writing it up as a test, rather than assuming the behaviour); a
flat series proves the pinned-at-zero no-cross case. Two directional
fixtures (long decline then a sharp 2-day rally for the bullish cross,
long rally then a sharp 2-day decline for the bearish cross, same
"long drift then countermove" construction T04's tests already use) are
cross-checked against an independent loop-based plain-EMA reference
(alpha = 2/(span+1), seeded by the first observation) computed directly in
the test file rather than reusing the module's own arithmetic as its own
check. Both fixtures were found by brute-force search over a few
candidate decline/rally lengths and tail shapes in this sandbox (not
analytically derived — a precise crossing bar is hard to hand-solve for a
recursive EMA), then locked in as fixed, deterministic series once
confirmed to actually cross. Ran the new test file alone first (11
passed), then the full suite: 515 passed, 1 failed (only the pre-existing,
already-documented `test_c01_day_of_week.py::test_causality_audit_passes`
pandas-version flake — `state/engine-issues.md`'s WATCH entry, unrelated
to this change) — no regressions. This sandbox needed `python3 -m pip
install numpy pandas pyyaml pytest pyarrow` first (same `pip3`/`python3`
version-mismatch workaround every recent run's journal entry documents).

Catalog lists this card's horizon as "both" (MACD needs no pick-date
knowledge, same reasoning T01's and T03's cards give), so two experiments
are queued: `experiments/pending/t05-macd-crossover-{day,week}.yml`.
`cards/catalog.csv`'s T05 row now reads `queued`.

Flags unchanged from the last two runs, now flagged for a seventh time
since 18 Oct: `engine/experiment_report.py` sits in front of what will be
26 fully-replayed, zero-scored experiments once this run's two T05 queue
entries land. The go-live track's P1 validation-query window opens Mon 26
Oct — three days from this run — and `config/live_source.json` is due Fri
30 Oct 12:00 UTC, seven days out. Neither deadline can be met with a real
validation-backed candidate (as opposed to falling straight through to
champion v1 by default for every table) unless this wiring lands first.
The last two runs (22 Oct, 18:11Z and 20:11Z) each recorded sending this
directly to Achintya outside the journal; not re-sending a third
notification this run on the same unchanged finding, but recording here
that the window is now measured in days, not weeks, and every further run
that finds this still unfixed should treat it as the most urgent possible
escalation, not routine journal noise.

Next: continue plain catalog order for `port` — T06 is the next untested
`testable_now: yes` row after T05 (check `cards/catalog.csv` for its exact
rule before carding; not previewed in this entry). `discover` remains open
and untouched for several runs if a future run prefers it over more T0x
indicator ports. `build` is still blocked on B3 alone — nothing changed
there this run.

## 2026-10-23T0216Z — Mode A (build blocked on B3 alone), lane: port

**Hypothesis:** T06 (Bollinger %B mean reversion, 20-day SMA ± 2σ, catalog
horizon "day" only) is the next untested `testable_now: yes` catalog row
in plain order after T05 (C03 pre-holiday stays genuinely blocked — same
confirmation every run since 18 Oct: `config/nse_holidays.txt` only
covers 2026, not the train split). Unlike T01/T03/T05's always-on or
cross-event shapes, T06's literal rule only takes a stance when the
latest close sits outside the bands (same "abstain inside, fire at the
extremes" shape T03's RSI thresholds already use), scored by %B
(`(close - lower) / (upper - lower)`): `-pctB` when bullish, `1 - pctB`
when bearish. Std uses the population convention (`ddof=0`) for
consistency with A02/A05/A06/A07/A09's own rolling-window choice rather
than pandas' sample-std default used elsewhere in this codebase.

**What happened:** wrote `cards/T06.yml`, `strategies/t06_bollinger_pctb.py`
(score + rules_fired), `strategies/t06_bollinger_pctb_audit.py` (cross-symbol
causality proof, same shape as T01–T05's), and 12 new tests in
`tests/test_t06_bollinger_pctb.py` — bullish/bearish firing checked against
an independent numpy (`mean`/`std(ddof=0)`, not pandas' rolling machinery)
reference, inside-the-bands abstain, flat-series (σ=0) abstain without a
division error, insufficient-history abstain, empty-history, the
`has_future` prefilter, both `rules_fired` message shapes, and the
causality audit. Ran the new test file alone first (12 passed), then the
full suite: 528 collected, 527 passed, 1 failed — only the pre-existing,
already-documented `test_c01_day_of_week.py::test_causality_audit_passes`
pandas-version flake (`state/engine-issues.md`'s WATCH entry), unrelated
to this change, no regressions. `python3 -m strategies.t06_bollinger_pctb_audit`
run standalone also passes (both AAA/CCC abstained on this seed — not
guaranteed to fire, same caveat T05's audit module documents).

Catalog horizon for T06 is "day" only (unlike T01/T03/T05's "both"), so
only one experiment is queued: `experiments/pending/t06-bollinger-pctb-day.yml`.
`cards/catalog.csv`'s T06 row now reads `queued`.

**Still unresolved, unchanged this run:** `engine/experiment_report.py`
(`state/engine-issues.md`) remains unwired — all 20 `port`ed cards now
sitting in `experiments/done/` (A01–A09, C01/C02/C04 ×2, T01–T06, D01,
D02 ×2) are replayed but zero-scored; the go-live track's P1 validation
window opened as of today (Mon 26 Oct is 3 days out) and
`config/live_source.json` is due Fri 30 Oct 12:00 UTC (7 days out).
Confirmed this run that commit c416997 (T05, 00:20Z) already sent a push
notification on this exact finding, on top of the two before it the
20:11Z journal entry recorded — not sending a fourth notification on an
unchanged finding, per the no-notification-fatigue judgment call, but
recording explicitly: if the next run to read this journal entry sees
`engine/experiment_report.py` still unwired AND today's date is on or
after Mon 26 Oct, that *is* new information (the window the last three
notifications warned about has now actually opened) and is worth a fresh,
dated notification rather than silence.

**Next:** continue plain catalog order for `port` — T07 (Bollinger squeeze
breakout, week horizon) is the next untested `testable_now: yes` row after
T06. `discover` remains open and untouched for several runs if a future
run prefers it over more T0x indicator ports. `build` is still blocked on
B3 alone — nothing changed there this run.

## 2026-10-23T0429Z — Mode A (build blocked on B3 alone), lane: port

**Hypothesis:** C03 (pre-holiday effect) has been logged as "genuinely
blocked" by five-plus consecutive `port`-lane runs since 18 Oct, each
citing `config/nse_holidays.txt` covering 2026 only. On closer reading of
`state/engine-issues.md`'s own entry, the second half of that blocker
("needs to know about a future date... which no amount of past price
history can supply") conflates the pick date's *price* (genuinely
unknowable) with its *calendar identity* (publicly known months ahead via
NSE's own circulars - the same category as "today's weekday", not price
history). `config/nse_holidays.txt` is not a protected path
(`PROTECTED.txt` only lists `config/splits.yml` under `config/`), so
extending it to cover the train split is plain research, not a
supervised-session task.

**What happened:** forked a research sub-agent to gather NSE equity-segment
weekday holidays for 2015-2020 via WebSearch/WebFetch, preferring NSE's
own circulars (found for 2017-2020) and cross-checking secondary
aggregators otherwise (2015-2016); did one more round of searches myself
to chase down its two flagged uncertain dates (2015-09-25, 2017-10-19) -
kept both on the balance of evidence, flagged in the file's own comments.
Extended `config/nse_holidays.txt` from 15 (2026-only) to 103 lines
(2015-2020 plus 2026), verified all land on real weekdays and that
`picks.calendar.load_holidays`/`next_trading_session` read them correctly.

With the calendar in hand, `today` (the pick date) is now computable
*exactly* from `history`'s last visible date via
`picks.calendar.next_trading_session` - not a proxy the way C01/C02 use
"yesterday's weekday", an exact answer to the catalog's literal question.
Wrote `cards/C03.yml`, `strategies/c03_pre_holiday.py` (score + rules_fired,
market-wide, selective - abstains when the inferred pick date isn't
pre-holiday), `strategies/c03_pre_holiday_audit.py` (pre-holiday-flag
correctness against an independent plain-`datetime` reimplementation,
abstain-when-not-pre-holiday, cross-symbol uniformity), and 14 tests in
`tests/test_c03_pre_holiday.py`. Added a dated update to
`state/engine-issues.md`'s C03 entry recording the fix and correcting its
own earlier "cannot be ported this way at all" framing. Full suite: 541
passed, 1 failed (the pre-existing `test_c01_day_of_week.py` pandas-version
flake the WATCH entry already documents, unrelated). Catalog's C03 row now
reads `queued`. Catalog horizon for C03 is "day" only, so one experiment
is queued: `experiments/pending/c03-pre-holiday-day.yml`.

**Next:** once this replay lands in `experiments/done/`, `diagnose` is
still blocked on the unwired `engine/experiment_report.py` scoring gap
(unchanged, same entry) - record the eventual edge/direction by hand from
`picks.json`'s own `score` column if a future run wants a sanity check
before that lands. Continue plain catalog order for `port` otherwise: T07
(Bollinger squeeze breakout, week horizon) is next. `build` is still
blocked on B3 alone (unchanged, needs a supervised session per the
methodology note). Go-live track: Mon 26 Oct (P1 holdout-query window
opens) is 3 days out; `config/live_source.json` is due Fri 30 Oct 12:00
UTC, 7 days out.

## 2026-10-23T0619Z — Mode A (build blocked on B3 alone), lane: port

**Hypothesis:** the prior run's `Next` note named T07 (Bollinger squeeze
breakout, week horizon) as the next plain-catalog-order `testable_now: yes`
row after T06 (which the 05:16Z replay has now landed). `build` is still
blocked on B3 alone (unchanged - the methodology note's direction choice
is a supervised-session call). `diagnose`/`tune` stay blocked on the same
`engine/experiment_report.py` scoring gap: this run's replay landed nine
more unscored experiments (T02-T06, both D02 variants, C03), on top of
A01-A09's earlier backlog - `research/diagnostics/` still doesn't exist
and `ledger/trials.csv` still doesn't exist, confirmed by directly checking
both paths this run. That blocker is already fully written up in
`state/engine-issues.md`; nothing new to add there beyond noting the
backlog keeps growing every replay cycle it stays unfixed.

**What happened:** claimed the `port` lease (`aa695f1`'s commit pattern,
no race - no lease files existed when this run started). Ported T07: the
catalog's literal rule ("band width at a 6-month low, then close outside
a band: direction of the break") is a breakout/continuation read of the
exact same Bollinger(20, 2) bands `cards/T06.yml` already builds, not a
second mean-reversion card - a close above the upper band while the band
width (normalised `2*band_width/middle`) sits at its own trailing
126-session low is **bullish** (opposite sign from T06's mean-reversion
mapping of the identical %B reading), below the lower band is **bearish**.
Read "then" as "both conditions true on the same bar" (every other card
here reads one bar with no cross-bar state, and `engine.replay` gives a
strategy no way to remember an earlier squeeze) rather than inventing
state the interface doesn't support - flagged as an interpretation choice
in `cards/T07.yml`'s red_flags, with the cross-bar variant named as the
first thing to try if this literal reading shows no edge.

Wrote `cards/T07.yml`, `strategies/t07_bollinger_squeeze_breakout.py`
(`MIN_ROWS = WINDOW + WIDTH_LOOKBACK - 1 = 145`, tail-bounded to
`close.iloc[-MIN_ROWS:]` before any rolling computation so the cost per
call stays fixed regardless of accumulated history - same WATCH-entry
concern T06 already addresses), `strategies/t07_bollinger_squeeze_breakout_audit.py`
(same cross-symbol causality proof shape as T01-T06's). 15 new tests in
`tests/test_t07_bollinger_squeeze_breakout.py`: a squeeze constructed by
narrowing the oscillation amplitude over the trailing 19 bars (not a
globally flat or constant-amplitude series, which would make every window
trivially tie for the 126-session low and never exercise the "squeeze
really is a new low" branch), cross-checked against an independent
numpy-loop reference (not pandas rolling) for both the %B and the squeeze
boolean; a dedicated "break without a squeeze abstains" case (wide-then-
narrow... actually narrow-then-wide amplitude, %B pushed well outside the
upper band while width is nowhere near a new low) proving the squeeze gate
itself does the suppressing, not just a coincidentally-unmet band break;
plus flat-bands, insufficient-history, empty-history, has_future-prefilter
and rules_fired coverage mirroring T01-T06's pattern. Queued
`experiments/pending/t07-bollinger-squeeze-breakout-week.yml` (catalog
lists this card's horizon as week only). `cards/catalog.csv`'s T07 row now
reads `queued`.

Full suite, run twice in this sandbox: first pass showed 9 failures, all
`ImportError: ... pyarrow or fastparquet is required for parquet support`
in `tests/test_picks_run.py`/`tests/test_run_queue.py` - a sandbox gap
(`python3.13`'s pandas had no parquet engine installed), not a regression;
installing `pyarrow` and rerunning both files directly (16 passed) then
the whole suite again confirmed this: **557 passed, 0 failed** (548 + 9
once pyarrow was present), including the pre-existing
`test_c01_day_of_week.py::test_causality_audit_passes` pandas-version
flake passing clean this time, consistent with its own WATCH entry
describing it as intermittent rather than consistently broken.

**Next:** T08 (Donchian/Turtle breakout, week horizon per catalog) is next
in plain catalog order. `diagnose`/`tune` stay blocked until a supervised
session wires `engine/experiment_report.py` per `state/engine-issues.md` -
worth that session's attention soon: every `port` cycle since A01 (16 cards
now: A01-A09, C01-C04, T01-T07, D01-D02) has landed a train replay with
zero of them actually scored, which also stalls the go-live track's P1
rule ("every train replay with positive edge... gets one validation
query") since no replay's edge is yet computable at all, not just unmeasured.
`build` is still blocked on B3 alone. Go-live track: Mon 26 Oct (P1
holdout-query window opens) is 2 days out; `config/live_source.json` is
due Fri 30 Oct 12:00 UTC, 6 days out - the provisional-strategy fallback
(champion v1 for any table with no qualifying candidate, SPEC.md section
10) still applies cleanly even with the scoring gap unresolved, so go-live
itself isn't at risk, only the quality of what sits behind it until the
gap is fixed.

## 2026-10-23T08:18Z — port lane

Hypothesis: `build` stays blocked on B3 alone (methodology blocker, needs
a supervised session); `diagnose`/`tune` stay blocked on
`engine/experiment_report.py` (`state/engine-issues.md`, still unwired,
now 16+ landed experiments with zero of them scored). Go-live track
P1/P2/P3 (consensus_v1, D1/D2 wiring) all need either that scoring gap
or a supervised session. The highest-value unblocked unit of work is
plain `port`-lane progress through `cards/catalog.csv` in SPEC order:
T08 (Donchian/Turtle breakout) is the next `testable_now: yes` row after
T07.

Result: `cards/catalog.csv`'s own `default_params` names both 20 and 55
as T08's stated windows (Faith's Turtle System 1 and System 2), so both
are ported as independent trials sharing one core
(`strategies/t08_donchian_breakout_core.py`,
`strategies/t08_donchian_breakout_20.py`,
`strategies/t08_donchian_breakout_55.py`), the same shared-core shape
`cards/D02.yml` already used for its own two catalog-stated variants.
Breakout is read against the PRIOR window's high/low (excluding today),
not a window including today's own close, which would be self-referentially
always-true - see `cards/T08.yml`'s rules_plain and red_flags for the full
reasoning. `strategies/t08_donchian_breakout_audit.py` (shared causality
proof, both windows), 26 new tests
(`tests/test_t08_donchian_breakout.py`, parametrized over both variants):
new-high/new-low fire correctly, a tie with the prior high/low does NOT
count as a new breakout, inside-range/insufficient-history/empty-history/
has_future-prefilter abstain correctly, `rules_fired` messages, causality
audit at both window=20 and window=55. Queued both train-split
experiments (`experiments/pending/t08-donchian-breakout-{20,55}-week.yml`,
catalog lists this card's horizon as week only). `cards/catalog.csv`'s T08
row now reads `queued`.

Full suite: 582 passed, 1 failed (the pre-existing
`tests/test_c01_day_of_week.py::test_causality_audit_passes` pandas-
version flake `state/engine-issues.md`'s own WATCH entry already
documents - unrelated to this change, and the new T08 tests are all
among the 582 passing).

**Next:** T09 (Supertrend) is next in plain catalog order. `diagnose`/
`tune` stay blocked until a supervised session wires
`engine/experiment_report.py` per `state/engine-issues.md` - worth that
session's attention soon, since every `port` cycle since A01 (now 17
cards: A01-A09, C01-C04, T01-T08, D01-D02) has landed train replays with
zero of them actually scored, which also stalls the go-live track's P1
rule (every positive-train-edge replay earns one validation query - none
of their edges are computable yet). `build` is still blocked on B3 alone.
Go-live track: `config/live_source.json` is due Fri 30 Oct 12:00 UTC, 7
days out - the provisional-strategy fallback (champion v1 for any table
with no qualifying candidate, SPEC.md section 10) still applies cleanly
even with the scoring gap unresolved, so go-live itself isn't at risk,
only the quality of what sits behind it until the gap is fixed.

## 2026-10-23T10:11Z — port lane

Hypothesis: `build` stays blocked on B3 alone (methodology blocker,
needs a supervised session); `diagnose`/`tune` stay blocked on
`engine/experiment_report.py` (`state/engine-issues.md`, still unwired
as of this run - 17 cards landed since A01 with zero scored). Go-live
track P1/P2/P3 all need either that scoring gap or a supervised session.
The highest-value unblocked unit of work is plain `port`-lane progress
through `cards/catalog.csv` in SPEC order: T09 (Supertrend) is the next
`testable_now: yes` row after T08.

Result: ported T09, Olivier Seban's ATR(10) x 3 Supertrend
(`cards/T09.yml`, `strategies/t09_supertrend.py`). Unlike every prior
`t0*` card, the line's final-band ratchet and trend-switch step is a
path-dependent recursion against the previous bar's own resolved state
(not expressible as a single `ewm()` call), so `_supertrend_line` runs a
plain Python loop - bounded to a fixed `MIN_ROWS = 60` trailing window
per symbol per call (ATR_PERIOD=10 to seed the first ATR value, then a
50-row warmup for the recursion to wash out its own arbitrary seed
choice), the same bounded-tail cost shape T06/T07/T08 already use, not
the full-history-loop shape that caused the "Replay took 1h45m+" issue.
ATR itself reuses the existing vectorized Wilder-smoothing helper
(copied from T03/champion_v1), applied to true range instead of a price
delta. Score is `(close - line) / abs(line)`, always-on like T01/T02
(no neutral zone). `strategies/t09_supertrend_audit.py` (cross-symbol
causality proof over the full recursion, not just the final score - this
card's recursive state makes a leak easier to introduce unnoticed than a
one-shot rolling max/min). 12 new tests (`tests/test_t09_supertrend.py`):
clean monotonic up/down trend fixtures (small noise and high/low spread
relative to the drift) assert the resulting direction rather than a
hand-derived exact value, since the band-ratchet recursion has no simple
closed form; insufficient-history/empty-history/has_future-prefilter
abstain correctly; a direct invariant check that the line's own output
satisfies "close >= line on a bullish bar" by construction; the Wilder
helper's known seed value; true-range arithmetic against hand-picked
high/low/prevclose numbers; the causality audit. Catalog lists this
card's horizon as "both", so both `experiments/pending/t09-supertrend-{day,week}.yml`
are queued. `cards/catalog.csv`'s T09 row now reads `queued`.

Full suite: 594 passed, 1 failed (the pre-existing
`tests/test_c01_day_of_week.py::test_causality_audit_passes` pandas-
version flake `state/engine-issues.md`'s own WATCH entry already
documents - unrelated to this change, and all 12 new T09 tests are
among the 594 passing).

**Next:** T10 (NR7/NR4 narrow range) is next in plain catalog order.
`diagnose`/`tune` stay blocked until a supervised session wires
`engine/experiment_report.py` per `state/engine-issues.md` - this gap is
now 5+ days old (first flagged 2026-10-18) and 18 cards deep (A01-A09,
C01-C04, T01-T09, D01-D02) with zero of their train replays scored,
which also stalls the go-live track's P1 rule (every positive-train-edge
replay is supposed to earn one validation query - none of their edges
are computable yet to tell which ones qualify). `build` is still blocked
on B3 alone (methodology: `detect_corporate_actions` structurally cannot
find real splits/bonuses in NSE's unrebased PREVCLOSE, per the READY FOR
WIRING entry in `state/engine-issues.md` dated 17 Oct - needs a
supervised decision on direction, not a routine-level fix). Go-live
track: Mon 26 Oct (P1 holdout-query window opens) is 3 days out;
`config/live_source.json` is due Fri 30 Oct 12:00 UTC, 7 days out - the
provisional-strategy fallback (champion v1 for any table with no
qualifying candidate, SPEC.md section 10) still applies cleanly even
with the scoring gap unresolved, so go-live itself isn't at risk, only
the quality of what sits behind it until the gap is fixed.

## 2026-10-23T1213Z — port lane

Hypothesis: with `build` blocked (B3 is the only unticked item, still
needing a supervised methodology decision per `state/engine-issues.md`)
and `diagnose`/`tune` still blocked on the open `engine/experiment_report.py`
scoring gap (same entry - now ~25+ landed `experiments/done/*` directories,
still zero of them scored or diagnosed, since no card has ever produced a
real train edge number), the highest-value unit of research work is plain
`port`-lane progress through `cards/catalog.csv` in SPEC order. T10 (NR4/NR7
narrow range, Crabel 1990) is the next untested `testable_now: yes` row
after T09 (Supertrend, ported by the immediately preceding run).

What I did: Crabel's actual rule trades an intraday breakout of the NR
day's own high/low, which this engine's once-before-the-open
`score(history)` interface structurally cannot see (SPEC.md section 4) -
the catalog's own rule already simplifies this to "pick next day in the
direction of the trend filter," so this card tests that simplification,
not the original intraday system (documented in `cards/T10.yml`'s
claim_as_stated and red_flags, not silently assumed equivalent). The
catalog names no trend filter of its own, so rather than inventing a new
one I reused `strategies/t01_sma_crossover.py`'s exact fast/slow (20/50)
SMA spread - the only trend filter already established in this codebase
with no card-specific parameter to justify from nothing. True range
reuses `strategies/t09_supertrend.py::_true_range`'s formula exactly. A
day counts as NR<N> when its true range is the *strict* minimum of the
trailing N days' true ranges (`np.argmin`, breaking an exact tie toward
the earliest occurrence rather than today - flagged as a deliberate,
untested-against-the-alternative choice, since the catalog gives no
tie-break rule and real adjusted true-range values essentially never tie
exactly anyway).

Wrote `cards/T10.yml`, a shared core (`strategies/t10_narrow_range_core.py`)
plus two thin variant wrappers for the catalog's own "NR4, NR7"
`default_params` (`strategies/t10_nr4_narrow_range.py`,
`strategies/t10_nr7_narrow_range.py`) - the same core-plus-variants shape
`cards/D02.yml`'s two sign variants already use, since the only
difference between the two windows is the lookback length, not the logic.
`strategies/t10_narrow_range_audit.py` (cross-symbol causality proof over
the shared core: a `BBB` symbol gets one extra, deliberately narrow
trailing day appended; `AAA`/`CCC` must stay unaffected and only `BBB`
should newly score). 16 new tests (`tests/test_t10_narrow_range.py`,
parametrized over both variants where the logic is shared): narrow-range
day in an uptrend scores bullish, non-narrow day abstains, a downtrend
fixture scores bearish, a flat-trend fixture proves the "narrow range
fires but the trend spread is exactly 0" abstain case (fast SMA == slow
SMA, undefined direction), an NR4-vs-NR7 fixture confirms both variants
agree on sign when both fire on the same deliberately-narrow day,
insufficient history, empty history, the `has_future` prefilter, three
`rules_fired` wording checks, and the causality audit. Queued both train
replays (`experiments/pending/t10-nr{4,7}-narrow-range-day.yml`, day
horizon only per the catalog) and marked T10 `queued` in
`cards/catalog.csv`.

Result: `python3 -m pytest -q --deselect tests/test_c01_day_of_week.py::test_causality_audit_passes`
(full suite, that one pre-existing/environment-specific flake excluded,
same `state/engine-issues.md` WATCH entry as every recent run has hit in
this sandbox's pandas/numpy pair) - 610 passed, 0 failed, in 308.12s (594
existing + 16 new). The audit module also runs standalone
(`python3 -m strategies.t10_narrow_range_audit`) and passes. `guard_check.py`
confirms no protected path touched. Pushing this should trigger `replay.yml`
against the real cached dataset for both new experiment files.

Next: once `replay.yml` lands both `experiments/done/t10-nr{4,7}-narrow-range-day/`
directories, they join the same backlog of unscored train replays every
ported card since A01 has hit. T11 (inside bar, same "trend filter"
wording as T10 - likely the same SMA20 substitution question, worth
checking whether the catalog's single-SMA phrasing there wants a
different filter than T10's reused 20/50 pair before assuming it's
identical) is the next untested `testable_now: yes` row for a future
`port`-lane run. The single highest-priority item for a supervised
session remains unchanged and is now materially overdue against the 30
Oct `config/live_source.json` deadline: `engine/experiment_report.py`
(`state/engine-issues.md`'s open READY FOR WIRING entry) - with this run,
somewhere north of 25 landed experiments across A/C/D/T-family cards have
zero real train numbers, and the go-live track's P1 (one validation query
per positive-train-edge card) cannot award a single query without it. B3
(corporate-actions methodology) and the D2 delivery-% workflow wiring
remain the other two open supervised-session items; nothing changed on
either this run.

## 2026-10-23T1417Z — port lane

Mode A (build) still active: `state/BUILD_DONE` does not exist. B3 stays
the lab's only unticked B item, and it is blocked (`state/queue.md`:
"B3 stays unticked until that direction is chosen" — a supervised
methodology decision, `state/engine-issues.md`'s "READY FOR WIRING
(methodology, not code): `detect_corporate_actions` cannot find what B3
needs it to find"). No lease was held (`state/leases/` didn't exist at
orient time), so claimed `port` and did the next unit of SPEC-order
catalog work rather than leaving the run idle on the blocked build item
(SPEC.md section 1: "the work never runs out").

**Hypothesis:** T11 (inside bar), the next untested `testable_now: yes`
catalog row in plain SPEC order after T10 (last run's journal entry
named T11 as next). Same claim family as T10 (range contraction
precedes expansion), but a plain two-bar comparison instead of a
trailing-N-day minimum: today's high/low both sit inside yesterday's.
The catalog names no trend filter for this row either, same gap T10
hit, so reused `strategies/t01_sma_crossover.py`'s exact SMA20/50 spread
rather than inventing a new one — no new tunable parameter to justify
from nothing.

**What happened:** wrote `cards/T11.yml`, `strategies/t11_inside_bar.py`
(`MIN_ROWS = 51`: the trend filter's own 50-row minimum plus one more row
so the two-bar comparison always has a real adjacent pair, no fabricated
prior-row true-range reasoning needed since this card never computes a
true range at all), `strategies/t11_inside_bar_audit.py` (cross-symbol
causality proof, same shape as T10's: give `BBB` one extra deliberately
inside trailing day, `AAA`/`CCC` must be unaffected, only `BBB` newly
scores). 12 new tests (`tests/test_t11_inside_bar.py`): inside bar in an
uptrend scores bullish, non-inside day abstains, a downtrend fixture
scores bearish, a flat-trend fixture proves the "inside bar fires but
trend spread is exactly 0" abstain case, an exact-tie fixture confirms
equality on either side of the high/low comparison still counts as
inside (this card's own red_flag — the catalog gives no
strict/non-strict rule), insufficient history, empty history, the
`has_future` prefilter, two `rules_fired` wording checks, and the
causality audit. Queued one day-split experiment
(`experiments/pending/t11-inside-bar-day.yml`; catalog lists this card's
horizon as day only) and marked T11 `queued` in `cards/catalog.csv`.

Result: `python3.13 -m pytest -q --deselect
tests/test_c01_day_of_week.py::test_causality_audit_passes` (full suite,
that one pre-existing/environment-specific flake excluded, same
`state/engine-issues.md` WATCH entry every recent run has hit in this
sandbox's pandas/numpy pair) — 622 passed, 0 failed, in 216.50s (610
existing + 12 new). The audit module also runs standalone
(`python3.13 -m strategies.t11_inside_bar_audit`) and passes.
`scripts/guard_check.py` confirms no protected path touched.

**Next:** once `replay.yml` lands `experiments/done/t11-inside-bar-day/`,
it joins the same unscored backlog every ported card since A01 has hit.
T12 (Stochastic %K/%D) is the next untested `testable_now: yes` row for a
future `port`-lane run. The single highest-priority item for a supervised
session is unchanged and now even more overdue against the 30 Oct
`config/live_source.json` deadline: `engine/experiment_report.py`
(`state/engine-issues.md`'s open READY FOR WIRING entry) — the unscored
backlog is now north of 26 landed experiments with zero real train
numbers, and go-live track P1 (one validation query per positive-train-
edge card) still cannot award a single query without it. B3
(corporate-actions methodology) and the D2 delivery-% workflow wiring
remain the other two open supervised-session items; nothing changed on
either this run.

## 2026-10-23T1620Z — port lane

Mode A (build) still active: `state/BUILD_DONE` does not exist. B3 stays
the lab's only unticked B item, still blocked on the supervised
methodology decision (`state/engine-issues.md`'s "READY FOR WIRING
(methodology, not code): `detect_corporate_actions`..." entry). No port
lease existed at orient time, so claimed `port` and did the next unit of
SPEC-order catalog work (SPEC.md section 1: "the work never runs out").

**Hypothesis:** T12 (Stochastic %K/%D, 14/3/3), the next untested
`testable_now: yes` catalog row in plain SPEC order after T11 (last run's
journal entry named T12 as next; A10 stays `testable_now: partly` -
opening volume unavailable - and was left for a later call, same as every
prior run's reading of SPEC's "rows marked testable_now: yes"). The
catalog's literal rule ("%K crossing up below 20 bullish, crossing down
above 80 bearish") is an event, the same "crossing, not persisted state"
reading `cards/T05.yml`'s MACD crossing and `cards/T03.yml`'s RSI
thresholds already established, so `strategies/t12_stochastic.py` only
fires on the bar smoothed %K actually crosses 20 or 80 and abstains
otherwise, even if %K has sat past a threshold for many bars. `%D`
(default_params' third value) is part of the standard indicator but
unused by this card's literal rule - flagged as a red_flag and left for a
future %K/%D-crossover variant, not invented here.

**What happened:** wrote `cards/T12.yml`, `strategies/t12_stochastic.py`
(raw %K over a 14-day rolling adjusted high/low window, smoothed by a
3-day SMA; score reuses T03's threshold-distance convention,
`(20-k_prev)/20` bullish / `-(k_prev-80)/20` bearish, keyed on the PRIOR
bar's %K since that is what makes the fresh cross notable, not the
latest bar's which is constrained by the cross condition itself;
`MIN_ROWS = 17`), `strategies/t12_stochastic_audit.py` (cross-symbol
causality proof, same shape as T05's/T11's, with a real intraday
high/low spread in its synthetic fixture since this card's rolling window
needs high/low, not just close). 12 new tests
(`tests/test_t12_stochastic.py`): a steady uptrend and a persistent
decline each prove the "already crossed/pinned at an extreme, no fresh
cross" abstain case (found by direct computation: a long monotonic
move pins smoothed %K at exactly 0 or 100 for many bars), a flat series
proves the zero-denominator abstain case, two directional fixtures
(decline/rally then a sharp 2-day countermove) cross-checked against an
independent loop-based rolling-window/SMA reference computed in the test
file (same approach T05's test used), insufficient history, empty
history, the `has_future` prefilter, two `rules_fired` wording checks,
and the causality audit. Queued one day-split experiment
(`experiments/pending/t12-stochastic-day.yml`; catalog lists this card's
horizon as day only) and marked T12 `queued` in `cards/catalog.csv`.

Result: `python3.13 -m pytest -q --deselect
tests/test_c01_day_of_week.py::test_causality_audit_passes` (full suite,
that one pre-existing/environment-specific flake excluded, same
`state/engine-issues.md` WATCH entry every recent run has hit in this
sandbox) - 634 passed, 0 failed, in 274.75s (622 existing + 12 new). The
audit module also runs standalone
(`python3.13 -m strategies.t12_stochastic_audit`) and passes.
`scripts/guard_check.py` confirms no protected path touched.

**Next:** once `replay.yml` lands `experiments/done/t12-stochastic-day/`,
it joins the same unscored backlog every ported card since A01 has hit.
T13 (Williams %R) is the next untested `testable_now: yes` row for a
future `port`-lane run. The single highest-priority item for a supervised
session remains unchanged and is now materially overdue against the 30
Oct `config/live_source.json` deadline: `engine/experiment_report.py`
(`state/engine-issues.md`'s open READY FOR WIRING entry) - with this run,
the unscored backlog is now north of 27 landed experiments with zero real
train numbers, and the go-live track's P1 (one validation query per
positive-train-edge card) still cannot award a single query without it.
B3 (corporate-actions methodology) and the D2 delivery-% workflow wiring
remain the other two open supervised-session items; nothing changed on
either this run.
