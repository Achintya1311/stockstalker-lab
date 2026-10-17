#!/usr/bin/env bash
# Guard (SPEC.md section 9): paths in PROTECTED.txt change only in supervised sessions.
# Usage: bash .github/guard.sh <before> <after> [--restore]
# Prints each protected path changed in before..after by a commit whose message lacks
# "[supervised]". With --restore, puts those paths back as they were at <before>, logs it
# in state/workflow_failures.md and pushes. The rules come from <before>'s PROTECTED.txt,
# so a push cannot loosen its own check.
# ponytail: the marker is an honour system (the routine and supervised sessions share one
# git identity). It stops accidental edits, not deliberate ones. Upgrade: signed commits.
set -euo pipefail
before=$1 after=$2 mode=${3:-}
git cat-file -e "$before^{commit}" 2>/dev/null || exit 0   # first push, or base not fetched
rules=$(git show "$before:PROTECTED.txt" | sed 's/#.*//; s/[[:space:]]*$//; /^$/d; s/[.]/\\./g; s|/$|/.*|; s|.*|^&$|')
bad=$(git rev-list --no-merges "$before..$after" | while read -r c; do
        git log -1 --format=%B "$c" | grep -qF '[supervised]' || git diff-tree --no-commit-id --name-only -r "$c"
      done | grep -E -f <(printf '%s\n' "$rules") | sort -u || true)
[ -n "$bad" ] || exit 0
printf '%s\n' "$bad"
[ "$mode" = --restore ] || exit 0
git config user.name Achintya1311
git config user.email 67464985+Achintya1311@users.noreply.github.com
for i in 1 2 3 4 5; do
  git rebase --abort 2>/dev/null || true
  git fetch -q origin main && git reset -q --hard origin/main
  while read -r p; do
    if git cat-file -e "$before:$p" 2>/dev/null; then git checkout -q "$before" -- "$p"; else git rm -q --ignore-unmatch -- "$p"; fi
  done <<< "$bad"
  { echo; echo "## $(date -u +%FT%H:%MZ) guard restored protected paths"
    echo "Commits in ${before:0:7}..${after:0:7} changed protected paths outside a supervised session, so they are back as they were at ${before:0:7}. Describe the change you need in state/engine-issues.md instead, then add RESOLVED <commit> under this entry."
    printf -- '- `%s`\n' $bad; } >> state/workflow_failures.md
  git add state/workflow_failures.md   # restored paths are already staged by checkout/rm
  git commit -qm "guard: restore protected paths changed in ${before:0:7}..${after:0:7}" && git push -q origin HEAD:main && exit 0
  sleep $((i * 10))
done
exit 1
