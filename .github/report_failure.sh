#!/usr/bin/env bash
# Append a failure note to state/workflow_failures.md, where the routine reads it.
# Usage: bash .github/report_failure.sh <job-name> <log-file>
# Starts from a fresh origin/main on every try, so a broken rebase in an earlier step
# cannot take the report down with it.
set -u
name=$1 log=$2
git config user.name Achintya1311
git config user.email 67464985+Achintya1311@users.noreply.github.com
for i in 1 2 3 4 5; do
  git rebase --abort 2>/dev/null || true
  git fetch -q origin main && git reset -q --hard origin/main
  { echo; echo "## $(date -u +%FT%H:%MZ) $name failed"
    echo "Run: $GITHUB_SERVER_URL/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID"
    echo '```'; tail -n 60 "$log" 2>/dev/null || echo "(no log)"; echo '```'; } >> state/workflow_failures.md
  git add state/workflow_failures.md && git commit -qm "ci: $name failure report" && git push -q origin HEAD:main && exit 0
  sleep $((i * 10))
done
exit 1
