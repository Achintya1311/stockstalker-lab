"""Parse NSE bhavcopy zips (old CM/FO CSV and UDiFF) into one dataset table.

Two on-disk eras, detected from each CSV's own header (not the filename):

Old era (until 2024-07-05):
  cmDDMONYYYYbhav.csv  SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,
                       TOTTRDQTY,TOTTRDVAL,TIMESTAMP,TOTALTRADES,ISIN
  foDDMONYYYYbhav.csv  INSTRUMENT,SYMBOL,EXPIRY_DT,STRIKE_PR,OPTION_TYP,OPEN,
                       HIGH,LOW,CLOSE,SETTLE_PR,CONTRACTS,VAL_INLAKH,
                       OPEN_INT,CHG_IN_OI,TIMESTAMP

UDiFF era (from 2024-07-08), one shared schema for both segments:
  TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,XpryDt,
  FininstrmActlXpryDt,StrkPric,OptnTp,FinInstrmNm,OpnPric,HghPric,LwPric,
  ClsPric,LastPric,PrvsClsgPric,UndrlygPric,SttlmPric,OpnIntrst,
  ChngInOpnIntrst,TtlTradgVol,TtlTrfVal,TtlNbOfTxsExctd,SsnId,NewBrdLotQty,Rmks,
  Rsvd1,Rsvd2,Rsvd3,Rsvd4
  CM rows have Sgmt == "CM" and FinInstrmTp == "STK"; FO stock-future rows
  have Sgmt == "FO" and FinInstrmTp == "STF".

The equity (CM) table keeps SERIES/SctySrs == "EQ" only, per SPEC.md section 2.
The FO table is used only to mark which symbols had an active stock future
that date (`has_future`); option and index rows are dropped.

Input layout: fetch_bhavcopy.py writes <out>/<seg>/<year>/<seg>_<YYYYMMDD>.csv.zip
under whatever --out root the caller gives it (raw/2015/cm/2015/..., raw/recent/cm/2026/...),
so this script finds files by name pattern under --raw, not by directory shape.

Usage:
    python scripts/build_dataset.py --raw raw --out data/dataset.parquet \
        --manifest state/data_manifest.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

FILENAME_RE = re.compile(r"(cm|fo)_(\d{8})\.csv\.zip$")

PRICE_COLUMNS = ["date", "symbol", "open", "high", "low", "close", "prevclose", "volume", "turnover"]


def _read_zip_csv(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not names:
            raise ValueError(f"no csv member in {path}")
        with zf.open(names[0]) as fh:
            return pd.read_csv(fh)


def _filename_date(path: Path) -> str:
    m = FILENAME_RE.search(path.name)
    if not m:
        raise ValueError(f"unrecognised bhavcopy filename: {path}")
    raw = m.group(2)
    return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"


def parse_cm_file(path: Path) -> pd.DataFrame:
    """Return equity rows (date, symbol, open, high, low, close, prevclose, volume, turnover)."""
    df = _read_zip_csv(path)
    d = _filename_date(path)
    cols = set(df.columns)
    if "TOTTRDQTY" in cols:  # old CM format
        df = df[df["SERIES"].str.strip() == "EQ"]
        out = pd.DataFrame({
            "date": d,
            "symbol": df["SYMBOL"].str.strip(),
            "open": df["OPEN"].astype(float),
            "high": df["HIGH"].astype(float),
            "low": df["LOW"].astype(float),
            "close": df["CLOSE"].astype(float),
            "prevclose": df["PREVCLOSE"].astype(float),
            "volume": df["TOTTRDQTY"].astype("int64"),
            "turnover": df["TOTTRDVAL"].astype(float),
        })
    elif "FinInstrmTp" in cols:  # UDiFF
        df = df[(df["Sgmt"].str.strip() == "CM") & (df["FinInstrmTp"].str.strip() == "STK")
                 & (df["SctySrs"].str.strip() == "EQ")]
        out = pd.DataFrame({
            "date": d,
            "symbol": df["TckrSymb"].str.strip(),
            "open": df["OpnPric"].astype(float),
            "high": df["HghPric"].astype(float),
            "low": df["LwPric"].astype(float),
            "close": df["ClsPric"].astype(float),
            "prevclose": df["PrvsClsgPric"].astype(float),
            "volume": df["TtlTradgVol"].astype("int64"),
            "turnover": df["TtlTrfVal"].astype(float),
        })
    else:
        raise ValueError(f"unrecognised CM bhavcopy columns in {path}: {sorted(cols)}")
    return out.drop_duplicates(subset=["symbol"], keep="last").reset_index(drop=True)


def parse_fo_file(path: Path) -> pd.DataFrame:
    """Return (date, symbol) pairs for symbols with an active stock future that date."""
    df = _read_zip_csv(path)
    d = _filename_date(path)
    cols = set(df.columns)
    if "INSTRUMENT" in cols:  # old FO format
        df = df[df["INSTRUMENT"].str.strip() == "FUTSTK"]
        symbols = df["SYMBOL"].str.strip()
    elif "FinInstrmTp" in cols:  # UDiFF
        df = df[(df["Sgmt"].str.strip() == "FO") & (df["FinInstrmTp"].str.strip() == "STF")]
        symbols = df["TckrSymb"].str.strip()
    else:
        raise ValueError(f"unrecognised FO bhavcopy columns in {path}: {sorted(cols)}")
    return pd.DataFrame({"date": d, "symbol": symbols}).drop_duplicates().reset_index(drop=True)


def build(raw_root: Path) -> pd.DataFrame:
    cm_frames = [parse_cm_file(p) for p in sorted(raw_root.rglob("cm_*.csv.zip"))]
    fo_frames = [parse_fo_file(p) for p in sorted(raw_root.rglob("fo_*.csv.zip"))]

    prices = pd.concat(cm_frames, ignore_index=True) if cm_frames else pd.DataFrame(columns=PRICE_COLUMNS)
    futures = pd.concat(fo_frames, ignore_index=True) if fo_frames else pd.DataFrame(columns=["date", "symbol"])

    prices = prices.drop_duplicates(subset=["date", "symbol"], keep="last")
    futures = futures.drop_duplicates(subset=["date", "symbol"])
    futures["has_future"] = True

    merged = prices.merge(futures, on=["date", "symbol"], how="left")
    merged["has_future"] = merged["has_future"].fillna(False)
    return merged.sort_values(["date", "symbol"]).reset_index(drop=True)


def merge_with_existing(existing: pd.DataFrame, fresh: pd.DataFrame) -> pd.DataFrame:
    if existing.empty:
        return fresh
    if fresh.empty:
        return existing
    combined = pd.concat([existing, fresh], ignore_index=True)
    return (combined.drop_duplicates(subset=["date", "symbol"], keep="last")
                     .sort_values(["date", "symbol"]).reset_index(drop=True))


def write_manifest(df: pd.DataFrame, dataset_path: Path, manifest_path: Path) -> None:
    checksum = hashlib.sha256(dataset_path.read_bytes()).hexdigest() if dataset_path.exists() else ""
    manifest = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "rows": int(len(df)),
        "symbols": int(df["symbol"].nunique()) if not df.empty else 0,
        "date_start": str(df["date"].min()) if not df.empty else None,
        "date_end": str(df["date"].max()) if not df.empty else None,
        "sha256": checksum,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--manifest", required=True)
    a = ap.parse_args()

    raw_root = Path(a.raw)
    out_path = Path(a.out)
    fresh = build(raw_root) if raw_root.exists() else pd.DataFrame(columns=PRICE_COLUMNS + ["has_future"])

    existing = pd.read_parquet(out_path) if out_path.exists() else pd.DataFrame(columns=PRICE_COLUMNS + ["has_future"])
    final = merge_with_existing(existing, fresh)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    final.to_parquet(out_path, index=False)
    write_manifest(final, out_path, Path(a.manifest))
    print(f"wrote {len(final)} rows, {final['symbol'].nunique() if not final.empty else 0} symbols -> {out_path}")


if __name__ == "__main__":
    main()
