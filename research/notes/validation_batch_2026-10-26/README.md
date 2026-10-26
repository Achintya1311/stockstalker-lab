# Validation batch for the go-live provisional rule (staged 25 Oct 2026, 20:42 UTC)

Eleven `split: validation` experiments (ten staged 25 Oct 20:42 UTC; `t05c-upcross-fade-week` added 26 Oct 00:10 UTC after its train replay landed), one per train experiment that meets SPEC.md section 10's train letter
(`research/notes/provisional_candidates.md`, written by `scripts/provisional_candidates.py`). Nothing here
has been asked yet: these files spend nothing until they are moved into `experiments/pending/`.

**When:** holdout queries for the provisional rule open Mon 26 Oct. They were staged rather than queued
because this run fell on Sunday 25 Oct in UTC (Monday only in IST), and `gates/budgets.py` counts the weekly
budget by UTC ISO week. Queue them from **00:00 UTC Mon 26 Oct** so they count against the week they belong to.

**How:** `git mv research/notes/validation_batch_2026-10-26/*-validation.yml experiments/pending/`, commit,
push. `replay.yml` answers each through Thresholdout (`engine.experiment_report.answer_validation`), logs both
sides in `ledger/holdout_queries.csv` and writes released values to `experiments/done/<id>/holdout.json`.

**Budget:** each experiment asks both sides, so up to 22 queries, against 60 for the week (checked:
`holdout_budget_remaining` = 60 for 26 Oct). For the bearish-only consensus cards the bullish side has no
train edge and is skipped, but the budget check still reserves two.

| Table | Experiments, best train edge first |
|---|---|
| day / bearish | e2a-day, d01c-day, consensus-db-v1-day, a09-gap-fade-day |
| week / bearish | t05c-upcross-fade-week, d02-stock-pcr-contrarian-week, t15-adx-regime-week, a01-weekly-reversal-week, consensus-wb-v1-week, t05-macd-crossover-week, a07c-volume-fade-week |
| day / bullish, week / bullish | none eligible: champion v1 fallback, whose `top` train edge is negative on both (`research/diagnostics/champion_v1.md`); AB decision pending |

The released validation edge decides each table (highest wins). Read the answers in the evaluate lane
before Fri 30 Oct 12:00 UTC, when `config/live_source.json` is due.

**Queued 26 Oct 2026, 00:09 UTC** (Monday in UTC): all eleven files moved to `experiments/pending/` in one commit.
