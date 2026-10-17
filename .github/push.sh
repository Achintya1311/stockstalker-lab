#!/usr/bin/env bash
# Commit the given paths and push to main, surviving pushes that land while the job runs.
# Usage: bash .github/push.sh "<message>" <path>...
# ponytail: -X theirs keeps this job's copy when both sides changed the same lines. Callers
# pass only files the job regenerates; append-only ledgers merge by union (.gitattributes).
# Never pass a hand-edited file.
set -u
msg=$1; shift
git config user.name Achintya1311
git config user.email 67464985+Achintya1311@users.noreply.github.com
for p in "$@"; do git add -A -- "$p" 2>/dev/null || true; done   # one missing path must not drop the rest
git diff --cached --quiet && { echo "nothing to commit"; exit 0; }
git commit -qm "$msg"
for i in 1 2 3 4 5; do
  git pull -q --rebase --autostash -X theirs origin main && git push -q origin HEAD:main && exit 0
  git rebase --abort 2>/dev/null || true
  sleep $((i * 10))
done
echo "push failed after 5 tries"; exit 1
