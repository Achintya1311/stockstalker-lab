"""`config/sectors.csv` (FINISH F13, design lab-requests L2): builder order and coverage of the F&O universe."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.build_sectors import build, write

ROOT = Path(__file__).resolve().parents[1]


def test_build_takes_nse_industry_first_then_manual_rows_and_never_lets_manual_override(tmp_path):
    nse = tmp_path / "n500.csv"
    nse.write_text("﻿Company Name,Industry,Symbol,Series,ISIN Code\nA Ltd.,Power,AAA,EQ,X1\nB Ltd.,Healthcare,BBB,EQ,X2\nC Ltd.,,CCC,EQ,X3\n")
    manual = tmp_path / "m.csv"
    manual.write_text("symbol,sector,note\nBBB,Realty,wrong on purpose\nZZZ,Chemicals,outside the list\n")
    rows = build(nse, "2026-11-22", manual)
    assert [(r["symbol"], r["sector"], r["source"]) for r in rows] == [
        ("AAA", "Power", "nifty500"), ("BBB", "Healthcare", "nifty500"), ("ZZZ", "Chemicals", "manual")]
    out = tmp_path / "sectors.csv"
    write(rows, out)
    assert out.read_text().splitlines()[0] == "symbol,sector,source,checked"


def test_committed_sector_map_covers_at_least_95_percent_of_the_latest_live_universe():
    with open(ROOT / "config" / "sectors.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows and all(r["sector"] and r["source"] in {"nifty500", "manual"} and len(r["checked"]) == 10 for r in rows)
    assert len({r["symbol"] for r in rows}) == len(rows)
    latest = sorted((ROOT / "live" / "day").glob("*.json"))[-1]
    universe = {s["s"] for s in json.loads(latest.read_text())["xray"]["stocks"]}
    covered = universe & {r["symbol"] for r in rows}
    assert len(covered) / len(universe) >= 0.95, sorted(universe - covered)
