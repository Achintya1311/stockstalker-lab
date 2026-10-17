"""Next-trading-session arithmetic for B9 (`state/queue.md`).

"The next session is the next weekday not in `config/nse_holidays.txt`" -
a plain weekday+holiday calendar, independent of what the cached dataset
happens to contain (the dataset's own last date is `asof`, supplied by the
caller; this module only answers "what day comes after it").
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

HOLIDAYS_PATH = Path(__file__).resolve().parent.parent / "config" / "nse_holidays.txt"


def load_holidays(path: Path = HOLIDAYS_PATH) -> set[str]:
    """ISO date strings for every weekday NSE holiday line in `path`.

    Blank lines and `#`-only comment lines are skipped; a trailing
    `  # <name>` comment on a date line is ignored.
    """
    if not path.exists():
        return set()
    out = set()
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            out.add(line)
    return out


def next_trading_session(after: str, holidays: set[str] | None = None) -> str:
    """The next calendar day after `after` that is a weekday and not a holiday."""
    holidays = load_holidays() if holidays is None else holidays
    d = date.fromisoformat(str(after)) + timedelta(days=1)
    while d.weekday() >= 5 or d.isoformat() in holidays:
        d += timedelta(days=1)
    return d.isoformat()


def iso_week(day: str) -> tuple[int, int]:
    iso = date.fromisoformat(str(day)).isocalendar()
    return (iso.year, iso.week)


def starts_new_iso_week(after: str, session: str) -> bool:
    """True iff `session` (the next trading session after `after`) falls in a
    later ISO week than `after` - i.e. `after` was that week's last trading
    day, so `session` is the new week's first trading day (SPEC.md section 1:
    a week pick is made at Monday's open). No separate "is this a Monday"
    check is needed: `session` is by construction the very next trading day,
    so a new ISO week can only have started at its own first trading day.
    """
    return iso_week(session) > iso_week(after)
