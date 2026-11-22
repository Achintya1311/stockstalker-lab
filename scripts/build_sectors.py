"""Build `config/sectors.csv` (design lab-requests L2, FINISH F13): one sector per stock for the desk's sector lines.

    python3 scripts/build_sectors.py --constituents ind_nifty500list.csv --checked 2026-11-22

Order of sources: the NSE Nifty 500 constituent list's `Industry` column first (NSE's file
`ind_nifty500list.csv`: Company Name, Industry, Symbol, Series, ISIN Code), then the hand-checked rows in
`config/sectors_manual.csv` for F&O stocks outside that list or renamed since. A manual row never overrides
an NSE row. Output columns: symbol, sector, source (`nifty500` or `manual`), checked (ISO date the list was read).
Coverage of the F&O universe is tested in `tests/test_sectors.py` against the latest committed live picks file.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANUAL = ROOT / "config" / "sectors_manual.csv"
OUT = ROOT / "config" / "sectors.csv"


def build(constituents: Path, checked: str, manual: Path = MANUAL) -> list[dict]:
    rows: dict[str, dict] = {}
    with open(constituents, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            sym, ind = (r.get("Symbol") or "").strip(), (r.get("Industry") or "").strip()
            if sym and ind:
                rows[sym] = {"symbol": sym, "sector": ind, "source": "nifty500", "checked": checked}
    with open(manual, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            sym = r["symbol"].strip()
            if sym and sym not in rows:
                rows[sym] = {"symbol": sym, "sector": r["sector"].strip(), "source": "manual", "checked": checked}
    return [rows[s] for s in sorted(rows)]


def write(rows: list[dict], out: Path = OUT) -> None:
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["symbol", "sector", "source", "checked"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--constituents", type=Path, required=True)
    ap.add_argument("--checked", required=True, help="ISO date the constituent list was read")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    rows = build(a.constituents, a.checked)
    write(rows, a.out)
    print(f"{len(rows)} symbols -> {a.out}")


if __name__ == "__main__":
    main()
