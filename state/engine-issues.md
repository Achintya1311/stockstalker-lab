# Engine / workflow issues for a supervised session

## READY FOR WIRING: B3 corporate-actions report

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

## READY FOR WIRING: `replay.yml`'s commit step can't survive two queued runs landing the same report (2026-10-17)

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
