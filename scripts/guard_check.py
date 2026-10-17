"""CI guard (B8, `state/queue.md`): fails if any path in `PROTECTED.txt` changed.

Per the lab's hard rules, the autonomous routine never edits a protected
path (`SPEC.md`, `PROTECTED.txt`, `config/splits.yml`, `engine/`, `gates/`,
`.github/`). This script is the code-enforced check `state/queue.md`'s B8
item asks for; wiring it into a required CI status check and branch
protection is `.github/` work the routine cannot do itself (see
`state/engine-issues.md`, "READY FOR WIRING: B8").

Usage: `python3 scripts/guard_check.py [--base origin/main] [--head HEAD]`.
Exits 1 and lists every protected path touched if any changed file under
`git diff --name-only <base>...<head>` matches a `PROTECTED.txt` entry;
exits 0 otherwise.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROTECTED_PATH = Path(__file__).resolve().parent.parent / "PROTECTED.txt"


def load_protected_entries(path: Path = PROTECTED_PATH) -> list[str]:
    """One entry per non-comment, non-blank line of `PROTECTED.txt`. A line
    ending in `/` protects that whole directory; any other line is an exact
    file path."""
    entries = []
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            entries.append(line)
    return entries


def is_protected(changed_path: str, entries: list[str]) -> bool:
    for entry in entries:
        if entry.endswith("/"):
            if changed_path == entry.rstrip("/") or changed_path.startswith(entry):
                return True
        elif changed_path == entry:
            return True
    return False


def find_violations(changed_paths: list[str], entries: list[str]) -> list[str]:
    return [p for p in changed_paths if is_protected(p, entries)]


def git_diff_names(base: str, head: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...{head}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="origin/main", help="base ref to diff against")
    ap.add_argument("--head", default="HEAD", help="head ref to diff")
    ap.add_argument("--protected", default=str(PROTECTED_PATH))
    args = ap.parse_args(argv)

    entries = load_protected_entries(Path(args.protected))
    changed = git_diff_names(args.base, args.head)
    violations = find_violations(changed, entries)
    if violations:
        print("guard check FAILED: protected path(s) changed:")
        for v in violations:
            print(f"  {v}")
        return 1
    print(f"guard check passed: {len(changed)} changed path(s), none protected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
