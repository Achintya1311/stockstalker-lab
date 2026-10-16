import io
import zipfile
from pathlib import Path

import pandas as pd
import pytest

from scripts.build_dataset import build, merge_with_existing, parse_cm_file, parse_fo_file

OLD_CM_CSV = (
    "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,TIMESTAMP,TOTALTRADES,ISIN\n"
    "RELIANCE,EQ,100.00,105.00,99.00,104.00,104.00,100.00,1000000,100000000.00,02-JAN-2015,5000,INE002A01018\n"
    "TATAMOTORS,EQ,50.00,52.00,49.00,51.00,51.50,50.50,500000,25000000.00,02-JAN-2015,2000,INE155A01022\n"
    "RELIANCE,BE,100.00,105.00,99.00,104.00,104.00,100.00,10,1000.00,02-JAN-2015,2,INE002A01018\n"
)

OLD_FO_CSV = (
    "INSTRUMENT,SYMBOL,EXPIRY_DT,STRIKE_PR,OPTION_TYP,OPEN,HIGH,LOW,CLOSE,SETTLE_PR,CONTRACTS,VAL_INLAKH,OPEN_INT,CHG_IN_OI,TIMESTAMP\n"
    "FUTSTK,RELIANCE,29-JAN-2015,0,XX,100.00,105.00,99.00,104.00,104.00,500,50000.00,10000,100,02-JAN-2015\n"
    "FUTIDX,NIFTY,29-JAN-2015,0,XX,8000,8100,7950,8050,8050,1000,100000.00,50000,500,02-JAN-2015\n"
    "OPTSTK,TATAMOTORS,29-JAN-2015,55,CE,2.00,2.50,1.80,2.10,2.10,100,500.00,2000,20,02-JAN-2015\n"
)

UDIFF_CM_CSV = (
    "TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,XpryDt,FininstrmActlXpryDt,"
    "StrkPric,OptnTp,FinInstrmNm,OpnPric,HghPric,LwPric,ClsPric,LastPric,PrvsClsgPric,UndrlygPric,"
    "SttlmPric,OpnIntrst,ChngInOpnIntrst,TtlTradgVol,TtlTrdgVal,TtlNbOfTxsExctd,SsrIndctr,Rmks,"
    "Rsvd1,Rsvd2,Rsvd3,Rsvd4\n"
    "2024-07-08,2024-07-08,CM,NSE,STK,1001,INE002A01018,RELIANCE,EQ,,,,,"
    "RELIANCE,200.00,205.00,199.00,204.00,204.00,200.00,,,,,600000,122400000.00,3000,,,,,,\n"
    "2024-07-08,2024-07-08,CM,NSE,STK,1002,INE062A01020,SBIN,BZ,,,,,"
    "SBIN,60.00,61.00,59.00,60.50,60.50,60.00,,,,,10000,605000.00,100,,,,,,\n"
)

UDIFF_FO_CSV = (
    "TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,XpryDt,FininstrmActlXpryDt,"
    "StrkPric,OptnTp,FinInstrmNm,OpnPric,HghPric,LwPric,ClsPric,LastPric,PrvsClsgPric,UndrlygPric,"
    "SttlmPric,OpnIntrst,ChngInOpnIntrst,TtlTradgVol,TtlTrdgVal,TtlNbOfTxsExctd,SsrIndctr,Rmks,"
    "Rsvd1,Rsvd2,Rsvd3,Rsvd4\n"
    "2024-07-08,2024-07-08,FO,NSE,STF,2001,INE002A01018,RELIANCE,,2024-07-25,2024-07-25,,,"
    "RELIANCEFUT,200.00,205.00,199.00,204.00,204.00,,,204.00,10000,50,400,81600.00,20,,,,,,\n"
    "2024-07-08,2024-07-08,FO,NSE,IDF,2002,,NIFTY,,2024-07-25,2024-07-25,,,"
    "NIFTYFUT,24000,24100,23900,24050,24050,,,24050,20000,100,800,192400.00,40,,,,,,\n"
)


def _write_zip(tmp_path: Path, name: str, csv_text: str) -> Path:
    path = tmp_path / name
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(name[:-4], csv_text)  # strip trailing .zip -> inner .csv name
    return path


def test_parse_cm_old_keeps_only_eq_series(tmp_path):
    path = _write_zip(tmp_path, "cm_20150102.csv.zip", OLD_CM_CSV)
    out = parse_cm_file(path)
    assert sorted(out["symbol"]) == ["RELIANCE", "TATAMOTORS"]
    row = out[out["symbol"] == "RELIANCE"].iloc[0]
    assert row["open"] == 100.0 and row["close"] == 104.0 and row["prevclose"] == 100.0
    assert row["volume"] == 1000000 and row["date"] == "2015-01-02"


def test_parse_fo_old_keeps_only_futstk(tmp_path):
    path = _write_zip(tmp_path, "fo_20150102.csv.zip", OLD_FO_CSV)
    out = parse_fo_file(path)
    assert list(out["symbol"]) == ["RELIANCE"]
    assert out.iloc[0]["date"] == "2015-01-02"


def test_parse_cm_udiff_keeps_only_eq_stk(tmp_path):
    path = _write_zip(tmp_path, "cm_20240708.csv.zip", UDIFF_CM_CSV)
    out = parse_cm_file(path)
    assert list(out["symbol"]) == ["RELIANCE"]  # SBIN is series BZ, dropped
    row = out.iloc[0]
    assert row["close"] == 204.0 and row["prevclose"] == 200.0 and row["volume"] == 600000
    assert row["date"] == "2024-07-08"


def test_parse_fo_udiff_keeps_only_stf(tmp_path):
    path = _write_zip(tmp_path, "fo_20240708.csv.zip", UDIFF_FO_CSV)
    out = parse_fo_file(path)
    assert list(out["symbol"]) == ["RELIANCE"]  # NIFTY is IDF (index future), dropped


def test_build_merges_cm_and_fo_with_has_future_flag(tmp_path):
    raw = tmp_path / "raw"
    (raw / "2015" / "cm" / "2015").mkdir(parents=True)
    (raw / "2015" / "fo" / "2015").mkdir(parents=True)
    _write_zip(raw / "2015" / "cm" / "2015", "cm_20150102.csv.zip", OLD_CM_CSV)
    _write_zip(raw / "2015" / "fo" / "2015", "fo_20150102.csv.zip", OLD_FO_CSV)

    df = build(raw)
    assert set(df["symbol"]) == {"RELIANCE", "TATAMOTORS"}
    by_symbol = df.set_index("symbol")
    assert by_symbol.loc["RELIANCE", "has_future"] == True  # noqa: E712
    assert by_symbol.loc["TATAMOTORS", "has_future"] == False  # noqa: E712


def test_build_finds_files_regardless_of_directory_nesting(tmp_path):
    raw = tmp_path / "raw"
    (raw / "recent" / "cm" / "2024").mkdir(parents=True)
    _write_zip(raw / "recent" / "cm" / "2024", "cm_20240708.csv.zip", UDIFF_CM_CSV)

    df = build(raw)
    assert list(df["symbol"]) == ["RELIANCE"]


def test_merge_with_existing_updates_overlapping_rows_and_keeps_the_rest():
    existing = pd.DataFrame([
        {"date": "2015-01-02", "symbol": "RELIANCE", "close": 104.0, "has_future": True},
        {"date": "2015-01-05", "symbol": "RELIANCE", "close": 110.0, "has_future": True},
    ])
    fresh = pd.DataFrame([
        {"date": "2015-01-02", "symbol": "RELIANCE", "close": 999.0, "has_future": True},
        {"date": "2015-01-06", "symbol": "RELIANCE", "close": 111.0, "has_future": False},
    ])
    out = merge_with_existing(existing, fresh)
    out = out.set_index("date")
    assert out.loc["2015-01-02", "close"] == 999.0  # overwritten by fresh
    assert out.loc["2015-01-05", "close"] == 110.0   # kept from existing
    assert out.loc["2015-01-06", "close"] == 111.0   # added from fresh


def test_parse_cm_file_rejects_unrecognised_columns(tmp_path):
    path = _write_zip(tmp_path, "cm_20150102.csv.zip", "A,B,C\n1,2,3\n")
    with pytest.raises(ValueError):
        parse_cm_file(path)
