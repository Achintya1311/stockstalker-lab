"""Download NSE equity and F&O bhavcopy zips for a date range, politely and resumably.

The lab's history comes from NSE's own daily files rather than yfinance because
they include stocks that were later delisted or merged (no survivorship bias) and
because the F&O file says which stocks had futures on each date (point-in-time
universe). Zips are saved unmodified; parsing is a separate step.

Formats: until 2024-07-05 NSE published the old CSVs
(content/historical/EQUITIES|DERIVATIVES/YYYY/MON/cmDDMONYYYYbhav.csv.zip);
from 2024-07-08 it publishes UDiFF files (content/cm|fo/BhavCopy_NSE_*_YYYYMMDD_F_0000.csv.zip).
A 404 means there was no session that day; it is remembered in missing.txt so
reruns skip it.

Every calendar day is attempted, not just weekdays: NSE runs real, full
bhavcopy-publishing sessions on some Saturdays and Sundays - a special
live session on Union Budget day when 1 Feb falls on a weekend (e.g.
2020-02-01, 2025-02-01, 2026-02-01), the one-hour Diwali Muhurat session
(e.g. 2016-10-30, 2019-10-27, 2023-11-12), and occasional BCP/DR mock
sessions (e.g. 2024-01-20, 2024-03-02, 2024-05-18). Skipping weekends
outright left those sessions out of the dataset, which made
`scripts/adjustments.py` compare the next weekday's PREVCLOSE against the
wrong (one session too old) prior close for almost every symbol at once -
see `state/engine-issues.md` for the diagnosis that found this.

Usage:
    python scripts/fetch_bhavcopy.py --start 2015-01-01 --end 2026-10-16 --out ~/.cache/stockstalker-lab/raw
"""

from __future__ import annotations

import argparse
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

BASE = "https://nsearchives.nseindia.com/content"
UDIFF_FROM = date(2024, 7, 8)
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"
PAUSE = 0.6  # seconds between requests; NSE throttles bursts


def urls(seg: str, d: date) -> list[str]:
    mon = d.strftime("%b").upper()
    old_dir = "EQUITIES" if seg == "cm" else "DERIVATIVES"
    old = f"{BASE}/historical/{old_dir}/{d.year}/{mon}/{seg}{d:%d}{mon}{d.year}bhav.csv.zip"
    new = f"{BASE}/{seg}/BhavCopy_NSE_{seg.upper()}_0_0_0_{d:%Y%m%d}_F_0000.csv.zip"
    return [new, old] if d >= UDIFF_FROM else [old, new]


def get(url: str) -> bytes | None:
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(5 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError):
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"gave up on {url}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    missing_file = out / "missing.txt"
    missing = set(missing_file.read_text().split()) if missing_file.exists() else set()

    d, end = date.fromisoformat(a.start), date.fromisoformat(a.end)
    got = skipped = 0
    while d <= end:
        for seg in ("cm", "fo"):
            target = out / seg / str(d.year) / f"{seg}_{d:%Y%m%d}.csv.zip"
            key = f"{seg}:{d:%Y%m%d}"
            if target.exists() or key in missing:
                skipped += 1
                continue
            blob = None
            for u in urls(seg, d):
                blob = get(u)
                time.sleep(PAUSE)
                if blob:
                    break
            if blob:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(blob)
                got += 1
            else:
                missing.add(key)
                with missing_file.open("a") as f:
                    f.write(key + "\n")
        if d.day == 1 or d == end:
            print(f"{d} downloaded={got} skipped={skipped} holidays/missing={len(missing)}", flush=True)
        d += timedelta(days=1)
    print(f"done: downloaded={got} skipped={skipped} missing={len(missing)}")


if __name__ == "__main__":
    main()
