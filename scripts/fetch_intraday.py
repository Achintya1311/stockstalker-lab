"""Archive 5-minute bars for the F&O universe before Yahoo's 60-day window drops them.

Merges new bars into one parquet (restored from and saved to the Actions cache; the
bars are never committed or published, same rule as the NSE files). Writes a small
manifest of coverage that IS committed. Usage:
    python3 scripts/fetch_intraday.py --store intraday/5m.parquet --manifest state/intraday_manifest.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

UNIVERSE = Path(__file__).resolve().parent.parent / "config" / "intraday_universe.txt"
BATCH = 40


def load_symbols(path: Path = UNIVERSE) -> list[str]:
    return [s.strip() for s in path.read_text().splitlines() if s.strip() and not s.startswith("#")]


def tidy(raw: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    """yfinance's wide multi-ticker frame -> long rows: symbol, ts (IST), open..volume."""
    frames = []
    for s in symbols:
        try:
            part = raw[s + ".NS"] if isinstance(raw.columns, pd.MultiIndex) else raw
        except KeyError:
            continue
        part = part.dropna(subset=["Close"])
        if part.empty:
            continue
        part = part.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].copy()
        part.index = part.index.tz_convert("Asia/Kolkata").tz_localize(None)
        part.insert(0, "symbol", s)
        frames.append(part.rename_axis("ts").reset_index())
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def merge(old: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    """Union by (symbol, ts); on a clash the newer fetch wins (Yahoo patches late volume)."""
    if old.empty:
        return new.sort_values(["symbol", "ts"]).reset_index(drop=True)
    both = pd.concat([old, new], ignore_index=True)
    return both.drop_duplicates(["symbol", "ts"], keep="last").sort_values(["symbol", "ts"]).reset_index(drop=True)


def manifest(df: pd.DataFrame, failed: list[str]) -> dict:
    days = df.groupby(df["ts"].dt.date)["symbol"].nunique()
    return {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "rows": int(len(df)), "symbols": int(df["symbol"].nunique()),
        "first_ts": str(df["ts"].min()), "last_ts": str(df["ts"].max()),
        "sessions": int(len(days)), "symbols_per_session": {str(d): int(n) for d, n in days.tail(10).items()},
        "failed_last_run": failed,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--period", default=None, help="default: 60d when the store is new, else 5d")
    a = ap.parse_args(argv)
    import yfinance as yf  # imported late so tests need no network library

    store = Path(a.store)
    old = pd.read_parquet(store) if store.exists() else pd.DataFrame()
    period = a.period or ("5d" if len(old) else "60d")
    symbols, failed, frames = load_symbols(), [], []
    for i in range(0, len(symbols), BATCH):
        chunk = symbols[i : i + BATCH]
        try:
            raw = yf.download([s + ".NS" for s in chunk], period=period, interval="5m", group_by="ticker",
                              auto_adjust=False, progress=False, threads=True)
            got = tidy(raw, chunk)
        except Exception as exc:  # one bad batch must not lose the others
            print(f"batch {i // BATCH} failed: {exc}", file=sys.stderr)
            got = pd.DataFrame()
        frames.append(got)
        failed += [s for s in chunk if got.empty or s not in set(got["symbol"])]
    new = pd.concat([f for f in frames if len(f)], ignore_index=True) if any(len(f) for f in frames) else pd.DataFrame()
    if new.empty:
        print("no bars fetched", file=sys.stderr)
        return 1
    out = merge(old, new)
    store.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(store, index=False)
    m = manifest(out, failed)
    Path(a.manifest).write_text(json.dumps(m, indent=2) + "\n")
    print(json.dumps({k: m[k] for k in ("rows", "symbols", "sessions", "first_ts", "last_ts")}), f"failed={len(failed)}")
    return 0 if len(failed) < len(symbols) // 2 else 1


if __name__ == "__main__":
    raise SystemExit(main())
