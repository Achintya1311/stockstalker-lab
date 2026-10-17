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
