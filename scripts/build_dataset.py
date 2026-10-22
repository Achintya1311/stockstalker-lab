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
The FO table marks which symbols had an active stock future that date
(`has_future`) and carries that near-month (soonest-expiry) contract's open
interest, change in OI (`oi_futstk`/`oi_chg_futstk`, catalog row D01) and its
own expiry date (`expiry_futstk`, ISO string, catalog row C04 - the exchange's
own published schedule for the contract already active that date, not a
derived guess). It also carries each symbol's own near-month *option*
expiry's open interest, summed by option type across strikes
(`oi_ce_optstk`/`oi_pe_optstk`, catalog row D02's stock-level put/call OI
need); index rows (`FUTIDX`/`OPTIDX`/`IDF`/`IDO`) are still dropped
throughout, since SPEC.md section 2 restricts the universe to stocks and
their stock futures.

Input layout: fetch_bhavcopy.py writes <out>/<seg>/<year>/<seg>_<YYYYMMDD>.csv.zip
under whatever --out root the caller gives it (raw/2015/cm/2015/..., raw/recent/cm/2026/...),
so this script finds files by name pattern under --raw, not by directory shape.
fetch_delivery.py writes <out>/delivery/<year>/delivery_<YYYYMMDD>.dat (plain
text, not zipped) the same way; its rows add `deliv_qty`/`deliv_pct`
(catalog rows D02/D03) for `SERIES == "EQ"` symbols, left-joined onto the
price table so dates with no delivery file yet (not fetched, or genuinely
missing) just carry NaN instead of being dropped.

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
DELIVERY_FILENAME_RE = re.compile(r"delivery_(\d{8})\.dat$")

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
    """Return one row per (date, symbol) with an active stock future that date,
    carrying the near-month contract's open interest, change in open interest,
    and its own expiry date (catalog row C04's "expiry calendar from FO
    bhavcopy" data need - the exchange's own schedule, not a derived guess).

    A symbol can have up to three live stock-future expiries (near/next/far
    month) on the same date; D01's "near-month futures OI" convention means
    the soonest-expiry contract, so where more than one expiry is present the
    others are dropped here, not averaged or summed - same convention applies
    to which expiry date is kept.
    """
    df = _read_zip_csv(path)
    d = _filename_date(path)
    cols = set(df.columns)
    if "INSTRUMENT" in cols:  # old FO format
        df = df[df["INSTRUMENT"].str.strip() == "FUTSTK"]
        out = pd.DataFrame({
            "symbol": df["SYMBOL"].str.strip(),
            "expiry": pd.to_datetime(df["EXPIRY_DT"].str.strip(), format="%d-%b-%Y"),
            "open_int": df["OPEN_INT"].astype(float),
            "chg_in_oi": df["CHG_IN_OI"].astype(float),
        })
    elif "FinInstrmTp" in cols:  # UDiFF
        df = df[(df["Sgmt"].str.strip() == "FO") & (df["FinInstrmTp"].str.strip() == "STF")]
        out = pd.DataFrame({
            "symbol": df["TckrSymb"].str.strip(),
            "expiry": pd.to_datetime(df["XpryDt"].str.strip()),
            "open_int": df["OpnIntrst"].astype(float),
            "chg_in_oi": df["ChngInOpnIntrst"].astype(float),
        })
    else:
        raise ValueError(f"unrecognised FO bhavcopy columns in {path}: {sorted(cols)}")
    out["date"] = d
    out = out.sort_values("expiry").drop_duplicates(subset=["symbol"], keep="first")
    out["expiry"] = out["expiry"].dt.strftime("%Y-%m-%d")
    return out[["date", "symbol", "open_int", "chg_in_oi", "expiry"]].reset_index(drop=True)


def parse_fo_options_file(path: Path) -> pd.DataFrame:
    """Return one row per (date, symbol) with the near-month stock-option
    expiry's open interest summed by option type across strikes
    (catalog row D02's stock-level put/call OI need).

    Near-month follows the same soonest-expiry convention `parse_fo_file`
    uses for stock futures, applied independently per symbol to its own
    option rows (the option near-month need not be the same expiry as the
    stock future's, though in practice both follow the same monthly cycle).
    """
    df = _read_zip_csv(path)
    d = _filename_date(path)
    cols = set(df.columns)
    if "INSTRUMENT" in cols:  # old FO format
        df = df[df["INSTRUMENT"].str.strip() == "OPTSTK"]
        opt = pd.DataFrame({
            "symbol": df["SYMBOL"].str.strip(),
            "expiry": pd.to_datetime(df["EXPIRY_DT"].str.strip(), format="%d-%b-%Y"),
            "option_typ": df["OPTION_TYP"].str.strip(),
            "open_int": df["OPEN_INT"].astype(float),
        })
    elif "FinInstrmTp" in cols:  # UDiFF
        df = df[(df["Sgmt"].str.strip() == "FO") & (df["FinInstrmTp"].str.strip() == "STO")]
        opt = pd.DataFrame({
            "symbol": df["TckrSymb"].str.strip(),
            "expiry": pd.to_datetime(df["XpryDt"].str.strip()),
            "option_typ": df["OptnTp"].str.strip(),
            "open_int": df["OpnIntrst"].astype(float),
        })
    else:
        raise ValueError(f"unrecognised FO bhavcopy columns in {path}: {sorted(cols)}")

    out_columns = ["date", "symbol", "oi_ce_optstk", "oi_pe_optstk"]
    if opt.empty:
        return pd.DataFrame(columns=out_columns)

    near_month = opt.groupby("symbol")["expiry"].transform("min")
    opt = opt[opt["expiry"] == near_month]
    pivot = opt.pivot_table(index="symbol", columns="option_typ", values="open_int", aggfunc="sum", fill_value=0.0)
    for typ, col in (("CE", "oi_ce_optstk"), ("PE", "oi_pe_optstk")):
        pivot[col] = pivot[typ] if typ in pivot.columns else 0.0
    pivot = pivot.reset_index()
    pivot["date"] = d
    return pivot[out_columns].reset_index(drop=True)


def parse_delivery_file(path: Path) -> pd.DataFrame:
    """Return one row per EQ symbol with that date's delivered quantity and
    delivery percentage (catalog rows D02/D03), from an NSE MTO file.

    The file is plain text, not CSV with a fixed header: three preamble
    lines of varying shape, then one `20,...` data row per symbol (see
    docs/nse_formats.md). Parsed line-by-line rather than with
    `pd.read_csv` so a preamble line with a different field count on an
    older file never gets mistaken for data.
    """
    m = DELIVERY_FILENAME_RE.search(path.name)
    if not m:
        raise ValueError(f"unrecognised delivery filename: {path}")
    raw = m.group(1)
    d = f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"

    rows = []
    for line in path.read_text().splitlines():
        parts = line.split(",")
        if len(parts) != 7 or parts[0] != "20":
            continue
        _, _, symbol, series, qty_traded, deliv_qty, deliv_pct = parts
        if series.strip() != "EQ":
            continue
        rows.append((symbol.strip(), float(deliv_qty), float(deliv_pct)))

    out = pd.DataFrame(rows, columns=["symbol", "deliv_qty", "deliv_pct"])
    out["date"] = d
    return out.drop_duplicates(subset=["symbol"], keep="last")[["date", "symbol", "deliv_qty", "deliv_pct"]].reset_index(drop=True)


def build(raw_root: Path) -> pd.DataFrame:
    cm_frames = [parse_cm_file(p) for p in sorted(raw_root.rglob("cm_*.csv.zip"))]
    fo_frames = [parse_fo_file(p) for p in sorted(raw_root.rglob("fo_*.csv.zip"))]
    options_frames = [parse_fo_options_file(p) for p in sorted(raw_root.rglob("fo_*.csv.zip"))]
    delivery_frames = [parse_delivery_file(p) for p in sorted(raw_root.rglob("delivery_*.dat"))]

    prices = pd.concat(cm_frames, ignore_index=True) if cm_frames else pd.DataFrame(columns=PRICE_COLUMNS)
    futures = (pd.concat(fo_frames, ignore_index=True) if fo_frames
               else pd.DataFrame(columns=["date", "symbol", "open_int", "chg_in_oi", "expiry"]))
    options = (pd.concat(options_frames, ignore_index=True) if options_frames
               else pd.DataFrame(columns=["date", "symbol", "oi_ce_optstk", "oi_pe_optstk"]))
    delivery = (pd.concat(delivery_frames, ignore_index=True) if delivery_frames
                else pd.DataFrame(columns=["date", "symbol", "deliv_qty", "deliv_pct"]))

    prices = prices.drop_duplicates(subset=["date", "symbol"], keep="last")
    futures = futures.drop_duplicates(subset=["date", "symbol"], keep="last")
    options = options.drop_duplicates(subset=["date", "symbol"], keep="last")
    delivery = delivery.drop_duplicates(subset=["date", "symbol"], keep="last")
    futures["has_future"] = True
    futures = futures.rename(columns={"open_int": "oi_futstk", "chg_in_oi": "oi_chg_futstk", "expiry": "expiry_futstk"})

    merged = prices.merge(futures, on=["date", "symbol"], how="left")
    merged["has_future"] = merged["has_future"].fillna(False)
    merged = merged.merge(options, on=["date", "symbol"], how="left")
    merged = merged.merge(delivery, on=["date", "symbol"], how="left")
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
        "trading_days": int(df["date"].nunique()) if not df.empty else 0,
        "max_gap_days": int(pd.to_datetime(pd.Series(sorted(df["date"].unique()))).diff().dt.days.max()) if df["date"].nunique() > 1 else 0,
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
    empty_columns = PRICE_COLUMNS + ["has_future", "oi_futstk", "oi_chg_futstk", "expiry_futstk", "deliv_qty", "deliv_pct"]
    fresh = build(raw_root) if raw_root.exists() else pd.DataFrame(columns=empty_columns)

    existing = pd.read_parquet(out_path) if out_path.exists() else pd.DataFrame(columns=empty_columns)
    final = merge_with_existing(existing, fresh)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    final.to_parquet(out_path, index=False)
    write_manifest(final, out_path, Path(a.manifest))
    print(f"wrote {len(final)} rows, {final['symbol'].nunique() if not final.empty else 0} symbols -> {out_path}")


if __name__ == "__main__":
    main()
