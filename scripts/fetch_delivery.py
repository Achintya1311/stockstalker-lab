"""Download NSE's security-wise delivery position file (MTO) for a date range.

D03 (`cards/catalog.csv`) needs delivery percentage - the share of traded
quantity actually delivered, versus squared off intraday - which the ordinary
CM/FO bhavcopy never carries. NSE publishes it separately as a plain-text
"MTO" (Market Type of securities... the file calls itself "Security Wise
Delivery Position - Compulsory Rolling Settlement") file, one per trading
day, unzipped, at a stable URL back to at least 2015-01-02 and still live as
of this run (2026-10-19):

    https://nsearchives.nseindia.com/archives/equities/mto/MTO_DDMMYYYY.DAT

Confirmed by direct fetch against real files dated 2015-01-02, 2015-06-15,
2024-07-08/09, 2026-09-15 and 2026-10-19: the data-row shape
(`20,<sr_no>,<symbol>,<series>,<qty_traded>,<deliverable_qty>,<deliv_pct>`,
7 comma-separated fields) is identical across the whole span - one era, no
old/UDiFF split the way the main bhavcopy has (see docs/nse_formats.md).
A 404 means no session that day (weekend or holiday); remembered in
missing.txt so reruns skip it, same convention as fetch_bhavcopy.py.

This script only downloads and caches the raw files; parsing is
`scripts/build_dataset.py`'s `parse_delivery_file`/`build()`, same split as
the CM/FO fetch-vs-parse division.

Usage:
    python scripts/fetch_delivery.py --start 2015-01-01 --end 2026-10-19 --out ~/.cache/stockstalker-lab/raw
"""

from __future__ import annotations

import argparse
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

BASE = "https://nsearchives.nseindia.com/archives/equities/mto"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"
PAUSE = 0.6  # seconds between requests; NSE throttles bursts


def url(d: date) -> str:
    return f"{BASE}/MTO_{d:%d%m%Y}.DAT"


def get(u: str) -> bytes | None:
    for attempt in range(3):
        try:
            req = urllib.request.Request(u, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(5 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError):
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"gave up on {u}")


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
        target = out / "delivery" / str(d.year) / f"delivery_{d:%Y%m%d}.dat"
        key = f"delivery:{d:%Y%m%d}"
        if target.exists() or key in missing:
            skipped += 1
        else:
            blob = get(url(d))
            time.sleep(PAUSE)
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
