# Engine / workflow issues for a supervised session

## WIRED 2026-10-17 (was READY FOR WIRING): B3 corporate-actions report

**WIRED** (supervised, 17 Oct): `dataset.yml` runs `scripts/check_corporate_actions.py` after the build whenever `reports/corporate_actions_check.md` does not exist, and commits it with the manifest. It writes once, so your cross-check edits are never overwritten; delete the file to regenerate it. What remains for B3 is yours: cross-check at least 10 events and explain the >30% jumps.

B3's acceptance (`state/queue.md`) needs an Actions run that executes
`detect_corporate_actions` against the real `data/dataset.parquet` and
writes `reports/corporate_actions_check.md`. `scripts/check_corporate_actions.py`
does this (tested on synthetic data in `tests/test_check_corporate_actions.py`;
`python3 scripts/check_corporate_actions.py --data data/dataset.parquet --out
reports/corporate_actions_check.md`), but no existing workflow runs it on
real data and commits the result:

- `dataset.yml`'s "Commit the manifest only" step only `git add`s
  `state/data_manifest.json`; it does not restore `data/dataset.parquet`
  from cache into a path the commit step would pick up as a report, and
  does not run this script at all.
- `replay.yml` already `git add -A ledger reports experiments state`, so a
  report landing in `reports/` would be committed by it automatically, but
  it only triggers on changes under `experiments/pending/**`, `strategies/**`,
  `engine/**` or `gates/**` — none of which this script's addition touches —
  and its job step runs `engine.run_queue`, not this script.

Needs one of (routine cannot edit `.github/`):
1. Add a step to `dataset.yml`, after "Build or update", that runs
   `python3 scripts/check_corporate_actions.py --data data/dataset.parquet
   --out reports/corporate_actions_check.md`, and extend the commit step's
   `git add` to include `reports/corporate_actions_check.md` alongside the
   manifest.
2. Or add a `workflow_dispatch`-only step/job that does the same, so it can
   be run on demand once the report is up to date.

Once the report exists with real detected events, a follow-up run still
needs to cross-check at least 10 of them against an independent public
source (NSE corporate announcements or news) and fill in the report's TODO
columns before B3 can be ticked — that part is manual/agent work, not
automatable, and is unblocked by this wiring.

## FIXED (no wiring needed): replay.yml silently committed nothing (2026-10-17)

Not open — recorded for context in case the same shape of bug recurs.
`replay.yml`'s commit step runs `git add -A ledger reports experiments
state` as one command over four pathspecs; `git add` aborts the *entire*
invocation if any one pathspec matches nothing on disk. `ledger/` and
`reports/` didn't exist, so every run of `engine.run_queue` computed real
output that was never staged — swallowed by the step's own
`2>/dev/null || true`, with the job still reporting green (the empty
`git diff --cached --quiet` after a no-op `add` is also a clean exit).
Fixed without touching `.github/` by adding `ledger/.gitkeep` and
`reports/.gitkeep` (neither path is in `PROTECTED.txt`); confirmed by a
real commit landing (`01b0ad6`, then `1c274e0` after a second, unrelated
fix). Full account in `state/journal.md`'s 2026-10-17T02:10Z entry.

**Still worth doing** when `.github/` is next touched: replace the single
multi-pathspec `git add -A ledger reports experiments state` with either
a per-path `git add -A -- <path>` loop or a `mkdir -p ledger reports
experiments state` immediately before it, so this class of bug can't
recur silently (e.g. if one of these four directories is ever renamed or
removed) — right now nothing would signal it; the job would just keep
reporting green while committing nothing.

## WATCH: real-data Replay run took 1h45m+ before this commit's fix (2026-10-17)

Not open as an action item for a supervised session - fixed within this
commit without needing `.github/` changes - recorded so the pattern is
recognised quickly if a future strategy hits the same wall.

`Replay` run 39017169385 (commit dc6a0a1, B7 champion v1 train-half) was
still `in_progress` at 1h45m+, versus 2-3 minutes for every earlier
`Replay` run against the same real cached dataset. Root cause: any
strategy's `score(history)` is called once per symbol per pick date by
`engine.replay.run_dates` (SPEC.md section 4's causal truncation - by
design, not a bug), so a strategy that (a) loops in pure Python instead of
vectorizing, or (b) processes every symbol `history` contains rather than
pre-restricting to symbols that could plausibly be picked, pays that cost
multiplied by thousands of dates against the real multi-year dataset -
even though it looks instant against every small/short test fixture.
`strategies/champion_v1.py` had both; this commit fixes both (vectorized
`_wilder_smooth`, `has_future` prefilter in `score()`) - see
`state/journal.md`'s entry at this timestamp for the full account and the
17.3x micro-benchmark.

Worth a general note for future strategy ports/discoveries: a strategy
that's fast on `tests/` fixtures is not proven fast at real scale. Before
trusting a `Replay` run's wall-clock as "it'll always be roughly this
long," compare it against the historical durations in the Actions run list
(`curl .../actions/runs`) - a multi-x jump versus history is a real signal
even without reading a single log line, exactly how this one was caught.

Resolved (2026-10-17T12:xxZ): run 39017169385 finished `success` at
11:49:22Z (after ~3.5h total, mostly queued/pre-fix execution time - the
fix in this same commit was never retroactively applied to it), and its
commit (`ad965e6`, "replay: results 2026-10-17T1149Z") landed
`reports/champion_v1_train.md` with sane numbers on `main`. But the run
queued behind it (39024479250, for the vectorization-fix commit itself)
then hit a *different*, new failure - see the next entry.

## WIRED 2026-10-17 (was READY FOR WIRING): `replay.yml`'s commit step can't survive two queued runs landing the same report

**WIRED** (supervised, 17 Oct):
- `replay.yml` checks out the latest `main`, not the triggering commit. That stale checkout was the root cause.
- Every workflow commits through `.github/push.sh`: per-path `git add`, then `pull --rebase --autostash -X theirs` with `rebase --abort` and 5 retries.
- Failures are reported through `.github/report_failure.sh`, which starts from a fresh `origin/main` on every try.
- `.gitattributes` merges `ledger/*.csv` by union, so concurrent appends keep both rows.
- All of this was tested on a throwaway repo before it was pushed.

`Replay` run 39024479250 (commit a19c61e9, queued behind 39017169385 in
the same `replay` concurrency group, no `cancel-in-progress`) ran
`engine.run_queue` successfully (`wrote reports/champion_v1_train.md`,
confirmed in its own log) but then failed at the commit step:

```
[main ee4858c] replay: results 2026-10-17T1208Z
 1 file changed, 59 insertions(+)
 create mode 100644 reports/champion_v1_train.md
Auto-merging reports/champion_v1_train.md
CONFLICT (add/add): Merge conflict in reports/champion_v1_train.md
error: could not apply ee4858c... replay: results 2026-10-17T1208Z
##[error]Process completed with exit code 1.
```

Root cause: this run's checkout predates 39017169385's push (both start
from the same base commit; the concurrency group only serialises *when*
each job's steps run, not when each job's checkout was taken - and
`actions/checkout@v4` only runs once, at job start, well before the
long `engine.run_queue` step). So by the time 39024479250 tries to
commit, `reports/champion_v1_train.md` already exists on `main` from
39017169385's commit - and because *this* run's local working tree never
had that file (it checked out before it existed), git sees "created
report_file" on both sides and calls it an add/add conflict, not a
clean 3-way merge, even though the two reports are near-identical
content.

That alone would just need a `git fetch && git merge` with the add/add
conflict auto-resolved toward the newer content (or a `git pull
--rebase` that actually succeeds) - but the workflow's own
failure-recovery step made it worse:

```
git reset -q --hard; git pull -q
You are not currently on a branch.
Please specify which branch you want to merge with.
##[error]Process completed with exit code 1.
```

A failed `git pull --rebase` (the commit step's own recovery attempt)
leaves the repo mid-rebase, which is a detached `HEAD` relative to any
branch ref. `git reset --hard` in that state does not reattach `HEAD` to
`main` - it just discards the rebase's partial state while *staying*
detached - so the following bare `git pull` (no remote/branch given, and
no upstream configured for a detached `HEAD`) immediately fails with "You
are not currently on a branch." The net effect: this run's whole
`replay: results` commit is silently dropped (never pushed, never
retried), and its own failure-reporting step (which runs after this
already-failed recovery, on the same detached `HEAD`) also never ran
far enough to append to `state/workflow_failures.md` - recorded there by
hand instead, from the job's log via the public API.

No data was lost (the correct, already-pushed `ad965e6` report has the
same numbers; this run's would have been identical, just not sped up for
future runs), but the pattern will recur every time two `replay.yml` runs
queue back to back in the same concurrency group and both regenerate the
same report file, which is routine (the workflow triggers on any push
touching `engine/`, `strategies/`, `experiments/pending/` or `gates/`,
and the lab makes several such pushes a day). Needs one of (routine
cannot edit `.github/`):

1. Before the commit step's `git pull --rebase`, add `git rebase --abort
   2>/dev/null || true` as the very first line of the failure-recovery
   step (so a failed rebase is actually abandoned, re-attaching `HEAD` to
   the branch, before `git reset --hard` runs) - cheapest fix, keeps the
   current rebase-based flow.
2. Or replace `git pull --rebase` with `git pull --rebase -X theirs` (or
   `-X ours`) for this specific commit step, since every file it commits
   (`ledger/`, `reports/`, `experiments/done/`, `state/leases/*.json`,
   `state/workflow_failures.md`) is either append-only or fully
   regenerated from the same inputs on every run, so either side of an
   add/add or content conflict on these specific paths is an acceptable
   resolution - there is no hand-authored content under these paths that
   `-X theirs`/`-X ours` could silently destroy.
3. Or switch the concurrency group's behaviour so only the newest queued
   `replay.yml` run actually executes the commit step when several are
   queued (closer to `cancel-in-progress`, but for the commit step only -
   a full `cancel-in-progress` would also cancel the possibly-long
   `engine.run_queue` step of a run that's actually making progress,
   which is what the original "WATCH" entry above was about).

Also worth revisiting while `.github/` is touched for this: the
failure-reporting step should run via its own fresh checkout state (e.g.
`git fetch && git reset --hard origin/<default-branch>` instead of a bare
`git reset --hard; git pull`), so a broken rebase in the commit step
can never take the failure report down with it the way it did here.

## WIRED 2026-10-17 (was READY FOR WIRING): B8 guard check, gates, budgets

**WIRED** (supervised, 17 Oct). Guard-by-restore instead of branch protection, so no repo settings change:
- `guard.yml` runs `.github/guard.sh` on every push to main. Any protected path changed by a commit without the supervised-session marker is put back as it was before the push, and the restore is logged in `state/workflow_failures.md`.
- The rules are read from the pre-push `PROTECTED.txt`, so a push cannot loosen them.
- `replay.yml` refuses to replay a push that changed protected paths.
- `engine/`, `gates/`, `.gitattributes` and `live/` are protected from now on. Put new code (B9) in `picks/`, and log engine changes here.
- `scripts/guard_check.py` stays as a local pre-push self-check.
- Budgets: no CI step yet. They are enforced in code before spending (`gates/budgets.py`). Add a CI check when the evaluate lane starts spending.

B8's acceptance (`state/queue.md`: "Write the code (`scripts/guard_check.py`,
gates, budgets, picks generator) with tests, then add a line 'READY FOR
WIRING: <item>'... A supervised session adds the workflows and branch
protection and ticks the item.") is the code side of this build item. Written
and tested this run, all on synthetic/hand-picked data - none of it needs the
real dataset or an Actions run to be correct:

- `gates/gates.py`: SPEC.md section 6's eight roster gates plus the
  high-conviction tag and the leak-alarm trigger/clear predicates, as pure
  functions over a `StrategyMetrics` dataclass (`tests/test_gates.py`).
  Gate 2's trial-corrected significance bar (`required_t`) is a Bonferroni
  correction on the single-trial t>=3 bar, parameterised by cumulative
  trial count.
- `gates/trials.py`: `ledger/trials.csv` schema (`FIELDS`) and an
  append-only `record_trial`/`cumulative_trial_count` pair — the trial
  count `gates.gates.required_t` needs (`tests/test_trials.py`). The
  ledger file itself does not exist yet; nothing has logged a real trial
  under it, so there's nothing to commit before a first real trial run
  writes it (same reasoning `ledger/holdout_queries.csv` followed before
  B7's one query).
- `gates/budgets.py`: weekly (ISO calendar week) rate limits for
  `ledger/holdout_queries.csv` (`config/splits.yml`'s
  `validation.max_queries_per_week`, currently 60) and the not-yet-created
  `ledger/test_looks.csv` (`test.max_looks_per_week`, currently 2), plus
  `record_test_look` for the latter (`tests/test_budgets.py`). Deliberately
  does not touch `engine/holdout_report.py` — its own docstring already
  says the weekly budget is B8's job, and it is B7's already-ticked,
  already-tested module; this module is what a future `evaluate`-lane
  query/look should consult *before* spending one, not a retrofit onto B7.
- `scripts/guard_check.py`: parses `PROTECTED.txt` (exact-file or
  directory-prefix entries) and fails (exit 1, lists every offending path)
  if `git diff --name-only <base>...<head>` touches any of them
  (`tests/test_guard_check.py`, including against the real `PROTECTED.txt`).

Not written this run (left for the item that needs it, so each build item
stays reviewable on its own): the "picks generator" B8/B9's acceptance note
also names is `state/queue.md` item B9's job ("Live picks JSON plus GitHub
Actions"), not B8's gates/budgets/guard scope.

Needs one of (routine cannot edit `.github/` or add branch protection):

1. A CI workflow (new, or a job added to an existing one) that runs on every
   PR/push and executes `python3 scripts/guard_check.py --base
   origin/<default-branch> --head <sha>`, failing the check on a non-zero
   exit. The script already defaults `--base` to `origin/main` and `--head`
   to `HEAD`, so a plain `python3 scripts/guard_check.py` after `actions/checkout@v4`
   with `fetch-depth: 0` (needed for the `...` merge-base diff to see
   `origin/main`) should work with no extra flags in the common case.
2. Branch protection on `main` requiring that check (plus the existing
   test suite) to pass before merge, and auto-merge configured to respect
   it — SPEC.md section 9: "Auto-merge requires green checks: tests, audit,
   protected paths untouched, budgets respected."
3. "Budgets respected" as an auto-merge condition needs a small CI step of
   its own once the `evaluate` lane actually starts spending holdout
   queries/test looks: e.g. fail the check if a PR's diff adds more rows to
   `ledger/holdout_queries.csv` or `ledger/test_looks.csv` than
   `gates.budgets.holdout_budget_remaining`/`test_look_budget_remaining`
   allowed at the time it was opened. Not written yet — no code path spends
   either budget yet (B8 only builds the check functions), so there is
   nothing real to wire against until a later build or lab run adds the
   spending side.

B8 itself stays unticked per the acceptance note above — a supervised
session ticks it once the wiring above lands and the CI check is confirmed
running green on a real PR.

## FIXED (no wiring needed): corporate-actions detector's 19,825 candidates were mostly one bug (2026-10-17)

Not open — root-caused and fixed in `scripts/fetch_bhavcopy.py` this run, no
`.github/` change needed. Recorded for context since the corporate-actions
report (`reports/corporate_actions_check.md`) is now stale and needs
regenerating once the backfill below lands.

B3's acceptance note (`state/queue.md`) said the 19,825 candidates were
implausibly high ("real splits and bonuses... should be in the low
thousands at most") and listed likely causes including "the previous row
is not the previous trading day." That one, confirmed:

`detect_corporate_actions`'s candidates cluster into ~18,000 scattered,
small (mostly 0.5-10%) per-symbol deviations (plausibly real noise/series
switches, still to investigate) plus eleven dates where **1,000+ of
~3,200 symbols all show a "corporate action" on the same single day** —
`2015-03-02` (1080), `2016-11-01` (1092), `2019-10-29` (1141),
`2020-02-03` (1304), `2020-11-17` (1198), `2023-11-13` (1341),
`2024-01-23` (1316), `2024-03-04` (1166), `2024-05-21` (1187),
`2025-02-03` (1522), `2026-02-02` (2017). No real corporate action hits
a third of the market on one day; a dataset gap does.

Checked directly against NSE's live archive (`nsearchives.nseindia.com`):
every one of these dates is the first weekday after a real NSE session
that fell on a **Saturday or Sunday** — Union Budget special trading
(1 Feb on a weekend: `cm01FEB2020bhav.csv.zip`, `BhavCopy_NSE_CM..._20250201...`,
`BhavCopy_NSE_CM..._20260201...`, and `cm28FEB2015bhav.csv.zip` from when
Budget day was still in February), Diwali Muhurat trading
(`cm30OCT2016bhav.csv.zip`, `cm27OCT2019bhav.csv.zip`,
`cm12NOV2023bhav.csv.zip`), and apparent BCP/DR mock sessions
(`cm20JAN2024bhav.csv.zip`, `cm02MAR2024bhav.csv.zip`,
`cm18MAY2024bhav.csv.zip`). F&O traded those days too (checked
`fo28FEB2015bhav.csv.zip`, HTTP 200). Spot check: on `cm_20150302.csv.zip`,
`3IINFOTECH`'s PREVCLOSE (7.95) doesn't match `cm_20150227.csv.zip`'s
CLOSE (8.2, a spurious 3% "action") but matches `cm28FEB2015bhav.csv.zip`'s
real CLOSE (7.95) exactly — the missing Saturday session, not a corporate
action.

Root cause: `scripts/fetch_bhavcopy.py`'s date loop only ever attempted
`d.weekday() < 5` (Mon-Fri), so these real sessions were never fetched —
not even attempted, let alone recorded as a 404/holiday. Every symbol
that traded that weekend session then had its dataset "previous row"
land one real session too early, so `scripts/adjustments.py`'s
`PREVCLOSE / prior CLOSE` (correct given a complete dataset) priced in
that whole weekend session's real move as a fake split/bonus ratio, for
every such symbol at once.

Fixed by attempting every calendar day (not just weekdays) in
`fetch_bhavcopy.py`; ordinary weekends with no NSE session just 404 both
URL variants and land in `missing.txt` same as a weekday holiday. Covered
by `tests/test_fetch_bhavcopy.py`. This does not touch `scripts/adjustments.py`
or `engine/` — the per-row comparison was already correct, it was starved
of rows.

**Still to do** (not this run): the fix only changes what a *future*
backfill fetches. `ledger`/`reports`/the current `data/dataset.parquet`
cache still reflect the old, weekend-less fetch. A `backfill.yml`
workflow_dispatch re-run across all years is needed to actually pull
these sessions into the cache (safe to re-run for every year, not just
the eleven dates found here, since 2017/2018/2021/2022 weren't checked
and the fetch is idempotent either way); `dataset.yml` auto-triggers on
`workflow_run: Backfill NSE history completed` and will then rebuild
`data/dataset.parquet` with the gaps closed.

Triggered this run: https://github.com/Achintya1311/stockstalker-lab/actions/runs/39049507308
(all years, `workflow_dispatch` on `main` at commit `e0f161a`). The next
run should check its status (and `dataset.yml`'s chained run after it)
before doing anything else with this entry. Only after that: delete
`reports/corporate_actions_check.md` so `dataset.yml` regenerates it,
confirm the eleven spike dates are gone (or shrunk to real ratios), and
only then do B3's real job — cross-check at least 10 of the *remaining*
events against an independent public source. The remaining ~18,000
scattered small-deviation candidates are a separate, smaller question
(EQ/BE series switches and thin-trading gaps are still plausible there)
that this run did not investigate.

## FIXED (no wiring needed): EQ/BE series gaps mistaken for corporate actions (2026-10-17)

Not open — root-caused and fixed in `scripts/adjustments.py` this run
(commit `84c6d2c`), no `.github/` change needed. Picks up where the
weekend-session fix left off: after that fix, `reports/corporate_actions_check.md`
still showed eleven-ish single dates (mostly Tuesdays) where 100-230
symbols all "acted" at once — same shape as the resolved weekend bug, one
order of magnitude smaller.

Root cause: the dataset only keeps `SERIES == "EQ"` rows (SPEC.md section
2). A symbol that trades in NSE's BE (trade-to-trade surveillance) series
on a given day has no row for that day, so `compute_adjustment_factors`'s
`groupby("symbol")["close"].shift(1)` skips straight past the gap to that
symbol's last *EQ* close — possibly weeks stale — while `PREVCLOSE` on
the row after the gap is the exchange's real, continuous previous-day
close (confirmed directly against raw NSE data: AUTOIND traded BE on
2020-08-17, close 37.40 filtered out; EQ again on 2020-08-18, PREVCLOSE
37.40 — correct and continuous — but our stale prior EQ close produced a
spurious ~2.68x "action"). Fixed by detecting the gap directly: compare
each symbol's previous dataset row's date against the whole market's
actual previous trading day; a mismatch is treated like a symbol's first
row (unadjusted, factor 1.0), not a detected event. Two new tests in
`tests/test_adjustments.py`. Full suite: 161 passed.

This also fixes `strategies/champion_v1.py`'s live price adjustment for
any symbol with BE-series history, not just the report — it calls the
same `compute_adjustment_factors`. Dropped the candidate count from
5,503 to 3 once regenerated on the real dataset (Actions run
39066804573) — see the next entry for why 3, not "low thousands," turned
out to be the real number, and why that's a bigger problem than it looks.

## READY FOR WIRING (methodology, not code): `detect_corporate_actions` cannot find what B3 needs it to find (2026-10-17)

Needs a supervised decision on direction, most likely a new data source;
not a one-line fix. B3 (`state/queue.md`) is blocked on this, not just
unticked — see below for why.

**Finding:** NSE's bhavcopy `PREVCLOSE` field does **not** get rebased on
a split or bonus ex-date. Checked directly against two confirmed, named,
real events (raw `cmDDMONYYYYbhav.csv`, not a secondary aggregator):

- **HDFCBANK, 1:2 stock split, ex-date 19-Sep-2019** (face value ₹2 → ₹1).
  18-Sep close 2187.75 (old scale). 19-Sep: `OPEN`/`CLOSE` ≈ 1100
  (correctly half, via ordinary trading), but `PREVCLOSE` = **2187.75**
  — the literal, unrebased prior close, still on the old scale. Ratio
  PREVCLOSE/prior-CLOSE = 1.0: no detection.
- **WIPRO, 1:3 bonus, ex-date 06-Mar-2019** (NSE F&O circular 33/2019,
  record date 07-Mar-2019). 5-Mar close 363.60. 6-Mar: `OPEN`/`CLOSE` ≈
  277 (correctly ~3/4 of 363.60, via ordinary trading), but `PREVCLOSE` =
  **363.60** again — unrebased. Same null result.

So the ~25-50%+ single-day move a real split or bonus causes shows up
only in that day's own `OPEN`/`HIGH`/`LOW`/`CLOSE` trading, exactly like
an ordinary large price move would — there is no exchange-side signal in
the bhavcopy columns this dataset carries that tells the two apart.
SPEC.md section 2's premise ("split and bonus adjustment factors come
from the bhavcopy's PREVCLOSE... divided by the previous day's CLOSE")
does not hold for either action type tested; `scripts/adjustments.py`
was built correctly to that premise, but the premise itself is false for
real NSE data, not a bug in how it's coded.

**What `detect_corporate_actions` *does* find instead**, confirmed on all
3 of the candidates that survive both fixes above (one real `PREVCLOSE`
jump per the whole EQ-only dataset, 2015-01-01 to the run date, is
genuinely rare):

1. **Face-value / unit changes that NSE does rebase for**: SETFGOLD's
   ₹100→₹1 face-value sub-division, confirmed against the NSE circular
   (ex-date 06-Jan-2022, ratio 0.0101 ≈ 1/100 — exact match). This is a
   real corporate action, just not a share-count split or bonus.
2. **Dividend-linked base-price adjustments** (NSE's own circular-based
   practice of nudging the base price down for a dividend above a
   threshold — separate from splits/bonuses): CARERATING's -2.84% move
   on 18-Sep-2018 plausibly lines up with a dividend aggregator lists
   around that date, though no primary NSE/BSE filing was found to
   confirm it outright.
3. **Still-unexplained small moves**: CUPID's -1.12% on the same date has
   no matching dividend, bonus or split found anywhere (its real 2018
   corporate actions — a ₹1 dividend ex-dated 19-Nov and a 1:5 bonus
   around Oct/Nov — are both on different dates with different ratios).
   Open; possibly a small adjustment no aggregator indexes, possibly a
   genuine data anomaly (not investigated further this run).

Full detail and sources in `reports/corporate_actions_check.md`'s
cross-check table (regenerated on Actions run 39066804573, after both
fixes).

**Why this blocks B3, not just leaves it short of 10 events:** the
acceptance note's ">= 10 events, independent-source cross-checked" was
written assuming the detector would keep finding genuine splits/bonuses
once the noise (weekend sessions, then series gaps) was cleaned out.
Instead, real splits/bonuses structurally cannot appear in its output at
all — there will likely never be 10 genuine split/bonus events to check
this way, no matter how much more noise gets fixed. B3 needs one of
these directions, which only a supervised session should pick (each is
a real design choice, not a bugfix):

1. **Source real corporate-action dates and ratios independently** —
   e.g. NSE's corporate-announcements archive/API (`nsearchives` hosts
   circulars; there may be a structured feed, not just PDFs — worth
   checking), or a reliable aggregator with a stable, scrapable history
   — then adjust on those directly instead of inferring from `PREVCLOSE`.
   This is new fetch infrastructure (a new `scripts/` fetcher plus
   probably a new/extended Actions workflow to cache it, similar to
   `backfill.yml`), not a change to `engine/`/`gates/`.
2. **Detect the price-side signature instead**: flag a day where a
   symbol's raw `OPEN`/`CLOSE` move is implausibly large (well past what
   `gates`'s cost model or normal volatility would explain) *and* the lot
   size or lower/upper circuit band resets, as a split/bonus candidate —
   still needs a secondary source to confirm the ratio and distinguish
   "real split" from "real 40% single-day crash," which does happen.
3. **Narrow SPEC.md section 2's own scope**: if (1) and (2) are judged
   not worth the cost given the roster only needs *adjusted* prices to
   avoid a false single-day spike at a strategy's indicators (not a
   historically-accurate corporate-action ledger), a supervised session
   could decide the cheaper fix is detecting the day of an implausible
   move and excluding/capping it from indicator inputs, rather than
   computing a true retroactive adjustment factor. This changes what
   "adjusted" means versus SPEC.md's current wording, so needs the
   SPEC.md author's sign-off, not a routine-level call.

Whichever direction is picked, it's worth revisiting `strategies/champion_v1.py`
and any future strategy's indicators for whether they've been silently
computed over 1-2 un-adjusted split/bonus days per affected symbol across
the full 2015-2026 history — likely a small number of symbol-days in
absolute terms (splits/bonuses are rare events), but worth knowing the
scale before judging it immaterial.
